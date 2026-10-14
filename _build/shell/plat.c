#define _CRT_SECURE_NO_WARNINGS
#ifndef _WIN32
#define _GNU_SOURCE
#endif
#include "plat.h"
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <ctype.h>

int plat_rmdir(const char *p);

/* ================================================================== common */
char *str_dup(const char *s)
{
    if (!s) s = "";
    size_t n = strlen(s) + 1;
    char *d = (char *)malloc(n);
    if (d) memcpy(d, s, n);
    return d;
}

char *str_fmt(const char *fmt, ...)
{
    va_list ap; va_start(ap, fmt);
    int n = vsnprintf(NULL, 0, fmt, ap);
    va_end(ap);
    if (n < 0) return NULL;
    char *s = (char *)malloc((size_t)n + 1);
    if (!s) return NULL;
    va_start(ap, fmt); vsnprintf(s, (size_t)n + 1, fmt, ap); va_end(ap);
    return s;
}

int str_ends(const char *s, const char *suffix)
{
    size_t a = strlen(s), b = strlen(suffix);
    if (b > a) return 0;
    for (size_t i = 0; i < b; i++) if (tolower((unsigned char)s[a - b + i]) != tolower((unsigned char)suffix[i])) return 0;
    return 1;
}

void str_lower(char *s) { for (; *s; s++) if ((unsigned char)*s < 0x80) *s = (char)tolower((unsigned char)*s); }

char *path_join(const char *a, const char *b)
{
    size_t n = strlen(a);
    if (!n) return str_dup(b);
    if (a[n - 1] == '/' || a[n - 1] == '\\') return str_fmt("%s%s", a, b);
    return str_fmt("%s%c%s", a, PSEP, b);
}

const char *path_base(const char *p)
{
    const char *b = p;
    for (const char *s = p; *s; s++) if (*s == '/' || *s == '\\') b = s + 1;
    return b;
}

char *path_dir(const char *p)
{
    const char *b = path_base(p);
    if (b == p) return str_dup(".");
    size_t n = (size_t)(b - p);
    if (n > 1) n--;                               /* drop the separator, keep "C:\" / "/" roots */
    if (n == 2 && p[1] == ':') n = 3;
    char *d = (char *)malloc(n + 1);
    if (!d) return NULL;
    memcpy(d, p, n); d[n] = 0;
    return d;
}

static int cmp_names(const void *a, const void *b) { return strcmp(*(char *const *)a, *(char *const *)b); }

void free_list(char **list, int n)
{
    for (int i = 0; i < n; i++) free(list[i]);
    free(list);
}

int64_t tree_size(const char *p)
{
    if (is_file(p)) return file_size(p);
    if (!is_dir(p)) return 0;
    char **names; int n = dir_list(p, &names);
    int64_t total = 0;
    for (int i = 0; i < n; i++) { char *c = path_join(p, names[i]); total += tree_size(c); free(c); }
    free_list(names, n);
    return total;
}

int remove_tree(const char *p)
{
    if (is_dir(p)) {
        char **names; int n = dir_list(p, &names);
        for (int i = 0; i < n; i++) { char *c = path_join(p, names[i]); remove_tree(c); free(c); }
        free_list(names, n);
        return plat_rmdir(p);
    }
    return remove_file(p);
}

typedef struct {
    proc *p; char *buf; size_t len;
    plat_mutex *m; plat_cond *c; int done;
} err_sink;

static void err_reader(void *arg)
{
    err_sink *s = (err_sink *)arg;
    char chunk[8192]; long got;
    while ((got = proc_read(s->p, P_ERR, chunk, sizeof chunk)) > 0) {
        if (s->len > (1u << 20)) continue;                 /* keep draining, stop storing */
        char *nb = (char *)realloc(s->buf, s->len + (size_t)got + 1);
        if (!nb) continue;
        s->buf = nb; memcpy(nb + s->len, chunk, (size_t)got); s->len += (size_t)got; nb[s->len] = 0;
    }
    mutex_lock(s->m); s->done = 1; cond_broadcast(s->c); mutex_unlock(s->m);
}

typedef struct { proc *p; plat_mutex *m; plat_cond *c; int finished, exited, timeout; } watchdog;

static void watchdog_main(void *arg)
{
    watchdog *w = (watchdog *)arg;
    double end = now_s() + w->timeout;
    mutex_lock(w->m);
    while (!w->finished) {
        double left = end - now_s();
        if (left <= 0) { proc_kill(w->p); break; }
        cond_wait_ms(w->c, w->m, (int)(left * 1000) + 1);
    }
    w->exited = 1; cond_broadcast(w->c);
    mutex_unlock(w->m);
}

int run_capture(const char *const *argv, const char *cwd, char **out, char **err, int timeout_s, size_t *out_len)
{
    proc *p = proc_start(argv, cwd, P_OUT | P_ERR);
    if (!p) { if (out) *out = str_dup(""); if (err) *err = str_dup("無法啟動程式"); return -1; }
    /* stderr on a helper thread so neither pipe can fill up and block the child */
    err_sink es = { p, (char *)calloc(1, 1), 0, mutex_new(), cond_new(), 0 };
    if (!thread_start(err_reader, &es)) es.done = 1;
    watchdog wd = { p, es.m, es.c, 0, 1, timeout_s };
    if (timeout_s > 0 && thread_start(watchdog_main, &wd)) wd.exited = 0;
    size_t cap = 1 << 16, len = 0;
    char *o = (char *)malloc(cap);
    char chunk[8192]; long got;
    while ((got = proc_read(p, P_OUT, chunk, sizeof chunk)) > 0) {
        if (len + (size_t)got + 1 > cap && cap < (64u << 20)) { cap *= 2; char *nb = (char *)realloc(o, cap); if (nb) o = nb; else cap /= 2; }
        if (len + (size_t)got + 1 <= cap) { memcpy(o + len, chunk, (size_t)got); len += (size_t)got; }
    }
    o[len] = 0;
    if (out_len) *out_len = len;
    mutex_lock(es.m);
    while (!es.done) cond_wait_ms(es.c, es.m, -1);
    mutex_unlock(es.m);
    int rc = proc_wait(p);
    mutex_lock(es.m);
    wd.finished = 1; cond_broadcast(es.c);
    while (!wd.exited) cond_wait_ms(es.c, es.m, -1);
    mutex_unlock(es.m);
    proc_free(p);
    if (out) *out = o; else free(o);
    if (err) *err = es.buf; else free(es.buf);
    free(es.m); free(es.c);
    return rc;
}


char *read_file(const char *path, size_t *len)
{
#ifdef _WIN32
    wchar_t *w; { int n = MultiByteToWideChar(CP_UTF8, 0, path, -1, NULL, 0); w = (wchar_t *)malloc(sizeof(wchar_t) * (size_t)n); MultiByteToWideChar(CP_UTF8, 0, path, -1, w, n); }
    FILE *f = _wfopen(w, L"rb"); free(w);
#else
    FILE *f = fopen(path, "rb");
#endif
    if (!f) return NULL;
    size_t cap = 1 << 16, n = 0, got;
    char *b = (char *)malloc(cap);
    while (b && (got = fread(b + n, 1, cap - n - 1, f)) > 0) {
        n += got;
        if (n + 1 >= cap) { cap *= 2; char *nb = (char *)realloc(b, cap); if (!nb) { free(b); b = NULL; break; } b = nb; }
    }
    fclose(f);
    if (b) b[n] = 0;
    if (len) *len = n;
    return b;
}

int write_file(const char *path, const char *data, size_t len)
{
#ifdef _WIN32
    wchar_t *w; { int n = MultiByteToWideChar(CP_UTF8, 0, path, -1, NULL, 0); w = (wchar_t *)malloc(sizeof(wchar_t) * (size_t)n); MultiByteToWideChar(CP_UTF8, 0, path, -1, w, n); }
    FILE *f = _wfopen(w, L"wb"); free(w);
#else
    FILE *f = fopen(path, "wb");
#endif
    if (!f) return 0;
    size_t put = fwrite(data, 1, len, f);
    return !fclose(f) && put == len;
}

int append_file(const char *path, const char *data, size_t len)
{
#ifdef _WIN32
    wchar_t *w; { int n = MultiByteToWideChar(CP_UTF8, 0, path, -1, NULL, 0); w = (wchar_t *)malloc(sizeof(wchar_t) * (size_t)n); MultiByteToWideChar(CP_UTF8, 0, path, -1, w, n); }
    FILE *f = _wfopen(w, L"ab"); free(w);
#else
    FILE *f = fopen(path, "ab");
#endif
    if (!f) return 0;
    size_t put = fwrite(data, 1, len, f);
    return !fclose(f) && put == len;
}

static int valid_utf8(const unsigned char *s, size_t n)
{
    for (size_t i = 0; i < n;) {
        unsigned char c = s[i];
        size_t k = c < 0x80 ? 0 : (c >> 5) == 6 ? 1 : (c >> 4) == 14 ? 2 : (c >> 3) == 30 ? 3 : 9;
        if (k == 9 || i + k >= n + (k ? 0 : 1)) { if (k == 9) return 0; }
        if (i + k >= n && k) return 0;
        for (size_t j = 1; j <= k; j++) if ((s[i + j] & 0xC0) != 0x80) return 0;
        i += k + 1;
    }
    return 1;
}

#ifdef _WIN32
/* ================================================================== Windows */
#include <shlwapi.h>

static wchar_t *W(const char *s)
{
    int n = MultiByteToWideChar(CP_UTF8, 0, s, -1, NULL, 0);
    wchar_t *w = (wchar_t *)malloc(sizeof(wchar_t) * (size_t)(n ? n : 1));
    if (!w) return NULL;
    if (n) MultiByteToWideChar(CP_UTF8, 0, s, -1, w, n); else w[0] = 0;
    return w;
}
static char *U(const wchar_t *w)
{
    int n = WideCharToMultiByte(CP_UTF8, 0, w, -1, NULL, 0, NULL, NULL);
    char *s = (char *)malloc((size_t)(n ? n : 1));
    if (!s) return NULL;
    if (n) WideCharToMultiByte(CP_UTF8, 0, w, -1, s, n, NULL, NULL); else s[0] = 0;
    return s;
}

struct plat_mutex { CRITICAL_SECTION cs; };
struct plat_cond { CONDITION_VARIABLE cv; };
plat_mutex *mutex_new(void) { plat_mutex *m = (plat_mutex *)malloc(sizeof *m); InitializeCriticalSection(&m->cs); return m; }
void mutex_lock(plat_mutex *m) { EnterCriticalSection(&m->cs); }
void mutex_unlock(plat_mutex *m) { LeaveCriticalSection(&m->cs); }
plat_cond *cond_new(void) { plat_cond *c = (plat_cond *)malloc(sizeof *c); InitializeConditionVariable(&c->cv); return c; }
int cond_wait_ms(plat_cond *c, plat_mutex *m, int ms)
{
    return SleepConditionVariableCS(&c->cv, &m->cs, ms < 0 ? INFINITE : (DWORD)ms) ? 0 : 1;
}
void cond_broadcast(plat_cond *c) { WakeAllConditionVariable(&c->cv); }

typedef struct { void (*fn)(void *); void *arg; } tstart;
static DWORD WINAPI thread_main(LPVOID p) { tstart t = *(tstart *)p; free(p); t.fn(t.arg); return 0; }
int thread_start(void (*fn)(void *), void *arg)
{
    tstart *t = (tstart *)malloc(sizeof *t);
    if (!t) return 0;
    t->fn = fn; t->arg = arg;
    HANDLE h = CreateThread(NULL, 0, thread_main, t, 0, NULL);
    if (!h) { free(t); return 0; }
    CloseHandle(h);
    return 1;
}
void sleep_ms(int ms) { Sleep((DWORD)ms); }
double now_s(void)
{
    FILETIME ft; GetSystemTimeAsFileTime(&ft);
    ULARGE_INTEGER u; u.LowPart = ft.dwLowDateTime; u.HighPart = ft.dwHighDateTime;
    return (double)(u.QuadPart - 116444736000000000ULL) / 1e7;
}

struct proc { HANDLE process, job, out, err; };

static void quote_arg(wchar_t **cmd, size_t *len, size_t *cap, const wchar_t *a)
{
    size_t need = wcslen(a) * 2 + 4;
    if (*len + need + 2 > *cap) { while (*len + need + 2 > *cap) *cap *= 2; *cmd = (wchar_t *)realloc(*cmd, *cap * sizeof(wchar_t)); }
    wchar_t *o = *cmd + *len;
    if (*len) *o++ = L' ';
    if (*a && !wcspbrk(a, L" \t\"")) { wcscpy(o, a); o += wcslen(a); }
    else {
        *o++ = L'"';
        for (const wchar_t *p = a;; p++) {
            unsigned slashes = 0;
            while (*p == L'\\') { p++; slashes++; }
            if (!*p) { for (unsigned i = 0; i < slashes * 2; i++) *o++ = L'\\'; break; }
            if (*p == L'"') { for (unsigned i = 0; i < slashes * 2 + 1; i++) *o++ = L'\\'; }
            else { for (unsigned i = 0; i < slashes; i++) *o++ = L'\\'; }
            *o++ = *p;
        }
        *o++ = L'"';
    }
    *o = 0;
    *len = (size_t)(o - *cmd);
}

proc *proc_start(const char *const *argv, const char *cwd, int pipes)
{
    size_t cap = 1024, len = 0;
    wchar_t *cmd = (wchar_t *)malloc(cap * sizeof(wchar_t));
    cmd[0] = 0;
    for (int i = 0; argv[i]; i++) { wchar_t *a = W(argv[i]); quote_arg(&cmd, &len, &cap, a); free(a); }
    SECURITY_ATTRIBUTES sa = { sizeof sa, NULL, TRUE };
    HANDLE outR = NULL, outW = NULL, errR = NULL, errW = NULL;
    HANDLE nul = CreateFileW(L"NUL", GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, &sa, OPEN_EXISTING, 0, NULL);
    if (pipes & P_OUT) { CreatePipe(&outR, &outW, &sa, 1 << 16); SetHandleInformation(outR, HANDLE_FLAG_INHERIT, 0); }
    if ((pipes & P_ERR) && !(pipes & P_MERGE)) { CreatePipe(&errR, &errW, &sa, 1 << 16); SetHandleInformation(errR, HANDLE_FLAG_INHERIT, 0); }
    STARTUPINFOW si = { sizeof si };
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdInput = nul;
    si.hStdOutput = outW ? outW : nul;
    si.hStdError = (pipes & P_MERGE) && outW ? outW : errW ? errW : nul;
    PROCESS_INFORMATION pi;
    wchar_t *wcwd = cwd ? W(cwd) : NULL;
    wchar_t *exe = W(argv[0]);
    BOOL ok = CreateProcessW(exe, cmd, NULL, NULL, TRUE, CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS | CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT,
                             NULL, wcwd, &si, &pi);
    if (!ok) ok = CreateProcessW(NULL, cmd, NULL, NULL, TRUE, CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS | CREATE_SUSPENDED, NULL, wcwd, &si, &pi);
    free(cmd); free(wcwd); free(exe);
    if (outW) CloseHandle(outW);
    if (errW) CloseHandle(errW);
    CloseHandle(nul);
    if (!ok) { if (outR) CloseHandle(outR); if (errR) CloseHandle(errR); return NULL; }
    proc *p = (proc *)calloc(1, sizeof *p);
    p->process = pi.hProcess; p->out = outR; p->err = errR;
    /* each child gets its own job object, so cancelling kills everything it started (LibreOffice, Calibre) */
    p->job = CreateJobObjectW(NULL, NULL);
    if (p->job) {
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = {0};
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        SetInformationJobObject(p->job, JobObjectExtendedLimitInformation, &limits, sizeof limits);
        AssignProcessToJobObject(p->job, pi.hProcess);
    }
    ResumeThread(pi.hThread);
    CloseHandle(pi.hThread);
    return p;
}
long proc_read(proc *p, int stream, char *buf, size_t n)
{
    HANDLE h = stream == P_ERR ? p->err : p->out;
    DWORD got = 0;
    if (!h || !ReadFile(h, buf, (DWORD)n, &got, NULL)) return 0;
    return (long)got;
}
int proc_wait(proc *p)
{
    WaitForSingleObject(p->process, INFINITE);
    DWORD code = 1; GetExitCodeProcess(p->process, &code);
    return (int)code;
}
void proc_kill(proc *p)
{
    if (p->job) TerminateJobObject(p->job, 1);
    else TerminateProcess(p->process, 1);
}
void proc_free(proc *p)
{
    if (!p) return;
    if (p->out) CloseHandle(p->out);
    if (p->err) CloseHandle(p->err);
    if (p->job) CloseHandle(p->job);
    CloseHandle(p->process);
    free(p);
}

static int attrs(const char *p, DWORD *a)
{
    wchar_t *w = W(p);
    *a = GetFileAttributesW(w);
    free(w);
    return *a != INVALID_FILE_ATTRIBUTES;
}
int is_file(const char *p) { DWORD a; return attrs(p, &a) && !(a & FILE_ATTRIBUTE_DIRECTORY); }
int is_dir(const char *p) { DWORD a; return attrs(p, &a) && (a & FILE_ATTRIBUTE_DIRECTORY); }
int path_exists(const char *p) { DWORD a; return attrs(p, &a); }
int64_t file_size(const char *p)
{
    WIN32_FILE_ATTRIBUTE_DATA d; wchar_t *w = W(p);
    BOOL ok = GetFileAttributesExW(w, GetFileExInfoStandard, &d); free(w);
    return ok ? ((int64_t)d.nFileSizeHigh << 32) | d.nFileSizeLow : -1;
}
double file_mtime(const char *p)
{
    WIN32_FILE_ATTRIBUTE_DATA d; wchar_t *w = W(p);
    BOOL ok = GetFileAttributesExW(w, GetFileExInfoStandard, &d); free(w);
    if (!ok) return 0;
    ULARGE_INTEGER u; u.LowPart = d.ftLastWriteTime.dwLowDateTime; u.HighPart = d.ftLastWriteTime.dwHighDateTime;
    return (double)(u.QuadPart - 116444736000000000ULL) / 1e7;
}
int make_dirs(const char *p)
{
    if (is_dir(p)) return 1;
    char *parent = path_dir(p);
    if (parent && strcmp(parent, p) && strcmp(parent, ".")) make_dirs(parent);
    free(parent);
    wchar_t *w = W(p); BOOL ok = CreateDirectoryW(w, NULL) || GetLastError() == ERROR_ALREADY_EXISTS; free(w);
    return ok;
}
int remove_file(const char *p) { wchar_t *w = W(p); BOOL ok = DeleteFileW(w); free(w); return ok; }
int plat_rmdir(const char *p) { wchar_t *w = W(p); BOOL ok = RemoveDirectoryW(w); free(w); return ok; }
int copy_file(const char *s, const char *d) { wchar_t *a = W(s), *b = W(d); BOOL ok = CopyFileW(a, b, FALSE); free(a); free(b); return ok; }
int move_file(const char *s, const char *d)
{
    wchar_t *a = W(s), *b = W(d);
    BOOL ok = MoveFileExW(a, b, MOVEFILE_REPLACE_EXISTING | MOVEFILE_COPY_ALLOWED);
    free(a); free(b); return ok;
}
int64_t disk_free(const char *dir)
{
    ULARGE_INTEGER freeb; wchar_t *w = W(dir);
    BOOL ok = GetDiskFreeSpaceExW(w, &freeb, NULL, NULL); free(w);
    return ok ? (int64_t)freeb.QuadPart : -1;
}
char *make_temp_dir(const char *prefix)
{
    wchar_t tmp[MAX_PATH]; GetTempPathW(MAX_PATH, tmp);
    char *base = U(tmp);
    for (int i = 0; i < 100; i++) {
        char *p = str_fmt("%s%s%08lx", base, prefix, (unsigned long)(GetTickCount() ^ (GetCurrentThreadId() << 8) ^ (DWORD)i * 2654435761u));
        wchar_t *w = W(p);
        BOOL ok = CreateDirectoryW(w, NULL); free(w);
        if (ok) { free(base); return p; }
        free(p);
    }
    free(base);
    return NULL;
}
int dir_list(const char *dir, char ***names)
{
    char *pat = path_join(dir, "*");
    wchar_t *w = W(pat); free(pat);
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW(w, &fd); free(w);
    int n = 0, cap = 16;
    *names = (char **)malloc(sizeof(char *) * (size_t)cap);
    if (h == INVALID_HANDLE_VALUE) return 0;
    do {
        if (!wcscmp(fd.cFileName, L".") || !wcscmp(fd.cFileName, L"..")) continue;
        if (n == cap) { cap *= 2; *names = (char **)realloc(*names, sizeof(char *) * (size_t)cap); }
        (*names)[n++] = U(fd.cFileName);
    } while (FindNextFileW(h, &fd));
    FindClose(h);
    qsort(*names, (size_t)n, sizeof(char *), cmp_names);
    return n;
}
char *path_abs(const char *p)
{
    wchar_t *w = W(p), out[32768];
    DWORD n = GetFullPathNameW(w, 32768, out, NULL); free(w);
    return n ? U(out) : str_dup(p);
}
int path_same(const char *a, const char *b)
{
    wchar_t *x = W(a), *y = W(b);
    int same = CompareStringOrdinal(x, -1, y, -1, TRUE) == CSTR_EQUAL;
    free(x); free(y);
    return same;
}
char *exe_dir(void)
{
    wchar_t w[MAX_PATH]; GetModuleFileNameW(NULL, w, MAX_PATH);
    char *s = U(w), *d = path_dir(s); free(s);
    return d;
}
int cpu_count(void) { SYSTEM_INFO si; GetSystemInfo(&si); return (int)si.dwNumberOfProcessors; }
double mem_gb(void)
{
    MEMORYSTATUSEX m = { sizeof m };
    return GlobalMemoryStatusEx(&m) ? (double)m.ullTotalPhys / 1073741824.0 : 8.0;
}
char *env_get(const char *name)
{
    wchar_t *w = W(name), buf[32768];
    DWORD n = GetEnvironmentVariableW(w, buf, 32768); free(w);
    return n && n < 32768 ? U(buf) : NULL;
}


char *text_to_utf8(const char *data, size_t n)
{
    const unsigned char *u = (const unsigned char *)data;
    if (n >= 3 && u[0] == 0xEF && u[1] == 0xBB && u[2] == 0xBF) { data += 3; n -= 3; u += 3; }
    else if (n >= 2 && ((u[0] == 0xFF && u[1] == 0xFE) || (u[0] == 0xFE && u[1] == 0xFF))) {
        size_t chars = (n - 2) / 2;
        wchar_t *w = (wchar_t *)malloc(sizeof(wchar_t) * (chars + 1));
        for (size_t i = 0; i < chars; i++) w[i] = u[0] == 0xFF ? (wchar_t)(u[2 + 2 * i] | u[3 + 2 * i] << 8) : (wchar_t)(u[3 + 2 * i] | u[2 + 2 * i] << 8);
        w[chars] = 0;
        char *s = U(w); free(w); return s;
    }
    if (valid_utf8(u, n)) { char *s = (char *)malloc(n + 1); memcpy(s, data, n); s[n] = 0; return s; }
    static const UINT pages[] = { 950, 54936, 1252 };      /* Big5 (Traditional Chinese), GB18030, Western */
    for (int i = 0; i < 3; i++) {
        int len = MultiByteToWideChar(pages[i], MB_ERR_INVALID_CHARS, data, (int)n, NULL, 0);
        if (len <= 0) continue;
        wchar_t *w = (wchar_t *)malloc(sizeof(wchar_t) * ((size_t)len + 1));
        MultiByteToWideChar(pages[i], 0, data, (int)n, w, len); w[len] = 0;
        char *s = U(w); free(w); return s;
    }
    char *s = (char *)malloc(n + 1); memcpy(s, data, n); s[n] = 0; return s;
}

#else
/* ================================================================== POSIX (tests) */
#include <pthread.h>
#include <unistd.h>
#include <signal.h>
#include <fcntl.h>
#include <dirent.h>
#include <errno.h>
#include <time.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/statvfs.h>
#include <sys/time.h>
#include <sys/resource.h>

struct plat_mutex { pthread_mutex_t m; };
struct plat_cond { pthread_cond_t c; };
plat_mutex *mutex_new(void)
{
    plat_mutex *m = (plat_mutex *)malloc(sizeof *m);
    pthread_mutexattr_t a; pthread_mutexattr_init(&a); pthread_mutexattr_settype(&a, PTHREAD_MUTEX_RECURSIVE);
    pthread_mutex_init(&m->m, &a);
    return m;
}
void mutex_lock(plat_mutex *m) { pthread_mutex_lock(&m->m); }
void mutex_unlock(plat_mutex *m) { pthread_mutex_unlock(&m->m); }
plat_cond *cond_new(void) { plat_cond *c = (plat_cond *)malloc(sizeof *c); pthread_cond_init(&c->c, NULL); return c; }
int cond_wait_ms(plat_cond *c, plat_mutex *m, int ms)
{
    if (ms < 0) { pthread_cond_wait(&c->c, &m->m); return 0; }
    struct timespec ts; clock_gettime(CLOCK_REALTIME, &ts);
    ts.tv_sec += ms / 1000; ts.tv_nsec += (long)(ms % 1000) * 1000000L;
    if (ts.tv_nsec >= 1000000000L) { ts.tv_sec++; ts.tv_nsec -= 1000000000L; }
    return pthread_cond_timedwait(&c->c, &m->m, &ts) == ETIMEDOUT;
}
void cond_broadcast(plat_cond *c) { pthread_cond_broadcast(&c->c); }
typedef struct { void (*fn)(void *); void *arg; } tstart;
static void *thread_main(void *p) { tstart t = *(tstart *)p; free(p); t.fn(t.arg); return NULL; }
int thread_start(void (*fn)(void *), void *arg)
{
    tstart *t = (tstart *)malloc(sizeof *t);
    t->fn = fn; t->arg = arg;
    pthread_t th;
    if (pthread_create(&th, NULL, thread_main, t)) { free(t); return 0; }
    pthread_detach(th);
    return 1;
}
void sleep_ms(int ms) { usleep((useconds_t)ms * 1000); }
double now_s(void) { struct timeval tv; gettimeofday(&tv, NULL); return (double)tv.tv_sec + tv.tv_usec / 1e6; }

struct proc { pid_t pid; int out, err, status, waited; };
proc *proc_start(const char *const *argv, const char *cwd, int pipes)
{
    int o[2] = {-1, -1}, e[2] = {-1, -1};
    if ((pipes & P_OUT) && pipe(o)) return NULL;
    if ((pipes & P_ERR) && !(pipes & P_MERGE) && pipe(e)) return NULL;
    pid_t pid = fork();
    if (pid < 0) return NULL;
    if (!pid) {
        setpgid(0, 0);
        int nul = open("/dev/null", O_RDWR);
        dup2(nul, 0);
        dup2(o[1] >= 0 ? o[1] : nul, 1);
        dup2((pipes & P_MERGE) && o[1] >= 0 ? o[1] : e[1] >= 0 ? e[1] : nul, 2);
        if (cwd && chdir(cwd)) _exit(127);
        setpriority(PRIO_PROCESS, 0, 5);
        execvp(argv[0], (char *const *)argv);
        _exit(127);
    }
    setpgid(pid, pid);
    if (o[1] >= 0) close(o[1]);
    if (e[1] >= 0) close(e[1]);
    proc *p = (proc *)calloc(1, sizeof *p);
    p->pid = pid; p->out = o[0]; p->err = e[0];
    return p;
}
long proc_read(proc *p, int stream, char *buf, size_t n)
{
    int fd = stream == P_ERR ? p->err : p->out;
    if (fd < 0) return 0;
    for (;;) { ssize_t r = read(fd, buf, n); if (r < 0 && errno == EINTR) continue; return r < 0 ? 0 : (long)r; }
}
int proc_wait(proc *p)
{
    if (!p->waited) { waitpid(p->pid, &p->status, 0); p->waited = 1; }
    return WIFEXITED(p->status) ? WEXITSTATUS(p->status) : 1;
}
void proc_kill(proc *p) { kill(-p->pid, SIGKILL); }
void proc_free(proc *p)
{
    if (!p) return;
    if (p->out >= 0) close(p->out);
    if (p->err >= 0) close(p->err);
    if (!p->waited) waitpid(p->pid, &p->status, 0);
    free(p);
}
int is_file(const char *p) { struct stat s; return !stat(p, &s) && S_ISREG(s.st_mode); }
int is_dir(const char *p) { struct stat s; return !stat(p, &s) && S_ISDIR(s.st_mode); }
int path_exists(const char *p) { struct stat s; return !stat(p, &s); }
int64_t file_size(const char *p) { struct stat s; return stat(p, &s) ? -1 : (int64_t)s.st_size; }
double file_mtime(const char *p) { struct stat s; return stat(p, &s) ? 0 : (double)s.st_mtim.tv_sec + s.st_mtim.tv_nsec / 1e9; }
int make_dirs(const char *p)
{
    if (is_dir(p)) return 1;
    char *parent = path_dir(p);
    if (parent && strcmp(parent, p) && strcmp(parent, ".")) make_dirs(parent);
    free(parent);
    return !mkdir(p, 0777) || errno == EEXIST;
}
int remove_file(const char *p) { return !unlink(p); }
int plat_rmdir(const char *p) { return !rmdir(p); }
int copy_file(const char *s, const char *d)
{
    FILE *a = fopen(s, "rb"), *b = a ? fopen(d, "wb") : NULL;
    if (!a || !b) { if (a) fclose(a); return 0; }
    char buf[1 << 16]; size_t n;
    while ((n = fread(buf, 1, sizeof buf, a)) > 0) fwrite(buf, 1, n, b);
    fclose(a);
    return !fclose(b);
}
int move_file(const char *s, const char *d) { if (!rename(s, d)) return 1; return copy_file(s, d) && remove_file(s); }
int64_t disk_free(const char *dir) { struct statvfs v; return statvfs(dir, &v) ? -1 : (int64_t)v.f_bavail * (int64_t)v.f_frsize; }
char *make_temp_dir(const char *prefix)
{
    const char *t = getenv("TMPDIR");
    char *tmpl = str_fmt("%s/%sXXXXXX", t ? t : "/tmp", prefix);
    if (!mkdtemp(tmpl)) { free(tmpl); return NULL; }
    return tmpl;
}
int dir_list(const char *dir, char ***names)
{
    int n = 0, cap = 16;
    *names = (char **)malloc(sizeof(char *) * (size_t)cap);
    DIR *d = opendir(dir);
    if (!d) return 0;
    struct dirent *e;
    while ((e = readdir(d))) {
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..")) continue;
        if (n == cap) { cap *= 2; *names = (char **)realloc(*names, sizeof(char *) * (size_t)cap); }
        (*names)[n++] = str_dup(e->d_name);
    }
    closedir(d);
    qsort(*names, (size_t)n, sizeof(char *), cmp_names);
    return n;
}
char *path_abs(const char *p)
{
    if (p[0] == '/') return str_dup(p);
    char cwd[4096];
    if (!getcwd(cwd, sizeof cwd)) return str_dup(p);
    return path_join(cwd, p);
}
int path_same(const char *a, const char *b) { return !strcmp(a, b); }
char *exe_dir(void)
{
    char buf[4096]; ssize_t n = readlink("/proc/self/exe", buf, sizeof buf - 1);
    if (n <= 0) return str_dup(".");
    buf[n] = 0;
    return path_dir(buf);
}
int cpu_count(void) { long n = sysconf(_SC_NPROCESSORS_ONLN); return n > 0 ? (int)n : 2; }
double mem_gb(void) { return (double)sysconf(_SC_PAGESIZE) * (double)sysconf(_SC_PHYS_PAGES) / 1073741824.0; }
char *env_get(const char *name) { const char *v = getenv(name); return v ? str_dup(v) : NULL; }

#include <iconv.h>
char *text_to_utf8(const char *data, size_t n)
{
    const unsigned char *u = (const unsigned char *)data;
    const char *from = NULL;
    if (n >= 3 && u[0] == 0xEF && u[1] == 0xBB && u[2] == 0xBF) { data += 3; n -= 3; u += 3; }
    else if (n >= 2 && u[0] == 0xFF && u[1] == 0xFE) from = "UTF-16LE", data += 2, n -= 2;
    else if (n >= 2 && u[0] == 0xFE && u[1] == 0xFF) from = "UTF-16BE", data += 2, n -= 2;
    if (!from && valid_utf8((const unsigned char *)data, n)) { char *s = (char *)malloc(n + 1); memcpy(s, data, n); s[n] = 0; return s; }
    const char *tries[] = { from, "BIG5-HKSCS", "GB18030", "CP1252" };
    for (int i = from ? 0 : 1; i < 4; i++) {
        iconv_t cd = iconv_open("UTF-8", tries[i]);
        if (cd == (iconv_t)-1) continue;
        size_t cap = n * 4 + 16, inl = n, outl = cap;
        char *out = (char *)malloc(cap + 1), *in = (char *)data, *o = out;
        size_t r = iconv(cd, &in, &inl, &o, &outl);
        iconv_close(cd);
        if (r != (size_t)-1 && !inl) { *o = 0; return out; }
        free(out);
        if (from) break;
    }
    char *s = (char *)malloc(n + 1); memcpy(s, data, n); s[n] = 0; return s;
}

#endif
