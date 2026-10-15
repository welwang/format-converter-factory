/* qpdf 的重寫層：把既有 PDF 重新寫出（重新壓縮串流、產生物件串流）。
 *
 * 為什麼需要它：PDFium 能組頁（合併／拆分）但**不會重新壓縮內容串流**，所以單檔「PDF → PDF」
 * 若交給 PDFium 會比現行 pypdf 的輸出更大——那不算等價。qpdf 的 `--compress-streams=y
 * --object-streams=generate` 正是 pypdf 在做的事，而且通常更小。
 *
 * 為什麼全程走記憶體：qpdf 的檔案 API 用窄字元 fopen，遇到 `E:\四維八德` 這種非 ASCII 路徑
 * 會直接失敗（與 stb、whisper 同一個病灶）。所以輸入由我們自己用 CreateFileW 讀進來、
 * 交給 `qpdf_read_memory`，輸出用 `qpdf_init_write_memory` + `qpdf_get_buffer` 取回、
 * 再由我們用 CreateFileW 寫出。qpdf 永遠不會看到路徑。
 *
 * 只用到 qpdf 的 C API 子集，以 LoadLibraryW + GetProcAddress 動態解析（不引入 import lib）；
 * 缺少符號時 ready() 為 false，呼叫端照舊降級。標頭參考 third_party/qpdf/qpdf-c.h（Apache-2.0）。
 */
#include "swbd/qpdf.hpp"

#include <windows.h>

#include <cstdio>
#include <string>
#include <vector>

namespace swbd::pdf {

namespace {

/* qpdf 的 C API 型別（opaque） */
using qpdf_data = void *;
using qpdf_error = void *;

constexpr int kObjectStreamGenerate = 2;   /* qpdf_object_stream_e（實測 pikepdf: generate=2） */
constexpr int kDecodeGeneralized = 1;      /* qpdf_stream_decode_level_e（generalized=1） */

std::wstring widen(const std::string &utf8) {
    if (utf8.empty()) return std::wstring();
    const int need = MultiByteToWideChar(CP_UTF8, 0, utf8.c_str(), -1, nullptr, 0);
    std::wstring out(static_cast<size_t>(need ? need : 1), L'\0');
    if (need) MultiByteToWideChar(CP_UTF8, 0, utf8.c_str(), -1, out.data(), need);
    out.resize(need ? static_cast<size_t>(need - 1) : 0);
    return out;
}

std::string narrow(const char *text) { return text ? std::string(text) : std::string(); }

/* 診斷：設 SWBD_QPDF_TRACE=1 會把每一步印到 stderr（原生 stderr 在 PowerShell 5.1 會被當成
   終止錯誤，所以只在手動追查時開啟）。 */
bool tracing() {
    static const bool on = [] {
        char buffer[8] = { 0 };
        return GetEnvironmentVariableA("SWBD_QPDF_TRACE", buffer, sizeof buffer) > 0;
    }();
    return on;
}

void trace(const char *step) {
    if (!tracing()) return;
    std::fprintf(stderr, "[qpdf] %s\n", step);
    std::fflush(stderr);
}

std::string narrow_wide(const std::wstring &w) {
    if (w.empty()) return std::string();
    const int need = WideCharToMultiByte(CP_UTF8, 0, w.c_str(), -1, nullptr, 0, nullptr, nullptr);
    std::string out(static_cast<size_t>(need ? need : 1), '\0');
    if (need) WideCharToMultiByte(CP_UTF8, 0, w.c_str(), -1, out.data(), need, nullptr, nullptr);
    out.resize(need ? static_cast<size_t>(need - 1) : 0);
    return out;
}

bool read_all(const std::string &path, std::vector<unsigned char> &out) {
    HANDLE file = CreateFileW(widen(path).c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                              FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return false;
    LARGE_INTEGER size{};
    bool ok = GetFileSizeEx(file, &size) && size.QuadPart > 0 && size.QuadPart < (1LL << 40);
    if (ok) {
        out.resize(static_cast<size_t>(size.QuadPart));
        DWORD read = 0, total = 0;
        while (total < out.size()) {
            if (!ReadFile(file, out.data() + total, static_cast<DWORD>(out.size() - total), &read, nullptr) || !read) {
                ok = false;
                break;
            }
            total += read;
        }
    }
    CloseHandle(file);
    return ok;
}

bool write_all(const std::string &path, const unsigned char *data, size_t size) {    HANDLE file = CreateFileW(widen(path).c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS,
                              FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return false;
    bool ok = true;
    size_t written_total = 0;
    while (ok && written_total < size) {
        DWORD written = 0;
        if (!WriteFile(file, data + written_total, static_cast<DWORD>(size - written_total), &written, nullptr) || !written) {
            ok = false;
            break;
        }
        written_total += written;
    }
    CloseHandle(file);
    if (!ok) DeleteFileW(widen(path).c_str());
    return ok;
}

}  // namespace

Qpdf &Qpdf::instance() {
    static Qpdf one;
    return one;
}

bool Qpdf::load(const std::string &base_dir) {
    if (ready_) return true;
    /* DLL 名稱帶雜湊（qpdf30-<hash>.dll），所以用目錄掃描找。 */
    std::wstring pattern = widen(base_dir) + L"\\_internal\\qpdf*.dll";
    WIN32_FIND_DATAW found{};
    HANDLE search = FindFirstFileW(pattern.c_str(), &found);
    std::wstring module;
    if (search != INVALID_HANDLE_VALUE) {
        module = widen(base_dir) + L"\\_internal\\" + found.cFileName;
        FindClose(search);
    }
    if (module.empty()) {
        const std::wstring beside = widen(base_dir) + L"\\qpdf30.dll";
        if (GetFileAttributesW(beside.c_str()) != INVALID_FILE_ATTRIBUTES) module = beside;
    }
    if (module.empty()) return false;

    /* qpdf30-*.dll 相依的 MSVC 執行檔（msvcp140 等）也在 _internal，而 LoadLibraryW 預設
       不會搜尋「被載入 DLL 自己的目錄」，所以要用 LOAD_WITH_ALTERED_SEARCH_PATH；
       失敗時再退回把 _internal 設成 DLL 目錄。 */
    HMODULE mod = LoadLibraryExW(module.c_str(), nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
    if (!mod) {
        const std::wstring folder = widen(base_dir) + L"\\_internal";
        SetDllDirectoryW(folder.c_str());
        mod = LoadLibraryW(module.c_str());
        SetDllDirectoryW(nullptr);
    }
    if (!mod) {
        last_load_error_ = GetLastError();
        return false;
    }
    auto sym = [mod](const char *name) { return reinterpret_cast<void *>(GetProcAddress(mod, name)); };
    Init = reinterpret_cast<qpdf_data (*)()>(sym("qpdf_init"));
    ReadMemory = reinterpret_cast<int (*)(qpdf_data, const char *, const char *, unsigned long long, const char *)>(sym("qpdf_read_memory"));
    InitWriteMemory = reinterpret_cast<int (*)(qpdf_data)>(sym("qpdf_init_write_memory"));
    Write = reinterpret_cast<int (*)(qpdf_data)>(sym("qpdf_write"));
    GetBuffer = reinterpret_cast<const unsigned char *(*)(qpdf_data)>(sym("qpdf_get_buffer"));
    GetBufferLength = reinterpret_cast<size_t (*)(qpdf_data)>(sym("qpdf_get_buffer_length"));
    HasError = reinterpret_cast<int (*)(qpdf_data)>(sym("qpdf_has_error"));
    GetError = reinterpret_cast<qpdf_error (*)(qpdf_data)>(sym("qpdf_get_error"));
    GetErrorText = reinterpret_cast<const char *(*)(qpdf_data, qpdf_error)>(sym("qpdf_get_error_full_text"));
    SetCompressStreams = reinterpret_cast<void (*)(qpdf_data, int)>(sym("qpdf_set_compress_streams"));
    SetObjectStreamMode = reinterpret_cast<void (*)(qpdf_data, int)>(sym("qpdf_set_object_stream_mode"));
    SetDecodeLevel = reinterpret_cast<void (*)(qpdf_data, int)>(sym("qpdf_set_decode_level"));
    SetPreserveUnreferenced = reinterpret_cast<void (*)(qpdf_data, int)>(sym("qpdf_set_preserve_unreferenced_objects"));
    Cleanup = reinterpret_cast<void (*)(qpdf_data *)>(sym("qpdf_cleanup"));
    GetVersion = reinterpret_cast<const char *(*)()>(sym("qpdf_get_qpdf_version"));

    const bool complete = Init && ReadMemory && InitWriteMemory && Write && GetBuffer && GetBufferLength &&
                          HasError && GetError && GetErrorText && SetCompressStreams && SetObjectStreamMode &&
                          SetDecodeLevel && SetPreserveUnreferenced && Cleanup;
    if (!complete) {
        FreeLibrary(mod);
        return false;
    }
    module_ = mod;
    ready_ = true;
    module_path_ = narrow_wide(module);   /* 診斷用 */
    if (GetVersion) version_ = narrow(GetVersion());
    return true;
}

std::string Qpdf::last_error(qpdf_data q) const {
    if (!q || !HasError || !HasError(q)) return "qpdf 沒有回報錯誤";
    qpdf_error e = GetError(q);
    const char *text = (e && GetErrorText) ? GetErrorText(q, e) : nullptr;
    return text && *text ? std::string(text) : "qpdf 未知錯誤";
}

bool Qpdf::rewrite_file(const std::string &input_utf8, const std::string &output_utf8, std::string &error,
                        bool recover) {
    if (!ready_) {
        error = "qpdf 未載入";
        return false;
    }
    std::vector<unsigned char> input;
    if (!read_all(input_utf8, input)) {
        error = "無法讀取來源 PDF";
        return false;
    }
    qpdf_data q = Init();
    if (!q) {
        error = "qpdf 初始化失敗";
        return false;
    }
    trace("init");
    bool ok = false;
    do {
        /* 復原必須在讀取之前開啟（qpdf 的設定會影響 parse 階段）。 */
        if (recover && SetAttemptRecovery) SetAttemptRecovery(q, 1);
        const int read_rc = ReadMemory(q, "input", reinterpret_cast<const char *>(input.data()),
                                       static_cast<unsigned long long>(input.size()), nullptr);
        trace("read_memory");
        if (read_rc != 0) {
            error = last_error(q);
            break;
        }
        /* 順序很重要：qpdf 的 setter 會寫入 writer，而 writer 要由 qpdf_init_write_* 建立。
           先呼叫 setter 會解引用空的 writer → 存取違規（實測 0xC0000005）。 */
        const int init_write_rc = InitWriteMemory(q);
        trace("init_write_memory");
        if (init_write_rc != 0) {
            error = last_error(q);
            break;
        }
        /* 與 pypdf 路徑等價的設定：重新壓縮串流、產生物件串流、丟掉未被引用的物件。 */
        SetCompressStreams(q, 1);
        SetObjectStreamMode(q, kObjectStreamGenerate);
        SetDecodeLevel(q, kDecodeGeneralized);
        SetPreserveUnreferenced(q, 0);
        trace("settings");
        const int write_rc = Write(q);
        trace("write");
        if (write_rc != 0) {
            error = last_error(q);
            break;
        }
        const unsigned char *buffer = GetBuffer(q);
        const size_t length = GetBufferLength(q);
        trace("get_buffer");
        if (!buffer || length == 0) {
            error = "qpdf 沒有產生輸出";
            break;
        }
        if (!write_all(output_utf8, buffer, length)) {
            error = "無法寫出重寫後的 PDF";
            break;
        }
        ok = true;
    } while (false);
    trace("cleanup");
    Cleanup(&q);
    return ok;
}

bool Qpdf::rewrite_memory(const std::vector<unsigned char> &input, std::vector<unsigned char> &output, std::string &error) {
    if (!ready_) {
        error = "qpdf 未載入";
        return false;
    }
    qpdf_data q = Init();
    if (!q) {
        error = "qpdf 初始化失敗";
        return false;
    }
    bool ok = false;
    do {
        if (ReadMemory(q, "input", reinterpret_cast<const char *>(input.data()),
                       static_cast<unsigned long long>(input.size()), nullptr) != 0) {
            error = last_error(q);
            break;
        }
        /* 與 rewrite_file 相同的順序要求：先建立 writer，再設定選項。 */
        const int init_write_rc = InitWriteMemory(q);
        if (init_write_rc != 0) { error = last_error(q); break; }
        SetCompressStreams(q, 1);
        SetObjectStreamMode(q, kObjectStreamGenerate);
        SetDecodeLevel(q, kDecodeGeneralized);
        SetPreserveUnreferenced(q, 0);
        if (Write(q) != 0) {
            error = last_error(q);
            break;
        }
        const unsigned char *buffer = GetBuffer(q);
        const size_t length = GetBufferLength(q);
        if (!buffer || length == 0) {
            error = "qpdf 沒有產生輸出";
            break;
        }
        output.assign(buffer, buffer + length);
        ok = true;
    } while (false);
    Cleanup(&q);
    return ok;
}

}  // namespace swbd::pdf
