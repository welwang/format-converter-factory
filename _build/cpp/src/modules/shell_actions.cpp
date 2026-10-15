/* 頁面方法接手：光碟機清單、開檔、在資料夾顯示。
 *
 * 三個方法都是純 Win32、沒有第三方相依，而且輸出（含錯誤字串）與 Python 版一字不差：
 *   drives     ← tools.list_drives()      只列光碟機（DRIVE_CDROM），label 的三段邏輯照抄
 *   open_file  ← file_actions.open_file() os.startfile → ShellExecuteW 的 "open"
 *   reveal     ← file_actions.reveal()    目錄：開啟資料夾；檔案：explorer /select,"路徑"
 *
 * normalized()/existing() 的驗證與錯誤字串刻意與 file_actions.py 相同，
 * 因為橋接層會把例外轉成 {"ok":false,"e":...}，字串一致才等價。
 */
#include <windows.h>
#include <shellapi.h>

#include <stdexcept>
#include <string>

#include "swbd/json.hpp"
#include "swbd/registry.hpp"
#include "swbd/sys.hpp"

namespace swbd {
namespace {

std::wstring widen(const std::string &utf8) {
    if (utf8.empty()) return std::wstring();
    const int need = MultiByteToWideChar(CP_UTF8, 0, utf8.c_str(), -1, nullptr, 0);
    std::wstring out(static_cast<size_t>(need ? need : 1), L'\0');
    if (need) MultiByteToWideChar(CP_UTF8, 0, utf8.c_str(), -1, out.data(), need);
    out.resize(need ? static_cast<size_t>(need - 1) : 0);
    return out;
}

std::string narrow(const wchar_t *w) {
    if (!w || !*w) return std::string();
    const int need = WideCharToMultiByte(CP_UTF8, 0, w, -1, nullptr, 0, nullptr, nullptr);
    std::string out(static_cast<size_t>(need ? need : 1), '\0');
    if (need) WideCharToMultiByte(CP_UTF8, 0, w, -1, out.data(), need, nullptr, nullptr);
    out.resize(need ? static_cast<size_t>(need - 1) : 0);
    return out;
}

/* ShellExecuteW：回傳值 <= 32 代表失敗，對應 Python os.startfile 擲出的 OSError。 */
bool shell_open(const std::wstring &file, const std::wstring &params = std::wstring()) {
    const HINSTANCE result = ShellExecuteW(nullptr, L"open", file.c_str(),
                                           params.empty() ? nullptr : params.c_str(), nullptr, SW_SHOWNORMAL);
    return reinterpret_cast<INT_PTR>(result) > 32;
}

/* tools.list_drives()：光碟機清單 [{'path': 'D:\\', 'label': ...}] */
Json list_drives(Context &, const jval *) {
    Json out = Json::array();
    const DWORD mask = GetLogicalDrives();
    for (int i = 0; i < 26; i++) {
        if (!((mask >> i) & 1)) continue;
        wchar_t root[4] = { static_cast<wchar_t>(L'A' + i), L':', L'\\', 0 };
        if (GetDriveTypeW(root) != DRIVE_CDROM) continue;
        wchar_t name[261] = { 0 };
        const BOOL ok = GetVolumeInformationW(root, name, 261, nullptr, nullptr, nullptr, nullptr, 0);
        const std::string letter(1, static_cast<char>('A' + i));
        std::string label = letter + ": ";
        if (ok && name[0]) label += narrow(name);
        else if (!ok) label += "（沒有光碟）";
        else label += "光碟";
        Json item = Json::object();
        item.set("path", Json::of(letter + ":\\"));
        item.set("label", Json::of(label));
        out.push(std::move(item));
    }
    return out;
}

bool is_space(unsigned char c) {
    return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\f' || c == '\v';
}

/* file_actions.normalized()：去頭尾空白、去 BOM、必要時解 JSON 字串，最後 abspath+normpath。 */
std::string normalize_path(const jval *args) {
    const jval *first = (args && args->len > 0) ? args->items[0] : nullptr;
    if (!first || first->type != J_STR || !first->str) throw std::runtime_error("沒有可開啟的檔案路徑");
    std::string value = first->str;
    size_t begin = 0, end = value.size();
    while (begin < end && is_space(static_cast<unsigned char>(value[begin]))) begin++;
    while (end > begin && is_space(static_cast<unsigned char>(value[end - 1]))) end--;
    value = value.substr(begin, end - begin);
    if (value.empty()) throw std::runtime_error("沒有可開啟的檔案路徑");
    if (value.size() >= 3 && static_cast<unsigned char>(value[0]) == 0xEF &&
        static_cast<unsigned char>(value[1]) == 0xBB && static_cast<unsigned char>(value[2]) == 0xBF) {
        value.erase(0, 3);
    }
    if (!value.empty() && value[0] == '"') {
        if (value.size() >= 2 && value.back() == '"') {
            jval *parsed = json_parse(value.c_str());
            if (parsed && parsed->type == J_STR && parsed->str) value = parsed->str;
            else value = value.substr(1, value.size() - 2);
            if (parsed) json_free(parsed);
        } else {
            value.erase(0, 1);
        }
    }
    if (value == "NA" || value == "None" || value == "null") throw std::runtime_error("下載元件沒有回報有效檔案路徑");
    return sys::abs_path(value);
}

/* file_actions.existing()：路徑必須存在，否則擲出與 Python 相同的錯誤字串。 */
std::string existing_path(const jval *args) {
    const std::string path = normalize_path(args);
    sys::FileInfo info;
    if (!sys::stat_path(path, info) || !info.ok) {
        throw std::runtime_error("找不到成品，檔案可能已移動或刪除：" + path);
    }
    return path;
}

void reveal_existing(const std::string &path, const sys::FileInfo &info) {
    if (info.is_dir) {
        shell_open(widen(path));
        return;
    }
    wchar_t windir[MAX_PATH] = { 0 };
    if (!GetWindowsDirectoryW(windir, MAX_PATH)) lstrcpyW(windir, L"C:\\Windows");
    const std::wstring explorer = std::wstring(windir) + L"\\explorer.exe";
    const std::wstring params = L"/select,\"" + widen(path) + L"\"";
    ShellExecuteW(nullptr, L"open", explorer.c_str(), params.c_str(), nullptr, SW_SHOWNORMAL);
}

Json open_file(Context &, const jval *args) {
    const std::string path = existing_path(args);
    if (!shell_open(widen(path))) {
        sys::FileInfo info;
        sys::stat_path(path, info);
        reveal_existing(path, info);          /* Python 也是先 reveal 再擲錯 */
        throw std::runtime_error("尚未設定此格式的預設開啟程式，已在資料夾中顯示檔案");
    }
    return Json::boolean(true);
}

Json reveal(Context &, const jval *args) {
    const std::string path = existing_path(args);
    sys::FileInfo info;
    sys::stat_path(path, info);
    reveal_existing(path, info);
    return Json::boolean(true);
}

Register register_drives("drives", &list_drives);
Register register_open_file("open_file", &open_file);
Register register_reveal("reveal", &reveal);

}  // namespace
}  // namespace swbd
