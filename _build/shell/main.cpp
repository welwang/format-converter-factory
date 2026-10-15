/*
 * 四維八德 — native main program (C++20, Win32 + Microsoft Edge WebView2).
 *
 * Native window and conversion orchestration. This executable owns:
 * the window, the WebView2 page, drag-and-drop with real paths, file / folder dialogs, a single
 * running instance (files opened later are handed to the open window), window position memory,
 * the taskbar flash and the WebView2 runtime check.
 *
 * engine.cpp handles generic media, documents, archives and ebooks; api.cpp combines native and
 * Python jobs. Images, PDF, toolbox tools and workflows run in the windowless swbd-core.exe.
 * The two talk over anonymous pipes with one
 * UTF-8 line per message:
 *
 *   shell -> core   Q <json>                 request from the page   {"id":n,"m":"method","a":[...]}
 *                   A <id>\t<json>           answer to a core request (dialogs)
 *                   E <json>                 event: {"ev":"files","paths":[...]} or {"ev":"close"}
 *   core  -> shell  R <json>                 message for the page (answers, dropped files)
 *                   S <id>\t<op>\t<args...>  window operation; id 0 = no answer wanted
 *
 * Build: _build\shell\CMakeLists.txt (C++20, MSVC + WebView2 SDK, static WebView2 loader).
 *        _build\shell\build_shell.ps1 fetches the SDK and drives that CMake build.
 */
#define WIN32_LEAN_AND_MEAN
#define _WIN32_WINNT 0x0A00
#define WINVER 0x0A00
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <windowsx.h>
#include <shellapi.h>
#include <shlobj.h>
#include <shobjidl.h>
#include <commdlg.h>
#include <shlwapi.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>
#include <limits.h>
#include <powrprof.h>
#include <wrl/client.h>     /* ComPtr: RAII for the COM objects the shell creates itself */
#include "WebView2.h"
#include "api.h"
#include "json.h"
#include "swbd/bridge.hpp"   /* the C++ core that takes methods over from the Python component */

#pragma comment(lib, "user32.lib")
#pragma comment(lib, "gdi32.lib")
#pragma comment(lib, "ole32.lib")
#pragma comment(lib, "oleaut32.lib")
#pragma comment(lib, "uuid.lib")
#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "comdlg32.lib")
#pragma comment(lib, "shlwapi.lib")
#pragma comment(lib, "advapi32.lib")
#pragma comment(lib, "version.lib")
#pragma comment(lib, "WebView2LoaderStatic.lib")
#pragma comment(lib, "powrprof.lib")

#define APP_TITLE      L"四維八德（開源版）"
#define WINDOW_CLASS   L"SiWeiBaDe.MainWindow"
#define MUTEX_NAME     L"Local\\SiWeiBaDe.SingleInstance"
#define CORE_EXE       L"swbd-core.exe"
#define WM_CORE_LINE   (WM_APP + 1)   /* lParam: char* line (malloc), from the reader thread */
#define WM_CORE_EXIT   (WM_APP + 2)
#define WM_PAGE_JSON   (WM_APP + 3)   /* lParam: char* JSON for the page (malloc) */
#define WM_SET_TITLE   (WM_APP + 4)   /* lParam: char* UTF-8 title (malloc) */
#define WM_FLASH       (WM_APP + 5)
#define TIMER_CLOSE    1
#define IDI_APPICON    1

/* ------------------------------------------------------------------ state */
static HWND g_hwnd;
static ICoreWebView2Controller *g_controller;
static ICoreWebView2 *g_webview;
static HANDLE g_coreProcess, g_coreIn, g_coreOut, g_job;
static CRITICAL_SECTION g_writeLock;
static BOOL g_coreReady, g_pageReady, g_readySent, g_closing, g_coreGone;
static wchar_t g_baseDir[MAX_PATH], g_dataDir[MAX_PATH], g_iniPath[MAX_PATH];
static wchar_t *g_pendingFiles;   /* JSON array of files given on the command line, sent once the core is ready */
static wchar_t g_pagePath[MAX_PATH], g_smokeReport[MAX_PATH * 2];
static BOOL g_smoke;
static int g_smokeExit = 1;
static volatile LONG g_smokeFinishes;
static void request_close(void);
static void smoke_write(const char *json)
{
    if (!g_smoke || !g_smokeReport[0]) return;
    HANDLE f = CreateFileW(g_smokeReport, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f != INVALID_HANDLE_VALUE) { DWORD written; WriteFile(f, json, (DWORD)strlen(json), &written, NULL); CloseHandle(f); }
}

/* ------------------------------------------------------------------ small helpers */
static char *utf8_from_wide(const wchar_t *w, int len)
{
    int n = WideCharToMultiByte(CP_UTF8, 0, w, len, NULL, 0, NULL, NULL);
    char *s = (char *)malloc((size_t)n + 1);
    if (!s) return NULL;
    WideCharToMultiByte(CP_UTF8, 0, w, len, s, n, NULL, NULL);
    s[n] = 0;
    return s;
}

static wchar_t *wide_from_utf8(const char *s)
{
    int n = MultiByteToWideChar(CP_UTF8, 0, s, -1, NULL, 0);
    wchar_t *w = (wchar_t *)malloc(sizeof(wchar_t) * (size_t)(n ? n : 1));
    if (!w) return NULL;
    if (n) MultiByteToWideChar(CP_UTF8, 0, s, -1, w, n); else w[0] = 0;
    return w;
}

/* growable UTF-16 string */
typedef struct { wchar_t *p; size_t len, cap; } wbuf;
static void wb_add(wbuf *b, const wchar_t *s, size_t n)
{
    if (b->len + n + 1 > b->cap) {
        size_t cap = b->cap ? b->cap : 256;
        while (b->len + n + 1 > cap) cap *= 2;
        wchar_t *p = (wchar_t *)realloc(b->p, cap * sizeof(wchar_t));
        if (!p) return;
        b->p = p; b->cap = cap;
    }
    memcpy(b->p + b->len, s, n * sizeof(wchar_t));
    b->len += n; b->p[b->len] = 0;
}
static void wb_str(wbuf *b, const wchar_t *s) { wb_add(b, s, wcslen(s)); }

/* append s as a JSON string literal */
static void wb_json(wbuf *b, const wchar_t *s)
{
    wb_str(b, L"\"");
    for (; *s; s++) {
        wchar_t c = *s, esc[8];
        if (c == L'"') wb_str(b, L"\\\"");
        else if (c == L'\\') wb_str(b, L"\\\\");
        else if (c < 0x20) { swprintf(esc, 8, L"\\u%04x", (unsigned)c); wb_str(b, esc); }
        else wb_add(b, &c, 1);
    }
    wb_str(b, L"\"");
}

static void log_line(const char *msg)
{
    wchar_t path[MAX_PATH];
    swprintf(path, MAX_PATH, L"%s\\logs\\shell.log", g_dataDir);
    FILE *f = _wfopen(path, L"ab");
    if (!f) return;
    SYSTEMTIME t; GetLocalTime(&t);
    fprintf(f, "%04d-%02d-%02d %02d:%02d:%02d %s\r\n", t.wYear, t.wMonth, t.wDay, t.wHour, t.wMinute, t.wSecond, msg);
    fclose(f);
}

static void fail_box(const wchar_t *msg)
{
    if (g_smoke) { smoke_write("{\"ok\":false,\"error\":\"native window startup failed\"}"); return; }
    MessageBoxW(g_hwnd, msg, APP_TITLE, MB_OK | MB_ICONWARNING);
}

/* Settings, logs and models live next to the program (portable use) unless that folder is read-only,
   e.g. under Program Files: then %LOCALAPPDATA%\ZhuanDangGongChang - the same rule as the core. */
static void init_dirs(void)
{
    GetModuleFileNameW(NULL, g_baseDir, MAX_PATH);
    PathRemoveFileSpecW(g_baseDir);
    wchar_t test[MAX_PATH];
    swprintf(test, MAX_PATH, L"%s\\.zdgc_write_test", g_baseDir);
    HANDLE h = CreateFileW(test, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_FLAG_DELETE_ON_CLOSE, NULL);
    if (h != INVALID_HANDLE_VALUE) {
        CloseHandle(h);
        wcscpy(g_dataDir, g_baseDir);
    } else {
        wchar_t local[MAX_PATH];
        if (!GetEnvironmentVariableW(L"LOCALAPPDATA", local, MAX_PATH)) wcscpy(local, g_baseDir);
        swprintf(g_dataDir, MAX_PATH, L"%s\\ZhuanDangGongChang", local);
        CreateDirectoryW(g_dataDir, NULL);
    }
    wchar_t logs[MAX_PATH];
    swprintf(logs, MAX_PATH, L"%s\\logs", g_dataDir);
    CreateDirectoryW(logs, NULL);
    swprintf(g_iniPath, MAX_PATH, L"%s\\window.ini", g_dataDir);
}

/* ------------------------------------------------------------------ talking to the core */
static void core_write_utf8(const char *prefix, const char *u)
{
    if (!g_coreIn || g_coreGone) return;
    EnterCriticalSection(&g_writeLock);
    DWORD w;
    WriteFile(g_coreIn, prefix, (DWORD)strlen(prefix), &w, NULL);
    WriteFile(g_coreIn, u, (DWORD)strlen(u), &w, NULL);
    WriteFile(g_coreIn, "\n", 1, &w, NULL);
    LeaveCriticalSection(&g_writeLock);
}

static void core_write(const char *prefix, const wchar_t *body)
{
    char *u = utf8_from_wide(body, -1);
    if (!u) return;
    core_write_utf8(prefix, u);
    free(u);
}

static DWORD WINAPI core_reader(LPVOID unused)
{
    (void)unused;
    size_t cap = 1 << 16, len = 0;
    char *buf = (char *)malloc(cap);
    char chunk[1 << 15];
    DWORD got;
    while (buf && ReadFile(g_coreOut, chunk, sizeof chunk, &got, NULL) && got) {
        if (len + got + 1 > cap) {
            while (len + got + 1 > cap) cap *= 2;
            char *nb = (char *)realloc(buf, cap);
            if (!nb) break;
            buf = nb;
        }
        memcpy(buf + len, chunk, got); len += got;
        size_t start = 0;
        for (size_t i = 0; i < len; i++) {
            if (buf[i] != '\n') continue;
            size_t n = i - start;
            if (n && buf[start + n - 1] == '\r') n--;
            char *line = (char *)malloc(n + 1);
            if (line) {
                memcpy(line, buf + start, n); line[n] = 0;
                /* answers to calls the C side made itself are handed over right here */
                if (api_core_line(line)) free(line);
                else if (!PostMessageW(g_hwnd, WM_CORE_LINE, 0, (LPARAM)line)) free(line);
            }
            start = i + 1;
        }
        memmove(buf, buf + start, len - start); len -= start;
    }
    free(buf);
    PostMessageW(g_hwnd, WM_CORE_EXIT, 0, 0);
    return 0;
}

/* Windows command-line quoting for one argument (CommandLineToArgvW rules). */
static void append_arg(wbuf *b, const wchar_t *a)
{
    if (*a && !wcspbrk(a, L" \t\"")) { wb_str(b, a); return; }
    wb_str(b, L"\"");
    for (const wchar_t *p = a;; p++) {
        unsigned slashes = 0;
        while (*p == L'\\') { p++; slashes++; }
        if (!*p) { for (unsigned i = 0; i < slashes * 2; i++) wb_str(b, L"\\"); break; }
        if (*p == L'"') { for (unsigned i = 0; i < slashes * 2 + 1; i++) wb_str(b, L"\\"); }
        else { for (unsigned i = 0; i < slashes; i++) wb_str(b, L"\\"); }
        wb_add(b, p, 1);
    }
    wb_str(b, L"\"");
}

/* Start swbd-core.exe with piped stdin/stdout; stderr goes to logs\core.log.  The core is put in a job
   object so it can never outlive the window; programs it opens for the user (Explorer, the default app
   of a finished file) break away from the job and stay open. */
static BOOL start_core(int argc, wchar_t **argv, BOOL pipes, HANDLE *process)
{
    wchar_t exe[MAX_PATH];
    swprintf(exe, MAX_PATH, L"%s\\%s", g_baseDir, CORE_EXE);
    if (GetFileAttributesW(exe) == INVALID_FILE_ATTRIBUTES) return FALSE;

    wbuf cmd = {0};
    append_arg(&cmd, exe);
    for (int i = 1; i < argc; i++) { wb_str(&cmd, L" "); append_arg(&cmd, argv[i]); }

    SECURITY_ATTRIBUTES sa = { sizeof sa, NULL, TRUE };
    HANDLE inR = NULL, inW = NULL, outR = NULL, outW = NULL, errW = INVALID_HANDLE_VALUE;
    STARTUPINFOW si = { sizeof si };
    if (pipes) {
        if (!CreatePipe(&inR, &inW, &sa, 0) || !CreatePipe(&outR, &outW, &sa, 0)) { free(cmd.p); return FALSE; }
        SetHandleInformation(inW, HANDLE_FLAG_INHERIT, 0);
        SetHandleInformation(outR, HANDLE_FLAG_INHERIT, 0);
        wchar_t logp[MAX_PATH];
        swprintf(logp, MAX_PATH, L"%s\\logs\\core.log", g_dataDir);
        errW = CreateFileW(logp, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, &sa, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        si.dwFlags = STARTF_USESTDHANDLES;
        si.hStdInput = inR; si.hStdOutput = outW;
        si.hStdError = errW != INVALID_HANDLE_VALUE ? errW : outW;
    }
    PROCESS_INFORMATION pi;
    BOOL ok = CreateProcessW(exe, cmd.p, NULL, NULL, pipes, CREATE_NO_WINDOW | CREATE_SUSPENDED, NULL, g_baseDir, &si, &pi);
    free(cmd.p);
    if (pipes) {
        CloseHandle(inR); CloseHandle(outW);
        if (errW != INVALID_HANDLE_VALUE) CloseHandle(errW);
    }
    if (!ok) {
        if (pipes) { CloseHandle(inW); CloseHandle(outR); }
        return FALSE;
    }
    if (pipes) {
        g_job = CreateJobObjectW(NULL, NULL);
        if (g_job) {
            JOBOBJECT_EXTENDED_LIMIT_INFORMATION li = {0};
            li.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK;
            SetInformationJobObject(g_job, JobObjectExtendedLimitInformation, &li, sizeof li);
            AssignProcessToJobObject(g_job, pi.hProcess);
        }
        g_coreIn = inW; g_coreOut = outR;
    }
    ResumeThread(pi.hThread);
    CloseHandle(pi.hThread);
    *process = pi.hProcess;
    return TRUE;
}

/* ------------------------------------------------------------------ page messages */
static void post_json(const wchar_t *json)
{
    if (g_webview) g_webview->PostWebMessageAsJson(json);
}

static void maybe_ready(void)
{
    if (g_coreReady && g_pageReady && !g_readySent) {
        g_readySent = TRUE;
        post_json(L"{\"ev\":\"ready\"}");      /* files handed over before this point are sent right after */
        if (g_pendingFiles) {
            wbuf e = {0};
            wb_str(&e, L"{\"ev\":\"files\",\"paths\":"); wb_str(&e, g_pendingFiles); wb_str(&e, L"}");
            core_write("E ", e.p);
            free(e.p); free(g_pendingFiles); g_pendingFiles = NULL;
        }
    }
}

static void send_files(const wbuf *pathsJson)
{
    if (!pathsJson->p) return;
    if (!g_readySent) {     /* opened with files before the page is up: deliver once everything is ready */
        free(g_pendingFiles);
        g_pendingFiles = _wcsdup(pathsJson->p);
        return;
    }
    wbuf e = {0};
    wb_str(&e, L"{\"ev\":\"files\",\"paths\":"); wb_str(&e, pathsJson->p); wb_str(&e, L"}");
    core_write("E ", e.p);
    free(e.p);
}

static void bring_to_front(void)
{
    if (IsIconic(g_hwnd)) ShowWindow(g_hwnd, SW_RESTORE);
    else ShowWindow(g_hwnd, SW_SHOW);
    SetForegroundWindow(g_hwnd);
}

/* ------------------------------------------------------------------ dialogs */
/* filters arrive as  name \x1f pattern \x1e name \x1f pattern ...  -> "name\0pattern\0...\0\0" */
static wchar_t *build_filter(const wchar_t *spec)
{
    size_t n = wcslen(spec);
    wchar_t *f = (wchar_t *)calloc(n + 64, sizeof(wchar_t));
    if (!f) return NULL;
    size_t o = 0;
    if (!n) {
        const wchar_t all[] = L"所有檔案\0*.*\0";
        memcpy(f, all, sizeof all);
        return f;
    }
    for (size_t i = 0; i < n; i++) f[o++] = (spec[i] == 0x1f || spec[i] == 0x1e) ? 0 : spec[i];
    f[o++] = 0; f[o] = 0;
    return f;
}

static void dialog_open(wbuf *out, BOOL multi, const wchar_t *filters)
{
    DWORD cap = 1 << 16;
    wchar_t *buf = (wchar_t *)calloc(cap, sizeof(wchar_t));
    wchar_t *filter = build_filter(filters);
    OPENFILENAMEW of = { sizeof of };
    of.hwndOwner = g_hwnd; of.lpstrFile = buf; of.nMaxFile = cap; of.lpstrFilter = filter;
    of.Flags = OFN_EXPLORER | OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR | (multi ? OFN_ALLOWMULTISELECT : 0);
    wb_str(out, L"[");
    if (buf && GetOpenFileNameW(&of)) {
        const wchar_t *dir = buf, *p = buf + wcslen(buf) + 1;
        if (!*p) wb_json(out, dir);                     /* a single file: the buffer holds its full path */
        else {
            BOOL first = TRUE;
            for (; *p; p += wcslen(p) + 1) {
                wchar_t full[MAX_PATH * 2];
                swprintf(full, MAX_PATH * 2, L"%s\\%s", dir, p);
                if (!first) wb_str(out, L",");
                wb_json(out, full); first = FALSE;
            }
        }
    }
    wb_str(out, L"]");
    free(buf); free(filter);
}

static void dialog_save(wbuf *out, const wchar_t *name, const wchar_t *filters)
{
    wchar_t buf[MAX_PATH * 2] = {0};
    wcsncpy(buf, name, MAX_PATH * 2 - 1);
    wchar_t *filter = build_filter(filters);
    OPENFILENAMEW of = { sizeof of };
    of.hwndOwner = g_hwnd; of.lpstrFile = buf; of.nMaxFile = MAX_PATH * 2; of.lpstrFilter = filter;
    of.Flags = OFN_EXPLORER | OFN_OVERWRITEPROMPT | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR;
    wb_str(out, L"[");
    if (GetSaveFileNameW(&of)) wb_json(out, buf);
    wb_str(out, L"]");
    free(filter);
}

static void dialog_folder(wbuf *out)
{
    Microsoft::WRL::ComPtr<IFileOpenDialog> dlg;
    wb_str(out, L"[");
    if (SUCCEEDED(CoCreateInstance(CLSID_FileOpenDialog, nullptr, CLSCTX_INPROC_SERVER, IID_IFileOpenDialog, (void **)dlg.GetAddressOf()))) {
        DWORD opts = 0;
        dlg->GetOptions(&opts);
        dlg->SetOptions(opts | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST);
        if (SUCCEEDED(dlg->Show(g_hwnd))) {
            Microsoft::WRL::ComPtr<IShellItem> item;
            if (SUCCEEDED(dlg->GetResult(item.GetAddressOf()))) {
                PWSTR path = NULL;
                if (SUCCEEDED(item->GetDisplayName(SIGDN_FILESYSPATH, &path))) {
                    wb_json(out, path);
                    CoTaskMemFree(path);
                }
            }
        }
    }
    wb_str(out, L"]");
}

/* ------------------------------------------------------------------ requests from the core */
static void flash_if_background(void)
{
    if (GetForegroundWindow() == g_hwnd) return;
    FLASHWINFO fw = { sizeof fw, g_hwnd, FLASHW_ALL | FLASHW_TIMERNOFG, 0, 0 };
    FlashWindowEx(&fw);
}

static void handle_shell_op(wchar_t *line)
{
    /* line: <id>\t<op>\t<arg1>\t<arg2> */
    wchar_t *field[6] = {0};
    int nf = 0;
    wchar_t *p = line;
    field[nf++] = p;
    while (*p && nf < 6) { if (*p == L'\t') { *p = 0; field[nf++] = p + 1; } p++; }
    const wchar_t *id = field[0], *op = nf > 1 ? field[1] : L"";
    const wchar_t *a1 = nf > 2 ? field[2] : L"", *a2 = nf > 3 ? field[3] : L"";
    wbuf ans = {0};

    if (!wcscmp(op, L"ready")) { g_coreReady = TRUE; maybe_ready(); }
    else if (!wcscmp(op, L"open")) dialog_open(&ans, !wcscmp(a1, L"1"), a2);
    else if (!wcscmp(op, L"folder")) dialog_folder(&ans);
    else if (!wcscmp(op, L"save")) dialog_save(&ans, a1, a2);
    else if (!wcscmp(op, L"title")) SetWindowTextW(g_hwnd, a1);
    else if (!wcscmp(op, L"minimize")) ShowWindow(g_hwnd, SW_MINIMIZE);
    else if (!wcscmp(op, L"restore") || !wcscmp(op, L"front")) bring_to_front();
    else if (!wcscmp(op, L"flash")) flash_if_background();
    else if (!wcscmp(op, L"quit")) { g_closing = TRUE; DestroyWindow(g_hwnd); return; }

    if (wcscmp(id, L"0")) {
        wbuf reply = {0};
        wb_str(&reply, id); wb_str(&reply, L"\t"); wb_str(&reply, ans.p ? ans.p : L"null");
        core_write("A ", reply.p);
        free(reply.p);
    }
    free(ans.p);
}

static void handle_core_line(char *line)
{
    if (line[0] && line[1] == ' ') {
        wchar_t *w = wide_from_utf8(line + 2);
        if (w) {
            if (line[0] == 'R') post_json(w);
            else if (line[0] == 'S') handle_shell_op(w);
            free(w);
        }
    }
    free(line);
}

/* ------------------------------------------------------------------ WebView2 COM handlers (C++)
   The shell's WebView2 callbacks are COM objects.  In C they were static vtbl structs and function
   pointers, because the WebView2 headers only expose that shape in C mode; in C++ they are classes
   that implement the interfaces directly.  They are static objects that live as long as the program,
   so AddRef / Release keep the original no-op behaviour. */
namespace {

template <class TInterface>
class StaticHandler : public TInterface {
public:
    explicit StaticHandler(const IID *own_iid) : own_iid_(own_iid) {}
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void **out) override
    {
        if (!out) return E_POINTER;
        if (IsEqualIID(riid, IID_IUnknown) || IsEqualIID(riid, *own_iid_)) { *out = static_cast<TInterface *>(this); return S_OK; }
        *out = nullptr;
        return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return 1; }
    ULONG STDMETHODCALLTYPE Release() override { return 1; }
private:
    const IID *own_iid_;
};

class EnvHandler final : public StaticHandler<ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler> {
public:
    EnvHandler() : StaticHandler<ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler>(&IID_ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler) {}
    HRESULT STDMETHODCALLTYPE Invoke(HRESULT hr, ICoreWebView2Environment *env) override;
};

class CtrlHandler final : public StaticHandler<ICoreWebView2CreateCoreWebView2ControllerCompletedHandler> {
public:
    CtrlHandler() : StaticHandler<ICoreWebView2CreateCoreWebView2ControllerCompletedHandler>(&IID_ICoreWebView2CreateCoreWebView2ControllerCompletedHandler) {}
    HRESULT STDMETHODCALLTYPE Invoke(HRESULT hr, ICoreWebView2Controller *controller) override;
};

class MsgHandler final : public StaticHandler<ICoreWebView2WebMessageReceivedEventHandler> {
public:
    MsgHandler() : StaticHandler<ICoreWebView2WebMessageReceivedEventHandler>(&IID_ICoreWebView2WebMessageReceivedEventHandler) {}
    HRESULT STDMETHODCALLTYPE Invoke(ICoreWebView2 *sender, ICoreWebView2WebMessageReceivedEventArgs *args) override;
};

class ScriptHandler final : public StaticHandler<ICoreWebView2AddScriptToExecuteOnDocumentCreatedCompletedHandler> {
public:
    ScriptHandler() : StaticHandler<ICoreWebView2AddScriptToExecuteOnDocumentCreatedCompletedHandler>(&IID_ICoreWebView2AddScriptToExecuteOnDocumentCreatedCompletedHandler) {}
    HRESULT STDMETHODCALLTYPE Invoke(HRESULT hr, LPCWSTR id) override;
};

class NavHandler final : public StaticHandler<ICoreWebView2NavigationStartingEventHandler> {
public:
    NavHandler() : StaticHandler<ICoreWebView2NavigationStartingEventHandler>(&IID_ICoreWebView2NavigationStartingEventHandler) {}
    HRESULT STDMETHODCALLTYPE Invoke(ICoreWebView2 *sender, ICoreWebView2NavigationStartingEventArgs *args) override;
};

EnvHandler    g_envHandler;
CtrlHandler   g_ctrlHandler;
MsgHandler    g_msgHandler;
ScriptHandler g_scriptHandler;
NavHandler    g_navHandler;

}   /* namespace */

HRESULT STDMETHODCALLTYPE ScriptHandler::Invoke(HRESULT hr, LPCWSTR id)
{
    (void)hr; (void)id;
    return S_OK;
}

/* Files dropped on the page arrive as ICoreWebView2File objects: the only way to get their real paths. */
static void collect_dropped(ICoreWebView2WebMessageReceivedEventArgs *args)
{
    Microsoft::WRL::ComPtr<ICoreWebView2WebMessageReceivedEventArgs2> args2;
    if (FAILED(args->QueryInterface(IID_ICoreWebView2WebMessageReceivedEventArgs2, (void **)args2.GetAddressOf()))) return;
    Microsoft::WRL::ComPtr<ICoreWebView2ObjectCollectionView> objs;
    wbuf list = {0};
    wb_str(&list, L"[");
    BOOL first = TRUE;
    if (SUCCEEDED(args2->get_AdditionalObjects(objs.GetAddressOf())) && objs) {
        UINT32 count = 0;
        objs->get_Count(&count);
        for (UINT32 i = 0; i < count; i++) {
            Microsoft::WRL::ComPtr<IUnknown> obj;
            if (FAILED(objs->GetValueAtIndex(i, obj.GetAddressOf())) || !obj) continue;
            Microsoft::WRL::ComPtr<ICoreWebView2File> file;
            if (SUCCEEDED(obj->QueryInterface(IID_ICoreWebView2File, (void **)file.GetAddressOf())) && file) {
                LPWSTR path = NULL;
                if (SUCCEEDED(file->get_Path(&path)) && path) {
                    if (!first) wb_str(&list, L",");
                    wb_json(&list, path); first = FALSE;
                    CoTaskMemFree(path);
                }
            }
        }
    }
    wb_str(&list, L"]");
    if (!first) send_files(&list);
    free(list.p);
}

static BOOL trusted_ui_uri(const wchar_t *uri)
{
    if (!uri || _wcsnicmp(uri,L"file:",5)) return FALSE;
    wchar_t path[MAX_PATH * 3], decoded[MAX_PATH]; DWORD length = MAX_PATH * 3;
    if (FAILED(PathCreateFromUrlW(uri,path,&length,0))) return FALSE;
    if (!_wcsicmp(path,g_pagePath)) return TRUE;
    /* WebView2 percent-escapes Unicode as UTF-8; PathCreateFromUrlW unescapes bytes as Latin-1.
       Decode those bytes once. Unescaping the URL twice would corrupt literal %xx filenames. */
    char bytes[MAX_PATH * 3]; size_t n = wcslen(path);
    if (n >= sizeof bytes) return FALSE;
    for (size_t i=0;i<n;i++) { if (path[i]>255) return FALSE; bytes[i]=(char)path[i]; }
    bytes[n]=0;
    return MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,bytes,-1,decoded,MAX_PATH)>0 && !_wcsicmp(decoded,g_pagePath);
}

HRESULT STDMETHODCALLTYPE MsgHandler::Invoke(ICoreWebView2 *sender, ICoreWebView2WebMessageReceivedEventArgs *args)
{
    (void)sender;
    LPWSTR source = NULL;
    BOOL trusted = SUCCEEDED(args->get_Source(&source)) && trusted_ui_uri(source);
    if (source) CoTaskMemFree(source);
    if (!trusted) return S_OK;
    LPWSTR msg = NULL;
    if (FAILED(args->TryGetWebMessageAsString(&msg)) || !msg) return S_OK;
    if (!wcscmp(msg, L"drop")) collect_dropped(args);
    else if (!wcscmp(msg, L"hello")) { g_pageReady = TRUE; g_readySent = FALSE; maybe_ready(); }
    else if (msg[0] == L'{') {        /* {"id":n,"m":"...","a":[...]}: the C engine first, the Python component for the rest */
        char *u = utf8_from_wide(msg, -1);
        jval *test = g_smoke && u ? json_parse(u) : NULL;
        if (test && jget_bool(test, "_swbd_smoke", 0)) {
            jobj_set(test, "completion_notifications", jnum(g_smokeFinishes));
            if (jget_bool(test,"ok",0) && !g_smokeFinishes) { jobj_set(test,"ok",jbool(0)); jobj_set(test,"error",jstr("quick-job completion notification missing")); }
            g_smokeExit = jget_bool(test, "ok", 0) ? 0 : 1;
            char *report = json_dump(test); smoke_write(report); free(report); KillTimer(g_hwnd, 2); request_close();
            json_free(test); free(u); CoTaskMemFree(msg); return S_OK;
        }
        json_free(test);
        if (u && !api_request(u)) core_write_utf8("Q ", u);
        free(u);
    }
    CoTaskMemFree(msg);
    return S_OK;
}

/* Runs in every page before its own scripts: the same window.pywebview.api the page was written for,
   now backed by WebView2 messages to this program and on to the core. */
static const wchar_t *BRIDGE_JS =
    L"(function(){"
    L"const pend=new Map();let seq=0;"
    L"let started=false;const held=[];"
    L"const deliver=d=>{if(!started){held.push(d);return}if(window.onDropped)window.onDropped(d.list,d.paths)};"
    L"const call=(m,a)=>new Promise((res,rej)=>{const id=++seq;pend.set(id,{res,rej});"
    L"window.chrome.webview.postMessage(JSON.stringify({id:id,m:m,a:a}))}).then(r=>{"
    L"if(m==='startup_files'&&!started){started=true;setTimeout(()=>held.splice(0).forEach(deliver),0)}return r});"
    L"const api=new Proxy({},{get:(t,m)=>typeof m==='string'&&m!=='then'?(...a)=>call(m,a):undefined});"
    L"window.pywebview={api:null,platform:'swbd-c'};"
    L"window.chrome.webview.addEventListener('message',e=>{const d=e.data;if(!d)return;"
    L"if(d.id!==undefined){const p=pend.get(d.id);if(!p)return;pend.delete(d.id);"
    L"if(d.ok)p.res(d.r);else p.rej(new Error(d.e||'error'));return}"
    L"if(d.ev==='ready'){if(!window.pywebview.api){window.pywebview.api=api;window.dispatchEvent(new Event('pywebviewready'))}return}"
    L"if(d.ev==='drop')deliver(d)});"
    L"document.addEventListener('drop',e=>{const f=e.dataTransfer&&e.dataTransfer.files;"
    L"if(f&&f.length)window.chrome.webview.postMessageWithAdditionalObjects('drop',f)},true);"
    L"document.addEventListener('DOMContentLoaded',()=>window.chrome.webview.postMessage('hello'));"
    L"})();";

HRESULT STDMETHODCALLTYPE NavHandler::Invoke(ICoreWebView2 *sender, ICoreWebView2NavigationStartingEventArgs *args)
{
    (void)sender; LPWSTR uri = NULL;
    BOOL trusted = SUCCEEDED(args->get_Uri(&uri)) && trusted_ui_uri(uri);
    if (!trusted) args->put_Cancel(TRUE);
    if (uri) CoTaskMemFree(uri); return S_OK;
}
static const wchar_t *SMOKE_JS =
    L"window.addEventListener('pywebviewready',async()=>{let r;try{"
    L"const a=window.pywebview.api;r=await a.init();const f=await a.formats();"
    L"if(!r.version||!f.length)throw Error('initialization or formats missing');"
    L"let rejected=false;try{await a._invalid_smoke_method()}catch(e){rejected=true}"
    L"if(!rejected)throw Error('error reply did not reject');"
    L"const b=window.__swbdSmokeBase;await a.save_settings({finish:'sound',welcomed:true});"
    L"const ids=await a.start([{path:b+'/smoke-fixtures/video.mp4',target:'mp3'},{path:b+'/smoke-fixtures/image.png',target:'jpg'}],{out_dir:b+'/smoke-output',hwaccel:false,preset:'balanced',resource_mode:'quiet'},false);"
    L"if(ids.length!==2||ids[0]===ids[1]||!ids.some(id=>id.startsWith('x'))||!ids.some(id=>!id.startsWith('x')))throw Error('C/Python routing failed');"
    L"let done=false;for(let n=0;n<100;n++){const s=await a.status();const jobs=s.jobs.filter(j=>ids.includes(j.id));if(jobs.length===2&&jobs.every(j=>j.state==='done')){done=true;break}if(jobs.some(j=>j.state==='error'))throw Error(JSON.stringify(jobs));await new Promise(t=>setTimeout(t,150))}"
    L"if(!done)throw Error('mixed job completion timeout');const preview=await a.preview(b+'/smoke-fixtures/video.mp4',.5);if(!preview.src)throw Error('native preview missing');"
    /* 原生 PDF→PDF（qpdf）也要在出貨版本裡成立：工作 id 必須是 C 引擎的（x 開頭）、
       狀態完成、encoder 由 qpdf 負責。任何一項不符就讓整個煙霧測試失敗。
       刻意不新增報告欄位：C 版與 C++ 版的報告要逐欄相同（gate_compare.py 是全結構比對）。 */
    L"const pdfIds=await a.start([{path:b+'/smoke-fixtures/smoke.pdf',target:'pdf'}],{out_dir:b+'/smoke-output',preset:'balanced',resource_mode:'quiet'},false);"
    L"if(pdfIds.length!==1||!pdfIds[0].startsWith('x'))throw Error('pdf job was not taken over by the C engine: '+JSON.stringify(pdfIds));"
    L"let pdfJob=null;for(let n=0;n<100;n++){const s=await a.status();const j=s.jobs.filter(x=>x.id===pdfIds[0])[0];if(j&&j.state==='done'){pdfJob=j;break}if(j&&j.state==='error')throw Error('pdf job failed: '+JSON.stringify(j));await new Promise(t=>setTimeout(t,150))}"
    L"if(!pdfJob)throw Error('pdf job completion timeout');"
    L"if(!(pdfJob.encoder||'').startsWith('qpdf'))throw Error('pdf job did not run natively: '+pdfJob.encoder);"
    /* 「交回 Python」那條路徑也要在出貨版本裡成立：非無損壓縮刻意留在 Python，所以工作 id
       不可以是 C 引擎的（x 開頭），而且轉交之後仍然要跑得出結果。 */
    L"const rIds=await a.run_tool('p_compress',[b+'/smoke-fixtures/smoke.pdf'],{level:'balanced',out_dir:b+'/smoke-output',resource_mode:'quiet'});"
    L"if(!rIds||rIds.length!==1||String(rIds[0]).startsWith('x'))throw Error('relay failed: '+JSON.stringify(rIds));"
    L"let rJob=null;for(let n=0;n<150;n++){const s=await a.status();const j=s.jobs.filter(x=>x.id===rIds[0])[0];if(j&&j.state==='done'){rJob=j;break}if(j&&j.state==='error')throw Error('relay job failed: '+JSON.stringify(j));await new Promise(t=>setTimeout(t,150))}"
    L"if(!rJob)throw Error('relay timeout');"
    L"await new Promise(t=>setTimeout(t,1800));"
    L"window.chrome.webview.postMessage(JSON.stringify({_swbd_smoke:true,ok:true,version:r.version,platform:window.pywebview.platform,formats:f.length,mixed_jobs:ids.length,preview:true,error_rejection:true}));"
    L"}catch(e){window.chrome.webview.postMessage(JSON.stringify({_swbd_smoke:true,ok:false,error:String(e)}))}});";

HRESULT STDMETHODCALLTYPE CtrlHandler::Invoke(HRESULT hr, ICoreWebView2Controller *controller)
{
    if (FAILED(hr) || !controller) {
        fail_box(L"無法建立視窗元件（WebView2）。請重新安裝四維八德，或安裝 Microsoft Edge WebView2 執行環境。");
        DestroyWindow(g_hwnd);
        return S_OK;
    }
    controller->AddRef();
    g_controller = controller;
    controller->get_CoreWebView2(&g_webview);

    Microsoft::WRL::ComPtr<ICoreWebView2Settings> settings;
    if (SUCCEEDED(g_webview->get_Settings(settings.GetAddressOf())) && settings) {
        settings->put_AreDefaultContextMenusEnabled(FALSE);
        settings->put_AreDevToolsEnabled(FALSE);
        settings->put_IsStatusBarEnabled(FALSE);
        settings->put_IsZoomControlEnabled(FALSE);
    }
    RECT rc; GetClientRect(g_hwnd, &rc);
    controller->put_Bounds(rc);

    EventRegistrationToken token;
    swprintf(g_pagePath, MAX_PATH, L"%s\\_internal\\ui\\index.html", g_baseDir);
    g_webview->add_NavigationStarting(&g_navHandler, &token);
    g_webview->add_WebMessageReceived(&g_msgHandler, &token);
    g_webview->AddScriptToExecuteOnDocumentCreated(BRIDGE_JS, &g_scriptHandler);
    if (g_smoke) {
        wbuf test = {0}; wb_str(&test,L"window.__swbdSmokeBase=");wb_json(&test,g_baseDir);wb_str(&test,L";");wb_str(&test,SMOKE_JS);
        g_webview->AddScriptToExecuteOnDocumentCreated(test.p, &g_scriptHandler);free(test.p);
    }

    wchar_t page[MAX_PATH], url[MAX_PATH * 3];
    DWORD n = MAX_PATH * 3;
    swprintf(page, MAX_PATH, L"%s\\_internal\\ui\\index.html", g_baseDir);
    if (FAILED(UrlCreateFromPathW(page, url, &n, 0))) swprintf(url, MAX_PATH * 3, L"file:///%s", page);
    g_webview->Navigate(url);
    controller->MoveFocus(COREWEBVIEW2_MOVE_FOCUS_REASON_PROGRAMMATIC);
    return S_OK;
}

HRESULT STDMETHODCALLTYPE EnvHandler::Invoke(HRESULT hr, ICoreWebView2Environment *env)
{
    if (FAILED(hr) || !env) {
        fail_box(L"無法啟動視窗元件（WebView2）。請重新安裝四維八德。");
        DestroyWindow(g_hwnd);
        return S_OK;
    }
    env->CreateCoreWebView2Controller(g_hwnd, &g_ctrlHandler);
    return S_OK;
}

/* ------------------------------------------------------------------ WebView2 runtime */
static BOOL runtime_present(const wchar_t *folder)
{
    LPWSTR ver = NULL;
    HRESULT hr = GetAvailableCoreWebView2BrowserVersionString(folder, &ver);
    if (ver) CoTaskMemFree(ver);
    return SUCCEEDED(hr) && ver != NULL;
}

/* Installed runtime, else a private Fixed Version copy in tools\webview2, else the bundled offline installer. */
static BOOL ensure_runtime(wchar_t *fixedFolder)
{
    fixedFolder[0] = 0;
    if (runtime_present(NULL)) return TRUE;
    wchar_t fixed[MAX_PATH];
    swprintf(fixed, MAX_PATH, L"%s\\tools\\webview2", g_baseDir);
    if (runtime_present(fixed)) { wcscpy(fixedFolder, fixed); return TRUE; }
    wchar_t setup[MAX_PATH];
    swprintf(setup, MAX_PATH, L"%s\\tools\\WebView2-offline-x64.exe", g_baseDir);
    if (GetFileAttributesW(setup) == INVALID_FILE_ATTRIBUTES) {
        fail_box(L"四維八德的視窗需要 Microsoft Edge WebView2 執行環境，這台電腦目前沒有。\n請使用包含 WebView2 的完整離線安裝程式重新安裝。");
        return FALSE;
    }
    if (MessageBoxW(NULL, L"四維八德的視窗需要 Microsoft Edge WebView2 執行環境（Windows 11 已內建），這台電腦目前沒有。\n\n按「確定」使用隨附的離線安裝程式安裝，完成後會自動開啟四維八德。",
                    APP_TITLE, MB_OKCANCEL | MB_ICONINFORMATION) != IDOK) return FALSE;
    SHELLEXECUTEINFOW se = { sizeof se };
    se.fMask = SEE_MASK_NOCLOSEPROCESS; se.lpFile = setup; se.lpParameters = L"/silent /install"; se.nShow = SW_SHOWNORMAL;
    if (!ShellExecuteExW(&se) || !se.hProcess) return FALSE;
    WaitForSingleObject(se.hProcess, INFINITE);
    CloseHandle(se.hProcess);
    return runtime_present(NULL);
}

/* ------------------------------------------------------------------ host services for api.c */
static void host_send_core(const char *line)
{
    if (!g_coreIn || g_coreGone) return;
    EnterCriticalSection(&g_writeLock);
    DWORD w;
    WriteFile(g_coreIn, line, (DWORD)strlen(line), &w, NULL);
    WriteFile(g_coreIn, "\n", 1, &w, NULL);
    LeaveCriticalSection(&g_writeLock);
}
static void host_post_page(char *json) { if (!PostMessageW(g_hwnd, WM_PAGE_JSON, 0, (LPARAM)json)) free(json); }
static void host_set_title(const char *t) { char *c = _strdup(t); if (c && !PostMessageW(g_hwnd, WM_SET_TITLE, 0, (LPARAM)c)) free(c); }
static void host_flash(void) { PostMessageW(g_hwnd, WM_FLASH, 0, 0); }
static void host_keep_awake(int on) { SetThreadExecutionState(on ? (ES_CONTINUOUS | ES_SYSTEM_REQUIRED) : ES_CONTINUOUS); }

static void run_hidden(const wchar_t *exe, const wchar_t *args)
{
    wchar_t path[MAX_PATH], cmd[1024];
    GetSystemDirectoryW(path, MAX_PATH);
    wcscat(path, L"\\"); wcscat(path, exe);
    swprintf(cmd, 1024, L"\"%s\" %s", path, args);
    STARTUPINFOW si = { sizeof si }; PROCESS_INFORMATION pi;
    if (CreateProcessW(path, cmd, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) { CloseHandle(pi.hThread); CloseHandle(pi.hProcess); }
}
static void host_finish_action(const char *act)
{
    if (g_smoke) { if (!strcmp(act,"sound")) InterlockedIncrement(&g_smokeFinishes); return; }
    if (!strcmp(act, "sound")) MessageBeep(MB_ICONASTERISK);
    else if (!strcmp(act, "shutdown")) { MessageBeep(MB_ICONASTERISK); run_hidden(L"shutdown.exe", L"/s /t 120 /c \"四維八德：工作完成，2 分鐘後關機。要取消請在四維八德按「取消關機」。\""); }
    else if (!strcmp(act, "sleep")) { MessageBeep(MB_ICONASTERISK); SetSuspendState(FALSE, FALSE, FALSE); }
    else if (!strcmp(act, "cancel_shutdown")) run_hidden(L"shutdown.exe", L"/a");
}

/* ------------------------------------------------------------------ window */
static void save_placement(void)
{
    WINDOWPLACEMENT wp = { sizeof wp };
    if (!GetWindowPlacement(g_hwnd, &wp)) return;
    wchar_t v[64];
    RECT r = wp.rcNormalPosition;
    swprintf(v, 64, L"%ld", r.left); WritePrivateProfileStringW(L"window", L"x", v, g_iniPath);
    swprintf(v, 64, L"%ld", r.top); WritePrivateProfileStringW(L"window", L"y", v, g_iniPath);
    swprintf(v, 64, L"%ld", r.right - r.left); WritePrivateProfileStringW(L"window", L"w", v, g_iniPath);
    swprintf(v, 64, L"%ld", r.bottom - r.top); WritePrivateProfileStringW(L"window", L"h", v, g_iniPath);
    WritePrivateProfileStringW(L"window", L"max", wp.showCmd == SW_SHOWMAXIMIZED ? L"1" : L"0", g_iniPath);
}

/* Saved position if it is still on a screen, otherwise centred on the work area (taskbar excluded),
   sized for 1366x768 laptops at 125 % as well as large monitors. */
static void initial_rect(RECT *out, BOOL *maximized)
{
    RECT work;
    SystemParametersInfoW(SPI_GETWORKAREA, 0, &work, 0);
    UINT dpi = GetDpiForSystem();
    int ww = work.right - work.left, wh = work.bottom - work.top;
    int w = min(MulDiv(1240, dpi, 96), ww * 94 / 100), h = min(MulDiv(820, dpi, 96), wh * 94 / 100);
    int x = work.left + (ww - w) / 2, y = work.top + (wh - h) / 2;
    int sw = GetPrivateProfileIntW(L"window", L"w", 0, g_iniPath), sh = GetPrivateProfileIntW(L"window", L"h", 0, g_iniPath);
    int sx = GetPrivateProfileIntW(L"window", L"x", INT_MIN, g_iniPath), sy = GetPrivateProfileIntW(L"window", L"y", INT_MIN, g_iniPath);
    *maximized = GetPrivateProfileIntW(L"window", L"max", 0, g_iniPath) == 1;
    if (sw > 200 && sh > 200 && sx != INT_MIN && sy != INT_MIN) {
        RECT saved = { sx, sy, sx + sw, sy + sh };
        if (MonitorFromRect(&saved, MONITOR_DEFAULTTONULL)) { x = sx; y = sy; w = sw; h = sh; }
    }
    SetRect(out, x, y, x + w, y + h);
}

static void request_close(void)
{
    if (g_closing) return;
    g_closing = TRUE;
    api_close();                                 /* cancel conversions running in the C engine */
    if (g_coreGone || !g_coreIn) { DestroyWindow(g_hwnd); return; }
    core_write("E ", L"{\"ev\":\"close\"}");     /* the core cancels running work and saves settings, then says quit */
    SetTimer(g_hwnd, TIMER_CLOSE, 8000, NULL);
}

static LRESULT CALLBACK wnd_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    switch (msg) {
    case WM_SIZE:
        if (g_controller) { RECT rc; GetClientRect(hwnd, &rc); g_controller->put_Bounds(rc); }
        return 0;
    case WM_MOVE:
        if (g_controller) g_controller->NotifyParentWindowPositionChanged();
        return 0;
    case WM_GETMINMAXINFO: {
        UINT dpi = GetDpiForWindow(hwnd);
        MINMAXINFO *mm = (MINMAXINFO *)lp;
        mm->ptMinTrackSize.x = MulDiv(900, dpi ? dpi : 96, 96);
        mm->ptMinTrackSize.y = MulDiv(560, dpi ? dpi : 96, 96);
        return 0;
    }
    case WM_DPICHANGED: {
        RECT *r = (RECT *)lp;
        SetWindowPos(hwnd, NULL, r->left, r->top, r->right - r->left, r->bottom - r->top, SWP_NOZORDER | SWP_NOACTIVATE);
        return 0;
    }
    case WM_COPYDATA: {       /* a second launch handing over its files */
        COPYDATASTRUCT *cd = (COPYDATASTRUCT *)lp;
        if (cd->dwData == 0x5357 && cd->cbData >= sizeof(wchar_t)) {
            size_t chars = cd->cbData / sizeof(wchar_t);
            wchar_t *json = (wchar_t *)calloc(chars + 1, sizeof(wchar_t));
            if (json) {
                memcpy(json, cd->lpData, chars * sizeof(wchar_t));
                wbuf b = { json, chars, chars + 1 };
                b.len = wcslen(json);
                if (b.len > 2) send_files(&b);
                free(json);
            }
            bring_to_front();
        }
        return TRUE;
    }
    case WM_CORE_LINE:
        handle_core_line((char *)lp);
        return 0;
    case WM_PAGE_JSON: {
        wchar_t *w = wide_from_utf8((char *)lp);
        if (w) { post_json(w); free(w); }
        free((char *)lp);
        return 0;
    }
    case WM_SET_TITLE: {
        wchar_t *w = wide_from_utf8((char *)lp);
        if (w) { SetWindowTextW(hwnd, w); free(w); }
        free((char *)lp);
        return 0;
    }
    case WM_FLASH:
        flash_if_background();
        return 0;
    case WM_CORE_EXIT:
        g_coreGone = TRUE;
        api_core_gone();
        if (!g_closing) {
            log_line("core process ended unexpectedly");
            fail_box(L"四維八德的轉檔元件意外結束，程式將關閉。\n詳細原因記錄在 logs\\core.log。");
        }
        DestroyWindow(hwnd);
        return 0;
    case WM_TIMER:
        if (g_smoke && wp == 2) { KillTimer(hwnd, 2); smoke_write("{\"ok\":false,\"error\":\"native bridge timeout\"}"); request_close(); return 0; }
        if (wp == TIMER_CLOSE) { KillTimer(hwnd, TIMER_CLOSE); DestroyWindow(hwnd); }
        return 0;
    case WM_CLOSE:
        request_close();
        return 0;
    case WM_DESTROY:
        save_placement();
        if (g_controller) { g_controller->Close(); g_controller->Release(); g_controller = NULL; }
        if (g_coreIn) { CloseHandle(g_coreIn); g_coreIn = NULL; }   /* the core sees end of input and exits */
        if (g_coreProcess && WaitForSingleObject(g_coreProcess, 3000) == WAIT_TIMEOUT) TerminateProcess(g_coreProcess, 1);
        PostQuitMessage(g_smoke ? g_smokeExit : 0);
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

/* ------------------------------------------------------------------ entry */
static wbuf files_json(int argc, wchar_t **argv)
{
    wbuf b = {0};
    wb_str(&b, L"[");
    BOOL first = TRUE;
    for (int i = 1; i < argc; i++) {
        if (argv[i][0] == L'-' && argv[i][1] == L'-') continue;
        wchar_t full[MAX_PATH * 2];
        if (!GetFullPathNameW(argv[i], MAX_PATH * 2, full, NULL)) continue;
        if (GetFileAttributesW(full) == INVALID_FILE_ATTRIBUTES) continue;
        if (!first) wb_str(&b, L",");
        wb_json(&b, full); first = FALSE;
    }
    wb_str(&b, L"]");
    if (first) { free(b.p); b.p = NULL; b.len = 0; }
    return b;
}

static BOOL windows_supported(void)
{
    typedef LONG (WINAPI *RtlGetVersionFn)(OSVERSIONINFOW *);
    RtlGetVersionFn fn = (RtlGetVersionFn)(void *)GetProcAddress(GetModuleHandleW(L"ntdll.dll"), "RtlGetVersion");
    OSVERSIONINFOW v = { sizeof v };
    return fn && fn(&v) == 0 && v.dwMajorVersion >= 10;
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR cmdline, int show)
{
    (void)prev; (void)cmdline;
    int argc = 0;
    wchar_t **argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (argc > 2 && !wcscmp(argv[1], L"--shell-smoke-test")) {
        g_smoke = TRUE; wcsncpy(g_smokeReport, argv[2], MAX_PATH * 2 - 1);
    }
    InitializeCriticalSection(&g_writeLock);
    init_dirs();

    if (!windows_supported()) {
        MessageBoxW(NULL, L"這個版本支援 Windows 10／11 64 位元。", APP_TITLE, MB_OK | MB_ICONWARNING);
        return 1;
    }

    /* Self tests run headless in the core: wait for it and pass its exit code on. */
    if (argc > 1 && (!wcscmp(argv[1], L"--selftest") || !wcscmp(argv[1], L"--pdf-selftest"))) {
        HANDLE proc;
        if (!start_core(argc, argv, FALSE, &proc)) { MessageBoxW(NULL, L"找不到轉檔元件 swbd-core.exe。", APP_TITLE, MB_OK | MB_ICONWARNING); return 1; }
        WaitForSingleObject(proc, INFINITE);
        DWORD code = 1; GetExitCodeProcess(proc, &code);
        return (int)code;
    }

    /* One window only: a second launch (Send To, right-click, drag onto the icon) hands its files over. */
    HANDLE mutex = g_smoke ? NULL : CreateMutexW(NULL, TRUE, MUTEX_NAME);
    if (mutex && GetLastError() == ERROR_ALREADY_EXISTS) {
        HWND other = NULL;
        for (int i = 0; i < 50 && !(other = FindWindowW(WINDOW_CLASS, NULL)); i++) Sleep(100);
        if (other) {
            wbuf files = files_json(argc, argv);
            COPYDATASTRUCT cd = { 0x5357, files.p ? (DWORD)((files.len + 1) * sizeof(wchar_t)) : 0, files.p };
            DWORD_PTR result;
            SendMessageTimeoutW(other, WM_COPYDATA, 0, (LPARAM)&cd, SMTO_ABORTIFHUNG, 5000, &result);
            free(files.p);
        }
        return 0;
    }

    CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);
    wchar_t fixedFolder[MAX_PATH];
    if (!ensure_runtime(fixedFolder)) return 1;

    WNDCLASSEXW wc = { sizeof wc };
    wc.lpfnWndProc = wnd_proc; wc.hInstance = inst; wc.lpszClassName = WINDOW_CLASS;
    wc.hIcon = LoadIconW(inst, MAKEINTRESOURCEW(IDI_APPICON));
    wc.hIconSm = wc.hIcon;
    wc.hCursor = LoadCursorW(NULL, IDC_ARROW);
    wc.hbrBackground = CreateSolidBrush(RGB(0xF5, 0xF5, 0xF7));
    RegisterClassExW(&wc);

    RECT r; BOOL maximized;
    initial_rect(&r, &maximized);
    g_hwnd = CreateWindowExW(0, WINDOW_CLASS, APP_TITLE, WS_OVERLAPPEDWINDOW, r.left, r.top, r.right - r.left, r.bottom - r.top, NULL, NULL, inst, NULL);
    if (!g_hwnd) return 1;
    ShowWindow(g_hwnd, g_smoke ? SW_HIDE : maximized ? SW_SHOWMAXIMIZED : show);
    if (g_smoke) SetTimer(g_hwnd, 2, 45000, NULL);
    UpdateWindow(g_hwnd);

    /* The window, the page and the core all start at once: the core loads its libraries while
       WebView2 starts, and the page is told it may call the core once both are up. */
    if (!start_core(argc, argv, TRUE, &g_coreProcess)) {
        fail_box(L"找不到或無法啟動轉檔元件 swbd-core.exe，請重新安裝四維八德。");
        return 1;
    }
    {
        char *base = utf8_from_wide(g_baseDir, -1), *data = utf8_from_wide(g_dataDir, -1);
        api_host host = { host_send_core, host_post_page, host_set_title, host_flash, host_keep_awake, host_finish_action };
        api_init(base, data, &host);        /* the C engine: its workers and the window monitor start here */
        if (swbd_cpp_init(base, data)) {     /* the C++ core answers the methods it has registered */
            api_cpp_busy_probe();            /* let taken-over methods ask whether Python is busy */
            api_cpp_system_facts();          /* and let them read the C engine's system facts */
            api_cpp_py_call();               /* and let them ask Python for settings-derived options */
            api_cpp_tool_submit();           /* and let them submit native tool jobs */
            char note[96];
            snprintf(note, sizeof note, "C++ core ready: %d method(s) taken over", swbd_cpp_method_count());
            log_line(note);
        } else log_line("C++ core unavailable; every method stays in the Python component");
        free(base); free(data);
    }
    CloseHandle(CreateThread(NULL, 0, core_reader, NULL, 0, NULL));

    wchar_t userData[MAX_PATH], local[MAX_PATH];
    if (!GetEnvironmentVariableW(L"LOCALAPPDATA", local, MAX_PATH)) wcscpy(local, g_dataDir);
    if (g_smoke) swprintf(userData, MAX_PATH, L"%s\\webview-test-profile", g_dataDir);
    else swprintf(userData, MAX_PATH, L"%s\\SiWeiBaDe\\WebView2", local);
    HRESULT hr = CreateCoreWebView2EnvironmentWithOptions(fixedFolder[0] ? fixedFolder : NULL, userData, NULL,
                                                          &g_envHandler);
    if (FAILED(hr)) {
        fail_box(L"無法啟動視窗元件（WebView2）。請重新安裝四維八德。");
        return 1;
    }

    MSG m;
    while (GetMessageW(&m, NULL, 0, 0) > 0) {
        TranslateMessage(&m);
        DispatchMessageW(&m);
    }
    if (g_job) CloseHandle(g_job);
    CoUninitialize();
    LocalFree(argv);
    return (int)m.wParam;
}
