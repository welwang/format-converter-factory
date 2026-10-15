/* 等價測試用的 C++ 側執行檔：在**同一個行程**內依 app.py 的順序呼叫
   cleanup_scan → cleanup_execute，並輸出前後檔案清單，供與 Python 版逐欄比對。
   用法：swbd-cpp-equivalence <fixture_root> <data_dir> <temp_dir> <out.json>
   使用 wmain：PowerShell 傳給 char** 的是 ANSI（本機 CP950）位元組，含中文的路徑會壞掉。 */
#include <windows.h>

#include <algorithm>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

#include "swbd/bridge.hpp"
#include "swbd/registry.hpp"
#include "swbd/sys.hpp"

namespace {

std::string to_utf8(const wchar_t *w) {
    if (!w || !*w) return {};
    const int n = WideCharToMultiByte(CP_UTF8, 0, w, -1, nullptr, 0, nullptr, nullptr);
    if (n <= 0) return {};
    std::string s(static_cast<size_t>(n - 1), '\0');
    WideCharToMultiByte(CP_UTF8, 0, w, -1, s.data(), n, nullptr, nullptr);
    return s;
}

bool write_file_utf8(const std::wstring &path, const std::string &text) {
    HANDLE h = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS,
                           FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return false;
    DWORD written = 0;
    const bool ok = WriteFile(h, text.data(), static_cast<DWORD>(text.size()), &written, nullptr) != 0;
    CloseHandle(h);
    return ok && written == text.size();
}

/* 列出 fixture 內所有項目（檔案＝相對路徑、目錄＝相對路徑加尾端反斜線），
   不進入 reparse point 目錄，與 Python 端的 listing() 一致。 */
void list_tree(const std::string &root, const std::string &dir, std::vector<std::string> &out) {
    for (const swbd::sys::DirEntry &entry : swbd::sys::list_dir(dir)) {
        const std::string full = swbd::sys::join(dir, entry.name);
        std::string rel = full.size() > root.size() ? full.substr(root.size()) : entry.name;
        while (!rel.empty() && (rel.front() == '\\' || rel.front() == '/')) rel.erase(rel.begin());
        if (entry.is_dir) {
            out.push_back(rel + "\\");
            if (!entry.is_reparse) list_tree(root, full, out);
        } else {
            out.push_back(rel);
        }
    }
}

swbd::Json string_array(const std::vector<std::string> &items) {
    swbd::Json array = swbd::Json::array();
    for (const std::string &item : items) array.push(swbd::Json::of(item));
    return array;
}

}  // namespace

int wmain(int argc, wchar_t **argv) {
    SetConsoleOutputCP(CP_UTF8);
    if (argc < 5) {
        std::fprintf(stderr, "用法：swbd-cpp-equivalence <fixture_root> <data_dir> <temp_dir> <out.json>\n");
        return 2;
    }
    const std::string root = swbd::sys::abs_path(to_utf8(argv[1]));
    const std::string data = swbd::sys::abs_path(to_utf8(argv[2]));
    const std::string temp = swbd::sys::abs_path(to_utf8(argv[3]));
    const std::string out_path = to_utf8(argv[4]);

    if (!swbd_cpp_init(to_utf8(argv[1]).c_str(), to_utf8(argv[2]).c_str())) {
        std::fprintf(stderr, "C++ 核心初始化失敗\n");
        return 2;
    }

    swbd::Context ctx;
    ctx.base_dir = root;
    ctx.data_dir = data;
    ctx.temp_dir = temp;

    std::vector<std::string> before;
    list_tree(root, root, before);
    std::sort(before.begin(), before.end());

    swbd::Json categories = swbd::Json::array();
    for (const char *name : {"app_temp", "download_parts", "logs", "user_temp"})
        categories.push(swbd::Json::of(std::string(name)));
    swbd::Json scan_args = swbd::Json::array();
    scan_args.push(std::move(categories));

    swbd::Json report = swbd::Json::object();
    report.set("before", string_array(before));

    swbd::Json preview = swbd::Registry::instance().call(ctx, "cleanup_scan", scan_args.raw());
    const std::string token = preview.str("token");
    report.set("preview", std::move(preview));

    swbd::Json execute_args = swbd::Json::array();
    execute_args.push(swbd::Json::of(token));
    swbd::Json executed = swbd::Registry::instance().call(ctx, "cleanup_execute", execute_args.raw());
    report.set("execute", std::move(executed));

    std::vector<std::string> after;
    list_tree(root, root, after);
    std::sort(after.begin(), after.end());
    report.set("after", string_array(after));

    if (!write_file_utf8(argv[4], report.dump())) {
        std::fprintf(stderr, "無法寫入輸出檔\n");
        return 2;
    }
    return 0;
}
