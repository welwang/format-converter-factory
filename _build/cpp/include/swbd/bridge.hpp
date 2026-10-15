/* C↔C++ 橋接縫。C 的 api.c 只認得這四個函式，預設全部為 NULL（未連結 C++ 核心時行為完全不變）。
   方法名以 Python 的 app.Api 方法為準，例如 "cleanup_scan"。 */
#ifndef SWBD_CPP_BRIDGE_HPP
#define SWBD_CPP_BRIDGE_HPP

#include "json.h"

extern "C" {
/* 啟動時呼叫一次；data_dir 傳空字串時沿用 base_dir（可攜版行為）。回傳 1 表示就緒。 */
int swbd_cpp_init(const char *base_dir, const char *data_dir);

/* 這個方法是否已由 C++ 核心接手（給 api.c 判斷要不要轉給 Python）。 */
int swbd_cpp_has(const char *method);

/* 呼叫已接手的方法，回傳 malloc 的 {"ok":true,"r":...} 或 {"ok":false,"e":"..."}；
   未接手的方法回傳 NULL。呼叫端用 swbd_cpp_free() 釋放。 */
char *swbd_cpp_call(const char *method, const jval *args);
void swbd_cpp_free(char *text);

/* 這一版註冊了哪些方法（測試與診斷用）。 */
int swbd_cpp_method_count(void);
const char *swbd_cpp_method_at(int index);

/* 由 api.c 注入「Python 引擎忙碌中」的查詢（回傳非零＝忙碌）。傳 NULL 可解除。
   有些接手的方法需要與 Python 版相同的忙碌守門，而忙碌的定義住在 Python 那一側。 */
void swbd_cpp_set_busy_probe(int (*probe)(void));

/* 由 api.c 注入系統事實（記憶體、核心數、工作者政策、硬體編碼器）。這些數字在 Python 版是
   engine.py 算出來的，C 引擎有同一套政策，透過這個介面共用，避免同一件事有兩份實作。
   hw 是 hw_count 個以 NUL 結尾的字串（只在 hw_ready 為真時有效）。傳 NULL 可解除。 */
typedef struct swbd_cpp_system_facts {
    double ram_gb;
    int cores, heavy, light, slots;
    int hw_ready, hw_count;
    char *const *hw;
} swbd_cpp_system_facts;

void swbd_cpp_set_system_facts(void (*provider)(swbd_cpp_system_facts *out));

/* 由 api.c 注入：C++ 接手的方法反向呼叫 Python 的方法（例如取用設定相關的選項）。
   fn 把回覆信封 JSON 寫進 out（含結尾 0），成功回傳長度、失敗回傳負值。 */
void swbd_cpp_set_py_call(int (*fn)(const char *method, const char *args_json, char *out, int out_size));

/* 由 api.c 注入：把原生工具工作送進 C 引擎執行（工具箱由 C++ 接手時使用）。
   回傳 malloc 的工作 id 陣列 JSON，呼叫端負責 free。 */
void swbd_cpp_set_tool_submit(char *(*fn)(const char *tool, const jval *files, const jval *opt,
                                          const char *label, int together, int heavy));
}

#endif
