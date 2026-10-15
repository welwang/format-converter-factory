/* 系統層實作：Win32 原語，語意對齊 Python 的 os / os.path / tempfile。 */
#include "swbd/sys.hpp"

#include <windows.h>

#include <cstdio>
#include <vector>

namespace swbd::sys {
namespace {

std::wstring widen(std::string_view s) {
    if (s.empty()) return {};
    int n = MultiByteToWideChar(CP_UTF8, 0, s.data(), static_cast<int>(s.size()), nullptr, 0);
    if (n <= 0) return {};
    std::wstring w(static_cast<size_t>(n), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, s.data(), static_cast<int>(s.size()), w.data(), n);
    return w;
}

std::string narrow(const std::wstring &w) {
    if (w.empty()) return {};
    int n = WideCharToMultiByte(CP_UTF8, 0, w.c_str(), static_cast<int>(w.size()), nullptr, 0, nullptr, nullptr);
    if (n <= 0) return {};
    std::string s(static_cast<size_t>(n), '\0');
    WideCharToMultiByte(CP_UTF8, 0, w.c_str(), static_cast<int>(w.size()), s.data(), n, nullptr, nullptr);
    return s;
}

/* 去掉尾端斜線，但保留磁碟根目錄（"E:\" 不變），對齊 Python 的 abspath 結果。 */
std::string strip_trailing(std::string p) {
    while (p.size() > 3 && (p.back() == '\\' || p.back() == '/')) p.pop_back();
    return p;
}

bool is_writable_dir(const std::string &dir) {
    if (dir.empty()) return false;
    std::wstring probe = widen(dir + "\\zdgc_write_test.tmp");
    HANDLE h = CreateFileW(probe.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS,
                           FILE_ATTRIBUTE_TEMPORARY | FILE_FLAG_DELETE_ON_CLOSE, nullptr);
    if (h == INVALID_HANDLE_VALUE) return false;
    CloseHandle(h);
    return true;
}

bool stat_impl(std::string_view path, FileInfo &out, bool follow_links) {
    out = FileInfo{};
    std::wstring w = widen(path);
    if (w.empty()) return false;
    DWORD attr = GetFileAttributesW(w.c_str());
    if (attr == INVALID_FILE_ATTRIBUTES) return false;
    out.ok = true;
    out.is_dir = (attr & FILE_ATTRIBUTE_DIRECTORY) != 0;
    out.is_reparse = (attr & FILE_ATTRIBUTE_REPARSE_POINT) != 0;
    out.is_regular = !out.is_dir;
    DWORD flags = FILE_FLAG_BACKUP_SEMANTICS;
    if (!follow_links) flags |= FILE_FLAG_OPEN_REPARSE_POINT;
    HANDLE h = CreateFileW(w.c_str(), FILE_READ_ATTRIBUTES,
                           FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                           nullptr, OPEN_EXISTING, flags, nullptr);
    if (h != INVALID_HANDLE_VALUE) {
        BY_HANDLE_FILE_INFORMATION info{};
        if (GetFileInformationByHandle(h, &info)) {
            out.size = (static_cast<std::uint64_t>(info.nFileSizeHigh) << 32) | info.nFileSizeLow;
            ULARGE_INTEGER u;
            u.LowPart = info.ftLastWriteTime.dwLowDateTime;
            u.HighPart = info.ftLastWriteTime.dwHighDateTime;
            out.mtime_ticks = static_cast<std::int64_t>(u.QuadPart);
            /* 1601-01-01 → 1970-01-01 的 100ns 數，與 Python st_mtime 同一個算式。 */
            out.mtime = static_cast<double>(out.mtime_ticks - 116444736000000000LL) / 1e7;
        }
        CloseHandle(h);
    }
    return true;
}

}  // namespace

std::string abs_path(std::string_view path) {
    std::wstring w = widen(path);
    if (w.empty()) return {};
    DWORD need = GetFullPathNameW(w.c_str(), 0, nullptr, nullptr);
    if (!need) return std::string(path);
    std::wstring buf(need, L'\0');
    DWORD n = GetFullPathNameW(w.c_str(), need, buf.data(), nullptr);
    if (!n) return std::string(path);
    buf.resize(n);
    return strip_trailing(narrow(buf));
}

std::string final_path(std::string_view path) {
    std::wstring w = widen(path);
    HANDLE h = CreateFileW(w.c_str(), FILE_READ_ATTRIBUTES,
                           FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                           nullptr, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, nullptr);
    if (h == INVALID_HANDLE_VALUE) return abs_path(path);   /* 不存在時 Python realpath 也退回絕對路徑 */
    DWORD need = GetFinalPathNameByHandleW(h, nullptr, 0, FILE_NAME_NORMALIZED | VOLUME_NAME_DOS);
    std::wstring buf(need ? need : 1, L'\0');
    DWORD n = GetFinalPathNameByHandleW(h, buf.data(), static_cast<DWORD>(buf.size()),
                                        FILE_NAME_NORMALIZED | VOLUME_NAME_DOS);
    CloseHandle(h);
    if (!n || n > buf.size()) return abs_path(path);
    buf.resize(n);
    if (buf.rfind(L"\\\\?\\UNC\\", 0) == 0) buf = L"\\\\" + buf.substr(8);
    else if (buf.rfind(L"\\\\?\\", 0) == 0) buf = buf.substr(4);
    return strip_trailing(narrow(buf));
}

std::string norm_case(std::string_view path) {
    std::string s(path);
    for (char &c : s) {
        if (c == '/') c = '\\';
        else if (c >= 'A' && c <= 'Z') c = static_cast<char>(c - 'A' + 'a');
    }
    return s;
}

std::string join(std::string_view a, std::string_view b) {
    if (b.empty()) return std::string(a);
    const bool absolute = b.size() >= 2 && b[1] == ':' ? true : (b[0] == '\\' || b[0] == '/');
    if (absolute) return std::string(b);
    if (a.empty()) return std::string(b);
    std::string out(a);
    if (out.back() != '\\' && out.back() != '/') out.push_back('\\');
    out.append(b);
    return out;
}

std::string base_name(std::string_view path) {
    size_t cut = path.find_last_of("\\/");
    return std::string(cut == std::string_view::npos ? path : path.substr(cut + 1));
}

std::string system_temp_dir() {
    for (const wchar_t *name : {L"TMPDIR", L"TEMP", L"TMP"}) {
        DWORD need = GetEnvironmentVariableW(name, nullptr, 0);
        if (!need) continue;
        std::wstring buf(need, L'\0');
        DWORD n = GetEnvironmentVariableW(name, buf.data(), need);
        if (!n) continue;
        buf.resize(n);
        std::string dir = strip_trailing(abs_path(narrow(buf)));
        FileInfo info;
        if (stat_path(dir, info) && info.is_dir && !info.is_reparse && is_writable_dir(dir)) return dir;
    }
    wchar_t buf[MAX_PATH + 1] = {0};
    DWORD n = GetTempPathW(MAX_PATH, buf);
    if (n) return strip_trailing(abs_path(narrow(std::wstring(buf, n))));
    return {};
}

bool stat_path(std::string_view path, FileInfo &out) { return stat_impl(path, out, true); }
bool lstat_path(std::string_view path, FileInfo &out) { return stat_impl(path, out, false); }

std::vector<DirEntry> list_dir(std::string_view path) {
    std::vector<DirEntry> out;
    std::wstring pattern = widen(join(path, "*"));
    WIN32_FIND_DATAW data{};
    HANDLE h = FindFirstFileW(pattern.c_str(), &data);
    if (h == INVALID_HANDLE_VALUE) return out;
    do {
        std::wstring name = data.cFileName;
        if (name == L"." || name == L"..") continue;
        DirEntry entry;
        entry.name = narrow(name);
        entry.is_dir = (data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
        entry.is_reparse = (data.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0;
        out.push_back(std::move(entry));
    } while (FindNextFileW(h, &data));
    FindClose(h);
    return out;
}

bool path_inside(std::string_view child, std::string_view root) {
    std::string c = norm_case(final_path(child));
    std::string r = norm_case(final_path(root));
    if (c.empty() || r.empty()) return false;
    const bool prefix = c.size() > r.size() && c.compare(0, r.size(), r) == 0 &&
                        (r.back() == '\\' || c[r.size()] == '\\');
    if (!prefix) return false;
    return abs_path(child) != abs_path(root);   /* Python 另外排除根目錄本身 */
}

bool same_path(std::string_view a, std::string_view b) {
    return norm_case(final_path(a)) == norm_case(final_path(b));
}

bool remove_file(std::string_view path) {
    return DeleteFileW(widen(path).c_str()) != 0;
}

double now_s() {
    FILETIME ft{};
    GetSystemTimeAsFileTime(&ft);
    ULARGE_INTEGER u;
    u.LowPart = ft.dwLowDateTime;
    u.HighPart = ft.dwHighDateTime;
    return static_cast<double>(static_cast<std::int64_t>(u.QuadPart) - 116444736000000000LL) / 1e7;
}

std::string last_error_text() {
    DWORD code = GetLastError();
    LPWSTR message = nullptr;
    DWORD n = FormatMessageW(FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM |
                                 FORMAT_MESSAGE_IGNORE_INSERTS,
                             nullptr, code, MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
                             reinterpret_cast<LPWSTR>(&message), 0, nullptr);
    std::string text = (n && message) ? narrow(std::wstring(message, n)) : "Windows 錯誤 " + std::to_string(code);
    if (message) LocalFree(message);
    return text;
}

}  // namespace swbd::sys
