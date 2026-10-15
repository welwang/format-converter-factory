/* 頁面方法接手：磁碟工具（disk_tools.py 的頁面介面）。
 *
 * 接手 disk_info（磁碟清單）、disk_preview（chkdsk 預覽）、disk_launch（啟動 Windows 磁碟工具）。
 * disk_help 留在 Python：它只是開啟一個說明網址，沒有可驗證的輸出面，硬搬過來只會增加表面積。
 *
 * 忙碌守門：Python 版的 disk_preview／disk_launch 會先問 self._eng.busy()；
 * api.cpp 另外已經把這兩個方法放進 IDLE_ONLY（C 引擎忙碌時直接拒絕），
 * 所以 C++ 這一側只要再問 Python 那一側的忙碌狀態，兩邊合起來就與原行為完全相同。
 *
 * 輸出欄位與順序刻意與 Python 版相同（drive/filesystem/disk_number/free；預覽不含 command）。
 */
#include <windows.h>

#include <cctype>
#include <ctime>
#include <map>
#include <random>
#include <string>
#include <vector>

#include "plat.h"
#include "swbd/json.hpp"
#include "swbd/registry.hpp"
#include "swbd/sys.hpp"

namespace swbd {
namespace {

/* ---------------------------------------------------------------- 共用小工具 */

std::string windows_dir() {
    wchar_t buffer[MAX_PATH] = { 0 };
    DWORD got = GetEnvironmentVariableW(L"WINDIR", buffer, MAX_PATH);
    if (!got || got >= MAX_PATH) {
        got = GetWindowsDirectoryW(buffer, MAX_PATH);
        if (!got || got >= MAX_PATH) return "C:\\Windows";
    }
    const int need = WideCharToMultiByte(CP_UTF8, 0, buffer, -1, nullptr, 0, nullptr, nullptr);
    std::string out(static_cast<size_t>(need ? need : 1), '\0');
    if (need) WideCharToMultiByte(CP_UTF8, 0, buffer, -1, out.data(), need, nullptr, nullptr);
    out.resize(need ? static_cast<size_t>(need - 1) : 0);
    return out;
}

std::wstring widen(const std::string &utf8) {
    if (utf8.empty()) return std::wstring();
    const int need = MultiByteToWideChar(CP_UTF8, 0, utf8.c_str(), -1, nullptr, 0);
    std::wstring out(static_cast<size_t>(need ? need : 1), L'\0');
    if (need) MultiByteToWideChar(CP_UTF8, 0, utf8.c_str(), -1, out.data(), need);
    out.resize(need ? static_cast<size_t>(need - 1) : 0);
    return out;
}

std::string narrow(const wchar_t *text) {
    if (!text || !*text) return std::string();
    const int need = WideCharToMultiByte(CP_UTF8, 0, text, -1, nullptr, 0, nullptr, nullptr);
    std::string out(static_cast<size_t>(need ? need : 1), '\0');
    if (need) WideCharToMultiByte(CP_UTF8, 0, text, -1, out.data(), need, nullptr, nullptr);
    out.resize(need ? static_cast<size_t>(need - 1) : 0);
    return out;
}

/* 參數取值：Python 的 plan 只用 isinstance 判斷，型別不對就落到既有的錯誤訊息，
   所以這裡刻意寬容（取不到＝空字串），不要把 JSON 型別錯誤漏出去。 */
std::string arg_text(const jval *args, size_t index) {
    if (!args || args->type != J_ARR || index >= args->len) return std::string();
    const jval *v = args->items[index];
    return (v && v->type == J_STR && v->str) ? std::string(v->str) : std::string();
}

/* uuid4().hex 的等價：32 個十六進位字元（只用來當一次操作的確認碼）。 */
std::string random_token() {
    static const char *digits = "0123456789abcdef";
    unsigned char bytes[16] = { 0 };
    /* std::random_device 在 MSVC 上由作業系統提供熵；不要用 rand()（預設種子固定、可預期）。 */
    std::random_device source;
    for (size_t i = 0; i < sizeof bytes; i++) bytes[i] = static_cast<unsigned char>(source() & 0xFF);
    std::string out;
    out.reserve(32);
    for (unsigned char byte : bytes) {
        out += digits[byte >> 4];
        out += digits[byte & 0x0F];
    }
    return out;
}

/* ---------------------------------------------------------------- disk_info */

/* Get-Partition → {磁碟機代號: 磁碟編號}；失敗等同 Python 的 except：留空。 */
std::map<char, long long> partition_numbers() {
    std::map<char, long long> numbers;
    const std::string powershell = windows_dir() + "\\System32\\WindowsPowerShell\\v1.0\\powershell.exe";
    const char *argv[] = {
        powershell.c_str(), "-NoProfile", "-NonInteractive", "-Command",
        "Get-Partition -ErrorAction Stop | Where-Object DriveLetter | "
        "Select-Object DriveLetter,DiskNumber | ConvertTo-Json -Compress",
        nullptr,
    };
    char *out = nullptr;
    char *err = nullptr;
    size_t length = 0;
    run_capture(argv, nullptr, &out, &err, 12, &length);
    std::string text = (out && length) ? std::string(out, length) : std::string();
    free(out);
    free(err);
    if (text.empty()) return numbers;
    try {
        Json parsed = Json::parse(text);
        Json wrapper;
        const jval *items = parsed.raw();
        if (parsed.is_object()) {
            wrapper = Json::array();
            wrapper.push(Json(parsed.release()));
            items = wrapper.raw();
        }
        if (!items || items->type != J_ARR) return numbers;
        for (size_t i = 0; i < items->len; i++) {
            const jval *entry = items->items[i];
            if (!entry || entry->type != J_OBJ) continue;
            const jval *letter = jget(entry, "DriveLetter");
            const jval *number = jget(entry, "DiskNumber");
            if (!letter || !number) continue;
            char key = 0;
            if (letter->type == J_STR && letter->str && *letter->str) {
                key = static_cast<char>(toupper(static_cast<unsigned char>(*letter->str)));
            } else if (letter->type == J_NUM) {
                key = static_cast<char>('A' + static_cast<int>(letter->num));
            }
            if (!key) continue;
            numbers[key] = static_cast<long long>(number->type == J_NUM ? number->num : 0);
        }
    } catch (const std::exception &) {
        numbers.clear();
    }
    return numbers;
}

/* disk_tools.inventory()：只列固定（3）與可移除（2）磁碟。 */
Json inventory_json() {
    const std::map<char, long long> numbers = partition_numbers();
    Json drives = Json::array();
    for (char letter = 'A'; letter <= 'Z'; letter++) {
        const std::string root = std::string(1, letter) + ":\\";
        const std::wstring wide_root = widen(root);
        const UINT type = GetDriveTypeW(wide_root.c_str());
        if (type != DRIVE_REMOVABLE && type != DRIVE_FIXED) continue;

        wchar_t filesystem[64] = { 0 };
        GetVolumeInformationW(wide_root.c_str(), nullptr, 0, nullptr, nullptr, nullptr, filesystem, 64);

        ULARGE_INTEGER available{};
        if (!GetDiskFreeSpaceExW(wide_root.c_str(), &available, nullptr, nullptr)) continue;

        Json item = Json::object();
        item.set("drive", Json::of(std::string(1, letter) + ":"));
        const std::string fs = narrow(filesystem);
        item.set("filesystem", Json::of(fs.empty() ? "未知" : fs));
        const auto found = numbers.find(letter);
        if (found == numbers.end()) item.set("disk_number", Json::null());
        else item.set("disk_number", Json::of(found->second));
        item.set("free", Json::of(static_cast<double>(available.QuadPart)));
        drives.push(std::move(item));
    }
    Json out = Json::object();
    out.set("drives", std::move(drives));
    return out;
}

Json disk_info(Context &, const jval *) { return inventory_json(); }

/* ------------------------------------------------- disk_preview / disk_launch */

/* Python 版把預覽結果放在 app 物件的 _disk_plan；C++ 版放在這裡（單一視窗、生命週期相同）。 */
struct DiskPlan {
    bool valid = false;
    std::string mode;
    std::string source;
    std::string destination;
    std::string file_group;
    std::string recovery_mode;
    std::string token;
    double created = 0;
    std::vector<std::string> command;
};

DiskPlan g_plan;

/* 磁碟機代號必須是 [A-Za-z]:（Python 用 re.fullmatch）。 */
bool valid_source(const std::string &source) {
    return source.size() == 2 && std::isalpha(static_cast<unsigned char>(source[0])) && source[1] == ':';
}

std::string upper(std::string text) {
    for (char &c : text) c = static_cast<char>(toupper(static_cast<unsigned char>(c)));
    return text;
}

/* disk_tools.plan() 的等價實作。 */
DiskPlan make_plan(const std::string &mode, const std::string &source_in, const std::string &destination,
                   const std::string &file_group, const std::string &recovery_mode) {
    const Json devices = inventory_json();
    if (mode != "check" && mode != "repair") throw std::runtime_error("不支援的磁碟操作");
    if (!valid_source(source_in)) throw std::runtime_error("請選擇磁碟");
    const std::string source = upper(source_in);

    bool present = false;
    const Json *drives = &devices;
    const jval *list = drives->raw();
    const jval *items = list ? jget(list, "drives") : nullptr;
    for (size_t i = 0; items && i < items->len; i++) {
        const jval *drive = jget(items->items[i], "drive");
        if (drive && drive->type == J_STR && drive->str && source == drive->str) { present = true; break; }
    }
    if (!present) throw std::runtime_error("不是可用的本機磁碟");

    const std::string system = windows_dir() + "\\System32";
    DiskPlan plan;
    plan.valid = true;
    plan.mode = mode;
    plan.source = source;
    plan.destination = destination;
    plan.file_group = file_group;
    plan.recovery_mode = recovery_mode;
    plan.token = random_token();
    plan.created = sys::now_s();
    plan.command.push_back(system + "\\chkdsk.exe");
    plan.command.push_back(source);
    if (mode == "repair") plan.command.push_back("/f");
    return plan;
}

std::string warning_for(const std::string &mode) {
    if (mode == "repair") {
        return "修復會修改檔案系統。請先備份重要資料；使用中的磁碟可能需要在 Windows 視窗中選擇下次重新啟動時執行。";
    }
    return "此檢查不帶修復參數，不修正錯誤；使用中的磁碟可能出現需再次確認的錯誤報告。";
}

Json plan_reply(const DiskPlan &plan) {
    Json out = Json::object();
    out.set("token", Json::of(plan.token));
    out.set("created", Json::of(plan.created));
    out.set("mode", Json::of(plan.mode));
    out.set("source", Json::of(plan.source));
    out.set("destination", Json::of(plan.destination));
    out.set("file_group", Json::of(plan.file_group));
    out.set("recovery_mode", Json::of(plan.recovery_mode));
    out.set("description", Json::of(std::string(plan.mode == "check" ? "檢查 " : "修復 ") + plan.source + " 的檔案系統"));
    Json warnings = Json::array();
    warnings.push(Json::of(warning_for(plan.mode)));
    out.set("warnings", std::move(warnings));
    out.set("available", Json::boolean(true));
    return out;
}

Json disk_preview(Context &ctx, const jval *args) {
    if (ctx.busy()) throw std::runtime_error("請先完成目前工作，避免同時存取要檢查或修復的磁碟");
    g_plan = make_plan(arg_text(args, 0), arg_text(args, 1), arg_text(args, 2), arg_text(args, 3), arg_text(args, 4));
    return plan_reply(g_plan);      /* Python 版會濾掉 command，這裡本來就沒有放進去 */
}

/* subprocess.list2cmdline 的等價實作（只用到我們自己組出來的固定參數）。 */
std::string list2cmdline(const std::vector<std::string> &args) {
    std::string out;
    for (size_t i = 0; i < args.size(); i++) {
        if (i) out += ' ';
        const std::string &arg = args[i];
        const bool needs_quotes = arg.empty() || arg.find_first_of(" \t\"") != std::string::npos;
        if (!needs_quotes) { out += arg; continue; }
        out += '"';
        size_t backslashes = 0;
        for (char c : arg) {
            if (c == '\\') { backslashes++; continue; }
            if (c == '"') { out.append(backslashes * 2 + 1, '\\'); backslashes = 0; out += '"'; continue; }
            out.append(backslashes, '\\');
            backslashes = 0;
            out += c;
        }
        out.append(backslashes * 2, '\\');
        out += '"';
    }
    return out;
}

Json disk_launch(Context &ctx, const jval *args) {
    if (ctx.busy()) throw std::runtime_error("請先完成目前工作");
    if (!g_plan.valid) throw std::runtime_error("請先預覽磁碟操作");

    const std::string token = arg_text(args, 0);
    bool confirmed = false;
    if (args && args->type == J_ARR && args->len > 1 && args->items[1]) {
        const jval *flag = args->items[1];
        confirmed = flag->type == J_BOOL ? flag->num != 0 : (flag->type == J_NUM && flag->num != 0);
    }
    if (!confirmed || token != g_plan.token || sys::now_s() - g_plan.created > 600) {
        throw std::runtime_error("請重新預覽並確認磁碟操作");
    }

    /* 重新組一次指令（Python 也是這樣），並確認參數裡沒有會跑到命令殼層的字元。 */
    const std::string mode = g_plan.mode;
    const std::string source = g_plan.source;
    const std::string destination = g_plan.destination;
    const std::string file_group = g_plan.file_group;
    const std::string recovery_mode = g_plan.recovery_mode;
    const DiskPlan current = make_plan(mode, source, destination, file_group, recovery_mode);
    for (const std::string &arg : current.command) {
        if (arg.find_first_of("&|<>^%!\"\r\n") != std::string::npos) throw std::runtime_error("磁碟參數不合法");
    }

    const std::string cmd = windows_dir() + "\\System32\\cmd.exe";
    const std::string params = "/k " + list2cmdline(current.command);
    const HINSTANCE result = ShellExecuteW(nullptr, L"runas", widen(cmd).c_str(), widen(params).c_str(),
                                           nullptr, SW_SHOWNORMAL);
    if (reinterpret_cast<INT_PTR>(result) <= 32) {
        throw std::runtime_error("未啟動磁碟工具；可能取消了系統管理員權限要求");
    }
    g_plan.valid = false;
    return Json::of("已開啟 Windows 磁碟工具視窗；操作是否完成與結果請查看該視窗。");
}

Register register_disk_info("disk_info", &disk_info);
Register register_disk_preview("disk_preview", &disk_preview);
Register register_disk_launch("disk_launch", &disk_launch);

}  // namespace
}  // namespace swbd
