#!/bin/sh
# Cross-compiles FO4SFBorder.dll with mingw-w64, static, so the PC needs no runtime beyond Windows' own DLLs.
# Needs PluginAPI.h next to this file: copy it from ../FOCCSidecar after fetch_pluginapi.ps1, or run that script
# with -Dest pointing here (SFSE commit 48535cc, sha256 10b834f1...; never committed).
# Usage: sfse/FO4SFBorder/build.sh OUT_DIR
set -eu
here=$(cd "$(dirname "$0")" && pwd)
out=${1:?usage: build.sh OUT_DIR}
mkdir -p "$out"
[ -f "$here/PluginAPI.h" ] || { echo "PluginAPI.h missing in $here" >&2; exit 1; }
x86_64-w64-mingw32-g++ -std=c++20 -O2 -Wall -Wextra -Werror -shared -static -s \
    -o "$out/FO4SFBorder.dll" "$here/FO4SFBorder.cpp" -lshell32 -lole32 -luuid
cp "$here/FO4SFBorder.ini" "$out/"
cd "$out" && sha256sum FO4SFBorder.dll FO4SFBorder.ini
