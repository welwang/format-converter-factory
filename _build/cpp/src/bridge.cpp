/* C↔C++ 橋接：api.c 只認得這幾個函式；未連結 C++ 核心時它們不會被呼叫，既有行為不變。 */
#include "swbd/bridge.hpp"

#include <cstdlib>
#include <cstring>
#include <exception>
#include <string>
#include <vector>

#include "swbd/registry.hpp"
#include "swbd/sys.hpp"

namespace {

swbd::Context g_context;
bool g_ready = false;

/* 回覆物件與 Python 的 core.py 完全一致：{"ok":true,"r":...} / {"ok":false,"e":"..."} */
std::string make_reply(const std::string &method, const jval *args) {
    swbd::Json reply = swbd::Json::object();
    try {
        swbd::Json result = swbd::Registry::instance().call(g_context, method, args);
        reply.set("ok", swbd::Json::boolean(true));
        reply.set("r", std::move(result));
    } catch (const std::exception &ex) {
        const char *what = ex.what();
        reply.set("ok", swbd::Json::boolean(false));
        reply.set("e", swbd::Json::of((what && *what) ? what : "錯誤"));
    } catch (...) {
        reply.set("ok", swbd::Json::boolean(false));
        reply.set("e", swbd::Json::of("未知錯誤"));
    }
    return reply.dump();
}

}  // namespace

extern "C" {

int swbd_cpp_init(const char *base_dir, const char *data_dir) {
    g_context.base_dir = swbd::sys::abs_path(base_dir ? base_dir : "");
    g_context.data_dir = (data_dir && *data_dir) ? swbd::sys::abs_path(data_dir) : g_context.base_dir;
    g_context.temp_dir = swbd::sys::system_temp_dir();
    g_ready = !g_context.base_dir.empty();
    return g_ready ? 1 : 0;
}

int swbd_cpp_has(const char *method) {
    if (!g_ready || !method || !*method) return 0;
    return swbd::Registry::instance().has(method) ? 1 : 0;
}

char *swbd_cpp_call(const char *method, const jval *args) {
    if (!swbd_cpp_has(method)) return nullptr;
    const std::string text = make_reply(method, args);
    char *out = static_cast<char *>(std::malloc(text.size() + 1));
    if (!out) return nullptr;
    std::memcpy(out, text.c_str(), text.size() + 1);
    return out;
}

void swbd_cpp_free(char *text) { std::free(text); }

/* 外殼注入「Python 引擎忙碌中」的查詢（api.c 用既有的 core_call 問 status）。
   沒注入時 busy() 回 false，行為與沒有這個機制時相同。 */
void swbd_cpp_set_busy_probe(int (*probe)(void)) {
    g_context.python_busy = probe ? std::function<bool()>([probe] { return probe() != 0; })
                                  : std::function<bool()>();
}

/* 系統事實：把 C 引擎填好的結構複製成 C++ 快照（字串立即複製，不留下 borrowed 指標）。 */
void swbd_cpp_set_system_facts(void (*provider)(swbd_cpp_system_facts *out)) {
    if (!provider) {
        g_context.system_facts = std::function<swbd::SystemFacts()>();
        return;
    }
    g_context.system_facts = [provider] {
        swbd_cpp_system_facts raw{};
        raw.ram_gb = 0;
        provider(&raw);
        swbd::SystemFacts facts;
        facts.ready = true;
        facts.ram_gb = raw.ram_gb;
        facts.cores = raw.cores;
        facts.heavy = raw.heavy;
        facts.light = raw.light;
        facts.slots = raw.slots;
        facts.hw_ready = raw.hw_ready != 0;
        for (int i = 0; raw.hw && i < raw.hw_count; i++) {
            if (raw.hw[i]) facts.hw_encoders.emplace_back(raw.hw[i]);
        }
        return facts;
    };
}

/* 反向呼叫 Python：回覆是 {"ok":…,"r"|"e":…} 的信封，這裡拆開並在失敗時擲出錯誤字串，
   這樣接手的方法就能沿用 Python 原本的錯誤訊息。 */
void swbd_cpp_set_py_call(int (*fn)(const char *, const char *, char *, int)) {
    if (!fn) {
        g_context.py_call = std::function<swbd::Json(const std::string &, const swbd::Json &)>();
        return;
    }
    g_context.py_call = [fn](const std::string &method, const swbd::Json &args) {
        /* 一定要放堆積：接手的方法是由頁面處理執行緒呼叫的，那個執行緒的堆疊只有 1MB，
           在堆疊上放 1MB 會直接溢位（0xC00000FD）。 */
        std::vector<char> buffer(1 << 20);
        const std::string text = args.dump();
        const int length = fn(method.c_str(), text.c_str(), buffer.data(), static_cast<int>(buffer.size()));
        if (length < 0) throw swbd::JsonError("Python 沒有回應：" + method);
        swbd::Json envelope = swbd::Json::parse(std::string(buffer.data(), static_cast<size_t>(length)));
        const jval *ok = envelope.get("ok");
        if (ok && ok->type == J_BOOL && ok->num == 0) {
            const jval *error = envelope.get("e");
            throw swbd::JsonError((error && error->str) ? error->str : "Python 回報錯誤");
        }
        const jval *result = envelope.get("r");
        if (!result) throw swbd::JsonError("Python 的回覆沒有結果");
        return swbd::Json(json_clone(result));
    };
}

/* 送出原生工具工作：C 引擎回傳工作 id 陣列，這裡轉成 JSON 值。 */
void swbd_cpp_set_tool_submit(char *(*fn)(const char *, const jval *, const jval *, const char *, int, int)) {
    if (!fn) {
        g_context.submit_tool = std::function<swbd::Json(const std::string &, const std::vector<std::string> &,
                                                        const swbd::Json &, const std::string &, bool, bool)>();
        return;
    }
    g_context.submit_tool = [fn](const std::string &tool, const std::vector<std::string> &files,
                                 const swbd::Json &opt, const std::string &label, bool together, bool heavy) {
        jval *list = jnew(J_ARR);
        for (const std::string &file : files) jarr_push(list, jstr(file.c_str()));
        char *text = fn(tool.c_str(), list, opt.raw(), label.c_str(), together ? 1 : 0, heavy ? 1 : 0);
        json_free(list);
        if (!text) throw swbd::JsonError("無法送出原生工具工作");
        swbd::Json ids = swbd::Json::parse(text);
        free(text);
        return ids;
    };
}

int swbd_cpp_method_count(void) {
    return static_cast<int>(swbd::Registry::instance().names().size());
}

const char *swbd_cpp_method_at(int index) {
    static thread_local std::string name;
    const auto names = swbd::Registry::instance().names();
    if (index < 0 || static_cast<size_t>(index) >= names.size()) return nullptr;
    name = names[static_cast<size_t>(index)];
    return name.c_str();
}

}  // extern "C"
