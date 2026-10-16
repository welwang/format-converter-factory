# 四維八德 native shell — C++20 architecture (Win32 + Microsoft Edge WebView2).
#
# Windows (the shipped product):
#   cmake -S . -B out\cmake -DSWBD_WEBVIEW2_SDK=sdk
#   cmake --build out\cmake --config Release
#   -> out\cmake\bin\Release\swbd-shell.exe   (deployed as 四維八德.exe)
#   build_shell.ps1 downloads the SDK and drives exactly this build; build.ps1 calls that script.
#
# POSIX (engine only, used by the Linux test drivers in test\): the same file builds swbd_core
#   with g++ so the platform-neutral engine layer stays buildable and testable off Windows.
cmake_minimum_required(VERSION 3.25)
project(SiWeiBaDe LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)


if(MSVC)
    # Static C runtime: the shipped shell needs no Visual C++ Redistributable, as in the 2.3.x builds.
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
    add_compile_options(/utf-8 /W3 /GS /guard:cf /permissive-)
    add_link_options(/GUARD:CF)
endif()

if(WIN32)
    set(SWBD_WEBVIEW2_SDK "${CMAKE_CURRENT_SOURCE_DIR}/sdk" CACHE PATH "WebView2 SDK root (build/native/...)")
    set(SWBD_WV2_INCLUDE "${SWBD_WEBVIEW2_SDK}/build/native/include")
    set(SWBD_WV2_LIB     "${SWBD_WEBVIEW2_SDK}/build/native/x64/WebView2LoaderStatic.lib")
    if(NOT EXISTS "${SWBD_WV2_INCLUDE}/WebView2.h")
        message(FATAL_ERROR "WebView2 SDK not found under ${SWBD_WEBVIEW2_SDK}; run build_shell.ps1, which downloads it.")
    endif()
    # shell.rc names ..\logo.ico and app.manifest relative to this folder, while rc runs in the build tree.
    set(CMAKE_RC_FLAGS "${CMAKE_RC_FLAGS} /I \"${CMAKE_CURRENT_SOURCE_DIR}\"")
endif()

# ---------------------------------------------------------------- the platform-neutral core
add_library(swbd_core STATIC
    engine.cpp
    api.cpp
    plat.cpp
    json.cpp)

target_include_directories(swbd_core PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}")
# The C ABI seam to the C++ core (api.cpp includes swbd/bridge.hpp); the core itself is added below.
target_include_directories(swbd_core PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/../cpp/include")
target_compile_definitions(swbd_core PUBLIC UNICODE _UNICODE)

if(WIN32)
    target_link_libraries(swbd_core PUBLIC user32 advapi32 shell32 ole32 oleaut32 uuid)
else()
    find_package(Threads REQUIRED)
    target_compile_definitions(swbd_core PUBLIC _GNU_SOURCE)
    target_link_libraries(swbd_core PUBLIC Threads::Threads)
endif()

# ---------------------------------------------------------------- method-level C++ takeover layer
# ../cpp holds the C++ core that takes page methods over from the Python component one by one.
# It shares this single CMake project (no second project) and links swbd_core instead of
# compiling json/plat a second time.
if(WIN32)
    add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../cpp" "${CMAKE_BINARY_DIR}/swbd-cpp")
endif()

# ---------------------------------------------------------------- the Windows window (product)
if(WIN32)
    add_executable(swbd-shell WIN32
        main.cpp
        shell.rc)

    target_include_directories(swbd-shell PRIVATE "${SWBD_WV2_INCLUDE}")
    target_link_directories(swbd-shell PRIVATE "${SWBD_WEBVIEW2_SDK}/build/native/x64")
    target_link_libraries(swbd-shell PRIVATE swbd_core swbd_cpp "${SWBD_WV2_LIB}")
    # shell.rc embeds app.manifest as resource 1; Visual Studio would otherwise generate a second one.
    target_link_options(swbd-shell PRIVATE /MANIFEST:NO)

    set_target_properties(swbd-shell PROPERTIES
        OUTPUT_NAME "swbd-shell"
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
endif()
