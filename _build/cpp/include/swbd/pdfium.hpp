/* 原生 PDF 層的基礎：PDFium 的 C API。
 *
 * 為什麼是 PDFium 而不是直接綁 PyMuPDF 內部的 mupdfcpp64.dll：
 *   MuPDF 的 C API 用 setjmp/longjmp（fz_try）傳遞錯誤，而 fz_try 需要 fz_context 的內部佈局；
 *   PyMuPDF 只隨附 DLL、沒有 MuPDF 標頭，硬寫佈局會是無法驗證的風險。
 *   PDFium（已隨附，BSD-3）與 qpdf 的 C API 都只用回傳碼，握把是 opaque 指標，
 *   因此手寫最小宣告即可安全使用，且缺少符號時能乾淨降級回 Python。
 *
 * DLL 以 LoadLibraryW 動態載入：不引入 import lib，也不在載入期失敗。
 */
#ifndef SWBD_CPP_PDFIUM_HPP
#define SWBD_CPP_PDFIUM_HPP

#include <functional>
#include <string>
#include <vector>

namespace swbd::pdf {

using FPDF_DOCUMENT = void *;
using FPDF_PAGE = void *;
using FPDF_BITMAP = void *;

/* PDFium 的寫入回呼結構（公開標頭的佈局，台灣縮寫照抄以免對不上 ABI）。
   版本必須是 1，WriteBlock 回傳非零代表成功。 */
struct FPDF_FILEWRITE {
    int version;
    int (*WriteBlock)(FPDF_FILEWRITE *self, const void *data, unsigned long size);
};

class Pdfium {
public:
    static Pdfium &instance();

    /* 依序在 base_dir\_internal\pypdfium2_raw、base_dir\_internal\pypdfium2、base_dir 底下尋找 pdfium.dll。
       回傳 false 表示這一版沒有可用的原生 PDF 層，呼叫端照舊交給 Python。 */
    bool load(const std::string &base_dir);
    bool ready() const { return ready_; }
    const std::string &path() const { return path_; }
    std::string last_error_text() const;

    /* PDFium 公開 C API 的子集（回傳碼制） */
    void (*InitLibrary)();
    void (*DestroyLibrary)();
    FPDF_DOCUMENT (*LoadDocument)(const char *path, const char *password);
    void (*CloseDocument)(FPDF_DOCUMENT);
    int (*GetPageCount)(FPDF_DOCUMENT);
    FPDF_PAGE (*LoadPage)(FPDF_DOCUMENT, int);
    void (*ClosePage)(FPDF_PAGE);
    float (*GetPageWidthF)(FPDF_PAGE);
    float (*GetPageHeightF)(FPDF_PAGE);
    unsigned long (*GetMetaText)(FPDF_DOCUMENT, const char *tag, void *buffer, unsigned long length);
    unsigned long (*GetLastError)();
    int (*GetSecurityHandlerRevision)(FPDF_DOCUMENT);   /* > 0 表示文件有加密處理常式 */

    /* 渲染用的子集（與 engine.py 的 pypdfium2 page.render 對齊） */
    FPDF_BITMAP (*Bitmap_Create)(int width, int height, int alpha);
    void (*Bitmap_FillRect)(FPDF_BITMAP, int left, int top, int width, int height, unsigned long color);
    void (*RenderPageBitmap)(FPDF_BITMAP, FPDF_PAGE, int x, int y, int width, int height, int rotate, int flags);
    void *(*Bitmap_GetBuffer)(FPDF_BITMAP);
    int (*Bitmap_GetStride)(FPDF_BITMAP);
    void (*Bitmap_Destroy)(FPDF_BITMAP);

    /* 組頁用的子集（選用；缺少時合併會降級回 Python，渲染不受影響） */
    FPDF_DOCUMENT (*CreateNewDocument)();
    int (*ImportPages)(FPDF_DOCUMENT dest, FPDF_DOCUMENT src, const char *pagerange, int index);
    int (*ImportPagesByIndex)(FPDF_DOCUMENT dest, FPDF_DOCUMENT src, const int *page_indices, int length, int index);
    int (*SaveAsCopy)(FPDF_DOCUMENT doc, FPDF_FILEWRITE *writer, unsigned long flags);
    FPDF_PAGE (*Page_New)(FPDF_DOCUMENT doc, int page_index, double width, double height);   /* p_organize 的空白頁 */
    int (*Page_Flatten)(FPDF_PAGE page, int flags);                                          /* p_flatten */
    bool can_merge() const { return CreateNewDocument && ImportPages && SaveAsCopy; }
    bool can_select() const { return CreateNewDocument && ImportPagesByIndex && SaveAsCopy; }

private:
    Pdfium() = default;
    bool ready_ = false;
    std::string path_;
    void *module_ = nullptr;
};

/* 讀取 PDF 中繼資料（PDFium 以 UTF-16LE 回傳）；不存在時回傳空字串。 */
std::string meta_text(Pdfium &pdfium, FPDF_DOCUMENT doc, const char *tag);

/* 把一份 PDF 的基本資訊寫成 JSON：{"pages":N,"sizes":[[w,h],…],"title":…,"author":…,"producer":…,"creator":…} */
std::string describe_document(Pdfium &pdfium, const std::string &path_utf8);

/* 渲染結果。width/height 是實際產生的像素尺寸，失敗時 error 有說明。 */
struct RenderOutcome {
    bool ok = false;
    int width = 0;
    int height = 0;
    std::string error;
};

/* 把第 page（1 起算）頁以 dpi 渲染成 PNG。實作刻意對齊 engine.py 的
   pypdfium2 `page.render(scale=dpi/72)`：BGRA 位圖、白底、FPDF_ANNOT 旗標，
   最後轉成 RGBA 交給 stb_image_write（同一份像素，換一個編碼器）。 */
RenderOutcome render_page_to_png(Pdfium &pdfium, const std::string &pdf_path_utf8,
                                int page_1based, double dpi, const std::string &png_path_utf8);

/* 整份文件的渲染：開檔一次、逐頁輸出 <folder>/001.<ext>（與 engine.py _pdf_pages 相同的命名）。
   progress(done, total) 回傳 false 代表取消。目前只支援 png——JPEG 的編碼器與 Pillow 不同，
   要維持「輸出結果一致」就必須先換到相容的編碼器才能接手。 */
struct RenderAll {
    bool ok = false;
    int pages = 0;
    int rendered = 0;
    bool cancelled = false;
    std::string error;
};

/* 一般化版本：可指定頁碼、密碼、逐頁 dpi 與自訂檔名（p_pdf_images 的「每頁轉成圖片」）。
   indices 是 0 起算的原始頁碼（依序）；dpi_for／namer 收到原始頁碼。仍舊只開檔一次。 */
RenderAll render_pages(Pdfium &pdfium, const std::string &pdf_path_utf8, const std::string &password,
                       const std::vector<int> &indices, double dpi,
                       const std::function<double(int index, double w, double h)> &dpi_for,
                       const std::function<std::string(int index)> &namer,
                       const std::string &folder_utf8, const std::string &extension,
                       const std::function<bool(int, int)> &progress, int encode_threads);

/* 整份文件、固定 dpi、<folder>/001.png 命名（engine.py _pdf_pages 用）。 */
RenderAll render_all_pages(Pdfium &pdfium, const std::string &pdf_path_utf8, double dpi,
                           const std::string &folder_utf8, const std::string &extension,
                           const std::function<bool(int done, int total)> &progress,
                           int encode_threads = 1);

/* 多份 PDF 依序組成一份（PDFium 的 FPDF_ImportPages），結果留在記憶體。
   呼叫端通常再交給 qpdf 重新壓縮——這正是 engine.py 合併路徑做的事（組頁＋重壓）。
   progress(done, total) 以「已匯入頁數／總頁數」回報，回傳 false 代表取消。 */
struct MergeResult {
    bool ok = false;
    int pages = 0;
    bool cancelled = false;
    std::string error;
};

MergeResult merge_documents(Pdfium &pdfium, const std::vector<std::string> &inputs_utf8,
                            const std::string &password, std::vector<unsigned char> &output,
                            const std::function<bool(int done, int total)> &progress);

/* 未提供密碼時的空密碼版本（PDF→PDF 的合併轉檔用）。 */
MergeResult merge_documents(Pdfium &pdfium, const std::vector<std::string> &inputs_utf8,
                            std::vector<unsigned char> &output,
                            const std::function<bool(int done, int total)> &progress);

/* 開檔並回報頁數；失敗時 error 用 pdf_tools.open_pdf 的同一句話：
   「文件沒有可讀取的 PDF 頁面」／「PDF 需要正確的文件密碼」。成功回傳頁數（> 0）。 */
int open_page_count(Pdfium &pdfium, const std::string &pdf_path_utf8, const std::string &password,
                    std::string &error);

/* 同上，另外回報文件是否有加密處理常式（Python 的 reader.is_encrypted）。 */
int open_document_info(Pdfium &pdfium, const std::string &pdf_path_utf8, const std::string &password,
                       int *encrypted, std::string &error);

/* pdf_tools.indices 的等價實作：解析「1,3-5,8-」（也接受全形逗號）。
   空白＝全部頁面；allow_repeat 對應 p_extract 的重複選取。失敗時 error 是同一句錯誤訊息。 */
bool parse_page_spec(const std::string &spec, int count, bool allow_repeat,
                     std::vector<int> &out_zero_based, std::string &error);

/* 依索引（0 起算，依給定順序）重新組頁，結果留在記憶體。 */
MergeResult select_pages(Pdfium &pdfium, const std::string &pdf_path_utf8, const std::string &password,
                         const std::vector<int> &indices, std::vector<unsigned char> &output);

/* 逐頁重建：只保留「載入並以低解析度渲染得出來」的頁面（p_repair 的第二條路徑）。
   unreadable 會填入 1 起算、無法恢復的頁碼；回傳可恢復頁數，-1 表示完全失敗。 */
int rebuild_readable_pages(Pdfium &pdfium, const std::string &pdf_path_utf8, const std::string &password,
                           std::vector<unsigned char> &output, std::vector<int> &unreadable,
                           const std::function<bool(int done, int total)> &progress);

/* 逐頁壓平（把註記與表單畫進頁面內容，p_flatten／PyMuPDF 的 bake(annots,widgets)）。 */
MergeResult flatten_document(Pdfium &pdfium, const std::string &pdf_path_utf8,
                             const std::string &password, std::vector<unsigned char> &output);

/* 依索引組頁，並在選取的原始頁碼之後插入同尺寸空白頁（p_organize 的 blank 模式）。 */
MergeResult assemble_with_blanks(Pdfium &pdfium, const std::string &pdf_path_utf8, const std::string &password,
                                 const std::vector<int> &selected, std::vector<unsigned char> &output);

}  // namespace swbd::pdf

#endif
