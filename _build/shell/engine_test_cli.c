/* Test driver for the actual Windows C engine; no UI or machine maintenance. */
#define _CRT_SECURE_NO_WARNINGS
#include "engine.h"
#include "plat.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc,char **argv) {
 /* The driver receives paths in JSON, avoiding the legacy ANSI CRT argv. */
 if(argc!=3)return 2;
 char *line=(char*)malloc(2*1024*1024);
 if(!fgets(line,2*1024*1024,stdin))return 2;
 jval *setup=json_parse(line);
 engine *e=engine_new(jget_str(setup,"base",""),jget_str(setup,"data",""));json_free(setup);
 while(fgets(line,2*1024*1024,stdin)) {
  jval *q=json_parse(line),*r=NULL;const char *m=jget_str(q,"m","");
  if(!strcmp(m,"start"))r=eng_submit(e,jget(q,"files"),jget_str(q,"target",""),jget(q,"opt"),jget_bool(q,"merge",0));
  else if(!strcmp(m,"status"))r=eng_status(e,150);
  else if(!strcmp(m,"describe"))r=eng_describe(e,jget(q,"files"));
  else if(!strcmp(m,"media_info"))r=eng_media_info(e,jget(q,"files"));
  else if(!strcmp(m,"cancel")){eng_cancel(e,jget_str(q,"id",""));r=jbool(1);}
  else if(!strcmp(m,"retry")){char *id=eng_retry(e,jget_str(q,"id",""));r=id?jstr(id):jnew(J_NULL);free(id);}
  else if(!strcmp(m,"clear")){eng_clear_done(e);r=jbool(1);}
  else if(!strcmp(m,"quit")){json_free(q);puts("true");fflush(stdout);break;}
  else r=jnew(J_NULL);
  char *text=json_dump(r);puts(text?text:"null");fflush(stdout);free(text);json_free(r);json_free(q);
 }
 engine_shutdown(e);free(line);return 0;
}
