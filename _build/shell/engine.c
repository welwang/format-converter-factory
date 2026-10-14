/* 四維八德 conversion engine (C port of engine.py's converters and queue). */
#define _CRT_SECURE_NO_WARNINGS
#include "engine.h"
#include "plat.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <ctype.h>
#include <stdarg.h>
#include <time.h>

#ifdef _MSC_VER
#define THREAD_LOCAL __declspec(thread)
#else
#define THREAD_LOCAL _Thread_local
#endif

#define MB 1048576.0

/* ================================================================== string vectors (argv) */
typedef struct { char **v; int n, cap; } strv;
static void sv_add(strv *s, const char *a)
{
    if (s->n + 2 > s->cap) { s->cap = s->cap ? s->cap * 2 : 32; s->v = (char **)realloc(s->v, sizeof(char *) * (size_t)s->cap); }
    s->v[s->n++] = str_dup(a); s->v[s->n] = NULL;
}
static void sv_addf(strv *s, const char *fmt, ...)
{
    char buf[4096];
    va_list ap; va_start(ap, fmt); vsnprintf(buf, sizeof buf, fmt, ap); va_end(ap);
    sv_add(s, buf);
}
static void sv_cat(strv *s, const strv *o) { for (int i = 0; i < o->n; i++) sv_add(s, o->v[i]); }
static void sv_free(strv *s) { for (int i = 0; i < s->n; i++) free(s->v[i]); free(s->v); s->v = NULL; s->n = s->cap = 0; }

/* ================================================================== formats */
typedef struct { const char *ext, *cat; } extcat;
static const extcat EXTS[] = {
    {"mp4","video"},{"mkv","video"},{"webm","video"},{"mov","video"},{"avi","video"},{"flv","video"},{"wmv","video"},{"m4v","video"},
    {"ts","video"},{"mts","video"},{"3gp","video"},{"mpg","video"},{"mpeg","video"},{"gif","video"},
    {"mp3","audio"},{"aac","audio"},{"m4a","audio"},{"wav","audio"},{"flac","audio"},{"ogg","audio"},{"opus","audio"},{"wma","audio"},{"amr","audio"},{"aiff","audio"},
    {"jpg","image"},{"jpeg","image"},{"png","image"},{"webp","image"},{"avif","image"},{"heic","image"},{"heif","image"},{"ico","image"},{"bmp","image"},{"tif","image"},{"tiff","image"},
    {"cr2","image"},{"cr3","image"},{"nef","image"},{"arw","image"},{"dng","image"},{"orf","image"},{"rw2","image"},{"raf","image"},{"pef","image"},{"srw","image"},
    {"psd","image"},{"svg","image"},{"tga","image"},{"jp2","image"},{"jfif","image"},{"pcx","image"},{"dds","image"},{"qoi","image"},
    {"pdf","pdf"},
    {"doc","doc"},{"docx","doc"},{"odt","doc"},{"rtf","doc"},{"txt","doc"},{"md","doc"},{"markdown","doc"},{"html","doc"},{"htm","doc"},{"tex","doc"},{"rst","doc"},{"org","doc"},{"wps","doc"},
    {"xls","sheet"},{"xlsx","sheet"},{"ods","sheet"},{"csv","sheet"},{"ppt","sheet"},{"pptx","sheet"},{"odp","sheet"},{"key","sheet"},{"numbers","sheet"},
    {"epub","ebook"},{"mobi","ebook"},{"azw3","ebook"},{"azw","ebook"},{"fb2","ebook"},{"kfx","ebook"},
    {"zip","archive"},{"7z","archive"},{"rar","archive"},{"tar","archive"},{"gz","archive"},{"tgz","archive"},{"bz2","archive"},{"xz","archive"},{"zst","archive"},{"cab","archive"},{"iso","archive"},
    {"srt","subtitle"},{"ass","subtitle"},{"ssa","subtitle"},{"vtt","subtitle"},{"sub","subtitle"},{"lrc","subtitle"},
    {"obj","model"},{"stl","model"},{"ply","model"},{"glb","model"},{"gltf","model"},{"off","model"},{"3mf","model"},
    {NULL,NULL}
};
static const char *VIDEO_T[] = {"mp4","mkv","webm","mov","avi","gif",NULL};
static const char *AUDIO_T[] = {"mp3","aac","m4a","wav","flac","ogg","opus",NULL};
static const char *IMAGE_T[] = {"jpg","png","webp","avif","ico","bmp","tiff","pdf",NULL};
static const char *PANDOC_IN[] = {"docx","odt","rtf","txt","md","markdown","html","htm","tex","rst","org","epub","fb2",NULL};
typedef struct { const char *ext, *why; } unsup;
static const unsup UNSUPPORTED[] = {
    {"kfx","亞馬遜 KFX 有 DRM，無法轉換"},{"key","Apple Keynote 專有格式，請先在 Keynote 匯出"},{"numbers","Apple Numbers 專有格式，請先匯出"},
    {"wps","WPS 舊格式支援有限"},{"azw","舊 Kindle 格式多半有 DRM"},{NULL,NULL}
};
static const char *REMOVED[][2] = {{"epub","mobi"},{"stl","glb"},{NULL,NULL}};

static int in_list(const char *const *l, const char *s) { for (; *l; l++) if (!strcmp(*l, s)) return 1; return 0; }

static void ext_of(const char *path, char *out, size_t n)
{
    const char *b = path_base(path), *dot = strrchr(b, '.');
    out[0] = 0;
    if (!dot || dot == b) return;
    snprintf(out, n, "%s", dot + 1);
    str_lower(out);
}

const char *eng_category(const char *path)
{
    char ext[32]; ext_of(path, ext, sizeof ext);
    for (const extcat *e = EXTS; e->ext; e++) if (!strcmp(e->ext, ext)) return e->cat;
    return NULL;
}

static const char *unsupported_why(const char *ext) { for (const unsup *u = UNSUPPORTED; u->ext; u++) if (!strcmp(u->ext, ext)) return u->why; return NULL; }

/* what this C engine converts; the rest (pictures, PDF, 3D) goes to the Python component */
int eng_handles(const char *cat, const char *target)
{
    (void)target;
    if (!cat) return 0;
    return !strcmp(cat, "video") || !strcmp(cat, "audio") || !strcmp(cat, "archive") || !strcmp(cat, "subtitle") ||
           !strcmp(cat, "doc") || !strcmp(cat, "sheet") || !strcmp(cat, "ebook");
}

/* ================================================================== engine state */
enum { Q_QUEUED, Q_RUNNING, Q_DONE, Q_PARTIAL, Q_ERROR, Q_CANCELLED };
static const char *STATE_NAME[] = {"queued","running","done","partial","error","cancelled"};

typedef struct job {
    char id[16];
    char **files; int nfiles;
    char target[16], cat[16];
    jval *opt;
    int merge, heavy, taken, busy;      /* busy: a worker still holds this job (never freed then) */
    volatile int state, cancelled;
    double progress, eta; int has_eta;
    char speed[64], msg[640], encoder[320], validation[320];
    char *output;
    double created, started, elapsed, finished;
    long long in_size, out_size;
    proc *proc;
    int rc; char *err;
    int keep_output;
} job;

typedef struct { char *path; double mtime; long long size; double dur; int w, h, akbps; char acodec[32], hdr[8]; char (*streams)[2][32]; int nstreams; } probe_t;

struct engine {
    char *base, *data, *ffmpeg, *sevenzip, *pandoc, *soffice, *calibre;
    plat_mutex *m; plat_cond *qc;
    job **jobs; int njobs, cap;
    int heavy_workers, light_workers, slots, office_slots, quiet_slots, enc_active;
    unsigned seq;
    char **reserved; int nreserved, capreserved;
    probe_t **probes; int nprobes, capprobes;
    char **hw; int nhw; int hw_state;         /* 0 unknown, 1 detecting, 2 done */
    int stopping;
};

static engine *G;   /* for the worker threads */

static const char *ostr(const jval *o, const char *k, const char *d) { const char *s = jget_str(o, k, d); return s ? s : d; }
static double onum(const jval *o, const char *k) { return jget_num(o, k, 0); }
static int obool(const jval *o, const char *k, int d) { return jget_bool(o, k, d); }

static char *tool_path(const char *base, const char *rel)
{
    char *p = str_fmt("%s%ctools%c%s", base, PSEP, PSEP, rel);
#ifdef _WIN32
    for (char *c = p; *c; c++) if (*c == '/') *c = '\\';
#endif
    if (is_file(p)) return p;
#ifndef _WIN32
    /* tests on Linux: tools/ffmpeg without .exe */
    if (str_ends(p, ".exe")) { p[strlen(p) - 4] = 0; if (is_file(p)) return p; }
#endif
    free(p);
    return NULL;
}

/* ================================================================== logging */
static void elog(engine *e, const char *msg)
{
    char *dir = path_join(e->data, "logs"); make_dirs(dir);
    char *p = path_join(dir, "zdgc.log");
    if (file_size(p) > 2000000) { char *old = str_fmt("%s.1", p); move_file(p, old); free(old); }
    time_t tt = (time_t)now_s(); struct tm *tm = localtime(&tt);
    char stamp[32]; strftime(stamp, sizeof stamp, "%Y-%m-%d %H:%M:%S ", tm);
    sbuf b = {0};
    sb_str(&b, stamp); sb_str(&b, msg); sb_str(&b, "\n");
    append_file(p, b.p, b.len);
    free(b.p); free(p); free(dir);
}

/* ================================================================== workers / resources */
static int auto_workers(void) { int n = cpu_count(); if (n <= 4 || mem_gb() <= 6) return 1; int w = n / 4; return w < 2 ? 2 : w > 4 ? 4 : w; }
static int light_workers(void) { double g = mem_gb(); if (g <= 4.5) return 1; if (g <= 8.5) return 2; int w = cpu_count() / 2; return w < 2 ? 2 : w > 6 ? 6 : w; }
static int work_slots(void) { if (mem_gb() <= 4.5 || cpu_count() <= 2) return 1; if (mem_gb() <= 8.5) return 2; return 4; }

static int encoder_threads(engine *e, const jval *opt)
{
    int cores = cpu_count();
    if (!strcmp(ostr(opt, "resource_mode", "auto"), "quiet")) { int t = cores / 2; return t < 1 ? 1 : t > 2 ? 2 : t; }
    mutex_lock(e->m); int active = e->enc_active < 1 ? 1 : e->enc_active; mutex_unlock(e->m);
    int t = cores / active;
    return t < 1 ? 1 : t > 16 ? 16 : t;
}

/* counting semaphore on the engine mutex; gives up when the job is cancelled */
static int acquire(engine *e, int *count, job *j, const char *wait_msg)
{
    mutex_lock(e->m);
    while (*count <= 0) {
        if (j->cancelled) { mutex_unlock(e->m); return 0; }
        snprintf(j->msg, sizeof j->msg, "%s", wait_msg);
        cond_wait_ms(e->qc, e->m, 100);
    }
    (*count)--;
    mutex_unlock(e->m);
    return 1;
}
static void release(engine *e, int *count) { mutex_lock(e->m); (*count)++; cond_broadcast(e->qc); mutex_unlock(e->m); }

/* ================================================================== output names */
static int reserved(engine *e, const char *p) { for (int i = 0; i < e->nreserved; i++) if (path_same(e->reserved[i], p)) return 1; return 0; }

/* free output name; names handed out are reserved for the session so two jobs never write the same file */
static char *unique_path(engine *e, const char *path, char **avoid, int navoid)
{
    const char *b = path_base(path), *dot = strrchr(b, '.');
    size_t stemlen = dot && dot != b ? (size_t)(dot - path) : strlen(path);
    const char *ext = dot && dot != b ? dot : "";
    char *cand = str_dup(path);
    mutex_lock(e->m);
    for (int n = 1;; n++) {
        char *abs = path_abs(cand);
        int clash = path_exists(cand) || reserved(e, abs);
        for (int i = 0; !clash && i < navoid; i++) if (path_same(abs, avoid[i])) clash = 1;
        if (!clash) {
            if (e->nreserved == e->capreserved) { e->capreserved = e->capreserved ? e->capreserved * 2 : 64; e->reserved = (char **)realloc(e->reserved, sizeof(char *) * (size_t)e->capreserved); }
            e->reserved[e->nreserved++] = abs;
            break;
        }
        free(abs); free(cand);
        cand = str_fmt("%.*s (%d)%s", (int)stemlen, path, n, ext);
    }
    mutex_unlock(e->m);
    return cand;
}

static char *stem_of(const char *path)
{
    const char *b = path_base(path); size_t n = strlen(b);
    while (n && (b[n - 1] == '/' || b[n - 1] == '\\')) n--;
    const char *dot = NULL;
    for (size_t i = 1; i < n; i++) if (b[i] == '.') dot = b + i;
    if (dot) n = (size_t)(dot - b);
    char *s = (char *)malloc(n + 1); memcpy(s, b, n); s[n] = 0;
    return s;
}

static char *out_path(engine *e, job *j, const char *src, const char *ext)
{
    const char *od = ostr(j->opt, "out_dir", "");
    char *folder = od[0] ? str_dup(od) : path_dir(src);
    make_dirs(folder);
    char *stem = stem_of(src);
    char *name = str_fmt("%s%s%s.%s", stem, j->merge ? "_合併" : "", ostr(j->opt, "_suffix", ""), ext);
    char *full = path_join(folder, name);
    char *u = unique_path(e, full, j->files, j->nfiles);
    free(folder); free(stem); free(name); free(full);
    return u;
}

/* ================================================================== probe (ffmpeg -i, no ffprobe needed) */
static const probe_t *probe(engine *e, const char *path)
{
    static probe_t empty;
    if (!e->ffmpeg) return &empty;
    char *abs = path_abs(path);
    double mt = file_mtime(abs); long long sz = file_size(abs);
    mutex_lock(e->m);
    for (int i = 0; i < e->nprobes; i++)
        if (!strcmp(e->probes[i]->path, abs) && e->probes[i]->mtime == mt && e->probes[i]->size == sz) { mutex_unlock(e->m); free(abs); return e->probes[i]; }
    mutex_unlock(e->m);

    const char *argv[] = { e->ffmpeg, "-hide_banner", "-i", path, NULL };
    char *out = NULL, *err = NULL;
    run_capture(argv, NULL, &out, &err, 60, NULL);
    probe_t r; memset(&r, 0, sizeof r);
    r.path = abs; r.mtime = mt; r.size = sz;
    const char *d = strstr(err, "Duration: ");
    int hh, mm; double ss;
    if (d && sscanf(d + 10, "%d:%d:%lf", &hh, &mm, &ss) == 3) r.dur = hh * 3600 + mm * 60 + ss;
    r.streams = calloc(64, sizeof *r.streams);
    for (char *line = err; line && *line;) {
        char *nl = strchr(line, '\n');
        size_t len = nl ? (size_t)(nl - line) : strlen(line);
        char *l = (char *)malloc(len + 1); memcpy(l, line, len); l[len] = 0;
        char *st = strstr(l, "Stream #");
        static const char *kinds[] = { ": Video: ", ": Audio: ", ": Subtitle: " };
        static const char *names[] = { "video", "audio", "subtitle" };
        for (int k = 0; st && k < 3; k++) {
            char *at = strstr(st, kinds[k]);
            if (!at) continue;
            char codec[32] = {0}; const char *c = at + strlen(kinds[k]); int n = 0;
            while ((isalnum((unsigned char)*c) || *c == '_') && n < 31) codec[n++] = *c++;
            if (r.nstreams < 64) { snprintf(r.streams[r.nstreams][0], 32, "%s", names[k]); snprintf(r.streams[r.nstreams][1], 32, "%s", codec); r.nstreams++; }
            if (k == 0 && !r.h && !strstr(l, "attached pic")) {
                for (char *p = strstr(at, ", "); p; p = strstr(p + 1, ", ")) {
                    int w, h; char x;
                    if (sscanf(p + 2, "%5d%c%5d", &w, &x, &h) == 3 && x == 'x' && w >= 10 && h >= 10) { r.w = w; r.h = h; break; }
                }
                if (strstr(l, "arib-std-b67")) strcpy(r.hdr, "hlg");
                else if (strstr(l, "smpte2084")) strcpy(r.hdr, "pq");
            }
            if (k == 1 && !r.acodec[0]) {
                snprintf(r.acodec, sizeof r.acodec, "%s", codec);
                char *kb = strstr(at, " kb/s");
                if (kb) { char *s = kb; while (s > at && isdigit((unsigned char)s[-1])) s--; r.akbps = atoi(s); }
            }
            break;
        }
        free(l);
        line = nl ? nl + 1 : NULL;
    }
    free(out); free(err);
    probe_t *stable = (probe_t *)malloc(sizeof *stable); *stable = r;      /* entries never move or go away */
    mutex_lock(e->m);
    if (e->nprobes == e->capprobes) { e->capprobes = e->capprobes ? e->capprobes * 2 : 32; e->probes = (probe_t **)realloc(e->probes, sizeof(probe_t *) * (size_t)e->capprobes); }
    e->probes[e->nprobes++] = stable;
    mutex_unlock(e->m);
    return stable;
}

static int has_stream(const probe_t *p, const char *kind) { for (int i = 0; i < p->nstreams; i++) if (!strcmp(p->streams[i][0], kind)) return 1; return 0; }

/* HDR (HLG / PQ) -> SDR BT.709 so iPhone / Android HDR clips do not come out grey */
static void hdr_filters(const probe_t *p, strv *vf)
{
    if (!p->hdr[0]) return;
    sv_add(vf, "zscale=t=linear:npl=100"); sv_add(vf, "format=gbrpf32le"); sv_add(vf, "zscale=p=bt709");
    sv_add(vf, "tonemap=tonemap=hable:desat=0"); sv_add(vf, "zscale=t=bt709:m=bt709:r=tv"); sv_add(vf, "format=yuv420p");
}

static char *join(const strv *s, const char *sep)
{
    sbuf b = {0}; sb_str(&b, "");
    for (int i = 0; i < s->n; i++) { if (i) sb_str(&b, sep); sb_str(&b, s->v[i]); }
    return b.p;
}

/* ================================================================== GPU encoders (cached 7 days per ffmpeg build) */
static void detect_hw(engine *e)
{
    mutex_lock(e->m);
    if (e->hw_state) { mutex_unlock(e->m); return; }
    e->hw_state = 1;
    mutex_unlock(e->m);
    char **found = (char **)calloc(4, sizeof(char *)); int nf = 0;
    char *cache = path_join(e->data, "hw_cache_c.json");
    int cached = 0;
    if (e->ffmpeg) {
        size_t n; char *txt = read_file(cache, &n);
        jval *c = txt ? json_parse(txt) : NULL;
        if (c && jget_num(c, "ffmpeg", -1) == file_mtime(e->ffmpeg) && now_s() - jget_num(c, "t", 0) < 7 * 86400) {
            const jval *hw = jget(c, "hw");
            for (size_t i = 0; hw && hw->type == J_ARR && i < hw->len && nf < 3; i++) if (hw->items[i]->type == J_STR) found[nf++] = str_dup(hw->items[i]->str);
            cached = 1;
        }
        json_free(c); free(txt);
        if (!cached) {
            static const char *encs[] = { "h264_nvenc", "h264_qsv", "h264_amf" };
            for (int i = 0; i < 3; i++) {
                const char *argv[] = { e->ffmpeg, "-hide_banner", "-v", "error", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.2", "-c:v", encs[i], "-f", "null", "-", NULL };
                if (run_capture(argv, NULL, NULL, NULL, 8, NULL) == 0) found[nf++] = str_dup(encs[i]);
            }
            jval *c2 = jnew(J_OBJ), *arr = jnew(J_ARR);
            for (int i = 0; i < nf; i++) jarr_push(arr, jstr(found[i]));
            jobj_set(c2, "hw", arr); jobj_set(c2, "t", jnum(now_s())); jobj_set(c2, "ffmpeg", jnum(file_mtime(e->ffmpeg)));
            char *d = json_dump(c2); write_file(cache, d, strlen(d)); free(d); json_free(c2);
        }
    }
    free(cache);
    mutex_lock(e->m);
    e->hw = found; e->nhw = nf; e->hw_state = 2;
    mutex_unlock(e->m);
}
static void hw_thread(void *arg) { detect_hw((engine *)arg); }

/* ================================================================== presets */
typedef struct { int crf, cq; const char *x264; int ab, aac, opus, vab, q, vp9, pdfq, pdfdpi; } preset_t;
static const preset_t P_HIGH = { 20, 22, "medium", 256, 192, 160, 192, 90, 30, 90, 300 };
static const preset_t P_BAL  = { 23, 26, "veryfast", 192, 160, 128, 128, 80, 34, 85, 200 };
static const preset_t P_SMALL = { 28, 30, "medium", 128, 112, 80, 96, 68, 38, 70, 150 };
static const preset_t *preset_of(const jval *o)
{
    const char *p = ostr(o, "preset", "balanced");
    return !strcmp(p, "high") ? &P_HIGH : !strcmp(p, "small") ? &P_SMALL : &P_BAL;
}

/* video encoder arguments; vbr_scale > 0 = second attempt after the target size was overshot */
static void video_args(engine *e, const char *t, const jval *o, double dur, char **hw, int nhw, double vbr_scale, strv *a, char *enc_out, size_t enc_n)
{
    const preset_t *p = preset_of(o);
    double tsize = onum(o, "target_mb");
    int vab = p->vab, vbr = 0;
    if (tsize > 0 && dur > 0) {
        double total_k = tsize * 8192 * 0.92 / dur;      /* headroom for container overhead + VBV overshoot */
        if (total_k < 600) vab = 64;                     /* tiny budget: give the picture the bits */
        vbr = (int)((total_k - vab - 8) * (vbr_scale > 0 ? vbr_scale : 1));
        if (vbr < 80) vbr = 80;
    }
    int strict = vbr_scale > 0;
    int th = encoder_threads(e, o);
#define RATE() do { sv_add(a, "-b:v"); sv_addf(a, "%dk", vbr); sv_add(a, "-maxrate"); sv_addf(a, "%dk", (int)(vbr * 1.5)); sv_add(a, "-bufsize"); sv_addf(a, "%dk", vbr * 2); } while (0)
    enc_out[0] = 0;
    if (!strcmp(t, "mp4") || !strcmp(t, "mov") || !strcmp(t, "mkv")) {
        const char *codec = ostr(o, "codec", "auto");
        if (!strcmp(codec, "auto")) codec = "h264";
        const char *enc = (nhw && obool(o, "hwaccel", 1) && !strcmp(codec, "h264")) ? hw[0] :
                          !strcmp(codec, "hevc") ? "libx265" : !strcmp(codec, "av1") ? "libsvtav1" : "libx264";
        snprintf(enc_out, enc_n, "%s", enc);
        sv_add(a, "-c:v"); sv_add(a, enc);
        sv_add(a, "-threads"); sv_addf(a, "%d", th);
        if (!strcmp(enc, "libx264") || !strcmp(enc, "libx265")) {
            sv_add(a, "-preset"); sv_add(a, p->x264);
            if (vbr) { if (strict) RATE(); else { sv_add(a, "-crf"); sv_addf(a, "%d", P_HIGH.crf); sv_add(a, "-maxrate"); sv_addf(a, "%dk", vbr); sv_add(a, "-bufsize"); sv_addf(a, "%dk", vbr * 2); } }
            else { sv_add(a, "-crf"); sv_addf(a, "%d", p->crf); }
            if (!strcmp(enc, "libx265")) {
                sv_add(a, "-x265-params"); sv_addf(a, "log-level=error:pools=%d:frame-threads=%d", th, th < 3 ? th : 3);
                if (!strcmp(t, "mp4") || !strcmp(t, "mov")) { sv_add(a, "-tag:v"); sv_add(a, "hvc1"); }
            }
        } else if (!strcmp(enc, "libsvtav1")) {
            sv_add(a, "-preset"); sv_add(a, "8"); sv_add(a, "-crf"); sv_addf(a, "%d", p->crf + 7);
            if (vbr) RATE();
        } else if (!strcmp(enc, "h264_nvenc")) {
            sv_add(a, "-preset"); sv_add(a, "p5"); sv_add(a, "-tune"); sv_add(a, "hq"); sv_add(a, "-spatial-aq"); sv_add(a, "1");
            sv_add(a, "-rc-lookahead"); sv_add(a, "20"); sv_add(a, "-bf"); sv_add(a, "3");
            if (vbr) {
                sv_add(a, "-rc"); sv_add(a, "vbr");
                if (strict) RATE();
                else { sv_add(a, "-cq"); sv_addf(a, "%d", P_HIGH.cq); sv_add(a, "-b:v"); sv_addf(a, "%dk", vbr); sv_add(a, "-maxrate"); sv_addf(a, "%dk", vbr); sv_add(a, "-bufsize"); sv_addf(a, "%dk", vbr * 2); }
            } else { sv_add(a, "-rc"); sv_add(a, "vbr"); sv_add(a, "-cq"); sv_addf(a, "%d", p->cq); sv_add(a, "-b:v"); sv_add(a, "0"); }
        } else if (!strcmp(enc, "h264_qsv")) {
            sv_add(a, "-preset"); sv_add(a, "slow");
            if (vbr) RATE(); else { sv_add(a, "-global_quality"); sv_addf(a, "%d", p->cq); }
        } else {
            sv_add(a, "-quality"); sv_add(a, "quality");
            if (vbr) { sv_add(a, "-rc"); sv_add(a, "vbr_peak"); RATE(); }
            else { sv_add(a, "-rc"); sv_add(a, "cqp"); sv_add(a, "-qp_i"); sv_addf(a, "%d", p->cq); sv_add(a, "-qp_p"); sv_addf(a, "%d", p->cq); sv_add(a, "-qp_b"); sv_addf(a, "%d", p->cq + 2); }
        }
        sv_add(a, "-pix_fmt"); sv_add(a, "yuv420p"); sv_add(a, "-c:a"); sv_add(a, "aac"); sv_add(a, "-b:a"); sv_addf(a, "%dk", vab);
        if (!strcmp(t, "mp4") || !strcmp(t, "mov")) { sv_add(a, "-movflags"); sv_add(a, "+faststart"); }
    } else if (!strcmp(t, "webm")) {
        snprintf(enc_out, enc_n, "libvpx-vp9");
        sv_add(a, "-c:v"); sv_add(a, "libvpx-vp9"); sv_add(a, "-threads"); sv_addf(a, "%d", th); sv_add(a, "-row-mt"); sv_add(a, "1");
        sv_add(a, "-tile-columns"); sv_add(a, "2"); sv_add(a, "-deadline"); sv_add(a, "good"); sv_add(a, "-cpu-used"); sv_add(a, p == &P_SMALL ? "3" : "4");
        if (vbr) { if (strict) RATE(); else { sv_add(a, "-crf"); sv_addf(a, "%d", P_HIGH.vp9); sv_add(a, "-b:v"); sv_addf(a, "%dk", vbr); } }
        else { sv_add(a, "-crf"); sv_addf(a, "%d", p->vp9); sv_add(a, "-b:v"); sv_add(a, "0"); }
        sv_add(a, "-c:a"); sv_add(a, "libopus"); sv_add(a, "-b:a"); sv_addf(a, "%dk", vab < p->opus ? vab : p->opus);
    } else if (!strcmp(t, "avi")) {
        snprintf(enc_out, enc_n, "mpeg4");
        sv_add(a, "-c:v"); sv_add(a, "mpeg4"); sv_add(a, "-q:v"); sv_add(a, p == &P_SMALL ? "8" : "4");
        sv_add(a, "-c:a"); sv_add(a, "libmp3lame"); sv_add(a, "-b:a"); sv_addf(a, "%dk", vab);
    }
#undef RATE
}

static int audio_kbps(const char *t, const jval *o)
{
    const preset_t *p = preset_of(o);
    if (!strcmp(t, "mp3")) return p->ab;
    if (!strcmp(t, "aac") || !strcmp(t, "m4a")) return p->aac;
    if (!strcmp(t, "opus")) return p->opus;
    return 0;
}
static void audio_args(const char *t, const jval *o, int cap_kbps, strv *a, char *enc, size_t n)
{
    const preset_t *p = preset_of(o);
    int k = cap_kbps ? cap_kbps : 0;
    if (!strcmp(t, "mp3")) { sv_add(a, "-c:a"); sv_add(a, "libmp3lame"); sv_add(a, "-b:a"); sv_addf(a, "%dk", k ? k : p->ab); }
    else if (!strcmp(t, "aac")) { sv_add(a, "-c:a"); sv_add(a, "aac"); sv_add(a, "-b:a"); sv_addf(a, "%dk", k ? k : p->aac); sv_add(a, "-f"); sv_add(a, "adts"); }
    else if (!strcmp(t, "m4a")) { sv_add(a, "-c:a"); sv_add(a, "aac"); sv_add(a, "-b:a"); sv_addf(a, "%dk", k ? k : p->aac); }
    else if (!strcmp(t, "wav")) { sv_add(a, "-c:a"); sv_add(a, "pcm_s16le"); }
    else if (!strcmp(t, "flac")) { sv_add(a, "-c:a"); sv_add(a, "flac"); sv_add(a, "-compression_level"); sv_add(a, "8"); }
    else if (!strcmp(t, "ogg")) { sv_add(a, "-c:a"); sv_add(a, "libvorbis"); sv_add(a, "-q:a"); sv_add(a, p->ab >= 256 ? "6" : p->ab >= 192 ? "5" : "3"); }
    else if (!strcmp(t, "opus")) { sv_add(a, "-c:a"); sv_add(a, "libopus"); sv_add(a, "-b:a"); sv_addf(a, "%dk", k ? k : p->opus); }
    for (int i = 0; i + 1 < a->n; i++) if (!strcmp(a->v[i], "-c:a")) { snprintf(enc, n, "%s", a->v[i + 1]); return; }
    enc[0] = 0;
}

/* ================================================================== running programs */
typedef struct { job *j; char *buf; size_t len; plat_mutex *m; plat_cond *c; int done; } errsink;
static void stderr_reader(void *arg)
{
    errsink *s = (errsink *)arg;
    char chunk[4096]; long got;
    while ((got = proc_read(s->j->proc, P_ERR, chunk, sizeof chunk)) > 0) {
        if (s->len + (size_t)got > 200000) {             /* keep the tail */
            size_t drop = s->len / 2;
            memmove(s->buf, s->buf + drop, s->len - drop); s->len -= drop;
        }
        char *nb = (char *)realloc(s->buf, s->len + (size_t)got + 1);
        if (!nb) continue;
        s->buf = nb; memcpy(nb + s->len, chunk, (size_t)got); s->len += (size_t)got; nb[s->len] = 0;
    }
    mutex_lock(s->m); s->done = 1; cond_broadcast(s->c); mutex_unlock(s->m);
}

/* run a program for a job; FFmpeg's -progress lines move the bar.  Returns exit code (-1 = could not start). */
static int run_job_proc(engine *e, job *j, const strv *cmd, double dur, const char *cwd, double base, double span)
{
    (void)e;
    if (j->cancelled) return -2;
    mutex_lock(G->m);
    j->proc = proc_start((const char *const *)cmd->v, cwd, P_OUT | P_ERR);
    proc *p = j->proc;
    mutex_unlock(G->m);
    if (!p) { free(j->err); j->err = str_fmt("無法啟動 %s", path_base(cmd->v[0])); j->rc = -1; return -1; }
    if (j->cancelled) proc_kill(p);
    errsink es = { j, (char *)calloc(1, 1), 0, mutex_new(), cond_new(), 0 };
    if (!thread_start(stderr_reader, &es)) es.done = 1;
    double t0 = now_s();
    char chunk[4096], line[1024]; size_t ll = 0; long got;
    while ((got = proc_read(p, P_OUT, chunk, sizeof chunk)) > 0) {
        for (long i = 0; i < got; i++) {
            char c = chunk[i];
            if (c != '\n') { if (ll < sizeof line - 1) line[ll++] = c; continue; }
            line[ll] = 0; ll = 0;
            if (!strncmp(line, "out_time_us=", 12) && dur > 0) {
                double cur = atof(line + 12) / 1e6, f = cur / dur;
                if (f < 0) f = 0;
                if (f > 1) f = 1;
                double pr = base + span * f; j->progress = pr < 0.99 ? pr : 0.99;
                double el = now_s() - t0;
                if (f > 0.01) { j->eta = floor(el / f - el + 0.5); j->has_eta = 1; }
            } else if (!strncmp(line, "speed=", 6)) {
                const char *v = line + 6; while (*v == ' ') v++;
                snprintf(j->speed, sizeof j->speed, "%s", v);
                size_t n = strlen(j->speed); while (n && (j->speed[n - 1] == '\r' || j->speed[n - 1] == ' ')) j->speed[--n] = 0;
            }
        }
    }
    int rc = proc_wait(p);
    mutex_lock(es.m); while (!es.done) cond_wait_ms(es.c, es.m, -1); mutex_unlock(es.m);
    mutex_lock(G->m); j->proc = NULL; mutex_unlock(G->m);
    proc_free(p);
    free(j->err); j->err = es.buf;
    free(es.m); free(es.c);
    j->rc = rc;
    return j->cancelled ? -2 : rc;
}

/* the line that actually explains an FFmpeg failure (the last one is usually a generic follow-up) */
static void ff_error(const char *err, char *out, size_t n, const char *def)
{
    static const char *noise[] = { "Nothing was written", "Terminating thread", "Task finished with error", "Could not open encoder before EOF",
        "Conversion failed", "Error while filtering", "Error sending frames", "Error marking filters", "Error closing", "Error while processing the decoded data", NULL };
    char good[512] = "", last[512] = "";
    for (const char *l = err ? err : ""; *l;) {
        const char *nl = strchr(l, '\n'); size_t len = nl ? (size_t)(nl - l) : strlen(l);
        char t[512]; size_t k = len < 511 ? len : 511; memcpy(t, l, k); t[k] = 0;
        char *s = t;
        for (;;) { while (*s == ' ' || *s == '\t' || *s == '\r') s++; if (*s != '[') break; char *c = strchr(s, ']'); if (!c) break; s = c + 1; }
        size_t m = strlen(s); while (m && (s[m - 1] == '\r' || s[m - 1] == ' ')) s[--m] = 0;
        if (*s) {
            snprintf(last, sizeof last, "%s", s);
            int bad = 0; for (int i = 0; noise[i]; i++) if (strstr(s, noise[i])) bad = 1;
            if (!bad && !good[0]) snprintf(good, sizeof good, "%s", s);
        }
        l = nl ? nl + 1 : l + len;
    }
    const char *msg = good[0] ? good : last[0] ? last : def;
    static const char *map[][2] = { {"no space left","磁碟空間不足"}, {"permission denied","沒有寫入權限（檔案可能正被其他程式開啟）"},
        {"invalid data found","檔案損毀或格式無法辨識"}, {"no such file","找不到檔案"}, {"does not contain any stream","檔案裡沒有可用的影音內容"},
        {"stream map","找不到需要的影像或聲音軌"}, {"out of memory","記憶體不足"}, {"cannot allocate memory","記憶體不足"}, {NULL,NULL} };
    char low[512]; snprintf(low, sizeof low, "%s", msg); str_lower(low);
    for (int i = 0; map[i][0]; i++) if (strstr(low, map[i][0])) { snprintf(out, n, "%s（%.160s）", map[i][1], msg); return; }
    snprintf(out, n, "%.250s", msg);
}

static void fail(job *j, const char *msg) { snprintf(j->msg, sizeof j->msg, "%s", msg); j->state = Q_ERROR; }

/* ================================================================== FFmpeg conversions */
static const char *AUDIO_COPY[][4] = { {"mp3","mp3",NULL}, {"aac","aac",NULL}, {"m4a","aac","alac",NULL}, {"opus","opus",NULL}, {"ogg","vorbis",NULL}, {"flac","flac",NULL}, {NULL} };

static int can_copy_audio(job *j, const char *t, const probe_t *info)
{
    const jval *o = j->opt;
    if (j->merge || !obool(o, "fastcopy", 1) || obool(o, "loudnorm", 0)) return 0;
    for (int i = 0; AUDIO_COPY[i][0]; i++) {
        if (strcmp(AUDIO_COPY[i][0], t)) continue;
        int ok = 0; for (int k = 1; k < 4 && AUDIO_COPY[i][k]; k++) if (!strcmp(AUDIO_COPY[i][k], info->acodec)) ok = 1;
        if (!ok) return 0;
        if (!strcmp(t, "flac") || !strcmp(info->acodec, "alac")) return 1;
        return info->akbps && info->akbps <= audio_kbps(t, o) + 16;
    }
    return 0;
}

/* do not spend more bits than a lossy source has: 96k AAC -> 192k MP3 only makes the file bigger */
static int audio_cap(job *j, const char *t, const probe_t *info)
{
    int want = audio_kbps(t, j->opt), src = info->akbps;
    if (j->merge || !want || !src || !strncmp(info->acodec, "pcm", 3)) return 0;
    static const char *lossless[] = { "flac", "alac", "wavpack", "ape", "truehd", NULL };
    if (in_list(lossless, info->acodec)) return 0;
    int cap = ((int)(src * 1.15) + 15) / 16 * 16;
    if (cap < 64) cap = 64;
    return cap < want ? cap : 0;
}

static int streams_copyable(const probe_t *info, const char *t)
{
    static const char *v_std[] = { "h264", "hevc", "av1", NULL }, *v_mkv[] = { "h264", "hevc", "av1", "vp9", "vp8", "mpeg4", NULL };
    static const char *a_std[] = { "aac", "mp3", "ac3", "opus", "flac", NULL }, *a_mov[] = { "aac", "mp3", "ac3", NULL };
    int mkv = !strcmp(t, "mkv"), has_v = 0;
    for (int i = 0; i < info->nstreams; i++) {
        const char *k = info->streams[i][0], *c = info->streams[i][1];
        if (!strcmp(k, "video") && strcmp(c, "mjpeg") && strcmp(c, "png")) { if (!in_list(mkv ? v_mkv : v_std, c)) return 0; has_v = 1; }
        else if (!strcmp(k, "audio") && !in_list(!strcmp(t, "mov") ? a_mov : a_std, c)) return 0;
        else if (!strcmp(k, "subtitle") && !mkv) return 0;
    }
    return has_v;
}

static int can_copy_video(job *j, const char *t, const probe_t *info)
{
    const jval *o = j->opt;
    if (j->merge || !obool(o, "fastcopy", 1) || (strcmp(t, "mp4") && strcmp(t, "mkv") && strcmp(t, "mov")) || onum(o, "height") || onum(o, "target_mb") || obool(o, "loudnorm", 0)) return 0;
    const char *codec = ostr(o, "codec", "auto");
    if (strcmp(codec, "auto")) for (int i = 0; i < info->nstreams; i++) if (!strcmp(info->streams[i][0], "video") && strcmp(info->streams[i][1], codec)) return 0;
    char ext[32]; ext_of(j->files[0], ext, sizeof ext);
    return streams_copyable(info, t) && strcmp(ext, t);
}

static void conv_ffmpeg(engine *e, job *j)
{
    const jval *o = j->opt; const char *t = j->target; const char *src = j->files[0];
    if (!e->ffmpeg) { fail(j, "找不到 ffmpeg（tools 資料夾）"); return; }
    j->output = out_path(e, j, src, t);
    double ss = onum(o, "trim_start"), to = onum(o, "trim_end"), tmb = onum(o, "target_mb");
    int hopt = (int)onum(o, "height");
    const char *codec = ostr(o, "codec", "auto");
    int is_audio_t = in_list(AUDIO_T, t);
    char srcext[32]; ext_of(src, srcext, sizeof srcext);
    if (tmb > 0 && !j->merge && !ss && !to && !hopt && !obool(o, "loudnorm", 0) && !strcmp(codec, "auto") && !strcmp(srcext, t) && file_size(src) <= tmb * MB) {
        copy_file(src, j->output); snprintf(j->encoder, sizeof j->encoder, "原檔已小於目標大小，直接複製"); return;
    }
    strv head = {0}, mid = {0};
    sv_add(&head, e->ffmpeg); sv_add(&head, "-hide_banner"); sv_add(&head, "-nostdin"); sv_add(&head, "-y");
    sv_add(&head, "-progress"); sv_add(&head, "pipe:1"); sv_add(&head, "-nostats"); sv_add(&head, "-v"); sv_add(&head, "error");
    { int th = encoder_threads(e, o); sv_add(&head, "-filter_complex_threads"); sv_addf(&head, "%d", th < 2 ? th : 2); }
    double dur = 0;
    const probe_t *info = probe(e, src);
    if (j->merge) {
        double *durs = (double *)calloc((size_t)j->nfiles, sizeof(double));
        for (int i = 0; i < j->nfiles; i++) { durs[i] = probe(e, j->files[i])->dur; dur += durs[i]; sv_add(&head, "-i"); sv_add(&head, j->files[i]); }
        sbuf fc = {0}; sb_str(&fc, "");
        if (is_audio_t || !strcmp(j->cat, "audio")) {
            for (int i = 0; i < j->nfiles; i++) sb_printf(&fc, "[%d:a:0]", i);
            sb_printf(&fc, "concat=n=%d:v=0:a=1[a]", j->nfiles);
            sv_add(&head, "-filter_complex"); sv_add(&head, fc.p); sv_add(&head, "-map"); sv_add(&head, "[a]");
        } else {
            int h = hopt ? hopt : 720;
            int w = (int)floor(h * (double)(info->w ? info->w : 16) / (info->h ? info->h : 9) + 0.5) / 2 * 2;
            if (w < 2) w = 2;
            for (int i = 0; i < j->nfiles; i++) {
                const probe_t *pi = probe(e, j->files[i]);
                strv tm = {0}; hdr_filters(pi, &tm);
                sb_printf(&fc, "[%d:v:0]", i);
                for (int k = 0; k < tm.n; k++) sb_printf(&fc, "%s,", tm.v[k]);
                sv_free(&tm);
                sb_printf(&fc, "scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p,setpts=PTS-STARTPTS[v%d];", w, h, w, h, i);
                if (has_stream(pi, "audio")) sb_printf(&fc, "[%d:a:0]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS[a%d];", i, i);
                else sb_printf(&fc, "anullsrc=r=48000:cl=stereo,atrim=duration=%g,asetpts=PTS-STARTPTS[a%d];", durs[i] > 0.1 ? durs[i] : 0.1, i);
            }
            for (int i = 0; i < j->nfiles; i++) sb_printf(&fc, "[v%d][a%d]", i, i);
            sb_printf(&fc, "concat=n=%d:v=1:a=1[v][a]", j->nfiles);
            sv_add(&head, "-filter_complex"); sv_add(&head, fc.p); sv_add(&head, "-map"); sv_add(&head, "[v]"); sv_add(&head, "-map"); sv_add(&head, "[a]");
        }
        free(fc.p); free(durs);
    } else {
        dur = info->dur;
        if (ss) { sv_add(&head, "-ss"); sv_addf(&head, "%g", ss); }
        if (to && to > ss) { sv_add(&head, "-to"); sv_addf(&head, "%g", to); }
        sv_add(&head, "-i"); sv_add(&head, src);
        if (to && to > ss) dur = to - ss;
        else if (ss) dur = dur - ss > 0.1 ? dur - ss : 0.1;
    }
    strv vf = {0};
    int h = hopt;
    if (h && !j->merge && info->h && h >= info->h && strcmp(t, "gif")) h = 0;     /* never upscale */
    if (!j->merge) hdr_filters(info, &vf);
    if (h && !j->merge && strcmp(t, "gif")) sv_addf(&vf, "scale=-2:%d", h);
    int encoded = 0, copied = 0;
    char enc[64] = "";
    char **hw = NULL; int nhw = 0;
    if (is_audio_t) {
        if (can_copy_audio(j, t, info)) {
            sv_add(&mid, "-vn"); sv_add(&mid, "-map"); sv_add(&mid, "0:a:0"); sv_add(&mid, "-c:a"); sv_add(&mid, "copy");
            if (!strcmp(t, "aac")) { sv_add(&mid, "-f"); sv_add(&mid, "adts"); }
            snprintf(j->encoder, sizeof j->encoder, "直接取出音軌（不重新編碼）"); copied = 1;
        } else {
            sv_add(&mid, "-vn");
            audio_args(t, o, audio_cap(j, t, info), &mid, enc, sizeof enc);
            snprintf(j->encoder, sizeof j->encoder, "%s", enc);
        }
    } else if (!strcmp(t, "gif")) {
        int gh = h ? h : 480, fps = !strcmp(ostr(o, "preset", "balanced"), "small") ? 12 : 15;
        sbuf g = {0}; sb_str(&g, "");
        for (int i = 0; i < vf.n; i++) if (strncmp(vf.v[i], "scale=", 6)) sb_printf(&g, "%s,", vf.v[i]);
        sb_printf(&g, "fps=%d,scale=-2:%d:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a", fps, gh);
        sv_add(&mid, "-vf"); sv_add(&mid, g.p); sv_add(&mid, "-an"); free(g.p);
        snprintf(j->encoder, sizeof j->encoder, "gif");
    } else if (can_copy_video(j, t, info)) {
        sv_add(&mid, "-map"); sv_add(&mid, "0"); sv_add(&mid, "-c"); sv_add(&mid, "copy");
        if (!strcmp(t, "mp4") || !strcmp(t, "mov")) { sv_add(&mid, "-movflags"); sv_add(&mid, "+faststart"); }
        snprintf(j->encoder, sizeof j->encoder, "直接封裝（不重新編碼）"); copied = 1;
    } else {
        detect_hw(e);
        mutex_lock(e->m); hw = e->hw; nhw = e->nhw; mutex_unlock(e->m);
        if (vf.n) { char *s = join(&vf, ","); sv_add(&mid, "-vf"); sv_add(&mid, s); free(s); }
        video_args(e, t, o, dur, hw, nhw, 0, &mid, enc, sizeof enc);
        snprintf(j->encoder, sizeof j->encoder, "%s", enc);
        encoded = 1;
    }
    int loud = obool(o, "loudnorm", 0) && strcmp(t, "gif") && !copied;
    strv cmd = {0};
#define BUILD() do { sv_free(&cmd); sv_cat(&cmd, &head); sv_cat(&cmd, &mid); if (loud) { sv_add(&cmd, "-af"); sv_add(&cmd, "loudnorm=I=-16:TP=-1.5:LRA=11"); } sv_add(&cmd, j->output); } while (0)
    BUILD();
    int rc = run_job_proc(e, j, &cmd, dur, NULL, 0, 1);
    /* GPU failure: same command with the CPU encoder */
    if (rc > 0 && encoded && (!strcmp(enc, "h264_nvenc") || !strcmp(enc, "h264_qsv") || !strcmp(enc, "h264_amf"))) {
        sv_free(&mid);
        if (vf.n) { char *s = join(&vf, ","); sv_add(&mid, "-vf"); sv_add(&mid, s); free(s); }
        jval *o2 = json_clone(o); jobj_set(o2, "hwaccel", jbool(0));
        video_args(e, t, o2, dur, NULL, 0, 0, &mid, enc, sizeof enc);
        json_free(o2);
        snprintf(j->encoder, sizeof j->encoder, "%s（GPU 失敗改用 CPU）", enc);
        BUILD();
        rc = run_job_proc(e, j, &cmd, dur, NULL, 0, 1);
    }
    if (rc == -2) goto out;
    if (rc != 0) { char m[600]; ff_error(j->err, m, sizeof m, "ffmpeg 失敗"); fail(j, m); goto out; }
    /* target size is a promise: if the encoder overshot, redo once in strict bitrate mode, scaled down */
    if (tmb > 0 && !is_audio_t && strcmp(t, "gif") && encoded && file_size(j->output) > tmb * MB) {
        double got = file_size(j->output) / MB;
        sv_free(&mid);
        if (vf.n) { char *s = join(&vf, ","); sv_add(&mid, "-vf"); sv_add(&mid, s); free(s); }
        char prev[64]; snprintf(prev, sizeof prev, "%s", enc);
        char *usehw[1] = { prev };
        int gpu = !strncmp(prev, "h264_", 5);
        video_args(e, t, o, dur, gpu ? usehw : NULL, gpu ? 1 : 0, tmb / got * 0.97, &mid, enc, sizeof enc);
        snprintf(j->encoder, sizeof j->encoder, "%s（第一次 %.1f MB 超過目標，已重壓）", enc, got);
        BUILD();
        rc = run_job_proc(e, j, &cmd, dur, NULL, 0, 1);
        if (rc == -2) goto out;
        if (rc != 0) { char m[600]; ff_error(j->err, m, sizeof m, "ffmpeg 失敗"); fail(j, m); goto out; }
    }
    /* re-encoded result bigger than the source and nothing was asked to change: keep the original streams */
    if (!j->merge && !ss && !to && !h && !tmb && !obool(o, "loudnorm", 0) && !strcmp(codec, "auto") &&
        (!strcmp(t, "mp4") || !strcmp(t, "mkv") || !strcmp(t, "mov")) && encoded && obool(o, "fastcopy", 1) &&
        file_size(j->output) > file_size(src) && streams_copyable(info, t)) {
        strv c2 = {0};
        sv_add(&c2, e->ffmpeg); sv_add(&c2, "-hide_banner"); sv_add(&c2, "-nostdin"); sv_add(&c2, "-y"); sv_add(&c2, "-v"); sv_add(&c2, "error");
        sv_add(&c2, "-i"); sv_add(&c2, src); sv_add(&c2, "-map"); sv_add(&c2, "0"); sv_add(&c2, "-c"); sv_add(&c2, "copy");
        if (strcmp(t, "mkv")) { sv_add(&c2, "-movflags"); sv_add(&c2, "+faststart"); }
        sv_add(&c2, j->output);
        if (run_capture((const char *const *)c2.v, NULL, NULL, NULL, 0, NULL) == 0) snprintf(j->encoder, sizeof j->encoder, "保留原始編碼（重新編碼反而較大）");
        sv_free(&c2);
    }
out:
#undef BUILD
    sv_free(&cmd); sv_free(&head); sv_free(&mid); sv_free(&vf);
}

/* ================================================================== other converters */
static int run_simple(engine *e, job *j, strv *cmd, const char *what, const char *cwd)
{
    int rc = run_job_proc(e, j, cmd, 0, cwd, 0, 1);
    if (rc == -2) return 0;
    if (rc != 0) {
        const char *src = j->err && j->err[0] ? j->err : "";
        char lastl[300] = "";
        for (const char *l = src; *l;) { const char *nl = strchr(l, '\n'); size_t n = nl ? (size_t)(nl - l) : strlen(l); while (n && (l[n-1] == '\r' || l[n-1] == ' ')) n--; if (n) snprintf(lastl, sizeof lastl, "%.*s", (int)(n < 200 ? n : 200), l); l = nl ? nl + 1 : l + strlen(l); }
        char m[600]; snprintf(m, sizeof m, "%s 失敗：%s", what, lastl);
        fail(j, m);
        return 0;
    }
    return 1;
}

static void conv_subtitle(engine *e, job *j)
{
    const char *src = j->files[0];
    if (!e->ffmpeg) { fail(j, "找不到 ffmpeg（tools 資料夾）"); return; }
    j->output = out_path(e, j, src, j->target);
    char *tmp = NULL, *in = str_dup(src);
    if (!strcmp(j->cat, "subtitle")) {      /* Big5 / GBK / UTF-16 subtitles are common; ffmpeg reads UTF-8 */
        tmp = make_temp_dir("zdgc_s_");
        char ext[32]; ext_of(src, ext, sizeof ext);
        char *name = str_fmt("in.%s", ext);
        free(in); in = path_join(tmp, name); free(name);
        size_t n; char *raw = read_file(src, &n);
        char *u = raw ? text_to_utf8(raw, n) : str_dup("");
        write_file(in, u, strlen(u)); free(raw); free(u);
    }
    strv cmd = {0};
    sv_add(&cmd, e->ffmpeg); sv_add(&cmd, "-hide_banner"); sv_add(&cmd, "-nostdin"); sv_add(&cmd, "-v"); sv_add(&cmd, "error"); sv_add(&cmd, "-y"); sv_add(&cmd, "-i"); sv_add(&cmd, in);
    if (!strcmp(j->cat, "video")) { sv_add(&cmd, "-map"); sv_add(&cmd, "0:s:0"); }
    sv_add(&cmd, j->output);
    if (run_simple(e, j, &cmd, "字幕轉換（影片需內含字幕軌）", NULL)) snprintf(j->encoder, sizeof j->encoder, "FFmpeg");
    sv_free(&cmd);
    if (tmp) { remove_tree(tmp); free(tmp); }
    free(in);
}

static void conv_archive(engine *e, job *j)
{
    const char *src = j->files[0];
    if (!e->sevenzip) { fail(j, "缺少 7-Zip 元件"); return; }
    if (!strcmp(j->target, "extract")) {
        const char *b = path_base(src); char *stem = NULL;
        static const char *dbl[] = { ".tar.gz", ".tar.xz", ".tar.bz2", ".tgz", NULL };
        for (int i = 0; dbl[i]; i++) if (str_ends(b, dbl[i])) { stem = str_fmt("%.*s", (int)(strlen(b) - strlen(dbl[i])), b); break; }
        if (!stem) stem = stem_of(src);
        const char *od = ostr(j->opt, "out_dir", "");
        char *folder = od[0] ? str_dup(od) : path_dir(src);
        char *want = path_join(folder, stem);
        j->output = unique_path(e, want, j->files, j->nfiles);
        free(stem); free(folder); free(want);
        strv cmd = {0};
        sv_add(&cmd, e->sevenzip); sv_add(&cmd, "x"); sv_add(&cmd, "-y"); sv_add(&cmd, "-bso0"); sv_add(&cmd, "-bsp0"); sv_addf(&cmd, "-o%s", j->output); sv_add(&cmd, src);
        int ok = run_simple(e, j, &cmd, "解壓縮", NULL);
        sv_free(&cmd);
        if (!ok) return;
        char **names; int n = dir_list(j->output, &names);
        if (n == 1 && str_ends(names[0], ".tar")) {
            char *tar = path_join(j->output, names[0]);
            sv_add(&cmd, e->sevenzip); sv_add(&cmd, "x"); sv_add(&cmd, "-y"); sv_add(&cmd, "-bso0"); sv_addf(&cmd, "-o%s", j->output); sv_add(&cmd, tar);
            if (run_simple(e, j, &cmd, "解壓縮", NULL)) remove_file(tar);
            sv_free(&cmd); free(tar);
        }
        free_list(names, n);
    } else {
        j->output = out_path(e, j, src, j->target);
        const char *pr = ostr(j->opt, "preset", "balanced");
        const char *lvl = !strcmp(pr, "balanced") ? "5" : "9";
        char *tmp = make_temp_dir("zdgc_repack_");
        strv cmd = {0};
        sv_add(&cmd, e->sevenzip); sv_add(&cmd, "x"); sv_add(&cmd, "-y"); sv_add(&cmd, "-bso0"); sv_add(&cmd, "-bsp0"); sv_addf(&cmd, "-o%s", tmp); sv_add(&cmd, src);
        int ok = run_simple(e, j, &cmd, "解開來源壓縮檔", NULL); sv_free(&cmd);
        if (ok) {
            char **names; int n = dir_list(tmp, &names);
            if (n == 1 && str_ends(names[0], ".tar")) {
                char *tar = path_join(tmp, names[0]);
                sv_add(&cmd, e->sevenzip); sv_add(&cmd, "x"); sv_add(&cmd, "-y"); sv_add(&cmd, "-bso0"); sv_addf(&cmd, "-o%s", tmp); sv_add(&cmd, tar);
                ok = run_simple(e, j, &cmd, "解開 TAR", NULL); sv_free(&cmd);
                if (ok) remove_file(tar);
                free(tar);
            }
            free_list(names, n);
            n = dir_list(tmp, &names); free_list(names, n);
            if (ok && !n) { fail(j, "來源壓縮檔沒有內容"); ok = 0; }
            if (ok) {
                sv_add(&cmd, e->sevenzip); sv_add(&cmd, "a"); sv_add(&cmd, "-bso0"); sv_add(&cmd, "-bsp0"); sv_addf(&cmd, "-mx=%s", lvl); sv_add(&cmd, "-mmt=on");
                sv_add(&cmd, j->output); sv_add(&cmd, "." PSEP_S "*");
                run_simple(e, j, &cmd, "重新壓縮", tmp); sv_free(&cmd);
            }
        }
        remove_tree(tmp); free(tmp);
    }
    if (j->state != Q_ERROR) snprintf(j->encoder, sizeof j->encoder, "7-Zip");
}

/* file:// URI for LibreOffice's -env:UserInstallation (percent-encoded UTF-8) */
static char *file_uri(const char *path)
{
    sbuf b = {0}; sb_str(&b, path[0] == '/' ? "file://" : "file:///");
    for (const unsigned char *p = (const unsigned char *)path; *p; p++) {
        if (*p == '\\') sb_str(&b, "/");
        else if (isalnum(*p) || strchr("/-_.~:", *p)) { char c = (char)*p; sb_add(&b, &c, 1); }
        else sb_printf(&b, "%%%02X", *p);
    }
    return b.p;
}

static THREAD_LOCAL int lo_slot = -1;
static int lo_next;

/* one LibreOffice profile per worker thread, kept between jobs: a fresh one costs seconds of setup */
static char *lo_profile(engine *e)
{
    if (lo_slot < 0) { mutex_lock(e->m); lo_slot = lo_next++; mutex_unlock(e->m); }
    char *tmp = env_get("TEMP");
    if (!tmp) tmp = env_get("TMPDIR");
    if (!tmp) tmp = str_dup("/tmp");
    char *d = str_fmt("%s%czdgc_native_lo%cp%d", tmp, PSEP, PSEP, lo_slot);
    make_dirs(d);
    char *u = file_uri(d);
    free(tmp); free(d);
    return u;
}

static void conv_office(engine *e, job *j)
{
    if (!e->soffice) { fail(j, "需要 LibreOffice 才能轉這個格式"); return; }
    if (!acquire(e, &e->office_slots, j, "等待 Office 轉換元件")) return;
    const char *src = j->files[0], *t = j->target;
    j->output = out_path(e, j, src, t);
    char *tmp = make_temp_dir("zdgc_");
    char ext[32]; ext_of(src, ext, sizeof ext);
    char conv[1024];
    if (!strcmp(t, "pdf")) {
        const preset_t *p = preset_of(j->opt);
        static const char *calc[] = { "xls", "xlsx", "ods", "csv", NULL }, *impress[] = { "ppt", "pptx", "odp", NULL };
        const char *filt = in_list(calc, ext) ? "calc_pdf_Export" : in_list(impress, ext) ? "impress_pdf_Export" : "writer_pdf_Export";
        snprintf(conv, sizeof conv, "pdf:%s:{\"Quality\":{\"type\":\"long\",\"value\":\"%d\"},\"ReduceImageResolution\":{\"type\":\"boolean\",\"value\":\"true\"},"
                 "\"MaxImageResolution\":{\"type\":\"long\",\"value\":\"%d\"},\"UseLosslessCompression\":{\"type\":\"boolean\",\"value\":\"false\"}}", filt, p->pdfq, p->pdfdpi);
    } else snprintf(conv, sizeof conv, "%s", t);
    char *profile = lo_profile(e);
    char *found = NULL;
    for (int attempt = 0; attempt < 2 && !found && !j->cancelled; attempt++) {
        if (attempt && !strcmp(conv, t)) break;
        strv cmd = {0};
        sv_add(&cmd, e->soffice); sv_addf(&cmd, "-env:UserInstallation=%s", profile); sv_add(&cmd, "--headless"); sv_add(&cmd, "--norestore"); sv_add(&cmd, "--nolockcheck");
        sv_add(&cmd, "--convert-to"); sv_add(&cmd, attempt ? t : conv); sv_add(&cmd, "--outdir"); sv_add(&cmd, tmp); sv_add(&cmd, src);
        run_job_proc(e, j, &cmd, 0, NULL, 0, 1);
        sv_free(&cmd);
        char **names; int n = dir_list(tmp, &names);
        char suffix[40]; snprintf(suffix, sizeof suffix, ".%s", t);
        for (int i = 0; i < n && !found; i++) if (str_ends(names[i], suffix)) found = path_join(tmp, names[i]);
        free_list(names, n);
    }
    if (!j->cancelled) {
        if (found && move_file(found, j->output)) snprintf(j->encoder, sizeof j->encoder, "LibreOffice");
        else fail(j, "LibreOffice 轉換失敗");
    }
    free(found); free(profile);
    remove_tree(tmp); free(tmp);
    release(e, &e->office_slots);
}

static void conv_doc(engine *e, job *j)
{
    char ext[32]; ext_of(j->files[0], ext, sizeof ext);
    const char *t = j->target;
    static const char *pandoc_out[] = { "docx", "odt", "html", "md", "txt", "epub", "rtf", NULL };
    if (e->pandoc && in_list(PANDOC_IN, ext) && in_list(pandoc_out, t)) {
        j->output = out_path(e, j, j->files[0], t);
        const char *fmt = !strcmp(t, "md") ? "gfm" : !strcmp(t, "txt") ? "plain" : t;
        const char *fin = !strcmp(ext, "md") || !strcmp(ext, "markdown") || !strcmp(ext, "txt") ? "markdown" : !strcmp(ext, "htm") ? "html" : !strcmp(ext, "tex") ? "latex" : ext;
        char *dir = path_dir(j->files[0]);
        strv cmd = {0};
        sv_add(&cmd, e->pandoc); sv_add(&cmd, j->files[0]); sv_add(&cmd, "-f"); sv_add(&cmd, fin); sv_add(&cmd, "-t"); sv_add(&cmd, fmt);
        sv_add(&cmd, "-o"); sv_add(&cmd, j->output); sv_add(&cmd, "--resource-path"); sv_add(&cmd, dir);
        if (!strcmp(t, "html") || !strcmp(t, "epub")) sv_add(&cmd, "--standalone");
        if (run_simple(e, j, &cmd, "Pandoc", NULL)) snprintf(j->encoder, sizeof j->encoder, "Pandoc");
        sv_free(&cmd); free(dir);
        return;
    }
    conv_office(e, j);
}

static void conv_ebook(engine *e, job *j)
{
    if (!e->calibre) { conv_doc(e, j); return; }
    if (!acquire(e, &e->office_slots, j, "等待電子書轉換元件")) return;
    j->output = out_path(e, j, j->files[0], j->target);
    strv cmd = {0};
    sv_add(&cmd, e->calibre); sv_add(&cmd, j->files[0]); sv_add(&cmd, j->output);
    if (run_simple(e, j, &cmd, "Calibre", NULL)) snprintf(j->encoder, sizeof j->encoder, "Calibre");
    sv_free(&cmd);
    release(e, &e->office_slots);
}

/* ================================================================== output checks */
static int check_file(engine *e, job *j, const char *path, const jval *opt, char *detail, size_t dn)
{
    long long size = file_size(path);
    if (size <= 0) { fail(j, "輸出檔案是空的"); return 0; }
    double cap = onum(opt, "target_mb");
    if (cap > 0 && size > cap * MB) {
        char m[300]; snprintf(m, sizeof m, "未達目標大小：實際 %.3f MB，目標 %g MB。請降低解析度或提高容量上限；已保留成品供檢查。", size / MB, cap);
        fail(j, m); j->keep_output = 1; return 0;
    }
    const char *cat = eng_category(path);
    snprintf(detail, dn, "檔案已產生");
    if (cat && (!strcmp(cat, "video") || !strcmp(cat, "audio"))) {
        const probe_t *info = probe(e, path);
        if (!info->nstreams) { fail(j, "輸出沒有可讀取的影音串流"); return 0; }
        if (!strcmp(cat, "video") && !has_stream(info, "video")) { fail(j, "輸出沒有影像軌"); return 0; }
        const char *codec = ostr(opt, "codec", "auto");
        char ext[32]; ext_of(path, ext, sizeof ext);
        if (strcmp(codec, "auto") && (!strcmp(ext, "mp4") || !strcmp(ext, "mov") || !strcmp(ext, "mkv"))) {
            int ok = 0; for (int i = 0; i < info->nstreams; i++) if (!strcmp(info->streams[i][0], "video") && !strcmp(info->streams[i][1], codec)) ok = 1;
            if (!ok) { fail(j, "影片編碼未符合指定格式"); return 0; }
        }
        if (obool(opt, "verify_full", 0)) {
            strv cmd = {0};
            sv_add(&cmd, e->ffmpeg); sv_add(&cmd, "-hide_banner"); sv_add(&cmd, "-nostdin"); sv_add(&cmd, "-v"); sv_add(&cmd, "error"); sv_add(&cmd, "-xerror");
            sv_add(&cmd, "-i"); sv_add(&cmd, path); sv_add(&cmd, "-map"); sv_add(&cmd, "0:v?"); sv_add(&cmd, "-map"); sv_add(&cmd, "0:a?"); sv_add(&cmd, "-f"); sv_add(&cmd, "null"); sv_add(&cmd, "-");
            int ok = run_simple(e, j, &cmd, "完整影音解碼檢查", NULL); sv_free(&cmd);
            if (!ok) return 0;
            snprintf(detail, dn, "完整解碼檢查通過");
        } else snprintf(detail, dn, "影音串流可讀取（未做全片解碼）");
    } else if (cat && !strcmp(cat, "pdf")) {
        size_t n; char *d = read_file(path, &n);
        int ok = d && n > 8 && !strncmp(d, "%PDF-", 5);
        int eof = 0;
        for (size_t i = n > 2048 ? n - 2048 : 0; d && i + 5 <= n; i++) if (!memcmp(d + i, "%%EOF", 5)) eof = 1;
        free(d);
        if (!ok || !eof) { fail(j, "PDF 結構不完整"); return 0; }
        snprintf(detail, dn, "PDF 結構可讀取");
    } else if (cat && !strcmp(cat, "archive") && e->sevenzip) {
        strv cmd = {0};
        sv_add(&cmd, e->sevenzip); sv_add(&cmd, "t"); sv_add(&cmd, "-bso0"); sv_add(&cmd, "-bsp0"); sv_add(&cmd, path);
        int ok = run_simple(e, j, &cmd, "壓縮檔完整性檢查", NULL); sv_free(&cmd);
        if (!ok) return 0;
        snprintf(detail, dn, "壓縮檔完整性檢查通過");
    }
    if (cap > 0) { size_t l = strlen(detail); snprintf(detail + l, dn - l, " · 容量符合上限"); }
    return 1;
}

static int validate(engine *e, job *j)
{
    if (!j->output || !path_exists(j->output)) { fail(j, "沒有產生輸出檔案"); return 0; }
    char detail[300];
    if (is_dir(j->output)) {
        /* every file below the output folder */
        int count = 0, ok = 1;
        char **stack = (char **)malloc(sizeof(char *) * 4096); int sp = 0;
        stack[sp++] = str_dup(j->output);
        jval *none = jnew(J_OBJ);
        while (sp && ok) {
            char *d = stack[--sp];
            char **names; int n = dir_list(d, &names);
            for (int i = 0; i < n && ok; i++) {
                char *c = path_join(d, names[i]);
                if (is_dir(c)) { if (sp < 4096) stack[sp++] = c; else free(c); continue; }
                count++;
                if (j->cancelled || !check_file(e, j, c, none, detail, sizeof detail)) ok = 0;
                free(c);
            }
            free_list(names, n); free(d);
        }
        while (sp) free(stack[--sp]);
        free(stack); json_free(none);
        if (!ok) return 0;
        if (!count) { fail(j, "輸出資料夾是空的"); return 0; }
        snprintf(j->validation, sizeof j->validation, "已檢查 %d 個輸出檔案", count);
        return 1;
    }
    if (!check_file(e, j, j->output, j->opt, detail, sizeof detail)) { snprintf(j->validation, sizeof j->validation, "未通過輸出檢查"); return 0; }
    snprintf(j->validation, sizeof j->validation, "%s", detail);
    return 1;
}

static int check_space(job *j)
{
    const char *od = ostr(j->opt, "out_dir", "");
    char *folder = od[0] ? str_dup(od) : is_file(j->files[0]) ? path_dir(j->files[0]) : str_dup("");
    if (!folder[0] || !is_dir(folder)) { free(folder); return 1; }
    long long freeb = disk_free(folder);
    static const char *big[] = { "extract", "wav", "flac", "avi", "bmp", "tiff", NULL };
    long long need = 200LL * 1048576 + (in_list(big, j->target) ? j->in_size : 0);
    if (freeb >= 0 && freeb < need) {
        char m[600]; snprintf(m, sizeof m, "磁碟空間不足：%s 只剩 %.0f MB，請清出空間或在「儲存位置」改存到其他磁碟", folder, freeb / MB);
        fail(j, m); free(folder); return 0;
    }
    free(folder);
    return 1;
}

/* ================================================================== running a job */
static void run_job(engine *e, job *j)
{
    j->state = Q_RUNNING; j->started = now_s(); j->msg[0] = 0;
    char ext[32]; ext_of(j->files[0], ext, sizeof ext);
    const char *why = unsupported_why(ext);
    if (!check_space(j)) {}
    else if (why && (!strcmp(ext, "kfx") || !strcmp(ext, "key") || !strcmp(ext, "numbers"))) fail(j, why);
    else if (!strcmp(j->cat, "video") && !strcmp(j->target, "srt")) conv_subtitle(e, j);
    else if (!strcmp(j->cat, "video") || !strcmp(j->cat, "audio")) conv_ffmpeg(e, j);
    else if (!strcmp(j->cat, "subtitle")) conv_subtitle(e, j);
    else if (!strcmp(j->cat, "archive")) conv_archive(e, j);
    else if (!strcmp(j->cat, "doc") || !strcmp(j->cat, "sheet")) conv_doc(e, j);
    else if (!strcmp(j->cat, "ebook")) conv_ebook(e, j);
    else fail(j, "無法辨識來源檔案類型");

    if (j->cancelled) {
        j->state = Q_CANCELLED; snprintf(j->msg, sizeof j->msg, "已取消");
        if (j->output && is_file(j->output)) remove_file(j->output);
    } else if (j->state == Q_RUNNING && validate(e, j)) {
        j->state = Q_DONE; j->progress = 1; snprintf(j->msg, sizeof j->msg, "完成"); j->eta = 0; j->has_eta = 1;
    }
    if (j->state == Q_ERROR) {
        if (j->output && is_file(j->output) && !j->keep_output) remove_file(j->output);
        sbuf b = {0};
        sb_printf(&b, "FAIL %s [", j->target);
        for (int i = 0; i < j->nfiles; i++) sb_printf(&b, "%s%s", i ? ", " : "", j->files[i]);
        sb_printf(&b, "] -> %s\n  msg: %s\n  stderr: ", j->output ? j->output : "", j->msg);
        if (j->err) { size_t n = strlen(j->err); sb_str(&b, j->err + (n > 1500 ? n - 1500 : 0)); }
        elog(e, b.p); free(b.p);
    }
    j->elapsed = now_s() - j->started;
    if (j->output) j->out_size = is_dir(j->output) ? tree_size(j->output) : file_size(j->output) < 0 ? 0 : file_size(j->output);
    j->finished = now_s();
}

typedef struct { engine *e; int heavy; } worker_arg;

static void worker(void *arg)
{
    worker_arg *w = (worker_arg *)arg;
    engine *e = w->e;
    for (;;) {
        mutex_lock(e->m);
        job *j = NULL;
        while (!e->stopping) {
            for (int i = 0; i < e->njobs; i++)
                if (e->jobs[i]->heavy == w->heavy && !e->jobs[i]->taken && e->jobs[i]->state == Q_QUEUED) { j = e->jobs[i]; break; }
            if (j) break;
            cond_wait_ms(e->qc, e->m, 1000);
        }
        if (e->stopping) { mutex_unlock(e->m); return; }
        j->taken = 1; j->busy = 1;
        mutex_unlock(e->m);
        int quiet = !strcmp(ostr(j->opt, "resource_mode", "auto"), "quiet"), heavy = j->heavy, ran = 0;
        if (!j->cancelled && (!quiet || acquire(e, &e->quiet_slots, j, "省資源模式：等待前一個工作"))) {
            if (acquire(e, &e->slots, j, "等待可用處理資源")) {
                if (heavy) { mutex_lock(e->m); e->enc_active++; mutex_unlock(e->m); }
                run_job(e, j); ran = 1;
                if (heavy) { mutex_lock(e->m); e->enc_active--; mutex_unlock(e->m); }
                release(e, &e->slots);
            }
            if (quiet) release(e, &e->quiet_slots);
        }
        (void)ran;
        mutex_lock(e->m); j->busy = 0; mutex_unlock(e->m);
    }
}

/* ================================================================== API */
engine *engine_new(const char *base, const char *data)
{
    engine *e = (engine *)calloc(1, sizeof *e);
    G = e;
    e->base = str_dup(base); e->data = str_dup(data);
    e->ffmpeg = tool_path(base, "ffmpeg.exe");
    e->sevenzip = tool_path(base, "7z.exe");
    e->pandoc = tool_path(base, "pandoc.exe");
    e->soffice = tool_path(base, "libreoffice/program/soffice.exe");
    e->calibre = tool_path(base, "calibre/ebook-convert.exe");
    e->m = mutex_new(); e->qc = cond_new();
    e->slots = work_slots(); e->quiet_slots = 1; e->office_slots = mem_gb() <= 8.5 ? 1 : 2;
    e->heavy_workers = auto_workers(); e->light_workers = light_workers();
    for (int i = 0; i < e->heavy_workers + e->light_workers; i++) {
        worker_arg *w = (worker_arg *)malloc(sizeof *w); w->e = e; w->heavy = i < e->heavy_workers;
        thread_start(worker, w);
    }
    thread_start(hw_thread, e);
    return e;
}

void engine_shutdown(engine *e)
{
    eng_cancel_all(e);
    mutex_lock(e->m); e->stopping = 1; cond_broadcast(e->qc); mutex_unlock(e->m);
}

static job *find_job(engine *e, const char *id) { for (int i = 0; i < e->njobs; i++) if (!strcmp(e->jobs[i]->id, id)) return e->jobs[i]; return NULL; }

static job *new_job(engine *e, char **files, int nfiles, const char *target, const jval *opt, int merge)
{
    job *j = (job *)calloc(1, sizeof *j);
    mutex_lock(e->m); unsigned n = ++e->seq; mutex_unlock(e->m);
    snprintf(j->id, sizeof j->id, "x%07x", (unsigned)((n * 2654435761u) ^ (unsigned)(now_s() * 1000)) & 0xfffffffu);
    j->files = (char **)malloc(sizeof(char *) * (size_t)nfiles);
    for (int i = 0; i < nfiles; i++) { j->files[i] = path_abs(files[i]); long long s = file_size(j->files[i]); if (s > 0) j->in_size += s; }
    j->nfiles = nfiles;
    snprintf(j->target, sizeof j->target, "%s", target);
    const char *cat = eng_category(j->files[0]);
    snprintf(j->cat, sizeof j->cat, "%s", cat ? cat : "");
    j->opt = opt ? json_clone(opt) : jnew(J_OBJ);
    j->merge = merge;
    j->heavy = (!strcmp(j->cat, "video") || !strcmp(j->cat, "audio")) && !(!strcmp(j->cat, "video") && !strcmp(target, "srt"));
    j->created = now_s();
    return j;
}

static void enqueue(engine *e, job *j)
{
    mutex_lock(e->m);
    if (e->njobs == e->cap) { e->cap = e->cap ? e->cap * 2 : 64; e->jobs = (job **)realloc(e->jobs, sizeof(job *) * (size_t)e->cap); }
    e->jobs[e->njobs++] = j;
    cond_broadcast(e->qc);
    mutex_unlock(e->m);
}

jval *eng_submit(engine *e, const jval *files, const char *target, const jval *opt, int merge)
{
    jval *ids = jnew(J_ARR);
    int n = files && files->type == J_ARR ? (int)files->len : 0;
    char **list = (char **)calloc((size_t)(n ? n : 1), sizeof(char *));
    int k = 0;
    for (int i = 0; i < n; i++) if (files->items[i]->type == J_STR) list[k++] = files->items[i]->str;
    if (k && merge) { job *j = new_job(e, list, k, target, opt, 1); jarr_push(ids, jstr(j->id)); enqueue(e, j); }
    else for (int i = 0; i < k; i++) { job *j = new_job(e, &list[i], 1, target, opt, 0); jarr_push(ids, jstr(j->id)); enqueue(e, j); }
    free(list);
    return ids;
}

static jval *job_info(const job *j)
{
    jval *o = jnew(J_OBJ);
    const char *b = path_base(j->files[0]);
    char name[1024];
    snprintf(name, sizeof name, "%s", *b ? b : j->files[0]);
    if (j->merge && j->nfiles > 1) { size_t l = strlen(name); snprintf(name + l, sizeof name - l, " 等 %d 個", j->nfiles); }
    jobj_set(o, "id", jstr(j->id)); jobj_set(o, "name", jstr(name)); jobj_set(o, "target", jstr(j->target));
    jobj_set(o, "label", jstr("")); jobj_set(o, "kind", jstr("")); jobj_set(o, "state", jstr(STATE_NAME[j->state]));
    jobj_set(o, "progress", jnum(floor((j->progress > 1 ? 1 : j->progress) * 1000 + 0.5) / 1000));
    jobj_set(o, "speed", jstr(j->speed));
    jobj_set(o, "eta", j->has_eta ? jnum(j->eta) : jnew(J_NULL));
    jobj_set(o, "msg", jstr(j->msg)); jobj_set(o, "output", jstr(j->output ? j->output : ""));
    jobj_set(o, "encoder", jstr(j->encoder));
    jobj_set(o, "elapsed", jnum(floor(j->elapsed * 100 + 0.5) / 100));
    jobj_set(o, "in_size", jnum((double)j->in_size)); jobj_set(o, "out_size", jnum((double)j->out_size));
    jobj_set(o, "finished", jnum(j->finished)); jobj_set(o, "retry", jbool(1));
    jobj_set(o, "validation", jstr(j->validation)); jobj_set(o, "notes", jnew(J_ARR));
    jobj_set(o, "created", jnum(j->created));
    return o;
}

jval *eng_status(engine *e, int tail)
{
    jval *arr = jnew(J_ARR);
    mutex_lock(e->m);
    int cut = tail > 0 && e->njobs > tail ? e->njobs - tail : 0;
    for (int i = 0; i < e->njobs; i++) if (i >= cut || e->jobs[i]->state == Q_RUNNING) jarr_push(arr, job_info(e->jobs[i]));
    mutex_unlock(e->m);
    return arr;
}

int eng_active(engine *e)
{
    int n = 0;
    mutex_lock(e->m);
    for (int i = 0; i < e->njobs; i++) if (e->jobs[i]->state == Q_QUEUED || e->jobs[i]->state == Q_RUNNING) n++;
    mutex_unlock(e->m);
    return n;
}

int eng_owns(engine *e, const char *id) { mutex_lock(e->m); int r = find_job(e, id) != NULL; mutex_unlock(e->m); return r; }

void eng_cancel(engine *e, const char *id)
{
    mutex_lock(e->m);
    job *j = find_job(e, id);
    if (j && (j->state == Q_QUEUED || j->state == Q_RUNNING)) {
        j->cancelled = 1;
        if (j->state == Q_QUEUED) { j->state = Q_CANCELLED; snprintf(j->msg, sizeof j->msg, "已取消"); }
        if (j->proc) proc_kill(j->proc);
    }
    cond_broadcast(e->qc);
    mutex_unlock(e->m);
}

void eng_cancel_all(engine *e)
{
    mutex_lock(e->m);
    for (int i = 0; i < e->njobs; i++) {
        job *j = e->jobs[i];
        if (j->state != Q_QUEUED && j->state != Q_RUNNING) continue;
        j->cancelled = 1;
        if (j->state == Q_QUEUED) { j->state = Q_CANCELLED; snprintf(j->msg, sizeof j->msg, "已取消"); }
        if (j->proc) proc_kill(j->proc);
    }
    cond_broadcast(e->qc);
    mutex_unlock(e->m);
}

static void free_job(job *j)
{
    for (int i = 0; i < j->nfiles; i++) free(j->files[i]);
    free(j->files); json_free(j->opt); free(j->output); free(j->err); free(j);
}

void eng_clear_done(engine *e)
{
    mutex_lock(e->m);
    int k = 0;
    for (int i = 0; i < e->njobs; i++) {
        job *j = e->jobs[i];
        if (j->state == Q_QUEUED || j->state == Q_RUNNING || j->busy) e->jobs[k++] = j;
        else free_job(j);
    }
    e->njobs = k;
    mutex_unlock(e->m);
}

char *eng_retry(engine *e, const char *id)
{
    mutex_lock(e->m);
    job *old = find_job(e, id);
    if (!old || old->state == Q_QUEUED || old->state == Q_RUNNING || old->busy) { mutex_unlock(e->m); return NULL; }
    job *j = new_job(e, old->files, old->nfiles, old->target, old->opt, old->merge);
    if (old->state != Q_DONE) {          /* the failed / cancelled entry is replaced by the new attempt */
        for (int i = 0; i < e->njobs; i++) if (e->jobs[i] == old) { memmove(&e->jobs[i], &e->jobs[i + 1], sizeof(job *) * (size_t)(e->njobs - i - 1)); e->njobs--; break; }
        free_job(old);
    }
    mutex_unlock(e->m);
    enqueue(e, j);
    return str_dup(j->id);
}

/* ---- describe / formats */
static jval *targets_for(engine *e, const char *cat, const char *ext)
{
    jval *t = jnew(J_ARR);
    if (!cat) return t;
    if (!strcmp(ext, "kfx") || !strcmp(ext, "key") || !strcmp(ext, "numbers")) return t;
    const char *list[24]; int n = 0;
#define ADD(x) do { const char *_x = (x); int dup = 0; for (int _i = 0; _i < n; _i++) if (!strcmp(list[_i], _x)) dup = 1; if (!dup && strcmp(_x, ext) && n < 24) list[n++] = _x; } while (0)
    if (!strcmp(cat, "video")) { for (int i = 0; VIDEO_T[i]; i++) list[n++] = VIDEO_T[i]; for (int i = 0; AUDIO_T[i]; i++) list[n++] = AUDIO_T[i]; list[n++] = "srt"; }
    else if (!strcmp(cat, "audio")) { for (int i = 0; AUDIO_T[i]; i++) list[n++] = AUDIO_T[i]; }
    else if (!strcmp(cat, "image")) { for (int i = 0; IMAGE_T[i]; i++) list[n++] = IMAGE_T[i]; }
    else if (!strcmp(cat, "pdf")) { list[n++] = "png"; list[n++] = "jpg"; list[n++] = "pdf"; if (e->calibre) { list[n++] = "docx"; list[n++] = "epub"; } list[n++] = "txt"; }
    else if (!strcmp(cat, "doc")) {
        static const char *pd[] = { "docx", "odt", "html", "md", "txt", "epub", "rtf", NULL };
        if (in_list(PANDOC_IN, ext) && e->pandoc) for (int i = 0; pd[i]; i++) ADD(pd[i]);
        if (e->soffice) { ADD("pdf"); if (strcmp(ext, "docx")) ADD("docx"); }
    } else if (!strcmp(cat, "sheet")) {
        static const char *calc[] = { "xls", "xlsx", "ods", "csv", NULL }, *imp[] = { "ppt", "pptx", "odp", NULL };
        if (e->soffice) { ADD("pdf"); if (in_list(calc, ext)) { ADD("xlsx"); ADD("ods"); ADD("csv"); } if (in_list(imp, ext)) { ADD("pptx"); ADD("odp"); } }
    } else if (!strcmp(cat, "ebook")) {
        static const char *cb[] = { "epub", "mobi", "azw3", "pdf", "docx", "txt", NULL }, *pd[] = { "docx", "html", "md", "txt", "odt", NULL };
        if (e->calibre) for (int i = 0; cb[i]; i++) ADD(cb[i]);
        else if (in_list(PANDOC_IN, ext) && e->pandoc) for (int i = 0; pd[i]; i++) ADD(pd[i]);
    } else if (!strcmp(cat, "archive")) { if (e->sevenzip) { list[n++] = "extract"; list[n++] = "zip"; list[n++] = "7z"; } }
    else if (!strcmp(cat, "subtitle")) { ADD("srt"); ADD("ass"); ADD("vtt"); }
    else if (!strcmp(cat, "model")) { ADD("glb"); ADD("obj"); ADD("stl"); ADD("ply"); }
#undef ADD
    for (int i = 0; i < n; i++) {
        int removed = 0;
        for (int r = 0; REMOVED[r][0]; r++) if (!strcmp(REMOVED[r][0], ext) && !strcmp(REMOVED[r][1], list[i])) removed = 1;
        if (!removed) jarr_push(t, jstr(list[i]));
    }
    return t;
}

static int jhas(const jval *arr, const char *s) { for (size_t i = 0; i < arr->len; i++) if (!strcmp(arr->items[i]->str, s)) return 1; return 0; }

static const char *suggest(const char *cat, const char *ext, const jval *t)
{
    if (!t->len) return NULL;
    const char *pref = NULL;
    if (!strcmp(cat, "doc")) pref = jhas(t, "pdf") ? "pdf" : "docx";
    else if (!strcmp(cat, "sheet")) pref = "pdf";
    else if (!strcmp(cat, "ebook")) pref = jhas(t, "epub") ? "epub" : "docx";
    else if (!strcmp(cat, "archive")) pref = "extract";
    else if (!strcmp(cat, "subtitle")) pref = strcmp(ext, "srt") ? "srt" : "vtt";
    else if (!strcmp(cat, "model")) pref = jhas(t, "glb") ? "glb" : jhas(t, "stl") ? "stl" : "obj";
    if (pref && jhas(t, pref)) return pref;
    if (!strcmp(cat, "video")) return strcmp(ext, "mp4") ? "mp4" : "webm";
    if (!strcmp(cat, "audio")) return strcmp(ext, "mp3") ? "mp3" : "m4a";
    if (!strcmp(cat, "image")) return strcmp(ext, "webp") ? "webp" : "png";
    if (!strcmp(cat, "pdf")) return "png";
    return NULL;
}

static void expand(const char *p, jval *out)
{
    if (is_dir(p)) {
        char **names; int n = dir_list(p, &names);
        /* files of a folder first (sorted), then its sub-folders, like os.walk */
        for (int pass = 0; pass < 2; pass++)
            for (int i = 0; i < n; i++) {
                char *c = path_join(p, names[i]);
                int d = is_dir(c);
                if (pass == 0 && !d && eng_category(c)) jarr_push(out, jstr(c));
                else if (pass == 1 && d) expand(c, out);
                free(c);
            }
        free_list(names, n);
    } else if (is_file(p) && eng_category(p)) jarr_push(out, jstr(p));
}

jval *eng_describe(engine *e, const jval *paths)
{
    jval *files = jnew(J_ARR), *out = jnew(J_ARR);
    for (size_t i = 0; paths && paths->type == J_ARR && i < paths->len; i++) if (paths->items[i]->type == J_STR) expand(paths->items[i]->str, files);
    for (size_t i = 0; i < files->len; i++) {
        const char *p = files->items[i]->str;
        char ext[32]; ext_of(p, ext, sizeof ext);
        const char *cat = eng_category(p);
        jval *o = jnew(J_OBJ), *t = targets_for(e, cat, ext);
        long long size = file_size(p);
        const char *sg = suggest(cat, ext, t), *why = unsupported_why(ext);
        jobj_set(o, "path", jstr(p)); jobj_set(o, "name", jstr(path_base(p))); jobj_set(o, "cat", jstr(cat)); jobj_set(o, "ext", jstr(ext));
        jobj_set(o, "size", jnum(size < 0 ? 0 : (double)size)); jobj_set(o, "targets", t);
        jobj_set(o, "suggest", sg ? jstr(sg) : jnew(J_NULL)); jobj_set(o, "note", jstr(why ? why : ""));
        jarr_push(out, o);
    }
    json_free(files);
    return out;
}

jval *eng_formats(engine *e)
{
    static const char *cats[][3] = { {"video","影片","FFmpeg"}, {"audio","音訊","FFmpeg"}, {"image","圖片","Pillow／LibRaw／resvg"}, {"pdf","PDF","PDFium／pypdf"},
        {"doc","文件","Pandoc／LibreOffice"}, {"sheet","試算表／簡報","LibreOffice"}, {"ebook","電子書","Calibre／Pandoc"}, {"archive","壓縮檔","7-Zip"},
        {"subtitle","字幕","FFmpeg"}, {"model","3D 模型","trimesh"}, {NULL} };
    jval *rows = jnew(J_ARR);
    for (int c = 0; cats[c][0]; c++) {
        jval *ins = jnew(J_ARR), *outs = jnew(J_ARR);
        sbuf note = {0}; sb_str(&note, "");
        const char *names[128]; int nn = 0;
        for (const extcat *x = EXTS; x->ext; x++) if (!strcmp(x->cat, cats[c][0])) names[nn++] = x->ext;
        for (int a = 0; a < nn; a++) for (int b = a + 1; b < nn; b++) if (strcmp(names[a], names[b]) > 0) { const char *t = names[a]; names[a] = names[b]; names[b] = t; }
        const char *all[64]; int na = 0;
        for (int i = 0; i < nn; i++) {
            jarr_push(ins, jstr(names[i]));
            jval *t = targets_for(e, cats[c][0], names[i]);
            for (size_t k = 0; k < t->len; k++) { int dup = 0; for (int q = 0; q < na; q++) if (!strcmp(all[q], t->items[k]->str)) dup = 1; if (!dup && na < 64) all[na++] = str_dup(t->items[k]->str); }
            json_free(t);
        }
        for (int a = 0; a < na; a++) for (int b = a + 1; b < na; b++) if (strcmp(all[a], all[b]) > 0) { const char *t = all[a]; all[a] = all[b]; all[b] = t; }
        for (int i = 0; i < na; i++) { jarr_push(outs, jstr(all[i])); free((char *)all[i]); }
        if (!strcmp(cats[c][0], "sheet") && !e->soffice) sb_str(&note, "需安裝 LibreOffice；");
        if (!strcmp(cats[c][0], "doc") && !e->soffice) sb_str(&note, "轉 PDF 與 .doc 需 LibreOffice；");
        if (!strcmp(cats[c][0], "ebook") && !e->calibre) sb_str(&note, "MOBI／AZW3 需 Calibre；EPUB 可用；");
        if (!strcmp(cats[c][0], "ebook")) sb_str(&note, "EPUB 不提供轉 MOBI；");
        if (!strcmp(cats[c][0], "model")) sb_str(&note, "STL 不提供轉 GLB；");
        for (int i = 0; i < nn; i++) { const char *w = unsupported_why(names[i]); if (w) { char up[16]; snprintf(up, sizeof up, "%s", names[i]); for (char *q = up; *q; q++) *q = (char)toupper((unsigned char)*q); sb_printf(&note, "%s：%s；", up, w); } }
        if (note.len >= 3 && !strcmp(note.p + note.len - 3, "；")) note.p[note.len -= 3] = 0;
        jval *row = jnew(J_OBJ);
        jobj_set(row, "cat", jstr(cats[c][1])); jobj_set(row, "key", jstr(cats[c][0])); jobj_set(row, "inputs", ins); jobj_set(row, "outputs", outs);
        jobj_set(row, "engine", jstr(cats[c][2])); jobj_set(row, "note", jstr(note.p));
        jarr_push(rows, row); free(note.p);
    }
    return rows;
}

/* ---- media info (several ffmpeg probes at once: they mostly wait on the disk) */
typedef struct { engine *e; const jval *paths; jval **out; int *next, *left; plat_mutex *m; plat_cond *c; } mi_ctx;
static void mi_worker(void *arg)
{
    mi_ctx *x = (mi_ctx *)arg;
    for (;;) {
        mutex_lock(x->m); int i = (*x->next)++; mutex_unlock(x->m);
        if (i >= (int)x->paths->len) break;
        const char *p = x->paths->items[i]->str;
        const probe_t *pi = probe(x->e, p);
        jval *o = jnew(J_OBJ);
        jobj_set(o, "dur", jnum(pi->dur)); jobj_set(o, "w", jnum(pi->w)); jobj_set(o, "h", jnum(pi->h));
        jobj_set(o, "hdr", jstr(pi->hdr)); jobj_set(o, "a", jstr(pi->acodec));
        x->out[i] = o;
    }
    mutex_lock(x->m); (*x->left)--; cond_broadcast(x->c); mutex_unlock(x->m);
}
jval *eng_media_info(engine *e, const jval *paths)
{
    jval *res = jnew(J_OBJ), *list = jnew(J_ARR);
    for (size_t i = 0; paths && paths->type == J_ARR && i < paths->len; i++) {
        if (paths->items[i]->type != J_STR) continue;
        const char *c = eng_category(paths->items[i]->str);
        if (c && (!strcmp(c, "video") || !strcmp(c, "audio"))) jarr_push(list, jstr(paths->items[i]->str));
    }
    if (list->len) {
        jval **out = (jval **)calloc(list->len, sizeof(jval *));
        int next = 0, workers = (int)list->len < 6 ? (int)list->len : 6;
        if (workers > cpu_count()) workers = cpu_count();
        int left = workers;
        mi_ctx x = { e, list, out, &next, &left, mutex_new(), cond_new() };
        for (int i = 0; i < workers; i++) if (!thread_start(mi_worker, &x)) { mutex_lock(x.m); left--; mutex_unlock(x.m); }
        mutex_lock(x.m); while (left > 0) cond_wait_ms(x.c, x.m, -1); mutex_unlock(x.m);
        if (next < (int)list->len) { left = 1; mi_worker(&x); }      /* no thread could start: do it here */
        for (size_t i = 0; i < list->len; i++) jobj_set(res, list->items[i]->str, out[i] ? out[i] : jnew(J_NULL));
        free(out); free(x.m); free(x.c);
    }
    json_free(list);
    return res;
}

jval *eng_hwinfo(engine *e)
{
    mutex_lock(e->m);
    if (e->hw_state != 2) { mutex_unlock(e->m); return jnew(J_NULL); }
    jval *a = jnew(J_ARR);
    for (int i = 0; i < e->nhw; i++)
        jarr_push(a, jstr(!strcmp(e->hw[i], "h264_nvenc") ? "NVIDIA NVENC" : !strcmp(e->hw[i], "h264_qsv") ? "Intel QSV" : "AMD AMF"));
    mutex_unlock(e->m);
    return a;
}

/* ---- preview: one frame as a data URL (rectangle picker / before-after compare) */
static const char B64[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
jval *eng_preview(engine *e, const char *path, double at, char **error)
{
    if (!e->ffmpeg) { *error = str_dup("找不到 ffmpeg"); return NULL; }
    const probe_t *pi = probe(e, path);
    double d = pi->dur, t = at >= 0 ? at : d * 0.3;
    if (t > d - 0.1) t = d - 0.1;
    if (t < 0) t = 0;
    strv vf = {0}; hdr_filters(pi, &vf); sv_add(&vf, "scale=1280:-2");
    char *vfs = join(&vf, ",");
    strv cmd = {0};
    sv_add(&cmd, e->ffmpeg); sv_add(&cmd, "-hide_banner"); sv_add(&cmd, "-v"); sv_add(&cmd, "error"); sv_add(&cmd, "-ss"); sv_addf(&cmd, "%.2f", t);
    sv_add(&cmd, "-i"); sv_add(&cmd, path); sv_add(&cmd, "-frames:v"); sv_add(&cmd, "1"); sv_add(&cmd, "-vf"); sv_add(&cmd, vfs);
    sv_add(&cmd, "-f"); sv_add(&cmd, "image2pipe"); sv_add(&cmd, "-c:v"); sv_add(&cmd, "mjpeg"); sv_add(&cmd, "-q:v"); sv_add(&cmd, "4"); sv_add(&cmd, "-");
    char *out = NULL; size_t n = 0;
    run_capture((const char *const *)cmd.v, NULL, &out, NULL, 60, &n);
    sv_free(&cmd); sv_free(&vf); free(vfs);
    sbuf b = {0}; sb_str(&b, "data:image/jpeg;base64,");
    const unsigned char *u = (const unsigned char *)out;
    for (size_t i = 0; i < n; i += 3) {
        unsigned v = (unsigned)u[i] << 16 | (i + 1 < n ? (unsigned)u[i + 1] << 8 : 0) | (i + 2 < n ? u[i + 2] : 0);
        char q[4] = { B64[v >> 18 & 63], B64[v >> 12 & 63], i + 1 < n ? B64[v >> 6 & 63] : '=', i + 2 < n ? B64[v & 63] : '=' };
        sb_add(&b, q, 4);
    }
    free(out);
    jval *o = jnew(J_OBJ);
    jobj_set(o, "src", jstr(b.p)); jobj_set(o, "w", jnum(pi->w)); jobj_set(o, "h", jnum(pi->h)); jobj_set(o, "dur", jnum(d));
    free(b.p);
    return o;
}

jval *eng_compare(engine *e, const char *id, char **error)
{
    mutex_lock(e->m);
    job *j = find_job(e, id);
    char *src = j ? str_dup(j->files[0]) : NULL, *out = j && j->output ? str_dup(j->output) : NULL;
    int ok = j && (j->state == Q_DONE || j->state == Q_PARTIAL);
    char validation[320]; snprintf(validation, sizeof validation, "%s", j ? j->validation : "");
    mutex_unlock(e->m);
    jval *r = NULL;
    if (!ok) *error = str_dup("請先完成轉檔");
    else if (!out || !is_file(out)) *error = str_dup("多檔案成品請開啟交付資料夾");
    else {
        const char *a = eng_category(src), *b = eng_category(out);
        if (!a || !b || strcmp(a, "video") || strcmp(b, "video")) *error = str_dup("目前可預覽圖片及影片畫面");
        else {
            jval *before = eng_preview(e, src, -1, error), *after = before ? eng_preview(e, out, -1, error) : NULL;
            if (before && after) {
                r = jnew(J_OBJ);
                jobj_set(r, "before", before); jobj_set(r, "after", after);
                jobj_set(r, "name", jstr(path_base(out))); jobj_set(r, "validation", jstr(validation));
            } else { json_free(before); json_free(after); }
        }
    }
    free(src); free(out);
    return r;
}
