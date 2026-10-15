/* Linux test driver: test_engine <base_dir> <jobs.json>  ;  jobs.json = [[files], target, opt, merge] ... */
#include "../engine.h"
#include "../plat.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc, char **argv)
{
    engine *e = engine_new(argv[1], argv[1]);
    size_t n; char *txt = read_file(argv[2], &n);
    jval *spec = json_parse(txt);
    if (!spec) { puts("bad spec"); return 2; }
    double t0 = now_s();
    for (size_t i = 0; i < spec->len; i++) {
        jval *s = spec->items[i];
        jval *ids = eng_submit(e, s->items[0], s->items[1]->str, s->items[2], s->len > 3 && s->items[3]->num);
        json_free(ids);
    }
    while (eng_active(e)) sleep_ms(100);
    jval *st = eng_status(e, 0);
    int bad = 0;
    for (size_t i = 0; i < st->len; i++) {
        const jval *j = st->items[i];
        const char *state = jget_str(j, "state", "");
        if (strcmp(state, "done")) bad++;
        printf("%-5s %-28.28s -> %-5s %7.2fs %9.0f KB  %s | %s | %s\n", state, jget_str(j, "name", ""), jget_str(j, "target", ""), jget_num(j, "elapsed", 0),
               jget_num(j, "out_size", 0) / 1024, jget_str(j, "encoder", ""), jget_str(j, "validation", ""), strcmp(state, "done") ? jget_str(j, "msg", "") : "");
    }
    printf("total %.1fs, %d not done\n", now_s() - t0, bad);
    jval *paths = jnew(J_ARR); jarr_push(paths, jstr(argv[3] ? argv[3] : "."));
    jval *d = eng_describe(e, paths); char *ds = json_dump(d); printf("describe: %.300s\n", ds);
    jval *f = eng_formats(e); char *fs = json_dump(f); printf("formats: %.400s\n", fs);
    jval *hw = eng_hwinfo(e); char *hs = json_dump(hw); printf("hw: %s\n", hs);
    return bad;
}
