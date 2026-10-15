/* Request routing between the page, the C engine and the Python component; window monitor and finish actions. */
#define _CRT_SECURE_NO_WARNINGS
#include "api.h"
#include "engine.h"
#include "json.h"
#include "plat.h"
#include "swbd/bridge.hpp"   /* the C++ core answers the methods it has taken over */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define APP_TITLE "四維八德（開源版）"

static api_host H;
static engine *E;
static volatile int core_gone;

/* ================================================================== calls into the Python component */
typedef struct pending { unsigned id; char *reply; int done; struct pending *next; } pending;
static pending *calls;
static plat_mutex *cm;
static plat_cond *cc;
static unsigned call_seq;

/* 有些方法是 C 自己發起的（monitor 要顯示成品、存設定…）：先問 C++ 核心有沒有接手，
   沒有才轉 Python。這樣 C++ 的接手範圍就不限於「頁面送進來的方法」。 */
static jval *core_call(const char *method, jval *args);
static jval *cpp_or_core(const char *method, jval *args)
{
    if (swbd_cpp_has(method)) {
        char *text = swbd_cpp_call(method, args);
        json_free(args);
        jval *r = text ? json_parse(text) : NULL;
        if (text) swbd_cpp_free(text);
        return r;
    }
    return core_call(method, args);
}

/* blocking call from a worker thread; returns the whole reply object {"id","ok","r"|"e"} or NULL */
static jval *core_call(const char *method, jval *args)
{
    if (core_gone) { json_free(args); return NULL; }
    pending p = {0};
    mutex_lock(cm); p.id = ++call_seq; p.next = calls; calls = &p; mutex_unlock(cm);
    sbuf b = {0};
    sb_printf(&b, "Q {\"id\":\"c%u\",\"m\":", p.id); sb_json_str(&b, method); sb_str(&b, ",\"a\":");
    if (args) json_write(&b, args); else sb_str(&b, "[]");
    sb_str(&b, "}");
    json_free(args);
    H.send_core(b.p);
    free(b.p);
    double end = now_s() + 300;
    mutex_lock(cm);
    while (!p.done && !core_gone && now_s() < end) cond_wait_ms(cc, cm, 500);
    for (pending **q = &calls; *q; q = &(*q)->next) if (*q == &p) { *q = p.next; break; }
    mutex_unlock(cm);
    jval *r = p.reply ? json_parse(p.reply) : NULL;
    free(p.reply);
    return r;
}

int api_core_line(const char *line)
{
    static const char tag[] = "R {\"id\": \"c";
    if (strncmp(line, tag, sizeof tag - 1)) return 0;
    unsigned id = (unsigned)strtoul(line + sizeof tag - 1, NULL, 10);
    int found = 0;
    mutex_lock(cm);
    for (pending *p = calls; p; p = p->next)
        if (p->id == id) { p->reply = str_dup(line + 2); p->done = 1; found = 1; break; }
    cond_broadcast(cc);
    mutex_unlock(cm);
    return found || 1;           /* "c" ids are always ours; a late answer after a timeout is dropped */
}

void api_core_gone(void) { core_gone = 1; mutex_lock(cm); cond_broadcast(cc); mutex_unlock(cm); }

/* ================================================================== replies to the page */
static void reply(const jval *id, jval *result, const char *error)
{
    sbuf b = {0};
    sb_str(&b, "{\"id\":"); json_write(&b, id);
    if (error) { sb_str(&b, ",\"ok\":false,\"e\":"); sb_json_str(&b, error); }
    else { sb_str(&b, ",\"ok\":true,\"r\":"); json_write(&b, result); }
    sb_str(&b, "}");
    json_free(result);
    H.post_page(b.p);
}

/* pass a Python answer on to the page under the page's own id */
static void relay(const jval *id, jval *r)
{
    if (!r) { reply(id, NULL, "轉檔元件沒有回應"); return; }
    if (jget_bool(r, "ok", 0)) reply(id, json_clone(jget(r, "r")), NULL);
    else reply(id, NULL, jget_str(r, "e", "error"));
    json_free(r);
}

static jval *arr1(jval *v) { jval *a = jnew(J_ARR); jarr_push(a, v); return a; }

/* ================================================================== methods answered in C */
static double job_created(const jval *j) { return jget_num(j, "created", 0); }
static int cmp_created(const void *a, const void *b)
{
    double x = job_created(*(jval *const *)a), y = job_created(*(jval *const *)b);
    return x < y ? -1 : x > y;
}

static volatile int shutdown_pending;

static jval *merged_status(void)
{
    jval *py = core_call("status", jnew(J_ARR));
    const jval *r = py ? jget(py, "r") : NULL;
    const jval *pj = r ? jget(r, "jobs") : NULL;
    jval *cj = eng_status(E, 150);
    size_t n = (pj ? pj->len : 0) + cj->len;
    jval **all = (jval **)malloc(sizeof(jval *) * (n ? n : 1));
    size_t k = 0;
    for (size_t i = 0; pj && i < pj->len; i++) all[k++] = json_clone(pj->items[i]);
    for (size_t i = 0; i < cj->len; i++) { all[k++] = cj->items[i]; cj->items[i] = NULL; }
    cj->len = 0; json_free(cj);
    qsort(all, k, sizeof(jval *), cmp_created);
    jval *jobs = jnew(J_ARR);
    size_t cut = k > 150 ? k - 150 : 0;
    for (size_t i = 0; i < k; i++) {
        if (i >= cut || !strcmp(jget_str(all[i], "state", ""), "running")) jarr_push(jobs, all[i]);
        else json_free(all[i]);
    }
    free(all);
    int active = eng_active(E) + (int)jget_num(r, "active", 0);
    jval *o = jnew(J_OBJ);
    jobj_set(o, "jobs", jobs);
    jobj_set(o, "active", jnum(active));
    jobj_set(o, "busy", jbool(active > 0));
    jobj_set(o, "rec", r && jget(r, "rec") ? json_clone(jget(r, "rec")) : jnew(J_OBJ));
    jobj_set(o, "shutdown", jbool(shutdown_pending || jget_bool(r, "shutdown", 0)));
    jobj_set(o, "finish", jstr(jget_str(r, "finish", "sound")));
    json_free(py);
    return o;
}

static jval *start_jobs(const jval *items, const jval *opt, int merge)
{
    jval *ids = jnew(J_ARR), *py_items = jnew(J_ARR);
    size_t n = items && items->type == J_ARR ? items->len : 0;
    char *done = (char *)calloc(n ? n : 1, 1);
    for (size_t i = 0; i < n; i++) {
        if (done[i]) continue;
        const jval *it = items->items[i];
        const char *target = jget_str(it, "target", ""), *path = jget_str(it, "path", "");
        const char *cat = eng_category(path);
        jval *files = jnew(J_ARR);
        jarr_push(files, jstr(path)); done[i] = 1;
        if (merge)        /* one merged job per target, as before */
            for (size_t k = i + 1; k < n; k++)
                if (!done[k] && !strcmp(jget_str(items->items[k], "target", ""), target)) { jarr_push(files, jstr(jget_str(items->items[k], "path", ""))); done[k] = 1; }
        if (eng_handles(cat, target, merge, opt)) {
            jval *got = eng_submit(E, files, target, opt, merge);
            for (size_t k = 0; k < got->len; k++) jarr_push(ids, json_clone(got->items[k]));
            json_free(got);
        } else
            for (size_t k = 0; k < files->len; k++) {
                jval *o = jnew(J_OBJ);
                jobj_set(o, "path", jstr(files->items[k]->str)); jobj_set(o, "target", jstr(target));
                jarr_push(py_items, o);
            }
        json_free(files);
    }
    free(done);
    if (py_items->len) {
        jval *a = jnew(J_ARR);
        jarr_push(a, py_items); jarr_push(a, opt ? json_clone(opt) : jnew(J_OBJ)); jarr_push(a, jbool(merge));
        jval *r = core_call("start", a);
        const jval *got = r ? jget(r, "r") : NULL;
        for (size_t k = 0; got && got->type == J_ARR && k < got->len; k++) jarr_push(ids, json_clone(got->items[k]));
        json_free(r);
    } else json_free(py_items);
    return ids;
}

static const char *IDLE_ONLY[] = { "cleanup_scan", "cleanup_execute", NULL };
static const char *NATIVE[] = { "describe", "formats", "media_info", "hwinfo", "start", "status", "cancel", "cancel_all", "clear_done",
                                "retry", "compare_job", "preview", "cancel_shutdown", "cleanup_scan", "cleanup_execute", NULL };

static int in(const char *const *l, const char *s) { for (; *l; l++) if (!strcmp(*l, s)) return 1; return 0; }

/* The C++ core replies in exactly the envelope Python uses ({"ok":true,"r":...} / {"ok":false,"e":...}),
   so relay() keeps the wire format to the page identical no matter which side did the work. */
static void answer_cpp(const jval *id, const char *m, const jval *args)
{
    char *text = swbd_cpp_call(m, args);
    jval *r = text ? json_parse(text) : NULL;
    if (text) swbd_cpp_free(text);
    relay(id, r);
}

static void handle(void *arg)
{
    jval *req = (jval *)arg;
    const jval *id = jget(req, "id"), *a = jget(req, "a");
    const char *m = jget_str(req, "m", "");
    const jval *a0 = a && a->len > 0 ? a->items[0] : NULL, *a1 = a && a->len > 1 ? a->items[1] : NULL, *a2 = a && a->len > 2 ? a->items[2] : NULL;
    const char *sid = a0 && a0->type == J_STR ? a0->str : "";
    char *err = NULL;

    if (!strcmp(m, "describe")) reply(id, eng_describe(E, a0), NULL);
    else if (!strcmp(m, "formats")) reply(id, eng_formats(E), NULL);
    else if (!strcmp(m, "media_info")) reply(id, eng_media_info(E, a0), NULL);
    else if (!strcmp(m, "hwinfo")) reply(id, eng_hwinfo(E), NULL);
    else if (!strcmp(m, "start")) reply(id, start_jobs(a0, a1, a2 && a2->type == J_BOOL && a2->num), NULL);
    else if (!strcmp(m, "status")) reply(id, merged_status(), NULL);
    else if (!strcmp(m, "cancel")) {
        if (eng_owns(E, sid)) { eng_cancel(E, sid); reply(id, jbool(1), NULL); }
        else relay(id, core_call(m, json_clone(a)));
    } else if (!strcmp(m, "cancel_all") || !strcmp(m, "clear_done")) {
        if (!strcmp(m, "cancel_all")) eng_cancel_all(E); else eng_clear_done(E);
        relay(id, core_call(m, jnew(J_ARR)));
    } else if (!strcmp(m, "retry")) {
        if (eng_owns(E, sid)) { char *n = eng_retry(E, sid); reply(id, n ? jstr(n) : jnew(J_NULL), NULL); free(n); }
        else relay(id, core_call(m, json_clone(a)));
    } else if (!strcmp(m, "compare_job")) {
        if (eng_owns(E, sid)) { jval *r = eng_compare(E, sid, &err); reply(id, r, err); free(err); }
        else relay(id, core_call(m, json_clone(a)));
    } else if (!strcmp(m, "preview")) {
        const char *cat = eng_category(sid);
        if (cat && !strcmp(cat, "video")) {
            double at = a1 && a1->type == J_NUM ? a1->num : -1;
            jval *r = eng_preview(E, sid, at, &err); reply(id, r, err); free(err);
        } else relay(id, core_call(m, json_clone(a)));
    } else if (!strcmp(m, "cancel_shutdown")) {
        shutdown_pending = 0;
        H.finish_action("cancel_shutdown");
        relay(id, core_call(m, jnew(J_ARR)));
    } else if (in(IDLE_ONLY, m)) {
        /* Busy means refuse, whoever owns the method: cleanup must never run alongside real work.
           Only when idle does the C++ core get its turn, and Python after that. */
        if (eng_active(E)) reply(id, NULL, "請先完成或停止進行中的工作");
        else if (swbd_cpp_has(m)) answer_cpp(id, m, a);
        else relay(id, core_call(m, json_clone(a)));
    } else if (swbd_cpp_has(m)) answer_cpp(id, m, a);
    else relay(id, core_call(m, json_clone(a)));
    json_free(req);
}

int api_request(const char *text)
{
    jval *req = json_parse(text);
    if (!req) return 0;
    const char *m = jget_str(req, "m", "");
    if (!in(NATIVE, m) && !swbd_cpp_has(m)) { json_free(req); return 0; }   /* methods the C++ core took over pass here too */
    if (!thread_start(handle, req)) { json_free(req); return 0; }
    return 1;
}

/* ================================================================== monitor: title, sleep, finish actions */
static void monitor(void *unused)
{
    (void)unused;
    int awake = 0;
    char shown[256] = APP_TITLE;
    char **batch = NULL; int nbatch = 0;
    double completed_before = now_s();
    for (;;) {
        sleep_ms(1000);
        if (core_gone) return;
        jval *py = core_call("monitor_state", jnew(J_ARR));
        const jval *r = py ? jget(py, "r") : NULL;
        const jval *pa = r ? jget(r, "active") : NULL;
        const jval *recent = r ? jget(r, "recent") : NULL;
        jval *cs = eng_status(E, 0);
        /* Jobs can finish between polls. Include newly created terminal jobs too. */
        const jval *sources[2] = { cs, recent };
        for (int source = 0; source < 2; source++) {
            const jval *list = sources[source];
            for (size_t i = 0; list && i < list->len; i++) {
                const jval *item = list->items[i];
                if (job_created(item) <= completed_before) continue;
                const char *jid = jget_str(item, "id", "");
                int have = 0; for (int k = 0; k < nbatch; k++) if (!strcmp(batch[k], jid)) have = 1;
                if (*jid && !have) { batch = (char **)realloc(batch, sizeof(char *) * (size_t)(nbatch + 1)); batch[nbatch++] = str_dup(jid); }
            }
        }
        double sum = 0; int n = 0;
        for (size_t i = 0; pa && i < pa->len; i++) {
            sum += jget_num(pa->items[i], "progress", 0); n++;
            const char *jid = jget_str(pa->items[i], "id", "");
            int have = 0; for (int k = 0; k < nbatch; k++) if (!strcmp(batch[k], jid)) have = 1;
            if (!have) { batch = (char **)realloc(batch, sizeof(char *) * (size_t)(nbatch + 1)); batch[nbatch++] = str_dup(jid); }
        }
        for (size_t i = 0; i < cs->len; i++) {
            const char *st = jget_str(cs->items[i], "state", "");
            if (strcmp(st, "queued") && strcmp(st, "running")) continue;
            sum += jget_num(cs->items[i], "progress", 0); n++;
            const char *jid = jget_str(cs->items[i], "id", "");
            int have = 0; for (int k = 0; k < nbatch; k++) if (!strcmp(batch[k], jid)) have = 1;
            if (!have) { batch = (char **)realloc(batch, sizeof(char *) * (size_t)(nbatch + 1)); batch[nbatch++] = str_dup(jid); }
        }
        int busy = n > 0;
        char title[256];
        if (busy) snprintf(title, sizeof title, "%.0f%% · %d 個工作 — %s", sum / n * 100, n, APP_TITLE);
        else snprintf(title, sizeof title, "%s", APP_TITLE);
        if (strcmp(title, shown)) { H.set_title(title); snprintf(shown, sizeof shown, "%s", title); }
        if (busy != awake) { H.keep_awake(busy); awake = busy; }
        if (!busy && nbatch > 0) {
            H.flash();
            /* finish action: shutdown / sleep only when every job of the batch really finished */
            const char *act = jget_str(r, "finish", "sound");
            int all_done = nbatch > 0;
            jval *ids = jnew(J_ARR);
            for (int k = 0; k < nbatch; k++) {
                if (eng_owns(E, batch[k])) {
                    for (size_t i = 0; i < cs->len; i++)
                        if (!strcmp(jget_str(cs->items[i], "id", ""), batch[k]) && strcmp(jget_str(cs->items[i], "state", ""), "done")) all_done = 0;
                } else jarr_push(ids, jstr(batch[k]));
            }
            if (ids->len) {
                jval *pr = core_call("job_states", arr1(ids));
                const jval *states = pr ? jget(pr, "r") : NULL;
                for (size_t i = 0; states && i < states->len; i++) if (states->items[i]->type != J_STR || strcmp(states->items[i]->str, "done")) all_done = 0;
                if (!states) all_done = 0;
                json_free(pr);
            } else json_free(ids);
            int unattended = !strcmp(act, "shutdown") || !strcmp(act, "sleep");
            if (unattended && !all_done) act = "sound";
            if (!strcmp(act, "sound") || unattended) H.finish_action(!strcmp(act, "sound") ? "sound" : act);
            if (!strcmp(act, "shutdown")) shutdown_pending = 1;
            if (unattended || strcmp(jget_str(r, "finish", "sound"), act)) {
                jval *s = jnew(J_OBJ); jobj_set(s, "finish", jstr("sound"));
                json_free(core_call("save_settings", arr1(s)));
            }
            if (!strcmp(act, "open")) {
                const char *last = NULL;
                double last_created = completed_before;
                for (int source = 0; source < 2; source++) {
                    const jval *list = sources[source];
                    for (size_t i = 0; list && i < list->len; i++) {
                        const jval *item = list->items[i];
                        if (!strcmp(jget_str(item, "state", ""), "done") && job_created(item) > last_created) {
                            last_created = job_created(item); last = jget_str(item, "output", NULL);
                        }
                    }
                }
                if (last && *last) json_free(cpp_or_core("reveal", arr1(jstr(last))));
            }
            for (int source = 0; source < 2; source++) {
                const jval *list = sources[source];
                for (size_t i = 0; list && i < list->len; i++) if (job_created(list->items[i]) > completed_before) completed_before = job_created(list->items[i]);
            }
            for (int k = 0; k < nbatch; k++) free(batch[k]);
            nbatch = 0;
        }
        json_free(cs); json_free(py);
    }
}

void api_init(const char *base, const char *data, const api_host *host)
{
    H = *host;
    cm = mutex_new(); cc = cond_new();
    E = engine_new(base, data);
    thread_start(monitor, NULL);
}

void api_close(void) { if (E) eng_cancel_all(E); }

/* 給 C++ 接手的方法用的忙碌查詢：只問 Python 那一側（語意等同 app.py 的 self._eng.busy()）。
   C 引擎自己的忙碌由 api_request 的 IDLE_ONLY 守門負責，兩者合起來與原行為相同。 */
static int cpp_python_busy(void)
{
    if (core_gone) return 0;
    jval *reply = core_call("status", jnew(J_ARR));
    if (!reply) return 0;
    const jval *result = jget(reply, "r");
    const int busy = result ? (int)jget_num(result, "busy", 0) : 0;
    json_free(reply);
    return busy;
}

void api_cpp_busy_probe(void) { swbd_cpp_set_busy_probe(cpp_python_busy); }

/* 給 C++ 接手的方法用的系統事實：工作者政策與硬體編碼器都由引擎決定，避免兩份實作。 */
static void cpp_system_facts(swbd_cpp_system_facts *out)
{
    if (!out) return;
    eng_facts facts;
    eng_facts_get(E, &facts);
    out->ram_gb = facts.ram_gb;
    out->cores = facts.cores;
    out->heavy = facts.heavy;
    out->light = facts.light;
    out->slots = facts.slots;
    out->hw_ready = facts.hw_ready;
    out->hw_count = facts.hw_count;
    out->hw = facts.hw;
}

void api_cpp_system_facts(void) { swbd_cpp_set_system_facts(cpp_system_facts); }

/* C++ 接手的方法若需要問 Python（例如設定相關的選項），走這裡：把參數 JSON 送給 core_call，
   再把回覆信封原樣寫進呼叫端的緩衝區。 */
static int cpp_py_call(const char *method, const char *args_json, char *out, int out_size)
{
    if (core_gone || !method || !out || out_size <= 0) return -1;
    jval *args = json_parse(args_json && *args_json ? args_json : "[]");
    if (!args) return -1;
    jval *reply = core_call(method, args);
    if (!reply) return -1;
    char *text = json_dump(reply);
    json_free(reply);
    if (!text) return -1;
    const int length = (int)strlen(text);
    if (length + 1 > out_size) { free(text); return -1; }
    memcpy(out, text, (size_t)length + 1);
    free(text);
    return length;
}

/* 原生工具工作：交給 C 引擎排程，回傳工作 id 陣列（malloc 的 JSON，C++ 側負責釋放）。 */
static char *cpp_tool_submit(const char *tool, const jval *files, const jval *opt, const char *label,
                             int together, int heavy)
{
    jval *ids = eng_submit_tool(E, tool, files, opt, label, together, heavy);
    char *text = json_dump(ids);
    json_free(ids);
    return text;
}

void api_cpp_py_call(void) { swbd_cpp_set_py_call(cpp_py_call); }
void api_cpp_tool_submit(void) { swbd_cpp_set_tool_submit(cpp_tool_submit); }
