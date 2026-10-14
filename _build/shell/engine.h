/* 四維八德 conversion engine in C: classification, queue, and the converters that drive external
   programs (FFmpeg, 7-Zip, Pandoc, LibreOffice, Calibre).  Pictures, PDF, 3D models and the tool box
   are handed to the Python component (see main.c). */
#ifndef SWBD_ENGINE_H
#define SWBD_ENGINE_H
#include "json.h"

typedef struct engine engine;

engine *engine_new(const char *base_dir, const char *data_dir);
void engine_shutdown(engine *e);

/* category of a path ("video", "audio", ... or NULL) and whether this engine converts it */
const char *eng_category(const char *path);
int eng_handles(const char *category, const char *target);

/* API (results are JSON values owned by the caller) */
jval *eng_describe(engine *e, const jval *paths);
jval *eng_formats(engine *e);
jval *eng_media_info(engine *e, const jval *paths);
jval *eng_submit(engine *e, const jval *files, const char *target, const jval *opt, int merge);   /* array of job ids */
jval *eng_status(engine *e, int tail);
int eng_active(engine *e);
int eng_owns(engine *e, const char *id);
void eng_cancel(engine *e, const char *id);
void eng_cancel_all(engine *e);
void eng_clear_done(engine *e);
char *eng_retry(engine *e, const char *id);                     /* new id, malloc'd, or NULL */
jval *eng_compare(engine *e, const char *id, char **error);
jval *eng_hwinfo(engine *e);                                      /* null while detecting */
jval *eng_preview(engine *e, const char *path, double at, char **error);

#endif
