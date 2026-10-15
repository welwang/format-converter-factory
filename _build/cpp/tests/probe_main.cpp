/* 驗證探針：不開視窗、不需要 WebView2，直接驅動 C++ 核心，供等價測試與人工檢查。
   用法：swbd-cpp-probe <base_dir> <data_dir> <method> [args-json | --args <file>] [--out <file>]
         swbd-cpp-probe <base_dir> <data_dir> --calls <file> [--out <file>]
   含引號的 JSON 在命令列會被 CRT 吃掉引號，因此建議用 --args 指定檔案。
   --calls 檔是 [{ "m": "方法", "a": [參數…] }, …]；有狀態的方法（例如 disk_preview → disk_launch）
   必須在同一個行程內連續呼叫才測得到，參數裡寫 "@token" 會代換成前一次回覆的 token 欄位。
   使用 wmain：PowerShell 傳給 char** 的是 ANSI（本機 CP950）位元組，含中文的路徑會壞掉。
   輸出：{"ok":true,"r":...} 或 {"ok":false,"e":"..."}；--calls 模式輸出回覆陣列。
   未接手的方法離開碼 3。 */
#include <windows.h>

#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "swbd/bridge.hpp"

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

bool read_file_utf8(const std::wstring &path, std::string &out) {
    HANDLE h = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                           FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return false;
    LARGE_INTEGER size{};
    if (!GetFileSizeEx(h, &size)) { CloseHandle(h); return false; }
    out.assign(static_cast<size_t>(size.QuadPart), '\0');
    DWORD read = 0;
    const bool ok = out.empty() || ReadFile(h, out.data(), static_cast<DWORD>(out.size()), &read, nullptr) != 0;
    CloseHandle(h);
    out.resize(read);
    while (!out.empty() && (out.back() == '\n' || out.back() == '\r' || out.back() == ' ')) out.pop_back();
    if (out.size() >= 3 && static_cast<unsigned char>(out[0]) == 0xEF) out.erase(0, 3);   /* UTF-8 BOM */
    return ok;
}

}  // namespace

int wmain(int argc, wchar_t **argv) {
    SetConsoleOutputCP(CP_UTF8);
    if (argc < 4) {
        std::fprintf(stderr, "用法：swbd-cpp-probe <base_dir> <data_dir> <method> [args-json | --args <file>] [--out <file>]\n");
        return 2;
    }
    std::wstring out_file;
    std::wstring args_file;
    std::wstring calls_file;
    for (int i = 3; i + 1 < argc; i++) {   /* 從 3 開始：--calls 模式沒有 method 參數 */
        if (!std::wcscmp(argv[i], L"--out")) out_file = argv[i + 1];
        else if (!std::wcscmp(argv[i], L"--args")) args_file = argv[i + 1];
        else if (!std::wcscmp(argv[i], L"--calls")) calls_file = argv[i + 1];
    }

    if (!swbd_cpp_init(to_utf8(argv[1]).c_str(), to_utf8(argv[2]).c_str())) {
        std::fprintf(stderr, "C++ 核心初始化失敗\n");
        return 2;
    }
    std::fprintf(stderr, "C++ 核心已註冊 %d 個方法\n", swbd_cpp_method_count());

    /* 多次呼叫模式：有狀態的方法（disk_preview → disk_launch）必須在同一個行程內連續呼叫。
       參數中的 "@token" 會代換成前一次回覆的 token，讓「預覽完再啟動」測得出來。 */
    if (!calls_file.empty()) {
        std::string calls_text;
        if (!read_file_utf8(calls_file, calls_text)) {
            std::fprintf(stderr, "無法讀取 calls 檔\n");
            return 2;
        }
        jval *calls = json_parse(calls_text.c_str());
        if (!calls || calls->type != J_ARR) {
            std::fprintf(stderr, "calls 檔必須是 [{ \"m\": ..., \"a\": [...] }, …]\n");
            if (calls) json_free(calls);
            return 2;
        }
        std::string last_token;
        std::string responses = "[";
        for (size_t i = 0; i < calls->len; i++) {
            const jval *call = calls->items[i];
            const jval *method = call ? jget(call, "m") : nullptr;
            if (!method || method->type != J_STR || !method->str) continue;
            const jval *source_args = call ? jget(call, "a") : nullptr;
            jval *owned = (source_args && source_args->type == J_ARR) ? json_clone(source_args) : jnew(J_ARR);
            jval *args = owned;
            if (source_args && source_args->type == J_ARR) {
                for (size_t k = 0; k < owned->len; k++) {
                    jval *item = owned->items[k];
                    if (item && item->type == J_STR && item->str && !std::strcmp(item->str, "@token")) {
                        json_free(item);
                        owned->items[k] = jstr(last_token.c_str());
                    }
                }
            }
            char *reply = swbd_cpp_call(method->str, args);
            json_free(owned);
            if (!reply) {
                std::fprintf(stderr, "C++ 核心沒有接手：%s\n", method->str);
                json_free(calls);
                return 3;
            }
            const std::string text = reply;
            swbd_cpp_free(reply);
            if (i) responses += ",";
            responses += text;
            /* 記下 token 供下一個呼叫使用 */
            jval *parsed = json_parse(text.c_str());
            const jval *result = parsed ? jget(parsed, "r") : nullptr;
            const jval *token = result ? jget(result, "token") : nullptr;
            if (token && token->type == J_STR && token->str) last_token = token->str;
            if (parsed) json_free(parsed);
        }
        responses += "]";
        json_free(calls);
        if (!out_file.empty()) {
            if (!write_file_utf8(out_file, responses)) {
                std::fprintf(stderr, "無法寫入輸出檔\n");
                return 2;
            }
        } else {
            std::fwrite(responses.data(), 1, responses.size(), stdout);
            std::fputc('\n', stdout);
        }
        return 0;
    }

    std::string args_text = "[]";
    if (!args_file.empty()) {
        if (!read_file_utf8(args_file, args_text)) {
            std::fprintf(stderr, "無法讀取 args 檔\n");
            return 2;
        }
        if (args_text.empty()) args_text = "[]";
    } else if (argc > 4 && std::wcsncmp(argv[4], L"--", 2) && std::wcscmp(argv[4], L"[]")) {
        args_text = to_utf8(argv[4]);
    }

    jval *args = json_parse(args_text.c_str());
    if (!args) {
        std::fprintf(stderr, "args JSON 格式錯誤（命令列含引號時請改用 --args <file>）\n");
        return 2;
    }
    char *reply = swbd_cpp_call(to_utf8(argv[3]).c_str(), args);
    json_free(args);
    if (!reply) {
        std::fprintf(stderr, "C++ 核心沒有接手：%s\n", to_utf8(argv[3]).c_str());
        return 3;
    }
    const std::string text = reply;
    swbd_cpp_free(reply);
    if (!out_file.empty()) {
        if (!write_file_utf8(out_file, text)) {
            std::fprintf(stderr, "無法寫入輸出檔\n");
            return 2;
        }
    } else {
        std::fwrite(text.data(), 1, text.size(), stdout);
        std::fputc('\n', stdout);
    }
    return 0;
}
