#include "../engine.h"
#include "../plat.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
int main(int argc, char **argv)
{
    (void)argc;
    engine *e = engine_new(argv[1], argv[1]);
    jval *files = jnew(J_ARR); jarr_push(files, jstr(argv[2]));
    jval *opt = json_parse("{\"out_dir\":\"/tmp/ccancel\",\"preset\":\"high\",\"fastcopy\":false}");
    jval *ids = eng_submit(e, files, "webm", opt, 0);
    jval *ids2 = eng_submit(e, files, "webm", opt, 0);
    const char *id = ids->items[0]->str, *id2 = ids2->items[0]->str;
    sleep_ms(1500);
    jval *st = eng_status(e, 0); char *s = json_dump(st); printf("running: %.200s\n", s); free(s); json_free(st);
    eng_cancel(e, id); eng_cancel(e, id2);
    while (eng_active(e)) sleep_ms(50);
    st = eng_status(e, 0);
    for (size_t i = 0; i < st->len; i++) printf("%s %s %s\n", jget_str(st->items[i], "id", ""), jget_str(st->items[i], "state", ""), jget_str(st->items[i], "msg", ""));
    json_free(st);
    char *nid = eng_retry(e, id);
    printf("retry -> %s owns=%d\n", nid, eng_owns(e, nid));
    sleep_ms(500); eng_cancel_all(e);
    while (eng_active(e)) sleep_ms(50);
    eng_clear_done(e);
    st = eng_status(e, 0); printf("after clear: %zu jobs\n", st->len); json_free(st);
    char *err = NULL; jval *pv = eng_preview(e, argv[2], -1, &err); s = json_dump(pv); printf("preview %.60s... len=%zu\n", s, strlen(s));
    jval *mi = eng_media_info(e, files); s = json_dump(mi); printf("media %s\n", s);
    return 0;
}
