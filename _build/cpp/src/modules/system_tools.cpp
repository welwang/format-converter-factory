/* system_tools 的清理功能，從 Python 移植的第一刀。
   對應 _build/src/system_tools.py 的 CLEANUP / _safe_root / _plain_file / scan_cleanup /
   cleanup_preview / execute_cleanup，以及 app.py 的 cleanup_scan / cleanup_execute
   （方法層級的擁有權：plan 狀態留在本模組，等同 app.py 的 self._cleanup_plan）。
   行為必須與 Python 版等價：掃描範圍、年齡門檻、10000 筆上限、去重順序、預覽欄位、
   token 驗證與 600 秒到期，以及所有錯誤訊息。 */
#include <windows.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cwchar>
#include <functional>
#include <map>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

#include "swbd/registry.hpp"
#include "swbd/sys.hpp"

extern "C" BOOLEAN NTAPI SystemFunction036(PVOID buffer, ULONG length);   /* RtlGenRandom（advapi32） */

namespace swbd::modules {
namespace {

constexpr double kDay = 86400.0;

struct Category {
    const char *id;
    const char *name;
    const char *desc;
    bool by_default;
};

/* 與 system_tools.CLEANUP 一字不差，順序也相同（preview 的 categories 依此順序）。 */
constexpr Category kCleanup[] = {
    {"app_temp", "四維八德舊暫存", "7 天以上的處理暫存；保留設定、模型與成品", true},
    {"download_parts", "未完成的模型下載", "1 天以上的下載片段；保留已完成模型", true},
    {"logs", "舊診斷記錄", "7 天以上的記錄檔", false},
    {"user_temp", "使用者暫存", "暫存資料夾內 7 天以上的散落檔案；不包含子資料夾", false},
};

struct Item {
    std::string path;
    std::string root;
    std::string category;
    std::uint64_t size = 0;
    double mtime = 0;
    std::int64_t ticks = 0;
};

struct Plan {
    std::string token;
    double created = 0;
    std::vector<Item> items;
    bool valid = false;
};

Plan g_plan;   /* 單視窗設計，等同 app.py 的 self._cleanup_plan */

bool known_category(const std::string &id) {
    for (const Category &c : kCleanup)
        if (id == c.id) return true;
    return false;
}

bool ends_with_ci(std::string_view text, std::string_view suffix) {
    if (text.size() < suffix.size()) return false;
    const size_t offset = text.size() - suffix.size();
    for (size_t i = 0; i < suffix.size(); i++) {
        char a = text[offset + i];
        char b = suffix[i];
        if (a >= 'A' && a <= 'Z') a = static_cast<char>(a - 'A' + 'a');
        if (b >= 'A' && b <= 'Z') b = static_cast<char>(b - 'A' + 'a');
        if (a != b) return false;
    }
    return true;
}

bool starts_with(std::string_view text, std::string_view prefix) {
    return text.size() >= prefix.size() && text.compare(0, prefix.size(), prefix) == 0;
}

/* Path.parent：去掉最後一層；磁碟根目錄的 parent 是自己。 */
std::string parent_dir(std::string path) {
    while (path.size() > 3 && (path.back() == '\\' || path.back() == '/')) path.pop_back();
    const size_t cut = path.find_last_of("\\/");
    if (cut == std::string::npos) return path;
    if (cut == 2 && path[1] == ':') return path.substr(0, 3);
    if (cut == 0) return path.substr(0, 1);
    return path.substr(0, cut);
}

std::string random_hex(size_t chars) {
    std::vector<unsigned char> buffer((chars + 1) / 2, 0);
    if (!SystemFunction036(buffer.data(), static_cast<ULONG>(buffer.size()))) {
        std::random_device device;
        for (unsigned char &b : buffer) b = static_cast<unsigned char>(device());
    }
    static const char *digits = "0123456789abcdef";
    std::string out;
    out.reserve(chars);
    for (unsigned char b : buffer) {
        out.push_back(digits[b >> 4]);
        if (out.size() < chars) out.push_back(digits[b & 0x0F]);
    }
    return out;
}

/* system_tools._plain_file：必須在 root 之內、路徑上每一層（不含 root）都不是 reparse point，
   且本身是普通檔案。 */
bool plain_file(const std::string &path, const std::string &root, sys::FileInfo &out) {
    if (!sys::path_inside(path, root)) return false;
    const std::string root_key = sys::norm_case(sys::abs_path(root));
    std::string current = path;
    for (;;) {
        if (sys::norm_case(sys::abs_path(current)) == root_key) break;
        sys::FileInfo link;
        if (!sys::lstat_path(current, link)) return false;
        if (link.is_reparse) return false;
        const std::string parent = parent_dir(current);
        if (parent == current) return false;
        current = parent;
    }
    sys::FileInfo info;
    if (!sys::stat_path(path, info)) return false;
    if (!info.is_regular) return false;
    out = info;
    return true;
}

/* os.walk(followlinks=False) 加上 system_tools 對 reparse 目錄的剪枝。
   順序必須與 os.walk 相同：同一層先輸出檔案，再進入子目錄。 */
void walk_files(const std::string &dir, const std::function<void(const std::string &)> &on_file) {
    const std::vector<sys::DirEntry> entries = sys::list_dir(dir);
    for (const sys::DirEntry &entry : entries)
        if (!entry.is_dir && !entry.is_reparse) on_file(sys::join(dir, entry.name));
    for (const sys::DirEntry &entry : entries)
        if (entry.is_dir && !entry.is_reparse) walk_files(sys::join(dir, entry.name), on_file);
}

Json preview_of(const Plan &plan) {
    Json out = Json::object();
    out.set("token", Json::of(plan.token));
    out.set("count", Json::of(static_cast<long long>(plan.items.size())));
    long long bytes = 0;
    for (const Item &item : plan.items) bytes += static_cast<long long>(item.size);
    out.set("bytes", Json::of(bytes));

    Json categories = Json::array();
    for (const Category &category : kCleanup) {
        long long count = 0;
        long long sum = 0;
        for (const Item &item : plan.items)
            if (item.category == category.id) { count++; sum += static_cast<long long>(item.size); }
        Json entry = Json::object();
        entry.set("id", Json::of(std::string(category.id)));
        entry.set("name", Json::of(std::string(category.name)));
        entry.set("count", Json::of(count));
        entry.set("bytes", Json::of(sum));
        categories.push(std::move(entry));
    }
    out.set("categories", std::move(categories));

    Json examples = Json::array();
    for (size_t i = 0; i < plan.items.size() && i < 20; i++)
        examples.push(Json::of(sys::base_name(plan.items[i].path)));
    out.set("examples", std::move(examples));
    return out;
}

Json cleanup_scan(Context &ctx, const jval *args) {
    const std::vector<std::string> categories = arg_strings(args, 0);
    for (const std::string &category : categories)
        if (!known_category(category)) throw std::runtime_error("不支援的清理項目");

    const std::string temp = ctx.temp_dir.empty() ? sys::system_temp_dir() : ctx.temp_dir;
    const std::string data = ctx.data_dir;
    const double now = sys::now_s();

    std::vector<Item> items;
    std::map<std::string, size_t> position;   /* norm_case(path) → items 索引（保留首次插入順序、值取最後一次） */

    auto add = [&](const std::string &path, const std::string &root, const std::string &category, double age) {
        if (items.size() >= 10000) return;
        sys::FileInfo info;
        if (!plain_file(path, root, info)) return;
        if (!(now - info.mtime >= age)) return;
        Item item{path, root, category, info.size, info.mtime, info.mtime_ticks};
        const std::string key = sys::norm_case(path);
        const auto found = position.find(key);
        if (found != position.end()) { items[found->second] = std::move(item); return; }
        position.emplace(key, items.size());
        items.push_back(std::move(item));
    };

    for (const std::string &category : categories) {
        if (category == "app_temp") {
            for (const sys::DirEntry &entry : sys::list_dir(temp)) {
                if (!starts_with(entry.name, "zdgc_") || !entry.is_dir || entry.is_reparse) continue;
                const std::string dir = sys::join(temp, entry.name);
                walk_files(dir, [&](const std::string &file) { add(file, temp, category, 7 * kDay); });
            }
        } else if (category == "download_parts") {
            for (const char *sub : {"models", "tools"}) {
                const std::string folder = sys::join(data, sub);
                sys::FileInfo info;
                if (!sys::stat_path(folder, info) || !info.is_dir) continue;
                for (const sys::DirEntry &entry : sys::list_dir(folder)) {
                    if (entry.is_dir || !ends_with_ci(entry.name, ".part")) continue;
                    add(sys::join(folder, entry.name), data, category, kDay);
                }
            }
        } else if (category == "logs") {
            const std::string folder = sys::join(data, "logs");
            sys::FileInfo info;
            if (sys::stat_path(folder, info) && info.is_dir) {
                for (const sys::DirEntry &entry : sys::list_dir(folder)) {
                    if (entry.is_dir || !starts_with(entry.name, "zdgc.log")) continue;
                    add(sys::join(folder, entry.name), data, category, 7 * kDay);
                }
            }
        } else if (category == "user_temp") {
            for (const sys::DirEntry &entry : sys::list_dir(temp))
                add(sys::join(temp, entry.name), temp, category, 7 * kDay);
        }
    }

    g_plan.token = random_hex(32);
    g_plan.created = now;
    g_plan.items = std::move(items);
    g_plan.valid = true;
    return preview_of(g_plan);
}

Json cleanup_execute(Context &ctx, const jval *args) {
    (void)ctx;
    const std::string token = arg_string(args, 0);
    if (!g_plan.valid) throw std::runtime_error("請先掃描清理項目");
    if (token != g_plan.token || sys::now_s() - g_plan.created > 600)
        throw std::runtime_error("清理預覽已過期，請重新掃描");

    long long freed = 0;
    long long removed = 0;
    long long skipped = 0;
    for (const Item &item : g_plan.items) {
        sys::FileInfo info;
        if (!plain_file(item.path, item.root, info) || info.size != item.size || info.mtime_ticks != item.ticks) {
            skipped++;
            continue;
        }
        if (sys::remove_file(item.path)) {
            freed += static_cast<long long>(item.size);
            removed++;
        } else {
            skipped++;
        }
    }
    g_plan.valid = false;
    g_plan.items.clear();
    g_plan.token.clear();

    Json out = Json::object();
    out.set("removed", Json::of(removed));
    out.set("skipped", Json::of(skipped));
    out.set("bytes", Json::of(freed));
    return out;
}

/* ============================================================ system_info
   app.py 的 system_info() = {hardware: system_tools.hardware_info(), cleanup: system_tools.CLEANUP}。
   hardware_info() 是 platform_info()（作業系統、架構、記憶體、核心數、工作者政策）再加 cpu、
   gpu_encoders、disks。工作者政策與硬體編碼器一律取自 C 引擎（Context::facts），
   這樣同一個數字不會有兩份實作；磁碟與登錄檔資訊則在這一層直接讀。 */

std::string narrow_text(const wchar_t *text) {
    if (!text || !*text) return std::string();
    const int need = WideCharToMultiByte(CP_UTF8, 0, text, -1, nullptr, 0, nullptr, nullptr);
    std::string out(static_cast<size_t>(need ? need : 1), '\0');
    if (need) WideCharToMultiByte(CP_UTF8, 0, text, -1, out.data(), need, nullptr, nullptr);
    out.resize(need ? static_cast<size_t>(need - 1) : 0);
    return out;
}

std::wstring widen_text(const std::string &utf8) {
    if (utf8.empty()) return std::wstring();
    const int need = MultiByteToWideChar(CP_UTF8, 0, utf8.c_str(), -1, nullptr, 0);
    std::wstring out(static_cast<size_t>(need ? need : 1), L'\0');
    if (need) MultiByteToWideChar(CP_UTF8, 0, utf8.c_str(), -1, out.data(), need);
    out.resize(need ? static_cast<size_t>(need - 1) : 0);
    return out;
}

std::string reg_text(const wchar_t *subkey, const wchar_t *name) {
    HKEY key = nullptr;
    if (RegOpenKeyExW(HKEY_LOCAL_MACHINE, subkey, 0, KEY_READ, &key) != ERROR_SUCCESS) return std::string();
    wchar_t buffer[512] = { 0 };
    DWORD size = sizeof(buffer) - sizeof(wchar_t);
    DWORD type = 0;
    const LONG rc = RegQueryValueExW(key, name, nullptr, &type, reinterpret_cast<LPBYTE>(buffer), &size);
    RegCloseKey(key);
    if (rc != ERROR_SUCCESS || (type != REG_SZ && type != REG_EXPAND_SZ)) return std::string();
    return narrow_text(buffer);
}

long long reg_number(const wchar_t *subkey, const wchar_t *name) {
    HKEY key = nullptr;
    if (RegOpenKeyExW(HKEY_LOCAL_MACHINE, subkey, 0, KEY_READ, &key) != ERROR_SUCCESS) return -1;
    DWORD value = 0, size = sizeof value, type = 0;
    const LONG rc = RegQueryValueExW(key, name, nullptr, &type, reinterpret_cast<LPBYTE>(&value), &size);
    RegCloseKey(key);
    if (rc == ERROR_SUCCESS && type == REG_DWORD) return static_cast<long long>(value);
    /* 有些版本只有字串形式的建置編號 */
    const std::string text = reg_text(subkey, name);
    return text.empty() ? -1 : atoll(text.c_str());
}

std::string env_text(const wchar_t *name) {
    wchar_t buffer[256] = { 0 };
    const DWORD got = GetEnvironmentVariableW(name, buffer, 256);
    return (got && got < 256) ? narrow_text(buffer) : std::string();
}

/* Python 的 round(x, 1)：四捨六入五成雙（nearbyint 用目前的捨入模式，預設就是這個）。 */
double round1(double value) { return std::nearbyint(value * 10.0) / 10.0; }

Json cleanup_categories() {
    Json out = Json::array();
    for (const Category &category : kCleanup) {
        Json item = Json::object();
        item.set("id", Json::of(category.id));
        item.set("name", Json::of(category.name));
        item.set("desc", Json::of(category.desc));
        item.set("default", Json::boolean(category.by_default));
        out.push(std::move(item));
    }
    return out;
}

Json disk_list() {
    Json out = Json::array();
    for (char letter = 'A'; letter <= 'Z'; letter++) {
        const std::string root = std::string(1, letter) + ":\\";
        const std::wstring wide_root = widen_text(root);
        const UINT type = GetDriveTypeW(wide_root.c_str());
        if (type != DRIVE_REMOVABLE && type != DRIVE_FIXED) continue;
        ULARGE_INTEGER available{}, total{};
        if (!GetDiskFreeSpaceExW(wide_root.c_str(), &available, &total, nullptr)) continue;
        Json item = Json::object();
        item.set("path", Json::of(root));
        item.set("total", Json::of(static_cast<double>(total.QuadPart)));
        item.set("free", Json::of(static_cast<double>(available.QuadPart)));
        out.push(std::move(item));
    }
    return out;
}

Json system_info(Context &ctx, const jval *) {
    SystemFacts facts = ctx.facts();
    if (!facts.ready) throw std::runtime_error("這一版沒有接上系統資訊來源");
    /* 硬體編碼器是由引擎的背景執行緒偵測的；Python 版會同步等它完成，這裡也等（最多 10 秒）。 */
    for (int waited = 0; !facts.hw_ready && waited < 100; waited++) {
        Sleep(100);
        facts = ctx.facts();
    }

    const long long build = reg_number(L"SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion", L"CurrentBuildNumber");
    const long long major = reg_number(L"SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion", L"CurrentMajorVersionNumber");
    const bool is64 = sizeof(void *) == 8;
    const std::string arch_env = env_text(L"PROCESSOR_ARCHITEW6432");
    std::string arch = arch_env.empty() ? env_text(L"PROCESSOR_ARCHITECTURE") : arch_env;
    if (arch.empty()) arch = is64 ? "AMD64" : "x86";

    Json hardware = Json::object();
    hardware.set("system", Json::of(build >= 22000 ? "Windows 11" : major >= 10 ? "Windows 10" : "Windows"));
    hardware.set("supported", Json::boolean(major >= 10 && is64));
    hardware.set("arch", Json::of(arch));
    std::string upper_arch = arch;
    for (char &c : upper_arch) c = static_cast<char>(toupper(static_cast<unsigned char>(c)));
    hardware.set("emulated", Json::boolean(upper_arch.find("ARM") != std::string::npos));
    hardware.set("ram", Json::of(round1(facts.ram_gb)));
    hardware.set("cores", Json::of(static_cast<long long>(facts.cores)));
    hardware.set("heavy", Json::of(static_cast<long long>(facts.heavy)));
    hardware.set("light", Json::of(static_cast<long long>(facts.light)));
    hardware.set("slots", Json::of(static_cast<long long>(facts.slots)));
    const std::string cpu = reg_text(L"HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0", L"ProcessorNameString");
    hardware.set("cpu", Json::of(cpu.empty() ? "未取得處理器名稱" : cpu));
    Json encoders = Json::array();
    for (const std::string &name : facts.hw_encoders) encoders.push(Json::of(name));
    hardware.set("gpu_encoders", std::move(encoders));
    hardware.set("disks", disk_list());

    Json out = Json::object();
    out.set("hardware", std::move(hardware));
    out.set("cleanup", cleanup_categories());
    return out;
}

Register register_system_info("system_info", &system_info);

Register register_cleanup_scan("cleanup_scan", &cleanup_scan);
Register register_cleanup_execute("cleanup_execute", &cleanup_execute);

}  // namespace
}  // namespace swbd::modules
