/* The page's API, answered in C where the C engine can do the work and passed on to the Python component
   for everything else.  Platform-neutral: main.c supplies the window / process glue through api_host,
   and the Linux test drives it with a real Python component. */
#ifndef SWBD_API_H
#define SWBD_API_H

typedef struct {
    void (*send_core)(const char *line);          /* one protocol line to the Python component (no newline) */
    void (*post_page)(char *json);                /* takes ownership; may be called from any thread */
    void (*set_title)(const char *title);         /* any thread */
    void (*flash)(void);                          /* taskbar flash when work finishes in the background */
    void (*keep_awake)(int on);                   /* stop the PC sleeping mid-conversion */
    void (*finish_action)(const char *action);    /* "sound" / "shutdown" / "sleep" / "cancel_shutdown" */
} api_host;

void api_init(const char *base_dir, const char *data_dir, const api_host *host);
int api_request(const char *json);                /* 1 = answered here (asynchronously), 0 = forward to Python */
int api_core_line(const char *line);              /* 1 = an answer to a call made from C (consumed) */
void api_core_gone(void);
void api_close(void);                             /* cancel C jobs */

#endif
