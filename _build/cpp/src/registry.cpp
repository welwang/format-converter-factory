/* 方法註冊表實作。 */
#include "swbd/registry.hpp"

#include "swbd/sys.hpp"

namespace swbd {

std::string Context::tool(std::string_view name) const {
    return sys::join(sys::join(base_dir, "tools"), name);
}

Registry &Registry::instance() {
    static Registry registry;
    return registry;
}

void Registry::add(std::string name, Handler handler) {
    handlers_[std::move(name)] = std::move(handler);
}

bool Registry::has(std::string_view name) const {
    return handlers_.find(std::string(name)) != handlers_.end();
}

Json Registry::call(Context &ctx, std::string_view name, const jval *args) const {
    const auto it = handlers_.find(std::string(name));
    if (it == handlers_.end()) throw UnknownMethod(std::string(name));
    return it->second(ctx, args);
}

std::vector<std::string> Registry::names() const {
    std::vector<std::string> out;
    out.reserve(handlers_.size());
    for (const auto &pair : handlers_) out.push_back(pair.first);
    return out;
}

std::string arg_string(const jval *args, size_t index) {
    const jval *v = (args && args->type == J_ARR && index < args->len) ? args->items[index] : nullptr;
    if (!v || v->type != J_STR || !v->str) throw JsonError("參數型別錯誤");
    return std::string(v->str);
}

std::vector<std::string> arg_strings(const jval *args, size_t index) {
    const jval *v = (args && args->type == J_ARR && index < args->len) ? args->items[index] : nullptr;
    if (!v) return {};
    if (v->type != J_ARR) throw JsonError("參數型別錯誤");
    std::vector<std::string> out;
    out.reserve(v->len);
    for (size_t i = 0; i < v->len; i++) {
        const jval *item = v->items[i];
        if (!item || item->type != J_STR || !item->str) throw JsonError("參數型別錯誤");
        out.emplace_back(item->str);
    }
    return out;
}

}  // namespace swbd
