/* 方法註冊表：C++ 核心接手前端方法的最小單位。
   每個方法名（例如 "cleanup_scan"）只能有一個擁有者；C 的 api.c 先用 NATIVE 清單，
   再用 swbd_cpp_has() 問 C++ 核心，因此一個 Python 模組可以逐個方法搬過來，不必一次翻掉。 */
#ifndef SWBD_CPP_REGISTRY_HPP
#define SWBD_CPP_REGISTRY_HPP

#include <functional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

#include "swbd/json.hpp"

namespace swbd {

/* C 引擎的系統事實快照（誰提供由外殼決定）。ready 為 false 時表示沒有注入，
   需要這些數字的方法就留在 Python。 */
struct SystemFacts {
    bool ready = false;
    double ram_gb = 0;
    int cores = 0, heavy = 1, light = 1, slots = 1;
    bool hw_ready = false;
    std::vector<std::string> hw_encoders;   /* 原始編碼器 id，例如 h264_nvenc */
};

/* 處理器拿得到的執行環境：與 Python 的 engine.base_dir() / engine.data_dir() 同義。 */
struct Context {
    std::string base_dir;   /* 程式所在目錄；隨附引擎在 base_dir\tools 之下 */
    std::string data_dir;   /* 設定、記錄與下載模型的位置（可攜版＝程式目錄） */
    std::string temp_dir;   /* Python tempfile.gettempdir() 的等價結果（無尾端斜線） */

    /* 由外殼注入：Python 引擎是否仍有未完成的工作（等同 app.py 的 self._eng.busy()）。
       有些方法（例如磁碟操作）在忙碌時必須拒絕，而忙碌的定義住在 Python 那一側，
       所以用注入而不是讓 C++ 自己猜。沒有注入時 busy() 一律回 false。 */
    std::function<bool()> python_busy;

    /* 由外殼注入：C 引擎的系統事實（工作者政策與硬體編碼器）。 */
    std::function<SystemFacts()> system_facts;

    /* 由外殼注入：反向呼叫 Python 的方法（回覆信封已拆開；失敗時擲出錯誤字串）。 */
    std::function<Json(const std::string &method, const Json &args)> py_call;
    /* 由外殼注入：把原生工具工作送進 C 引擎，回傳工作 id 陣列。 */
    std::function<Json(const std::string &tool, const std::vector<std::string> &files, const Json &opt,
                       const std::string &label, bool together, bool heavy)> submit_tool;

    bool busy() const { return python_busy && python_busy(); }
    SystemFacts facts() const { return system_facts ? system_facts() : SystemFacts(); }
    bool can_py_call() const { return static_cast<bool>(py_call); }
    bool can_submit_tool() const { return static_cast<bool>(submit_tool); }

    std::string tool(std::string_view name) const;   /* base_dir\tools\<name> */
};

/* args 是頁面傳來的 JSON 陣列（req.a），生命週期只在呼叫期間有效。 */
using Handler = std::function<Json(Context &, const jval *args)>;

class UnknownMethod : public std::runtime_error {
public:
    explicit UnknownMethod(const std::string &name)
        : std::runtime_error("沒有這個功能：" + name) {}
};

class Registry {
public:
    static Registry &instance();

    void add(std::string name, Handler handler);
    bool has(std::string_view name) const;
    Json call(Context &ctx, std::string_view name, const jval *args) const;
    std::vector<std::string> names() const;

private:
    std::unordered_map<std::string, Handler> handlers_;
};

/* 在模組的匿名命名空間裡用它註冊：static Register _("cleanup_scan", &cleanup_scan); */
struct Register {
    Register(std::string name, Handler handler) {
        Registry::instance().add(std::move(name), std::move(handler));
    }
};

/* 把 JSON 陣列的第 index 個元素當字串取值；缺少或型別錯誤時擲 JsonError。 */
std::string arg_string(const jval *args, size_t index);
std::vector<std::string> arg_strings(const jval *args, size_t index);

}  // namespace swbd

#endif
