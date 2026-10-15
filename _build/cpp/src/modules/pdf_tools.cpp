/* 工具箱接手：頁面方法 run_tool。
 *
 * 為什麼從 run_tool 下手：82 個工具的實作都在 Python（tools.py／pdf_tools.py…），而 C 引擎只認得
 * 「格式轉換」工作。接手 run_tool 之後，工具箱就變成可以逐個搬過來的介面：這裡有一份「已原生實作」
 * 的工具清單，清單內的工作送進 C 引擎跑（eng_submit_tool），其餘整包交回 Python 的 run_tool。
 *
 * 與 Python 版的分工：
 *   - 驗證（最少／固定檔案數）在這裡重做，訊息與 app.run_tool 相同。
 *   - 選項（base_opt + 記住上次設定）仍由 Python 提供（tool_job_opt）：設定住在那一側，
 *     C++ 不應該自己猜。沒有注入 Python 時（測試探針）退回 app.base_opt() 的預設值。
 *   - 工具實作在 C 引擎（見 engine.cpp 的 run_tool_job）。
 */
#include <stdexcept>
#include <string>
#include <vector>

#include "swbd/json.hpp"
#include "swbd/registry.hpp"

namespace swbd {
namespace {

struct ToolMeta {
    const char *id;
    const char *name;      /* 顯示名稱，同時是輸出檔名的後綴（Python 的 submit_tool 也這樣用） */
    int min_files;
    int max_files;         /* 0 = 不限 */
    bool together;
    bool heavy;
    /* 有些工具只在特定模式下才由 C++ 接手（其餘模式交回 Python）。nullptr = 全部都接手。 */
    const char *mode_key;
    const char *mode_value;
};

/* 已搬到 C++ 的工具。每一項都要有對應的引擎實作，否則工作會以「還沒有原生實作」失敗。 */
constexpr ToolMeta kNative[] = {
    { "p_copy", "複製 PDF", 1, 0, false, false, nullptr, nullptr },
    /* p_pdf_images 交回 Python，原因是渲染引擎不同：
       pdf_tools.pdf_images 用 PyMuPDF（MuPDF），原生渲染用 PDFium。已用同引擎的參考
       （pypdfium2 + Pillow，見 pdf_render_ref.py）驗證過：C++ 的輸出逐像素完全相同；
       與 MuPDF 比則有 7.23% 通道差異（最大 255，集中在內容區）—— 視覺相同但不是逐位元相同，
       所以要接手就必須接受這個差異（或把 MuPDF 一起搬進來）。引擎端的 tool_pdf_images 已經寫好
       （含資料夾輸出），決定接受時把下面這一行解除註解即可。
    { "p_pdf_images", "PDF 轉 JPG／圖片", 1, 0, false, false, "mode=pages;fmt=png", nullptr },
    */
    { "p_flatten", "PDF 壓平", 1, 0, false, false, nullptr, nullptr },
    /* p_repair 交回 Python：有效檔的第一條路徑（qpdf 結構復原）兩邊一致，但損壞檔的
       第二條路徑 Python 用 MuPDF 逐頁復原（會重建 xref，救得回頁面），PDFium 對截斷的
       xref 連開檔都不行 → 接手會是功能退步。引擎端的 tool_pdf_repair 已寫好，
       若日後接受「MuPDF 的第二條路徑不接手」再解除註解。
    { "p_repair", "修復 PDF", 1, 0, false, false, nullptr, nullptr },
    */
    /* 只有無損等級是單純重寫；重壓圖片那兩種等級仍留在 Python。 */
    { "p_compress", "壓縮 PDF", 1, 0, false, false, "level=lossless", nullptr },
    { "p_merge", "合併 PDF", 2, 0, true, false, nullptr, nullptr },
    { "p_remove", "移除頁面", 1, 0, false, false, nullptr, nullptr },
    { "p_extract", "提取頁面", 1, 0, false, false, nullptr, nullptr },
    { "p_organize", "整理／重新排列 PDF", 1, 0, false, false, nullptr, nullptr },
};

/* 這個工具在這些參數下是否由 C++ 接手（模式不符就整包交回 Python）。 */
/* 接手閘門："key=value[;key=value…]"，每個條件都必須「明確等於」指定值（預設值不算），
   所以參數缺席時不會意外接手。空指標＝這個工具全部由 C++ 接手。 */
bool gate_open(const char *gate, const jval *params)
{
    if (!gate || !*gate) return true;
    const std::string spec(gate);
    size_t at = 0;
    for (;;) {
        const size_t end = spec.find(';', at);
        const std::string clause = spec.substr(at, end == std::string::npos ? std::string::npos : end - at);
        const size_t eq = clause.find('=');
        if (eq != std::string::npos) {
            const std::string key = clause.substr(0, eq);
            const std::string want = clause.substr(eq + 1);
            const jval *value = params && params->type == J_OBJ ? jget(params, key.c_str()) : nullptr;
            const char *text = (value && value->type == J_STR && value->str) ? value->str : "";
            if (want != text) return false;
        }
        if (end == std::string::npos) break;
        at = end + 1;
    }
    return true;
}

const ToolMeta *find_tool(const std::string &id, const jval *params) {
    for (const ToolMeta &meta : kNative) {
        if (id != meta.id) continue;
        if (!gate_open(meta.mode_key, params)) return nullptr;   /* 交給 Python */
        return &meta;
    }
    return nullptr;
}

const jval *arg_at(const jval *args, size_t index) {
    return (args && args->type == J_ARR && index < args->len) ? args->items[index] : nullptr;
}

std::string arg_text(const jval *args, size_t index) {
    const jval *value = arg_at(args, index);
    return (value && value->type == J_STR && value->str) ? std::string(value->str) : std::string();
}

std::vector<std::string> arg_files(const jval *args, size_t index) {
    std::vector<std::string> out;
    const jval *value = arg_at(args, index);
    if (value && value->type == J_ARR) {
        for (size_t i = 0; i < value->len; i++) {
            const jval *item = value->items[i];
            if (item && item->type == J_STR && item->str) out.emplace_back(item->str);
        }
    }
    return out;
}

/* 整包交給 Python 的 run_tool（驗證、設定與實作都還在那裡），並把它的錯誤訊息原樣傳出去。 */
Json relay_to_python(Context &ctx, const jval *args) {
    if (!ctx.can_py_call()) throw std::runtime_error("這一版沒有接上 Python 呼叫介面");
    Json forwarded = args ? Json(json_clone(args)) : Json::array();
    return ctx.py_call("run_tool", forwarded);
}

/* 沒有注入 Python 時的選項：與 app.base_opt() 的預設值相同，再讓 params 覆蓋。 */
Json default_opt(const jval *params) {
    Json opt = Json::object();
    opt.set("preset", Json::of("balanced"));
    opt.set("hwaccel", Json::boolean(true));
    opt.set("fastcopy", Json::boolean(true));
    opt.set("out_dir", Json::of(""));
    opt.set("codec", Json::of("auto"));
    opt.set("verify_full", Json::boolean(false));
    opt.set("resource_mode", Json::of("auto"));
    if (params && params->type == J_OBJ) {
        for (size_t i = 0; i < params->len; i++) {
            const char *key = params->keys ? params->keys[i] : nullptr;
            if (key) opt.set(key, Json(json_clone(params->items[i])));
        }
    }
    return opt;
}

Json resolve_opt(Context &ctx, const std::string &tool, const jval *params) {
    if (!ctx.can_py_call()) return default_opt(params);
    Json pair = Json::array();
    pair.push(Json::of(tool));
    pair.push(params ? Json(json_clone(params)) : Json::object());
    return ctx.py_call("tool_job_opt", pair);
}

Json run_tool(Context &ctx, const jval *args) {
    const std::string tool = arg_text(args, 0);
    const ToolMeta *meta = find_tool(tool, arg_at(args, 2));
    if (!meta) return relay_to_python(ctx, args);

    const std::vector<std::string> files = arg_files(args, 1);
    const size_t min_files = static_cast<size_t>(meta->min_files);
    if (files.size() < min_files) throw std::runtime_error("加入的檔案數不足");
    if (meta->max_files && files.size() != static_cast<size_t>(meta->max_files)) {
        throw std::runtime_error("請加入 " + std::to_string(meta->max_files) + " 個檔案");
    }
    if (!ctx.can_submit_tool()) throw std::runtime_error("這一版沒有接上原生工具工作介面");

    const Json opt = resolve_opt(ctx, tool, arg_at(args, 2));
    return ctx.submit_tool(tool, files, opt, meta->name, meta->together, meta->heavy);
}

Register register_run_tool("run_tool", &run_tool);

}  // namespace
}  // namespace swbd
