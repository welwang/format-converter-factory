/* C++ 核心的 JSON 值：RAII 包裝既有 shell/json.c 的 jval，確保 C 與 C++ 產生位元組相同的線路格式。
   只用於 C++ 內部；跨 ABI 邊界一律走 UTF-8 文字。 */
#ifndef SWBD_CPP_JSON_HPP
#define SWBD_CPP_JSON_HPP

#include <cstdlib>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

/* shell/json.h 現在與 json.cpp 一起以 C++ 編譯（2026-10-15 由 .c 改名），因此以 C++ 連結引入，
   不可再包 extern "C"，否則符號會對不上。 */
#include "json.h"

namespace swbd {

/* 解析失敗或型別不符時擲出；橋接層會轉成 {"ok":false,"e":...}，與 Python 的例外處理一致。 */
class JsonError : public std::runtime_error {
public:
    explicit JsonError(const std::string &what) : std::runtime_error(what) {}
};

class Json {
public:
    Json() : v_(jnew(J_NULL)) {}
    explicit Json(jval *v) : v_(v ? v : jnew(J_NULL)) {}

    Json(Json &&other) noexcept : v_(other.v_) { other.v_ = nullptr; }
    Json &operator=(Json &&other) noexcept {
        if (this != &other) { json_free(v_); v_ = other.v_; other.v_ = nullptr; }
        return *this;
    }
    Json(const Json &) = delete;
    Json &operator=(const Json &) = delete;

    ~Json() { json_free(v_); }

    /* ---- 建立 ---- */
    static Json object() { return Json(jnew(J_OBJ)); }
    static Json array() { return Json(jnew(J_ARR)); }
    static Json of(std::string_view s) { return Json(jstr(std::string(s).c_str())); }
    static Json of(double n) { return Json(jnum(n)); }
    static Json of(long long n) { return Json(jnum(static_cast<double>(n))); }
    static Json boolean(bool b) { return Json(jbool(b ? 1 : 0)); }
    static Json null() { return Json(); }

    /* 解析一段 JSON 文字；失敗擲 JsonError。 */
    static Json parse(std::string_view text) {
        jval *v = json_parse(std::string(text).c_str());
        if (!v) throw JsonError("JSON 格式錯誤");
        return Json(v);
    }

    /* ---- 修改 ---- */
    void set(std::string_view key, Json value) { jobj_set(v_, std::string(key).c_str(), value.release()); }
    void push(Json value) { jarr_push(v_, value.release()); }

    /* ---- 讀取 ---- */
    jtype type() const { return v_->type; }
    bool is_object() const { return v_->type == J_OBJ; }
    bool is_array() const { return v_->type == J_ARR; }
    size_t size() const { return v_->len; }

    const jval *raw() const { return v_; }
    jval *release() { jval *v = v_; v_ = nullptr; return v; }

    const jval *get(std::string_view key) const {
        return type() == J_OBJ ? jget(v_, std::string(key).c_str()) : nullptr;
    }
    std::string str(std::string_view key, const char *fallback = "") const {
        return std::string(jget_str(v_, std::string(key).c_str(), fallback));
    }
    double num(std::string_view key, double fallback = 0) const {
        return jget_num(v_, std::string(key).c_str(), fallback);
    }
    bool boolean(std::string_view key, bool fallback = false) const {
        return jget_bool(v_, std::string(key).c_str(), fallback ? 1 : 0) != 0;
    }
    const jval *at(size_t index) const {
        return (type() == J_ARR && index < v_->len) ? v_->items[index] : nullptr;
    }

    /* 走訪陣列：strings() 收集字串元素，objects() 收集物件元素。 */
    std::vector<std::string> strings() const {
        std::vector<std::string> out;
        if (type() != J_ARR) return out;
        for (size_t i = 0; i < v_->len; i++)
            if (v_->items[i]->type == J_STR && v_->items[i]->str) out.emplace_back(v_->items[i]->str);
        return out;
    }

    std::string dump() const {
        char *text = json_dump(v_);
        std::string out = text ? text : "null";
        free(text);
        return out;
    }

private:
    jval *v_;
};

}  // namespace swbd

#endif
