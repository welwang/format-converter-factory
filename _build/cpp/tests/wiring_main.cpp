/*
 * 整合閘門：直接驅動 shell 的 api.cpp 路由，證明兩件事 ——
 *   1. C++ 核心已接手的方法（cleanup_scan）由 C++ 回答，而且**不會**把請求送給 Python；
 *   2. 未接手的方法仍然交回 Python（降級路徑安全）。
 * 這是「C++ 架構真的接上線」的證據，而不只是「C++ 能編譯」。
 */
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <string>

#include "api.h"
#include "swbd/bridge.hpp"

static int python_cleanup_calls = 0;
static char last_reply[16384];
static int replies = 0;

static void send_core(const char *line)
{
    if (strstr(line, "cleanup_scan")) python_cleanup_calls++;
    /* 這個探針沒有真的 Python 核心。C 引擎的 status 會問 Python 的 status 來合併，
       沒有回應就會永遠等下去，所以在這裡合成一個「Python 沒有任何工作」的回覆。
       正式外殼的同一條路徑會把請求送給真正的 Python 元件。 */
    /* 探針沒有真的 Python 核心，但可以替 tool_job_opt 合成一個回覆：這樣 C++ 接手的方法
       就會走過橋接層的「反向呼叫 Python」路徑（含回覆信封的拆解），同時覆蓋
       1 MB 回覆緩衝的配置與傳遞路徑。 */
    if (strstr(line, "\"m\":\"tool_job_opt\"")) {
        char name[64] = "c0";
        const char *id = strstr(line, "\"id\":\"");
        if (id) {
            id += 6;
            size_t i = 0;
            while (id[i] && id[i] != '"' && i + 1 < sizeof name) { name[i] = id[i]; i++; }
            name[i] = 0;
        }
        /* 與 Python 的 tool_job_opt 一樣：預設選項再讓 params 覆蓋（params 在 a[1]）。
           替身不能只回固定值，否則 pages／out_dir 這類參數會不見。 */
        jval *req = json_parse(line + 2);
        const jval *arr = req ? jget(req, "a") : nullptr;
        const jval *prm = (arr && arr->type == J_ARR && arr->len > 1) ? arr->items[1] : nullptr;
        jval *opt = jnew(J_OBJ);
        jobj_set(opt, "preset", jstr("balanced"));
        jobj_set(opt, "hwaccel", jbool(0));
        jobj_set(opt, "fastcopy", jbool(1));
        jobj_set(opt, "out_dir", jstr(""));
        jobj_set(opt, "codec", jstr("auto"));
        jobj_set(opt, "verify_full", jbool(0));
        jobj_set(opt, "resource_mode", jstr("quiet"));
        if (prm && prm->type == J_OBJ) {
            for (size_t k = 0; k < prm->len; k++) {
                if (prm->keys && prm->keys[k]) jobj_set(opt, prm->keys[k], json_clone(prm->items[k]));
            }
        }
        char *body = json_dump(opt);
        static char reply[4096];
        snprintf(reply, sizeof reply, "R {\"id\": \"%s\",\"ok\":true,\"r\":%s}", name, body ? body : "{}");
        if (body) free(body);
        if (req) json_free(req);
        api_core_line(reply);
        return;
    }
    if (strstr(line, "\"m\":\"status\"")) {
        printf("send_core: %s\n", line);
        fflush(stdout);
        char name[64] = "c0";
        const char *id = strstr(line, "\"id\":\"");
        if (id) {
            id += 6;
            size_t i = 0;
            while (id[i] && id[i] != '"' && i + 1 < sizeof name) { name[i] = id[i]; i++; }
            name[i] = 0;
        }
        char reply[320];
        /* 格式與 Python 元件的回覆相同：R {"id": "c<N>", "ok":…, "r":…}（api_core_line 認這個格式）。
           name 已經含開頭的 'c'（從請求的 "id":"c<N>" 取出來），所以格式裡不再加。 */
        snprintf(reply, sizeof reply,
                 "R {\"id\": \"%s\",\"ok\":true,\"r\":{\"jobs\":[],\"active\":0,\"busy\":false,"
                 "\"rec\":{\"rec\":false},\"shutdown\":false,\"finish\":\"sound\"}}",
                 name);
        const int consumed = api_core_line(reply);
        (void)consumed;
    }
}
static void post_page(char *json) { snprintf(last_reply, sizeof last_reply, "%s", json); replies++; free(json); }
static void set_title(const char *t) { (void)t; }
static void flash(void) {}
static void keep_awake(int on) { (void)on; }
static void finish_action(const char *a) { (void)a; }

/* 以寬字元 API 讀檔：非 ASCII 路徑（例如 E:\四維八德\...）不能被窄字元 fopen 開啟。 */
static bool read_file_utf8(const std::wstring &path, std::string &out)
{
    HANDLE file = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return false;
    LARGE_INTEGER size{};
    if (!GetFileSizeEx(file, &size)) { CloseHandle(file); return false; }
    out.assign((size_t)size.QuadPart, '\0');
    DWORD read = 0;
    const BOOL ok = out.empty() || ReadFile(file, out.data(), (DWORD)out.size(), &read, NULL);
    CloseHandle(file);
    out.resize(read);
    while (!out.empty() && (out.back() == '\n' || out.back() == '\r' || out.back() == ' ')) out.pop_back();
    return ok != 0;
}
static int wait_reply(int ms)
{
    for (int waited = 0; waited < ms && !replies; waited += 25) Sleep(25);
    return replies;
}

int wmain(int argc, wchar_t **argv)
{
    if (argc < 3) { fputs("usage: swbd-cpp-wiring <base_dir> <data_dir> [--system-info] [--run-tool <args.json>]\n", stderr); return 2; }
    setvbuf(stdout, NULL, _IONBF, 0);   /* 無緩衝：逾時被砍時仍看得到進度 */
    puts("wiring: start");
    int want_system_info = 0;
    int want_fake_py = 0;   /* 注入 py_call：讓接手的方法走過反向呼叫 Python 的橋接路徑 */
    std::wstring tool_args;
    for (int i = 3; i < argc; i++) {
        if (!wcscmp(argv[i], L"--system-info")) want_system_info = 1;
        else if (!wcscmp(argv[i], L"--fake-py")) want_fake_py = 1;
        else if (!wcscmp(argv[i], L"--run-tool") && i + 1 < argc) tool_args = argv[++i];
    }
    char base[2048] = { 0 }, data[2048] = { 0 };
    WideCharToMultiByte(CP_UTF8, 0, argv[1], -1, base, (int)sizeof base, NULL, NULL);
    WideCharToMultiByte(CP_UTF8, 0, argv[2], -1, data, (int)sizeof data, NULL, NULL);

    api_host host = { send_core, post_page, set_title, flash, keep_awake, finish_action };
    api_init(base, data, &host);
    const int ready = swbd_cpp_init(base, data);
    api_cpp_system_facts();      /* 與正式外殼相同的注入路徑 */
    api_cpp_tool_submit();       /* 原生工具工作需要 */
    if (want_fake_py) api_cpp_py_call();   /* --fake-py：注入 py_call（send_core 會合成 tool_job_opt 回覆） */
    const int methods = swbd_cpp_method_count();
    printf("cpp_ready=%d methods=%d has_cleanup_scan=%d has_cleanup_execute=%d\n",
           ready, methods, swbd_cpp_has("cleanup_scan"), swbd_cpp_has("cleanup_execute"));

    int failures = 0;
    if (!ready || methods < 2 || !swbd_cpp_has("cleanup_scan") || !swbd_cpp_has("cleanup_execute")) {
        puts("FAIL 註冊表沒有就緒或沒有接手預期的方法");
        failures++;
    }

    /* 已接手的方法：必須由 C++ 回答，且不得問 Python */
    replies = 0; python_cleanup_calls = 0; last_reply[0] = 0;
    const int handled = api_request("{\"id\":1,\"m\":\"cleanup_scan\",\"a\":[[\"logs\"]]}");
    wait_reply(15000);
    printf("cleanup_scan handled=%d python_calls=%d reply=%s\n", handled, python_cleanup_calls, last_reply);
    if (handled != 1) { puts("FAIL cleanup_scan 沒有被判為原生處理"); failures++; }
    if (python_cleanup_calls != 0) { puts("FAIL cleanup_scan 仍然被送去 Python"); failures++; }
    if (!strstr(last_reply, "\"id\":1") || !strstr(last_reply, "\"ok\":true")) {
        puts("FAIL cleanup_scan 的回覆信封不正確（應為 {\"id\":1,\"ok\":true,\"r\":…}）");
        failures++;
    }

    /* 未接手的方法：api_request 必須回 0，讓呼叫端照舊轉給 Python */
    replies = 0; last_reply[0] = 0;
    const int unknown = api_request("{\"id\":2,\"m\":\"swbd_method_that_nobody_owns\",\"a\":[]}");
    if (unknown != 0) { puts("FAIL 未接手的方法沒有交回 Python"); failures++; }
    printf("unowned handled=%d\n", unknown);

    /* 系統資訊：走與正式外殼相同的注入路徑，把回覆原文印出來給閘門逐欄比對。 */
    if (want_system_info) {
        replies = 0; last_reply[0] = 0;
        const int asked = api_request("{\"id\":3,\"m\":\"system_info\",\"a\":[]}");
        if (!asked || !wait_reply(30000)) { puts("FAIL system_info 沒有回覆"); failures++; }
        else {
            printf("system_info handled=%d\n", asked);
            printf("system_info_reply=%s\n", last_reply);
            if (!strstr(last_reply, "\"hardware\"") || !strstr(last_reply, "\"cleanup\"")) {
                puts("FAIL system_info 回覆缺少 hardware／cleanup");
                failures++;
            }
        }
    }

    /* 先確認 status 這條路在探針裡可以走完（它會問 Python 的 status 來合併）。 */
    if (!tool_args.empty()) {
        replies = 0; last_reply[0] = 0;
        api_request("{\"id\":4,\"m\":\"status\",\"a\":[]}");
        printf("status_before=%s\n", wait_reply(20000) ? last_reply : "(沒有回覆)");
    }

    /* 原生工具工作：走正式路由（api_request → C++ run_tool → eng_submit_tool），
       等它跑完再把工作的 JSON 印出來給閘門比對輸出檔。 */
    if (!tool_args.empty()) {
        std::string payload;
        if (!read_file_utf8(tool_args, payload)) { puts("FAIL 讀不到 run-tool 參數檔"); failures++; }
        else {
            static char request[1 << 17];
            snprintf(request, sizeof request, "{\"id\":9,\"m\":\"run_tool\",\"a\":%s}", payload.c_str());
            replies = 0; last_reply[0] = 0;
            const int asked = api_request(request);
            printf("run_tool handled=%d\n", asked);
            if (!asked || !wait_reply(60000)) { puts("FAIL run_tool 沒有回覆"); failures++; }
            else {
                printf("run_tool_reply=%s\n", last_reply);
                jval *reply = json_parse(last_reply);
                const jval *ids = reply ? jget(reply, "r") : NULL;
                const char *job = (ids && ids->type == J_ARR && ids->len && ids->items[0]->type == J_STR)
                                      ? ids->items[0]->str : NULL;
                if (!job) { puts("FAIL run_tool 沒有回傳工作 id"); failures++; }
                else {
                    char wanted[64];
                    snprintf(wanted, sizeof wanted, "%s", job);
                    int done = 0;
                    int round = 0;
                    for (int waited = 0; waited < 120000 && !done; waited += 200) {
                        Sleep(200);
                        replies = 0; last_reply[0] = 0;
                        api_request("{\"id\":10,\"m\":\"status\",\"a\":[]}");
                        const int got = wait_reply(20000);
                        if (++round <= 3) {
                            printf("run_tool_status[%d]=%s\n", round, got ? last_reply : "(沒有回覆)");
                        }
                        if (got) {
                            jval *status = json_parse(last_reply);
                            const jval *result = status ? jget(status, "r") : NULL;
                            const jval *jobs = result ? jget(result, "jobs") : NULL;
                            for (size_t i = 0; jobs && i < jobs->len; i++) {
                                const jval *entry = jobs->items[i];
                                if (strcmp(jget_str(entry, "id", ""), wanted)) continue;
                                if (round % 10 == 1) {
                                    printf("run_tool_state[%d]=%s msg=%s\n", round, jget_str(entry, "state", "?"),
                                           jget_str(entry, "msg", ""));
                                }
                            }
                            if (status) json_free(status);
                        }
                        jval *status = json_parse(last_reply);
                        const jval *result2 = status ? jget(status, "r") : NULL;
                        const jval *jobs = result2 ? jget(result2, "jobs") : NULL;
                        for (size_t i = 0; jobs && i < jobs->len; i++) {
                            const jval *entry = jobs->items[i];
                            const char *id = jget_str(entry, "id", "");
                            const char *state = jget_str(entry, "state", "");
                            if (strcmp(id, wanted)) continue;
                            if (strcmp(state, "queued") && strcmp(state, "running")) {
                                char *text = json_dump(entry);
                                printf("run_tool_job=%s\n", text ? text : "{}");
                                free(text);
                                done = 1;
                                if (strcmp(state, "done")) {
                                    printf("FAIL 原生工具工作沒有完成（%s）\n", state);
                                    failures++;
                                }
                            }
                        }
                        if (status) json_free(status);
                    }
                    if (!done) { puts("FAIL 原生工具工作逾時"); failures++; }
                }
                if (reply) json_free(reply);
            }
        }
    }

    printf(failures ? "WIRING FAIL (%d)\n" : "WIRING PASS\n", failures);
    fflush(stdout);
    ExitProcess(failures ? 1 : 0);
}
