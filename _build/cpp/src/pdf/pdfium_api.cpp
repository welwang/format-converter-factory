/* 原生 PDF 層：PDFium 動態載入、基本查詢與頁面渲染。 */
#include "swbd/pdfium.hpp"

#include <algorithm>
#include <exception>
#include <new>

#include <windows.h>

#include <cmath>
#include <cctype>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <mutex>
#include <set>
#include <thread>
#include <vector>

#include "swbd/json.hpp"

/* PNG 寫入在 png_writer.cpp（stb_image_write + Win32 寬字元開檔，支援非 ASCII 路徑）。 */
extern "C" int swbd_write_png_utf8(const char *utf8_path, int width, int height, int channels,
                                   const void *pixels, int stride);

namespace swbd::pdf {

namespace {

/* PDFium 的渲染旗標（與 pypdfium2 的預設值對齊：畫註解、不做 LCD 次像素）。
   FPDF_REVERSE_BYTE_ORDER：位圖格式為 BGRA 時，改以 RGBA 輸出——這樣就能把 PDFium 的
   緩衝直接交給 PNG 編碼器，省掉逐像素的 BGRx→RGB 重排（實測那是純 PDFium 渲染的 20 倍成本）。 */
constexpr int FPDF_ANNOT = 0x01;
constexpr int FPDF_REVERSE_BYTE_ORDER = 0x10;
constexpr unsigned long FPDF_WHITE = 0xFFFFFFFFu;

std::string utf8_from_utf16le(const char *bytes, size_t nbytes) {
    /* PDFium 回傳的長度含結尾 NUL（兩個位元組）。 */
    if (nbytes >= 2) nbytes -= 2;
    if (!nbytes) return std::string();
    const int chars = static_cast<int>(nbytes / 2);
    int need = WideCharToMultiByte(CP_UTF8, 0, reinterpret_cast<const wchar_t *>(bytes), chars, nullptr, 0, nullptr, nullptr);
    if (need <= 0) return std::string();
    std::string out(static_cast<size_t>(need), '\0');
    WideCharToMultiByte(CP_UTF8, 0, reinterpret_cast<const wchar_t *>(bytes), chars, out.data(), need, nullptr, nullptr);
    return out;
}

std::wstring widen(const std::string &utf8) {
    if (utf8.empty()) return std::wstring();
    const int need = MultiByteToWideChar(CP_UTF8, 0, utf8.c_str(), -1, nullptr, 0);
    std::wstring out(static_cast<size_t>(need ? need : 1), L'\0');
    if (need) MultiByteToWideChar(CP_UTF8, 0, utf8.c_str(), -1, out.data(), need);
    out.resize(need ? static_cast<size_t>(need - 1) : 0);
    return out;
}

}  // namespace

Pdfium &Pdfium::instance() {
    static Pdfium one;
    return one;
}

bool Pdfium::load(const std::string &base_dir) {
    if (ready_) return true;
    const char *relative[] = { "\\_internal\\pypdfium2_raw\\pdfium.dll",
                               "\\_internal\\pypdfium2\\pdfium.dll",
                               "\\pdfium.dll" };
    for (const char *rel : relative) {
        HMODULE mod = LoadLibraryW((widen(base_dir) + widen(rel)).c_str());
        if (!mod) continue;
        auto sym = [mod](const char *name) { return reinterpret_cast<void *>(GetProcAddress(mod, name)); };
        InitLibrary = reinterpret_cast<void (*)()>(sym("FPDF_InitLibrary"));
        DestroyLibrary = reinterpret_cast<void (*)()>(sym("FPDF_DestroyLibrary"));
        LoadDocument = reinterpret_cast<FPDF_DOCUMENT (*)(const char *, const char *)>(sym("FPDF_LoadDocument"));
        CloseDocument = reinterpret_cast<void (*)(FPDF_DOCUMENT)>(sym("FPDF_CloseDocument"));
        GetPageCount = reinterpret_cast<int (*)(FPDF_DOCUMENT)>(sym("FPDF_GetPageCount"));
        LoadPage = reinterpret_cast<FPDF_PAGE (*)(FPDF_DOCUMENT, int)>(sym("FPDF_LoadPage"));
        ClosePage = reinterpret_cast<void (*)(FPDF_PAGE)>(sym("FPDF_ClosePage"));
        GetPageWidthF = reinterpret_cast<float (*)(FPDF_PAGE)>(sym("FPDF_GetPageWidthF"));
        GetPageHeightF = reinterpret_cast<float (*)(FPDF_PAGE)>(sym("FPDF_GetPageHeightF"));
        GetMetaText = reinterpret_cast<unsigned long (*)(FPDF_DOCUMENT, const char *, void *, unsigned long)>(sym("FPDF_GetMetaText"));
        GetLastError = reinterpret_cast<unsigned long (*)()>(sym("FPDF_GetLastError"));
        GetSecurityHandlerRevision = reinterpret_cast<int (*)(FPDF_DOCUMENT)>(sym("FPDF_GetSecurityHandlerRevision"));
        Bitmap_Create = reinterpret_cast<FPDF_BITMAP (*)(int, int, int)>(sym("FPDFBitmap_Create"));
        Bitmap_FillRect = reinterpret_cast<void (*)(FPDF_BITMAP, int, int, int, int, unsigned long)>(sym("FPDFBitmap_FillRect"));
        RenderPageBitmap = reinterpret_cast<void (*)(FPDF_BITMAP, FPDF_PAGE, int, int, int, int, int, int)>(sym("FPDF_RenderPageBitmap"));
        Bitmap_GetBuffer = reinterpret_cast<void *(*)(FPDF_BITMAP)>(sym("FPDFBitmap_GetBuffer"));
        Bitmap_GetStride = reinterpret_cast<int (*)(FPDF_BITMAP)>(sym("FPDFBitmap_GetStride"));
        Bitmap_Destroy = reinterpret_cast<void (*)(FPDF_BITMAP)>(sym("FPDFBitmap_Destroy"));
        /* 組頁用的符號是選用的：PDFium 若少了它們，渲染照舊可用，只是合併會降級回 Python。 */
        CreateNewDocument = reinterpret_cast<FPDF_DOCUMENT (*)()>(sym("FPDF_CreateNewDocument"));
        ImportPages = reinterpret_cast<int (*)(FPDF_DOCUMENT, FPDF_DOCUMENT, const char *, int)>(sym("FPDF_ImportPages"));
        ImportPagesByIndex = reinterpret_cast<int (*)(FPDF_DOCUMENT, FPDF_DOCUMENT, const int *, int, int)>(sym("FPDF_ImportPagesByIndex"));
        SaveAsCopy = reinterpret_cast<int (*)(FPDF_DOCUMENT, FPDF_FILEWRITE *, unsigned long)>(sym("FPDF_SaveAsCopy"));
        Page_New = reinterpret_cast<FPDF_PAGE (*)(FPDF_DOCUMENT, int, double, double)>(sym("FPDFPage_New"));
        Page_Flatten = reinterpret_cast<int (*)(FPDF_PAGE, int)>(sym("FPDFPage_Flatten"));
        const bool complete = InitLibrary && DestroyLibrary && LoadDocument && CloseDocument && GetPageCount &&
                              LoadPage && ClosePage && GetPageWidthF && GetPageHeightF && GetMetaText &&
                              GetLastError && Bitmap_Create && Bitmap_FillRect && RenderPageBitmap &&
                              Bitmap_GetBuffer && Bitmap_GetStride && Bitmap_Destroy;
        if (!complete) {
            FreeLibrary(mod);
            continue;
        }
        module_ = mod;
        path_ = rel;   /* 相對於 base_dir 的 ASCII 路徑，僅供診斷 */
        ready_ = true;
        InitLibrary();
        return true;
    }
    return false;
}

std::string Pdfium::last_error_text() const {
    if (!ready_) return "PDFium 未載入";
    static const char *texts[] = { "成功", "未知錯誤", "檔案或路徑無效", "格式錯誤",
                                   "密碼錯誤或未提供", "安全錯誤", "頁面不存在" };
    const unsigned long code = GetLastError();
    return code < sizeof(texts) / sizeof(texts[0]) ? texts[code] : "PDFium 錯誤";
}

std::string meta_text(Pdfium &pdfium, FPDF_DOCUMENT doc, const char *tag) {
    const unsigned long need = pdfium.GetMetaText(doc, tag, nullptr, 0);
    if (need <= 2) return std::string();
    std::vector<char> buffer(static_cast<size_t>(need), '\0');
    const unsigned long got = pdfium.GetMetaText(doc, tag, buffer.data(), need);
    if (got <= 2) return std::string();
    return utf8_from_utf16le(buffer.data(), static_cast<size_t>(got));
}

std::string describe_document(Pdfium &pdfium, const std::string &path_utf8) {
    Json out = Json::object();
    FPDF_DOCUMENT doc = pdfium.LoadDocument(path_utf8.c_str(), nullptr);
    if (!doc) {
        out.set("error", Json::of(pdfium.last_error_text()));
        return out.dump();
    }
    const int pages = pdfium.GetPageCount(doc);
    out.set("pages", Json::of(static_cast<long long>(pages)));
    Json sizes = Json::array();
    for (int i = 0; i < pages; i++) {
        FPDF_PAGE page = pdfium.LoadPage(doc, i);
        Json size = Json::array();
        if (page) {
            size.push(Json::of(static_cast<double>(pdfium.GetPageWidthF(page))));
            size.push(Json::of(static_cast<double>(pdfium.GetPageHeightF(page))));
            pdfium.ClosePage(page);
        }
        sizes.push(std::move(size));
    }
    out.set("sizes", std::move(sizes));
    out.set("title", Json::of(meta_text(pdfium, doc, "Title")));
    out.set("author", Json::of(meta_text(pdfium, doc, "Author")));
    out.set("producer", Json::of(meta_text(pdfium, doc, "Producer")));
    out.set("creator", Json::of(meta_text(pdfium, doc, "Creator")));
    pdfium.CloseDocument(doc);
    return out.dump();
}

namespace {

/* FPDF_SaveAsCopy 的記憶體寫入端：writer 是結構的第一個成員，所以由 self 還原外層是安全的。 */
struct Sink {
    FPDF_FILEWRITE writer;
    std::vector<unsigned char> *bytes;
};

bool save_to_memory(Pdfium &pdfium, FPDF_DOCUMENT doc, std::vector<unsigned char> &output) {
    Sink sink{ { 1, nullptr }, &output };
    sink.writer.WriteBlock = [](FPDF_FILEWRITE *self, const void *data, unsigned long size) -> int {
        auto *holder = reinterpret_cast<Sink *>(self);
        if (!holder->bytes || !data) return 0;
        const unsigned char *begin = static_cast<const unsigned char *>(data);
        holder->bytes->insert(holder->bytes->end(), begin, begin + size);
        return 1;
    };
    output.clear();
    return pdfium.SaveAsCopy(doc, &sink.writer, 0) != 0;
}

}  // namespace

int open_document_info(Pdfium &pdfium, const std::string &pdf_path_utf8, const std::string &password,
                       int *encrypted, std::string &error) {
    FPDF_DOCUMENT doc = pdfium.LoadDocument(pdf_path_utf8.c_str(), password.empty() ? nullptr : password.c_str());
    if (!doc) {
        /* FPDF_ERR_PASSWORD = 4；其餘（檔案無效／格式錯誤）都對應 Python 的「沒有可讀取的頁面」。 */
        error = (pdfium.GetLastError() == 4) ? "PDF 需要正確的文件密碼" : "文件沒有可讀取的 PDF 頁面";
        return -1;
    }
    if (encrypted) {
        *encrypted = (pdfium.GetSecurityHandlerRevision && pdfium.GetSecurityHandlerRevision(doc) > 0) ? 1 : 0;
    }
    const int pages = pdfium.GetPageCount(doc);
    pdfium.CloseDocument(doc);
    if (pages <= 0) {
        error = "文件沒有可讀取的 PDF 頁面";
        return -1;
    }
    return pages;
}

int open_page_count(Pdfium &pdfium, const std::string &pdf_path_utf8, const std::string &password,
                    std::string &error) {
    return open_document_info(pdfium, pdf_path_utf8, password, nullptr, error);
}

bool parse_page_spec(const std::string &spec, int count, bool allow_repeat,
                     std::vector<int> &out_zero_based, std::string &error) {
    out_zero_based.clear();
    auto strip = [](const std::string &text) {
        size_t begin = 0, end = text.size();
        while (begin < end && isspace(static_cast<unsigned char>(text[begin]))) begin++;
        while (end > begin && isspace(static_cast<unsigned char>(text[end - 1]))) end--;
        return text.substr(begin, end - begin);
    };
    /* Python：空白＝全部頁面 */
    std::string text = strip(spec);
    if (text.empty()) {
        for (int i = 0; i < count; i++) out_zero_based.push_back(i);
        return true;
    }
    /* 全形逗號（U+FF0C）與半形等價 */
    std::string normalized;
    for (size_t i = 0; i < text.size();) {
        if (i + 3 <= text.size() && static_cast<unsigned char>(text[i]) == 0xEF &&
            static_cast<unsigned char>(text[i + 1]) == 0xBC && static_cast<unsigned char>(text[i + 2]) == 0x8C) {
            normalized += ',';
            i += 3;
        } else {
            normalized += text[i++];
        }
    }
    std::set<int> seen;
    size_t position = 0;
    while (position <= normalized.size()) {
        const size_t comma = normalized.find(',', position);
        const std::string part = strip(normalized.substr(position, comma == std::string::npos ? std::string::npos : comma - position));
        position = (comma == std::string::npos) ? normalized.size() + 1 : comma + 1;
        /* re.fullmatch(r'(\d+)(?:\s*-\s*(\d*))?', part) 的手寫等價版 */
        size_t i = 0;
        while (i < part.size() && isdigit(static_cast<unsigned char>(part[i]))) i++;
        if (i == 0) { error = "頁碼格式錯誤，請輸入例如 1,3-5,8-"; return false; }
        const int first = atoi(part.substr(0, i).c_str());
        int last = first;
        if (i < part.size()) {
            size_t j = i;
            while (j < part.size() && isspace(static_cast<unsigned char>(part[j]))) j++;
            if (j >= part.size() || part[j] != '-') { error = "頁碼格式錯誤，請輸入例如 1,3-5,8-"; return false; }
            j++;
            while (j < part.size() && isspace(static_cast<unsigned char>(part[j]))) j++;
            size_t digits = j;
            while (digits < part.size() && isdigit(static_cast<unsigned char>(part[digits]))) digits++;
            last = (digits == j) ? count : atoi(part.substr(j, digits - j).c_str());
            if (digits != part.size()) { error = "頁碼格式錯誤，請輸入例如 1,3-5,8-"; return false; }
        }
        if (!(first >= 1 && first <= last && last <= count)) {
            error = "頁碼超出範圍，文件共有 " + std::to_string(count) + " 頁";
            return false;
        }
        for (int n = first - 1; n < last; n++) {
            if (allow_repeat || seen.find(n) == seen.end()) {
                out_zero_based.push_back(n);
                seen.insert(n);
            }
        }
    }
    if (out_zero_based.empty()) {
        error = "沒有選取頁面";
        return false;
    }
    return true;
}

MergeResult select_pages(Pdfium &pdfium, const std::string &pdf_path_utf8, const std::string &password,
                         const std::vector<int> &indices, std::vector<unsigned char> &output) {
    MergeResult out;
    if (!pdfium.ready() || !pdfium.can_select()) {
        out.error = "這一版 PDFium 沒有組頁 API";
        return out;
    }
    FPDF_DOCUMENT src = pdfium.LoadDocument(pdf_path_utf8.c_str(), password.empty() ? nullptr : password.c_str());
    if (!src) {
        out.error = pdfium.last_error_text();
        return out;
    }
    const int count = pdfium.GetPageCount(src);
    std::vector<int> wanted;
    for (int index : indices) if (index >= 0 && index < count) wanted.push_back(index);
    if (wanted.empty()) {
        pdfium.CloseDocument(src);
        out.error = "沒有選取頁面";
        return out;
    }
    FPDF_DOCUMENT dest = pdfium.CreateNewDocument();
    if (!dest) {
        pdfium.CloseDocument(src);
        out.error = "無法建立新文件";
        return out;
    }
    if (!pdfium.ImportPagesByIndex(dest, src, wanted.data(), static_cast<int>(wanted.size()), 0)) {
        out.error = "匯入頁面失敗";
    } else if (!save_to_memory(pdfium, dest, output)) {
        out.error = "無法寫出組好的 PDF";
    } else {
        out.ok = true;
        out.pages = static_cast<int>(wanted.size());
    }
    pdfium.CloseDocument(dest);
    pdfium.CloseDocument(src);
    return out;
}

int rebuild_readable_pages(Pdfium &pdfium, const std::string &pdf_path_utf8, const std::string &password,
                           std::vector<unsigned char> &output, std::vector<int> &unreadable,
                           const std::function<bool(int, int)> &progress) {
    if (!pdfium.ready() || !pdfium.can_select()) return -1;
    FPDF_DOCUMENT src = pdfium.LoadDocument(pdf_path_utf8.c_str(), password.empty() ? nullptr : password.c_str());
    if (!src) return -1;
    const int count = pdfium.GetPageCount(src);
    FPDF_DOCUMENT dest = pdfium.CreateNewDocument();
    if (!dest) { pdfium.CloseDocument(src); return -1; }
    int recovered = 0;
    for (int i = 0; i < count; i++) {
        bool readable = false;
        FPDF_PAGE page = pdfium.LoadPage(src, i);
        if (page) {
            /* 以低解析度真的畫一次，才算這一頁讀得出來（與 pdf_tools.repair 的逐頁驗證同義）。 */
            const double w = static_cast<double>(pdfium.GetPageWidthF(page));
            const double h = static_cast<double>(pdfium.GetPageHeightF(page));
            const int bw = static_cast<int>(std::ceil(w * 0.3));
            const int bh = static_cast<int>(std::ceil(h * 0.3));
            FPDF_BITMAP bitmap = (bw > 0 && bh > 0) ? pdfium.Bitmap_Create(bw, bh, 1) : nullptr;
            if (bitmap) {
                pdfium.Bitmap_FillRect(bitmap, 0, 0, bw, bh, FPDF_WHITE);
                pdfium.RenderPageBitmap(bitmap, page, 0, 0, bw, bh, 0, FPDF_ANNOT | FPDF_REVERSE_BYTE_ORDER);
                readable = pdfium.Bitmap_GetBuffer(bitmap) != nullptr;
                pdfium.Bitmap_Destroy(bitmap);
            }
            pdfium.ClosePage(page);
        }
        if (readable) {
            int one = i;
            if (pdfium.ImportPagesByIndex(dest, src, &one, 1, 0)) recovered++;
            else unreadable.push_back(i + 1);
        } else {
            unreadable.push_back(i + 1);
        }
        if (progress && !progress(i + 1, count)) break;
    }
    bool ok = recovered > 0;
    if (ok) ok = save_to_memory(pdfium, dest, output);
    pdfium.CloseDocument(dest);
    pdfium.CloseDocument(src);
    return ok ? recovered : -1;
}

MergeResult flatten_document(Pdfium &pdfium, const std::string &pdf_path_utf8,
                             const std::string &password, std::vector<unsigned char> &output) {
    MergeResult out;
    if (!pdfium.ready() || !pdfium.Page_Flatten) {
        out.error = "這一版 PDFium 沒有壓平 API";
        return out;
    }
    FPDF_DOCUMENT doc = pdfium.LoadDocument(pdf_path_utf8.c_str(), password.empty() ? nullptr : password.c_str());
    if (!doc) {
        out.error = pdfium.last_error_text();
        return out;
    }
    const int count = pdfium.GetPageCount(doc);
    if (count <= 0) {
        pdfium.CloseDocument(doc);
        out.error = "文件沒有可讀取的 PDF 頁面";
        return out;
    }
    /* FLAT_NORMALDISPLAY = 0：與 PyMuPDF 的 bake(annots=True, widgets=True) 相同 ——
       把註記與表單欄位畫進頁面內容，然後從頁面移除。 */
    for (int i = 0; i < count; i++) {
        FPDF_PAGE page = pdfium.LoadPage(doc, i);
        if (!page) { out.error = "無法載入頁面"; pdfium.CloseDocument(doc); return out; }
        pdfium.Page_Flatten(page, 0);
        pdfium.ClosePage(page);
    }
    const bool ok = save_to_memory(pdfium, doc, output);
    pdfium.CloseDocument(doc);
    if (!ok) { out.error = "無法寫出壓平後的 PDF"; return out; }
    out.ok = true;
    out.pages = count;
    return out;
}

MergeResult assemble_with_blanks(Pdfium &pdfium, const std::string &pdf_path_utf8, const std::string &password,
                                 const std::vector<int> &selected, std::vector<unsigned char> &output) {
    MergeResult out;
    if (!pdfium.ready() || !pdfium.can_select() || !pdfium.Page_New) {
        out.error = "這一版 PDFium 沒有組頁 API";
        return out;
    }
    FPDF_DOCUMENT src = pdfium.LoadDocument(pdf_path_utf8.c_str(), password.empty() ? nullptr : password.c_str());
    if (!src) {
        out.error = pdfium.last_error_text();
        return out;
    }
    const int count = pdfium.GetPageCount(src);
    FPDF_DOCUMENT dest = pdfium.CreateNewDocument();
    if (!dest) {
        pdfium.CloseDocument(src);
        out.error = "無法建立新文件";
        return out;
    }
    std::vector<int> all;
    for (int i = 0; i < count; i++) all.push_back(i);
    bool ok = pdfium.ImportPagesByIndex(dest, src, all.data(), static_cast<int>(all.size()), 0) != 0;
    if (!ok) out.error = "匯入頁面失敗";

    /* 由大到小插入：blank 模式是在選取頁碼之後插入同尺寸的空白頁，這樣才不會打亂後面的索引。 */
    std::set<int> unique(selected.begin(), selected.end());
    for (auto it = unique.rbegin(); ok && it != unique.rend(); ++it) {
        const int index = *it;
        if (index < 0 || index >= count) continue;
        FPDF_PAGE page = pdfium.LoadPage(src, index);
        if (!page) { out.error = "無法載入頁面"; ok = false; break; }
        const double width = static_cast<double>(pdfium.GetPageWidthF(page));
        const double height = static_cast<double>(pdfium.GetPageHeightF(page));
        pdfium.ClosePage(page);
        if (!pdfium.Page_New(dest, index + 1, width, height)) { out.error = "無法插入空白頁"; ok = false; break; }
    }
    if (ok && !save_to_memory(pdfium, dest, output)) {
        out.error = "無法寫出組好的 PDF";
        ok = false;
    }
    pdfium.CloseDocument(dest);
    pdfium.CloseDocument(src);
    if (ok) {
        out.ok = true;
        out.pages = count + static_cast<int>(unique.size());
    }
    return out;
}

/* 未提供密碼時的轉呼叫。 */

/* 相容的轉呼叫：整份文件、固定 dpi、<folder>/001.<ext>。 */
RenderAll render_all_pages(Pdfium &pdfium, const std::string &pdf_path_utf8, double dpi,
                           const std::string &folder_utf8, const std::string &extension,
                           const std::function<bool(int, int)> &progress, int encode_threads) {
    return render_pages(pdfium, pdf_path_utf8, std::string(), std::vector<int>(), dpi, nullptr, nullptr,
                        folder_utf8, extension, progress, encode_threads);
}

MergeResult merge_documents(Pdfium &pdfium, const std::vector<std::string> &inputs_utf8,
                            std::vector<unsigned char> &output,
                            const std::function<bool(int, int)> &progress) {
    return merge_documents(pdfium, inputs_utf8, std::string(), output, progress);
}

MergeResult merge_documents(Pdfium &pdfium, const std::vector<std::string> &inputs_utf8,
                            const std::string &password, std::vector<unsigned char> &output,
                            const std::function<bool(int, int)> &progress) {
    MergeResult out;
    if (!pdfium.ready() || !pdfium.can_merge()) {
        out.error = "這一版 PDFium 沒有組頁 API";
        return out;
    }
    if (inputs_utf8.empty()) {
        out.error = "沒有來源檔案";
        return out;
    }

    /* 先開檔並統計總頁數：progress 才有正確的分母（engine.py 也是先 append 再逐頁回報）。 */
    std::vector<FPDF_DOCUMENT> sources;
    int total = 0;
    for (const std::string &path : inputs_utf8) {
        /* 與 Python 相同：每個來源都用同一組密碼開啟（空字串＝沒有密碼）。 */
        FPDF_DOCUMENT doc = pdfium.LoadDocument(path.c_str(), password.empty() ? nullptr : password.c_str());
        if (!doc) {
            for (FPDF_DOCUMENT opened : sources) pdfium.CloseDocument(opened);
            out.error = "無法開啟 " + path + "（" + pdfium.last_error_text() + "）";
            return out;
        }
        sources.push_back(doc);
        total += pdfium.GetPageCount(doc);
    }

    FPDF_DOCUMENT dest = pdfium.CreateNewDocument();
    if (!dest) {
        for (FPDF_DOCUMENT opened : sources) pdfium.CloseDocument(opened);
        out.error = "無法建立新文件";
        return out;
    }

    int imported = 0;
    bool ok = true;
    for (size_t i = 0; i < sources.size() && ok; i++) {
        /* pagerange = NULL 代表整份匯入；index 是目前累積的頁數，因此等於依序附加。 */
        if (!pdfium.ImportPages(dest, sources[i], nullptr, imported)) {
            out.error = "匯入頁面失敗";
            ok = false;
            break;
        }
        imported += pdfium.GetPageCount(sources[i]);
        if (progress && !progress(imported, total)) {
            out.cancelled = true;
            ok = false;
            break;
        }
    }
    for (FPDF_DOCUMENT opened : sources) pdfium.CloseDocument(opened);

    if (ok && !save_to_memory(pdfium, dest, output)) {
        out.error = "無法寫出組好的 PDF";
        ok = false;
    }
    pdfium.CloseDocument(dest);

    if (!ok) return out;
    out.ok = true;
    out.pages = imported;
    return out;
}

namespace {

constexpr double kMaxRenderSide = 12000.0;        /* 單邊像素上限 */
constexpr double kMaxRenderPixels = 80000000.0;   /* 面積上限（約 320 MB RGBA） */

/* dpi/72，只有異常大的頁面才等比例縮小到上限內（engine.py 的 render_scale 用相同規則）。 */
double capped_scale(double width_pt, double height_pt, double dpi) {
    double scale = dpi / 72.0;
    const double w0 = width_pt * scale, h0 = height_pt * scale;
    const double side = (std::max)(w0, h0), area = w0 * h0;
    if (side > kMaxRenderSide || area > kMaxRenderPixels)
        scale *= (std::min)(kMaxRenderSide / side, std::sqrt(kMaxRenderPixels / area));
    return scale;
}

/* 在已開啟的文件內渲染第 index（0 起算）頁成 PNG；兩個公開入口共用。 */
RenderOutcome render_page_in_document(Pdfium &pdfium, FPDF_DOCUMENT doc, int index, double dpi,
                                      const std::string &png_path_utf8) {
    RenderOutcome out;
    FPDF_PAGE page = pdfium.LoadPage(doc, index);
    if (!page) {
        out.error = "無法載入頁面";
        return out;
    }
    /* 像素上限：異常的 MediaBox 可能要求數 GB 的點陣圖。一般頁面（A0 @200 dpi 約 6600×9400）不受影響。 */
    const double scale = capped_scale(static_cast<double>(pdfium.GetPageWidthF(page)),
                                      static_cast<double>(pdfium.GetPageHeightF(page)), dpi);
    /* pypdfium2 以 ceil 計算像素尺寸（實測 595×842 pt @150 dpi → 1240×1755），必須一致才能逐像素比對。 */
    const int width = static_cast<int>(std::ceil(static_cast<double>(pdfium.GetPageWidthF(page)) * scale));
    const int height = static_cast<int>(std::ceil(static_cast<double>(pdfium.GetPageHeightF(page)) * scale));
    if (width <= 0 || height <= 0) {
        pdfium.ClosePage(page);
        out.error = "頁面尺寸無效";
        return out;
    }
    /* alpha=1 → PDFium 的 BGRA 格式，搭配 FPDF_REVERSE_BYTE_ORDER 變成 RGBA 輸出；
       白底讓 alpha 恆為 255，於是 PDFium 的緩衝可以直接寫成 PNG，不必逐像素重排。 */
    FPDF_BITMAP bitmap = pdfium.Bitmap_Create(width, height, 1);
    if (!bitmap) {
        pdfium.ClosePage(page);
        out.error = "無法建立位圖";
        return out;
    }
    pdfium.Bitmap_FillRect(bitmap, 0, 0, width, height, FPDF_WHITE);
    pdfium.RenderPageBitmap(bitmap, page, 0, 0, width, height, 0, FPDF_ANNOT | FPDF_REVERSE_BYTE_ORDER);
    const int stride = pdfium.Bitmap_GetStride(bitmap);
    const void *pixels = pdfium.Bitmap_GetBuffer(bitmap);
    const int written = swbd_write_png_utf8(png_path_utf8.c_str(), width, height, 4, pixels, stride);
    pdfium.Bitmap_Destroy(bitmap);
    pdfium.ClosePage(page);
    out.ok = written != 0;
    out.width = width;
    out.height = height;
    if (!out.ok) out.error = "PNG 寫入失敗";
    return out;
}

}  // namespace

RenderOutcome render_page_to_png(Pdfium &pdfium, const std::string &pdf_path_utf8,
                                 int page_1based, double dpi, const std::string &png_path_utf8) {
    RenderOutcome out;
    FPDF_DOCUMENT doc = pdfium.LoadDocument(pdf_path_utf8.c_str(), nullptr);
    if (!doc) {
        out.error = pdfium.last_error_text();
        return out;
    }
    const int count = pdfium.GetPageCount(doc);
    if (page_1based < 1 || page_1based > count) {
        pdfium.CloseDocument(doc);
        out.error = "頁面不存在";
        return out;
    }
    out = render_page_in_document(pdfium, doc, page_1based - 1, dpi, png_path_utf8);
    pdfium.CloseDocument(doc);
    return out;
}

RenderAll render_pages(Pdfium &pdfium, const std::string &pdf_path_utf8, const std::string &password,
                       const std::vector<int> &indices, double dpi,
                       const std::function<double(int, double, double)> &dpi_for,
                       const std::function<std::string(int)> &namer,
                       const std::string &folder_utf8, const std::string &extension,
                       const std::function<bool(int, int)> &progress, int encode_threads) {
    RenderAll out;
    if (extension != "png") {   /* JPEG 的編碼器與 Pillow 不同，接手會讓輸出不再是位元等價 */
        out.error = "原生 PDF 渲染目前只支援 PNG";
        return out;
    }
    FPDF_DOCUMENT doc = pdfium.LoadDocument(pdf_path_utf8.c_str(), password.empty() ? nullptr : password.c_str());
    if (!doc) {
        out.error = pdfium.last_error_text();
        return out;
    }
    const int pages = pdfium.GetPageCount(doc);
    out.pages = pages;
    if (pages <= 0) {
        pdfium.CloseDocument(doc);
        out.error = "這份 PDF 沒有頁面";
        return out;
    }
    if (encode_threads < 1) encode_threads = 1;

    /* 渲染必須序列化（PDFium 非執行緒安全，呼叫端已持鎖），但 PNG 編碼是純 CPU 工作，
       可以像 engine.py 那樣與下一頁的渲染重疊——這是追上 Python 效能的關鍵。 */
    struct Task {
        std::string path;
        int width = 0, height = 0, stride = 0;
        std::vector<unsigned char> pixels;
    };
    std::deque<Task> queue;
    std::mutex mutex;
    std::condition_variable has_work, has_room;
    bool stopping = false;
    std::string failure;
    int outstanding = 0;
    bool cancelled = false;

    auto worker = [&]() {
        for (;;) {
            Task task;
            {
                std::unique_lock<std::mutex> lock(mutex);
                has_work.wait(lock, [&] { return stopping || !queue.empty(); });
                if (queue.empty()) return;
                task = std::move(queue.front());
                queue.pop_front();
            }
            int written = 0;
            {
                std::lock_guard<std::mutex> lock(mutex);
                if (cancelled) { outstanding--; has_room.notify_all(); continue; }
            }
            /* 渲染緩衝是 RGBA（FPDF_REVERSE_BYTE_ORDER）；Pillow 產生的是 RGB，
               所以在編碼執行緒裡去掉 alpha 通道，讓輸出格式與原本完全一致。
               這個重排放在worker 裡才不會變成瓶頸。 */
            const int width = task.width, height = task.height;
            std::string error;
            /* 例外不能離開 std::thread（會 std::terminate 整個程式）：在這裡接住，寫進 failure。 */
            try {
                std::vector<unsigned char> rgb(static_cast<size_t>(width) * static_cast<size_t>(height) * 3u);
                for (int y = 0; y < height; y++) {
                    const unsigned char *source = task.pixels.data() + static_cast<size_t>(y) * static_cast<size_t>(task.stride);
                    unsigned char *dest = rgb.data() + static_cast<size_t>(y) * static_cast<size_t>(width) * 3u;
                    for (int x = 0; x < width; x++) {
                        dest[x * 3 + 0] = source[x * 4 + 0];
                        dest[x * 3 + 1] = source[x * 4 + 1];
                        dest[x * 3 + 2] = source[x * 4 + 2];
                    }
                }
                written = swbd_write_png_utf8(task.path.c_str(), width, height, 3,
                                              rgb.data(), width * 3);
            } catch (const std::bad_alloc &) {
                error = "記憶體不足，無法編碼這一頁";
            } catch (const std::exception &ex) {
                error = std::string("PNG 編碼失敗：") + ex.what();
            } catch (...) {
                error = "PNG 編碼失敗";
            }
            task.pixels = std::vector<unsigned char>();      /* 早點還記憶體 */
            {
                std::lock_guard<std::mutex> lock(mutex);
                if (!error.empty() && failure.empty()) failure = error;
                if (!written && failure.empty()) failure = "PNG 寫入失敗";
                outstanding--;
                has_room.notify_all();
            }
        }
    };
    std::vector<std::thread> workers;
    workers.reserve(static_cast<size_t>(encode_threads));
    for (int i = 0; i < encode_threads; i++) workers.emplace_back(worker);

    std::vector<int> targets = indices;
    if (targets.empty()) {
        for (int i = 0; i < pages; i++) targets.push_back(i);
    }
    for (size_t slot = 0; slot < targets.size(); slot++) {
        const int index = targets[slot];                 /* 0 起算的原始頁碼 */
        if (index < 0 || index >= pages) { failure = "頁碼超出範圍"; break; }
        FPDF_PAGE page = pdfium.LoadPage(doc, index);
        if (!page) { failure = "無法載入頁面"; break; }
        const double page_width = static_cast<double>(pdfium.GetPageWidthF(page));
        const double page_height = static_cast<double>(pdfium.GetPageHeightF(page));
        const double page_dpi = dpi_for ? dpi_for(index, page_width, page_height) : dpi;
        const double scale = capped_scale(page_width, page_height, page_dpi > 0 ? page_dpi : 72.0);
        const int width = static_cast<int>(std::ceil(page_width * scale));
        const int height = static_cast<int>(std::ceil(page_height * scale));
        FPDF_BITMAP bitmap = (width > 0 && height > 0) ? pdfium.Bitmap_Create(width, height, 1) : nullptr;
        if (!bitmap) {
            pdfium.ClosePage(page);
            failure = "無法建立位圖";
            break;
        }
        pdfium.Bitmap_FillRect(bitmap, 0, 0, width, height, FPDF_WHITE);
        pdfium.RenderPageBitmap(bitmap, page, 0, 0, width, height, 0, FPDF_ANNOT | FPDF_REVERSE_BYTE_ORDER);
        const int stride = pdfium.Bitmap_GetStride(bitmap);
        Task task;
        char fallback[32];
        std::snprintf(fallback, sizeof fallback, "%03d.%s", index + 1, extension.c_str());
        const std::string leaf = namer ? namer(index) : std::string(fallback);
        task.path = folder_utf8 + "\\" + leaf;
        task.width = width;
        task.height = height;
        task.stride = stride;
        try {
            task.pixels.resize(static_cast<size_t>(stride) * static_cast<size_t>(height));
        } catch (const std::bad_alloc &) {
            pdfium.Bitmap_Destroy(bitmap);
            pdfium.ClosePage(page);
            std::lock_guard<std::mutex> lock(mutex);
            if (failure.empty()) failure = "記憶體不足，無法渲染這一頁";
            break;                                        /* 照常往下：等編碼執行緒結束並 join */
        }
        std::memcpy(task.pixels.data(), pdfium.Bitmap_GetBuffer(bitmap), task.pixels.size());
        pdfium.Bitmap_Destroy(bitmap);
        pdfium.ClosePage(page);
        out.rendered = static_cast<int>(slot) + 1;
        if (progress && !progress(out.rendered, static_cast<int>(targets.size()))) { cancelled = true; break; }
        {
            std::unique_lock<std::mutex> lock(mutex);
            has_room.wait(lock, [&] { return outstanding < encode_threads * 2; });
            if (!failure.empty()) break;                  /* 編碼執行緒已失敗：不再排新頁 */
            queue.push_back(std::move(task));
            outstanding++;
            has_work.notify_one();
        }
    }
    {
        std::unique_lock<std::mutex> lock(mutex);
        has_room.wait(lock, [&] { return outstanding == 0; });
        stopping = true;
        has_work.notify_all();
    }
    for (auto &t : workers) t.join();
    pdfium.CloseDocument(doc);

    if (cancelled) {
        out.cancelled = true;
        return out;
    }
    if (!failure.empty()) {
        out.error = failure;
        return out;
    }
    out.ok = true;
    return out;
}

}  // namespace swbd::pdf
