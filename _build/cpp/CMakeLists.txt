# 四維八德 C++ 核心（方法級接手層）。
#
# 兩種用法：
#  1. 單一專案（正式建置）：由 ../shell/CMakeLists.txt 以 add_subdirectory 納入，
#     此時連結父層的 swbd_core，不重複編譯 json/plat，只有一個 CMake 專案。
#  2. 獨立建置（驗證用）：cmake -S _build/cpp -B _build/cpp/build，自行編 json/plat 當底層。
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    cmake_minimum_required(VERSION 3.24)
    project(swbd_cpp LANGUAGES C CXX)
    set(CMAKE_C_STANDARD 11)
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(MSVC)
    add_compile_options(/utf-8 /W4 /permissive- /EHsc /guard:cf /GS)
    add_compile_definitions(UNICODE _UNICODE _CRT_SECURE_NO_WARNINGS)
    # 與 shell 相同：靜態執行階段，程式本身不需要 VC++ 可轉散發套件
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()

set(SWBD_SHELL_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../shell" CACHE PATH "既有 shell 目錄（json/plat 與 C ABI 邊界）")

# 單一專案模式下共用父層的 swbd_core（engine/api/plat/json），避免同一個 exe 出現重複符號。
if(TARGET swbd_core)
    set(SWBD_CPP_BASE swbd_core)
else()
    add_library(swbd_c_base STATIC
        "${SWBD_SHELL_DIR}/json.cpp"
        "${SWBD_SHELL_DIR}/plat.cpp")
    target_include_directories(swbd_c_base PUBLIC "${SWBD_SHELL_DIR}")
    set(SWBD_CPP_BASE swbd_c_base)
endif()

# 刻意使用 OBJECT 程式庫：模組靠靜態初始化自我註冊，
# 若做成靜態程式庫且無人引用，連結器會把整個 .obj 丟掉，方法就「沒有人接手」。
add_library(swbd_cpp OBJECT
    src/registry.cpp
    src/sys.cpp
    src/bridge.cpp
    src/pdf/pdfium_api.cpp
    src/pdf/png_writer.cpp
    src/pdf/qpdf_api.cpp
    third_party/zlib/adler32.c
    third_party/zlib/compress.c
    third_party/zlib/deflate.c
    third_party/zlib/trees.c
    third_party/zlib/zutil.c
    src/modules/system_tools.cpp
    src/modules/shell_actions.cpp
    src/modules/pdf_tools.cpp)
target_include_directories(swbd_cpp PUBLIC include "${SWBD_SHELL_DIR}"
    "${CMAKE_CURRENT_SOURCE_DIR}/third_party/stb"
    "${CMAKE_CURRENT_SOURCE_DIR}/third_party/zlib")
# 只需要 zlib 格式（PNG 用），所以關掉 gzip 包裝：deflate.c 就不會再依賴 crc32（那張表格近 600 KB）。
target_compile_definitions(swbd_cpp PRIVATE NO_GZIP)
target_link_libraries(swbd_cpp PUBLIC ${SWBD_CPP_BASE})
