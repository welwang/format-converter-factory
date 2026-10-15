/* Linux end-to-end test: C router + C engine + the real Python component (python3 core.py). */
#define _GNU_SOURCE
#include "../api.h"
#include "../json.h"
#include "../plat.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>

static int to_py, from_py;
static pthread_mutex_t lk = PTHREAD_MUTEX_INITIALIZER;
static char *page[4096]; static int npage;
static char title[256];

static void send_core(const char *line) { pthread_mutex_lock(&lk); dprintf(to_py, "%s\n", line); pthread_mutex_unlock(&lk); }
static void post_page(char *json) { pthread_mutex_lock(&lk); if (npage < 4096) page[npage++] = json; pthread_mutex_unlock(&lk); }
static void set_title(const char *t) { snprintf(title, sizeof title, "%s", t); }
static void flash(void) { puts("[flash]"); }
static void keep_awake(int on) { printf("[keep_awake %d]\n", on); }
static void finish_action(const char *a) { printf("[finish %s]\n", a); }

static void *reader(void *u)
{
    (void)u;
    FILE *f = fdopen(from_py, "r"); char *line = NULL; size_t cap = 0; ssize_t n;
    while ((n = getline(&line, &cap, f)) > 0) {
        if (line[n - 1] == '\n') line[--n] = 0;
        if (api_core_line(line)) continue;
        if (line[0] == 'R') post_page(strdup(line + 2));
        else if (!strncmp(line, "S 0\tready", 9)) puts("[core ready]");
    }
    api_core_gone();
    return NULL;
}

static char *wait_reply(int id)
{
    char pre[32]; int k = snprintf(pre, sizeof pre, "{\"id\":%d,", id), k2;
    char pre2[32]; k2 = snprintf(pre2, sizeof pre2, "{\"id\": %d,", id);
    for (int t = 0; t < 600; t++) {
        pthread_mutex_lock(&lk);
        for (int i = 0; i < npage; i++) if (!strncmp(page[i], pre, (size_t)k) || !strncmp(page[i], pre2, (size_t)k2)) { char *r = page[i]; page[i] = strdup(""); pthread_mutex_unlock(&lk); return r; }
        pthread_mutex_unlock(&lk);
        usleep(100000);
    }
    return strdup("TIMEOUT");
}

static char *call(int id, const char *m, const char *args)
{
    char *req = str_fmt("{\"id\":%d,\"m\":\"%s\",\"a\":%s}", id, m, args);
    if (!api_request(req)) { char *q = str_fmt("Q %s", req); send_core(q); free(q); }
    free(req);
    return wait_reply(id);
}

int main(int argc, char **argv)
{
    (void)argc;
    int a[2], b[2]; pipe(a); pipe(b);
    if (!fork()) { dup2(a[0], 0); dup2(b[1], 1); close(a[1]); close(b[0]); chdir(argv[1]); execlp("python3", "python3", "core.py", NULL); _exit(1); }
    close(a[0]); close(b[1]); to_py = a[1]; from_py = b[0];
    pthread_t th; pthread_create(&th, NULL, reader, NULL);
    api_host h = { send_core, post_page, set_title, flash, keep_awake, finish_action };
    api_init(argv[2], argv[2], &h);
    const char *in = argv[3], *out = argv[4];
    char *r = call(1, "init", "[]"); printf("init: %.80s\n", r);
    char *args = str_fmt("[[\"%s\"]]", in);
    r = call(2, "describe", args); printf("describe: %.150s\n", r);
    char *items = str_fmt("[[{\"path\":\"%s/v.mp4\",\"target\":\"webm\"},{\"path\":\"%s/img0.jpg\",\"target\":\"webp\"},{\"path\":\"%s/a.wav\",\"target\":\"mp3\"},{\"path\":\"%s/img1.jpg\",\"target\":\"png\"}],{\"out_dir\":\"%s\",\"preset\":\"balanced\"},false]", in, in, in, in, out);
    r = call(3, "start", items); printf("start: %s\n", r);
    jval *ids = json_parse(r); const jval *list = jget(ids, "r");
    sleep(2);
    r = call(4, "status", "[]"); jval *st = json_parse(r); const jval *jobs = jget(jget(st, "r"), "jobs");
    printf("status: %zu jobs active=%g title=%s\n", jobs->len, jget_num(jget(st, "r"), "active", -1), title);
    for (size_t i = 0; i < jobs->len; i++) printf("  %s %-10s %s -> %s\n", jget_str(jobs->items[i], "id", ""), jget_str(jobs->items[i], "state", ""), jget_str(jobs->items[i], "name", ""), jget_str(jobs->items[i], "target", ""));
    char *cancel = str_fmt("[\"%s\"]", list->items[0]->str);
    r = call(5, "cancel", cancel); printf("cancel C job: %s\n", r);
    for (int t = 0; t < 120; t++) {
        r = call(6 + t, "status", "[]"); st = json_parse(r);
        if (!jget_bool(jget(st, "r"), "busy", 1)) break;
        sleep(1);
    }
    jobs = jget(jget(st, "r"), "jobs");
    for (size_t i = 0; i < jobs->len; i++) printf("  final %s %-10s %s -> %s  %s\n", jget_str(jobs->items[i], "id", ""), jget_str(jobs->items[i], "state", ""), jget_str(jobs->items[i], "name", ""), jget_str(jobs->items[i], "target", ""), jget_str(jobs->items[i], "encoder", ""));
    sleep(2);
    printf("title after: %s\n", title);
    char *py_id = NULL;
    for (size_t i = 0; i < jobs->len; i++) if (jget_str(jobs->items[i], "id", "")[0] != 'c') py_id = (char *)jget_str(jobs->items[i], "id", "");
    char *ra = str_fmt("[\"%s\"]", py_id); r = call(200, "retry", ra); printf("retry python job: %s\n", r);
    r = call(201, "retry", cancel); printf("retry C job: %s\n", r);
    char *pv = str_fmt("[\"%s/v.mp4\"]", in); r = call(202, "preview", pv); printf("preview video (C): %.60s\n", r);
    pv = str_fmt("[\"%s/img0.jpg\"]", in); r = call(203, "preview", pv); printf("preview image (Python): %.60s\n", r);
    r = call(204, "nonexistent", "[]"); printf("unknown: %s\n", r);
    r = call(205, "cleanup_scan", "[[\"logs\"]]"); printf("cleanup while busy: %.80s\n", r);
    sleep(3);
    r = call(206, "cancel_all", "[]"); printf("cancel_all: %s\n", r);
    sleep(2);
    r = call(207, "clear_done", "[]"); r = call(208, "status", "[]"); printf("after clear: %.120s\n", r);
    return 0;
}
