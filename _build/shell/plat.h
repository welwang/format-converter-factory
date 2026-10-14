/* Platform layer: threads, processes, files.  Windows is the product; POSIX lets the engine be built and
   tested on Linux with gcc.  All paths and strings are UTF-8. */
#ifndef SWBD_PLAT_H
#define SWBD_PLAT_H
#include <stddef.h>
#include <stdint.h>

#ifdef _WIN32
#define PSEP '\\'
#define PSEP_S "\\"
#else
#define PSEP '/'
#define PSEP_S "/"
#endif

/* ---- threads */
typedef struct plat_mutex plat_mutex;
typedef struct plat_cond plat_cond;
plat_mutex *mutex_new(void);
void mutex_lock(plat_mutex *m);
void mutex_unlock(plat_mutex *m);
plat_cond *cond_new(void);
int cond_wait_ms(plat_cond *c, plat_mutex *m, int ms);   /* 0 = signalled, 1 = timeout; ms < 0 waits forever */
void cond_broadcast(plat_cond *c);
int thread_start(void (*fn)(void *), void *arg);         /* detached */
void sleep_ms(int ms);
double now_s(void);                                      /* seconds since 1970 */

/* ---- child processes (no window, below-normal priority, stdin = NUL) */
typedef struct proc proc;
enum { P_OUT = 1, P_ERR = 2, P_MERGE = 4 };              /* which streams are piped; P_MERGE sends stderr to stdout */
proc *proc_start(const char *const *argv, const char *cwd, int pipes);
long proc_read(proc *p, int stream, char *buf, size_t n); /* stream P_OUT / P_ERR; 0 = end */
int proc_wait(proc *p);                                  /* exit code */
void proc_kill(proc *p);                                 /* the whole process tree */
void proc_free(proc *p);
/* run to completion, collecting stdout + stderr (each capped at 1 MB); returns exit code or -1 */
int run_capture(const char *const *argv, const char *cwd, char **out, char **err, int timeout_s, size_t *out_len);

/* ---- files */
int is_file(const char *p);
int is_dir(const char *p);
int path_exists(const char *p);
int64_t file_size(const char *p);
double file_mtime(const char *p);
int make_dirs(const char *p);
int remove_file(const char *p);
int remove_tree(const char *p);
int copy_file(const char *src, const char *dst);
int move_file(const char *src, const char *dst);         /* replaces dst */
int64_t disk_free(const char *dir);
char *make_temp_dir(const char *prefix);                 /* malloc'd */
int dir_list(const char *dir, char ***names);            /* sorted entry names; free with free_list */
void free_list(char **list, int n);
int64_t tree_size(const char *p);

/* ---- paths (malloc'd results) */
char *path_join(const char *a, const char *b);
char *path_dir(const char *p);
const char *path_base(const char *p);                    /* points into p */
char *path_abs(const char *p);
int path_same(const char *a, const char *b);             /* case-insensitive on Windows */
char *exe_dir(void);

/* ---- system */
int cpu_count(void);
double mem_gb(void);
char *env_get(const char *name);                         /* malloc'd or NULL */

/* UTF-8 helpers */
char *str_dup(const char *s);
char *str_fmt(const char *fmt, ...);
int str_ends(const char *s, const char *suffix);         /* ASCII case-insensitive */
void str_lower(char *s);

/* text in any common encoding (UTF-8 / UTF-16 with BOM, Big5, GB18030, Windows-1252) -> UTF-8, malloc'd */
char *text_to_utf8(const char *data, size_t n);
char *read_file(const char *path, size_t *len);          /* whole file, malloc'd, NUL-terminated */
int write_file(const char *path, const char *data, size_t len);
int append_file(const char *path, const char *data, size_t len);
#endif
