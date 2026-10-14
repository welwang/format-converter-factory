/* Small JSON reader / writer for 四維八德 (UTF-8, no dependencies). */
#ifndef SWBD_JSON_H
#define SWBD_JSON_H
#include <stddef.h>

typedef enum { J_NULL, J_BOOL, J_NUM, J_STR, J_ARR, J_OBJ } jtype;

typedef struct jval {
    jtype type;
    double num;          /* J_NUM, J_BOOL (0 / 1) */
    char *str;           /* J_STR */
    struct jval **items; /* J_ARR values, J_OBJ values */
    char **keys;         /* J_OBJ keys */
    size_t len, cap;
} jval;

jval *json_parse(const char *text);            /* NULL on syntax error */
void json_free(jval *v);
jval *json_clone(const jval *v);

jval *jnew(jtype t);
jval *jstr(const char *s);
jval *jnum(double n);
jval *jbool(int b);
void jarr_push(jval *arr, jval *item);           /* takes ownership */
void jobj_set(jval *obj, const char *key, jval *item);   /* replaces, takes ownership */

const jval *jget(const jval *obj, const char *key);
const char *jget_str(const jval *obj, const char *key, const char *def);
double jget_num(const jval *obj, const char *key, double def);   /* numbers and numeric strings ("12.5") */
int jget_bool(const jval *obj, const char *key, int def);        /* true/false, numbers, "1"/"true" */

/* growable text buffer */
typedef struct { char *p; size_t len, cap; } sbuf;
void sb_add(sbuf *b, const char *s, size_t n);
void sb_str(sbuf *b, const char *s);
void sb_printf(sbuf *b, const char *fmt, ...);
void sb_json_str(sbuf *b, const char *s);       /* quoted + escaped */
void sb_json_num(sbuf *b, double n);
void json_write(sbuf *b, const jval *v);
char *json_dump(const jval *v);                  /* malloc'd */

#endif
