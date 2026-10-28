# FOCCPing: the B0 spike's SFSE plugin, one Papyrus native (FOCC.Ping(int) answers int + 1) bound through CommonLibSF
# (docs/combined-core-cpp-port.md section 4; docs/spikes/combined-core-probes.md section B0). Built against an INSTALLED
# CommonLibSF (the `cmake --install` of the PC's configured tree at 9caec20) and the spdlog and fmt its vcpkg run built
# (x64-windows-static-md-release: static libraries, dynamic CRT), both handed in as CMAKE_PREFIX_PATH by build.ps1. No
# vcpkg run of its own, no CommonLibSF source in this repo.
cmake_minimum_required(VERSION 3.28)
project(FOCCPing VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
# the vcpkg triplet CommonLibSF was built with links the CRT dynamically; a plugin must match or the link fails
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>DLL")

find_package(CommonLibSF CONFIG REQUIRED)        # its config finds spdlog (and fmt) through CMAKE_PREFIX_PATH

add_library(FOCCPing SHARED src/main.cpp src/Plugin.h)
# CommonLibSF::CommonLibSF carries its PUBLIC definitions (WINVER, WIN32_LEAN_AND_MEAN, NOMINMAX, _ITERATOR_DEBUG_LEVEL=0)
# and options (/bigobj and the warning filters), so the plugin compiles the way the library was compiled
target_link_libraries(FOCCPing PRIVATE CommonLibSF::CommonLibSF)
target_compile_options(FOCCPing PRIVATE /W4 /permissive- /Zc:__cplusplus /utf-8 /EHsc)
set_target_properties(FOCCPing PROPERTIES OUTPUT_NAME "FOCCPing" PREFIX "")
