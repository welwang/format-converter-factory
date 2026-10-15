/* 系統層：C++ 核心用到的 Windows 原語，語意刻意對齊 Python 的 os / os.path / tempfile，
   這樣「移植」才是邏輯翻譯，而不是重新發明行為。全部路徑為 UTF-8，內部轉寬字元呼叫 Win32。 */
#ifndef SWBD_CPP_SYS_HPP
#define SWBD_CPP_SYS_HPP

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace swbd::sys {

/* 檔案狀態。mtime 同時提供秒（double，對齊 Python st_mtime）與 100ns 整數（精確比對用）。 */
struct FileInfo {
    bool ok = false;          /* 取得狀態成功（檔案或目錄存在且可讀取屬性） */
    bool is_dir = false;
    bool is_reparse = false;  /* 符號連結或 junction：Python 的 os.path.islink / st_file_attributes & 0x400 */
    bool is_regular = false;  /* S_ISREG */
    std::uint64_t size = 0;
    double mtime = 0;         /* 秒，1970 起算 */
    std::int64_t mtime_ticks = 0;  /* 100ns，1601 起算（FILETIME） */
};

struct DirEntry {
    std::string name;
    bool is_dir = false;
    bool is_reparse = false;
};

/* os.path.abspath：只做正規化，不解析連結、不要求存在。 */
std::string abs_path(std::string_view path);
/* os.path.realpath：解析連結後的最終路徑（去 \\?\ 前綴）。 */
std::string final_path(std::string_view path);
/* os.path.normcase：Windows 上轉小寫。 */
std::string norm_case(std::string_view path);
/* os.path.join：需要時補上反斜線。 */
std::string join(std::string_view a, std::string_view b);
/* os.path.basename。 */
std::string base_name(std::string_view path);

/* tempfile.gettempdir()：TMPDIR → TEMP → TMP（可寫入者優先），最後退回 GetTempPathW。無尾端斜線。 */
std::string system_temp_dir();

/* os.stat（跟隨連結）/ os.lstat（不跟隨）。 */
bool stat_path(std::string_view path, FileInfo &out);
bool lstat_path(std::string_view path, FileInfo &out);

/* os.listdir：不排序，回傳項目的 lstat 資訊。 */
std::vector<DirEntry> list_dir(std::string_view path);

/* os.path.commonpath 的包含判斷：child 在 root 之內（皆先 realpath + normcase），且 child != root。 */
bool path_inside(std::string_view child, std::string_view root);
/* os.path.normcase(os.path.realpath(a)) == normcase(realpath(b)) */
bool same_path(std::string_view a, std::string_view b);

/* 刪除單一檔案（os.remove）。 */
bool remove_file(std::string_view path);

/* 現在時間（秒，1970 起算）。 */
double now_s();

/* 錯誤訊息：GetLastError 的可讀文字（UTF-8）。 */
std::string last_error_text();

}  // namespace swbd::sys

#endif
