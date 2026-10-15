#define _CRT_SECURE_NO_WARNINGS
#include "json.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <stdarg.h>
#include <math.h>

static char *jdup(const char *s)
{
    size_t n = strlen(s) + 1;
    char *d = (char *)malloc(n);
    if (d) memcpy(d, s, n);
    return d;
}

/* ------------------------------------------------------------------ values */
jval *jnew(jtype t)
{
    jval *v = (jval *)calloc(1, sizeof *v);
    if (v) v->type = t;
    return v;
}
jval *jstr(const char *s)
{
    jval *v = jnew(J_STR);
    if (v) v->str = jdup(s ? s : "");
    return v;
}
jval *jnum(double n) { jval *v = jnew(J_NUM); if (v) v->num = n; return v; }
jval *jbool(int b) { jval *v = jnew(J_BOOL); if (v) v->num = b ? 1 : 0; return v; }

static int grow(jval *v)
{
    if (v->len < v->cap) return 1;
    size_t cap = v->cap ? v->cap * 2 : 8;
    jval **items = (jval **)realloc(v->items, cap * sizeof *items);
    if (!items) return 0;
    v->items = items;
    if (v->type == J_OBJ) {
        char **keys = (char **)realloc(v->keys, cap * sizeof *keys);
        if (!keys) return 0;
        v->keys = keys;
    }
    v->cap = cap;
    return 1;
}

void jarr_push(jval *arr, jval *item)
{
    if (!arr || !item || !grow(arr)) { json_free(item); return; }
    arr->items[arr->len++] = item;
}

void jobj_set(jval *obj, const char *key, jval *item)
{
    if (!obj || !item) { json_free(item); return; }
    for (size_t i = 0; i < obj->len; i++)
        if (!strcmp(obj->keys[i], key)) { json_free(obj->items[i]); obj->items[i] = item; return; }
    if (!grow(obj)) { json_free(item); return; }
    obj->keys[obj->len] = jdup(key);
    obj->items[obj->len++] = item;
}

void json_free(jval *v)
{
    if (!v) return;
    for (size_t i = 0; i < v->len; i++) {
        json_free(v->items[i]);
        if (v->keys) free(v->keys[i]);
    }
    free(v->items); free(v->keys); free(v->str); free(v);
}

jval *json_clone(const jval *v)
{
    if (!v) return NULL;
    jval *c = jnew(v->type);
    if (!c) return NULL;
    c->num = v->num;
    if (v->str) c->str = jdup(v->str);
    for (size_t i = 0; i < v->len; i++) {
        if (v->type == J_OBJ) jobj_set(c, v->keys[i], json_clone(v->items[i]));
        else jarr_push(c, json_clone(v->items[i]));
    }
    return c;
}

const jval *jget(const jval *obj, const char *key)
{
    if (!obj || obj->type != J_OBJ) return NULL;
    for (size_t i = 0; i < obj->len; i++) if (!strcmp(obj->keys[i], key)) return obj->items[i];
    return NULL;
}
const char *jget_str(const jval *obj, const char *key, const char *def)
{
    const jval *v = jget(obj, key);
    return v && v->type == J_STR ? v->str : def;
}
double jget_num(const jval *obj, const char *key, double def)
{
    const jval *v = jget(obj, key);
    if (!v) return def;
    if (v->type == J_NUM || v->type == J_BOOL) return v->num;
    if (v->type == J_STR && v->str[0]) {
        char *end; double d = strtod(v->str, &end);
        while (*end == ' ') end++;
        return *end ? def : d;
    }
    return def;
}
int jget_bool(const jval *obj, const char *key, int def)
{
    const jval *v = jget(obj, key);
    if (!v || v->type == J_NULL) return def;
    if (v->type == J_BOOL || v->type == J_NUM) return v->num != 0;
    if (v->type == J_STR) return v->str[0] && strcmp(v->str, "0") && strcmp(v->str, "false");
    return 1;
}

/* ------------------------------------------------------------------ parser */
typedef struct { const char *s; int depth; } P;

static void ws(P *p) { while (*p->s == ' ' || *p->s == '\t' || *p->s == '\n' || *p->s == '\r') p->s++; }

static void put_utf8(sbuf *b, unsigned cp)
{
    char t[4]; size_t n;
    if (cp < 0x80) { t[0] = (char)cp; n = 1; }
    else if (cp < 0x800) { t[0] = (char)(0xC0 | cp >> 6); t[1] = (char)(0x80 | (cp & 63)); n = 2; }
    else if (cp < 0x10000) { t[0] = (char)(0xE0 | cp >> 12); t[1] = (char)(0x80 | (cp >> 6 & 63)); t[2] = (char)(0x80 | (cp & 63)); n = 3; }
    else { t[0] = (char)(0xF0 | cp >> 18); t[1] = (char)(0x80 | (cp >> 12 & 63)); t[2] = (char)(0x80 | (cp >> 6 & 63)); t[3] = (char)(0x80 | (cp & 63)); n = 4; }
    sb_add(b, t, n);
}

static int hex4(const char *s, unsigned *out)
{
    unsigned v = 0;
    for (int i = 0; i < 4; i++) {
        char c = s[i]; v <<= 4;
        if (c >= '0' && c <= '9') v |= (unsigned)(c - '0');
        else if (c >= 'a' && c <= 'f') v |= (unsigned)(c - 'a' + 10);
        else if (c >= 'A' && c <= 'F') v |= (unsigned)(c - 'A' + 10);
        else return 0;
    }
    *out = v; return 1;
}

static char *pstring(P *p)
{
    if (*p->s != '"') return NULL;
    p->s++;
    sbuf b = {0};
    sb_add(&b, "", 0);
    while (*p->s && *p->s != '"') {
        if ((unsigned char)*p->s < 0x20) { free(b.p); return NULL; }
        if (*p->s != '\\') { const char *st = p->s; while (*p->s && *p->s != '"' && *p->s != '\\' && (unsigned char)*p->s >= 0x20) p->s++; sb_add(&b, st, (size_t)(p->s - st)); continue; }
        p->s++;
        char c = *p->s++;
        switch (c) {
        case '"': sb_add(&b, "\"", 1); break;
        case '\\': sb_add(&b, "\\", 1); break;
        case '/': sb_add(&b, "/", 1); break;
        case 'b': sb_add(&b, "\b", 1); break;
        case 'f': sb_add(&b, "\f", 1); break;
        case 'n': sb_add(&b, "\n", 1); break;
        case 'r': sb_add(&b, "\r", 1); break;
        case 't': sb_add(&b, "\t", 1); break;
        case 'u': {
            unsigned cp;
            if (!hex4(p->s, &cp)) { free(b.p); return NULL; }
            p->s += 4;
            if (cp >= 0xD800 && cp <= 0xDBFF && p->s[0] == '\\' && p->s[1] == 'u') {
                unsigned lo;
                if (hex4(p->s + 2, &lo) && lo >= 0xDC00 && lo <= 0xDFFF) { cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00); p->s += 6; }
            }
            put_utf8(&b, cp);
            break;
        }
        default: free(b.p); return NULL;
        }
    }
    if (*p->s != '"') { free(b.p); return NULL; }
    p->s++;
    return b.p;
}

static jval *pvalue(P *p)
{
    ws(p);
    if (++p->depth > 200) return NULL;
    jval *v = NULL;
    char c = *p->s;
    if (c == '{') {
        p->s++; v = jnew(J_OBJ); ws(p);
        if (*p->s == '}') { p->s++; goto done; }
        for (;;) {
            ws(p);
            char *k = pstring(p);
            if (!k) goto bad;
            ws(p);
            if (*p->s != ':') { free(k); goto bad; }
            p->s++;
            jval *item = pvalue(p);
            if (!item) { free(k); goto bad; }
            jobj_set(v, k, item); free(k);
            ws(p);
            if (*p->s == ',') { p->s++; continue; }
            if (*p->s == '}') { p->s++; break; }
            goto bad;
        }
    } else if (c == '[') {
        p->s++; v = jnew(J_ARR); ws(p);
        if (*p->s == ']') { p->s++; goto done; }
        for (;;) {
            jval *item = pvalue(p);
            if (!item) goto bad;
            jarr_push(v, item);
            ws(p);
            if (*p->s == ',') { p->s++; continue; }
            if (*p->s == ']') { p->s++; break; }
            goto bad;
        }
    } else if (c == '"') {
        char *s = pstring(p);
        if (!s) return NULL;
        v = jnew(J_STR); v->str = s;
    } else if (!strncmp(p->s, "true", 4)) { p->s += 4; v = jbool(1); }
    else if (!strncmp(p->s, "false", 5)) { p->s += 5; v = jbool(0); }
    else if (!strncmp(p->s, "null", 4)) { p->s += 4; v = jnew(J_NULL); }
    else if (c == '-' || (c >= '0' && c <= '9')) {
        char *end; double d = strtod(p->s, &end);
        if (end == p->s) return NULL;
        p->s = end; v = jnum(d);
    } else return NULL;
done:
    p->depth--;
    return v;
bad:
    json_free(v);
    return NULL;
}

jval *json_parse(const char *text)
{
    if (!text) return NULL;
    P p = { text, 0 };
    jval *v = pvalue(&p);
    if (!v) return NULL;
    ws(&p);
    if (*p.s) { json_free(v); return NULL; }
    return v;
}

/* ------------------------------------------------------------------ writer */
void sb_add(sbuf *b, const char *s, size_t n)
{
    if (b->len + n + 1 > b->cap) {
        size_t cap = b->cap ? b->cap : 256;
        while (b->len + n + 1 > cap) cap *= 2;
        char *p = (char *)realloc(b->p, cap);
        if (!p) return;
        b->p = p; b->cap = cap;
    }
    if (n) memcpy(b->p + b->len, s, n);
    b->len += n; b->p[b->len] = 0;
}
void sb_str(sbuf *b, const char *s) { sb_add(b, s, strlen(s)); }
void sb_printf(sbuf *b, const char *fmt, ...)
{
    char small[512];
    va_list ap; va_start(ap, fmt);
    int n = vsnprintf(small, sizeof small, fmt, ap);
    va_end(ap);
    if (n < 0) return;
    if ((size_t)n < sizeof small) { sb_add(b, small, (size_t)n); return; }
    char *big = (char *)malloc((size_t)n + 1);
    if (!big) return;
    va_start(ap, fmt); vsnprintf(big, (size_t)n + 1, fmt, ap); va_end(ap);
    sb_add(b, big, (size_t)n); free(big);
}
void sb_json_str(sbuf *b, const char *s)
{
    sb_add(b, "\"", 1);
    const char *st = s;
    for (; *s; s++) {
        unsigned char c = (unsigned char)*s;
        if (c != '"' && c != '\\' && c >= 0x20) continue;
        sb_add(b, st, (size_t)(s - st));
        if (c == '"') sb_add(b, "\\\"", 2);
        else if (c == '\\') sb_add(b, "\\\\", 2);
        else if (c == '\n') sb_add(b, "\\n", 2);
        else if (c == '\r') sb_add(b, "\\r", 2);
        else if (c == '\t') sb_add(b, "\\t", 2);
        else sb_printf(b, "\\u%04x", c);
        st = s + 1;
    }
    sb_add(b, st, (size_t)(s - st));
    sb_add(b, "\"", 1);
}
void sb_json_num(sbuf *b, double n)
{
    if (!isfinite(n)) { sb_str(b, "null"); return; }
    if (fabs(n) < 1e15 && n == (double)(long long)n) sb_printf(b, "%lld", (long long)n);
    else sb_printf(b, "%.17g", n);
}
void json_write(sbuf *b, const jval *v)
{
    if (!v) { sb_str(b, "null"); return; }
    switch (v->type) {
    case J_NULL: sb_str(b, "null"); break;
    case J_BOOL: sb_str(b, v->num ? "true" : "false"); break;
    case J_NUM: sb_json_num(b, v->num); break;
    case J_STR: sb_json_str(b, v->str); break;
    case J_ARR:
        sb_str(b, "[");
        for (size_t i = 0; i < v->len; i++) { if (i) sb_str(b, ","); json_write(b, v->items[i]); }
        sb_str(b, "]");
        break;
    case J_OBJ:
        sb_str(b, "{");
        for (size_t i = 0; i < v->len; i++) {
            if (i) sb_str(b, ",");
            sb_json_str(b, v->keys[i]); sb_str(b, ":"); json_write(b, v->items[i]);
        }
        sb_str(b, "}");
        break;
    }
}
char *json_dump(const jval *v)
{
    sbuf b = {0};
    json_write(&b, v);
    return b.p;
}
