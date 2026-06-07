#!/usr/bin/env bash
# Phase D：打 standalone .app（macOS）。
#
# 把"嵌入式 Python 组装 + 业务包安装 + Rust 链接参数 + tauri bundle"整条
# 流程固化下来。**不要手工跑其中某几步**——漏掉 PYO3_PYTHON / RUSTFLAGS
# 会让 pyo3 链接到系统 Python（CLT 的 Python3.framework 3.9），.app 启动
# 即 dyld crash（2026-06-07 实测翻车过一次，见 ADR-005）。
#
# 用法：
#   ./scripts/build_standalone.sh            # 全量构建
#   BOSS_PYEMBED_REBUILD=1 ./scripts/...     # 强制重建 pyembed
#
# 产物：src-tauri/target/bundle-release/bundle/macos/BOSS Zhipin Helper.app
set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT=$(pwd)

PYEMBED_DIR="$REPO_ROOT/src-tauri/pyembed"
PYTHON_SERIES="3.13"   # 跟 pyproject requires-python 对齐

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "❌ 目前只支持 macOS（Linux/Windows 的 rpath / install_name 处理不同）"
    echo "   Windows 端用 scripts/build_standalone.ps1"
    exit 1
fi

# Cargo.lock v4 需要 Cargo >=1.78，老版本在 step 5 才炸太晚
cargo_ver=$(cargo --version 2>/dev/null | sed -n 's/cargo \([0-9]*\)\.\([0-9]*\).*/\1.\2/p')
if [[ -z "$cargo_ver" ]]; then
    echo "❌ 找不到 cargo，请先装 rustup"; exit 1
fi
cargo_major=${cargo_ver%.*}; cargo_minor=${cargo_ver#*.}
if (( cargo_major < 1 || (cargo_major == 1 && cargo_minor < 78) )); then
    echo "❌ Cargo $cargo_ver 太老（需 >=1.78 解析 lockfile v4），跑 'rustup update stable'"
    exit 1
fi

# ---------- 1. 嵌入式 Python（python-build-standalone，经 uv 下载） ----------
if [[ "${BOSS_PYEMBED_REBUILD:-}" == "1" ]]; then
    rm -rf "$PYEMBED_DIR"
fi
if [[ ! -x "$PYEMBED_DIR/python/bin/python3" ]]; then
    echo "==> 下载嵌入式 Python $PYTHON_SERIES（python-build-standalone）"
    mkdir -p "$PYEMBED_DIR"
    UV_PYTHON_INSTALL_DIR="$PYEMBED_DIR/_download" uv python install "$PYTHON_SERIES"
    # uv 落盘目录名带完整版本号（cpython-3.13.x-macos-aarch64-none），规范成 python/
    src_dir=$(find "$PYEMBED_DIR/_download" -maxdepth 1 -type d -name "cpython-*" | head -1)
    [[ -n "$src_dir" ]] || { echo "❌ 没找到 uv 下载的 cpython 目录"; exit 1; }
    mv "$src_dir" "$PYEMBED_DIR/python"
    rm -rf "$PYEMBED_DIR/_download"
fi
EMBED_PY="$PYEMBED_DIR/python/bin/python3"
echo "==> 嵌入式 Python: $("$EMBED_PY" --version)"

# ---------- 2. macOS：libpython install_name 打 @rpath 补丁 ----------
# python-build-standalone 的 libpython install_name 不带 @rpath，导致给
# executable 设的 rpath 失效（pytauri build-standalone 教程明确要求这步）。
libpython=$(find "$PYEMBED_DIR/python/lib" -maxdepth 1 -name "libpython3.*.dylib" | head -1)
[[ -n "$libpython" ]] || { echo "❌ 没找到 libpython3.*.dylib"; exit 1; }
install_name_tool -id "@rpath/$(basename "$libpython")" "$libpython"
echo "==> libpython install_name 已设为 @rpath/$(basename "$libpython")"

# ---------- 3. 把业务包 + 依赖装进嵌入式环境 ----------
# [standalone] extra：pytauri 但不带 pytauri-wheel（ext_mod 由我们的 Rust
# binary 提供）。--exact 保证环境里只有声明过的东西。
# --break-system-packages：uv 把 python-build-standalone 标 PEP 668
# "externally managed"，默认拒绝 pip 写入；本场景就是要往里写，加 flag 放行。
# （2026-06-07 在 Windows 端 .ps1 上踩到，mac 上当时 uv 版本旧没拦，新 uv 两边都会拦。）
echo "==> 安装 boss_zhipin + 依赖到 pyembed（首次会拉 torch，较慢）"
PYTAURI_STANDALONE=1 uv pip install \
    --exact \
    --compile-bytecode \
    --break-system-packages \
    --python="$EMBED_PY" \
    --reinstall-package=boss-zhipin-job-search \
    "$REPO_ROOT[standalone]"

# ---------- 4. Rust 链接参数 ----------
# PYO3_PYTHON：不设的话 pyo3 自动探测系统 Python → 链到 CLT 的
# Python3.framework → .app 启动 dyld crash。这是整个脚本最关键的两行。
export PYO3_PYTHON="$EMBED_PY"
export RUSTFLAGS=" \
    -C link-arg=-Wl,-rpath,@executable_path/../Resources/lib \
    -L $PYEMBED_DIR/python/lib"

# ---------- 5. 前端 + tauri bundle ----------
echo "==> pnpm install（tauri-ui）"
pnpm --dir "$REPO_ROOT/tauri-ui" install --frozen-lockfile

echo "==> tauri build（bundle-release profile）"
# --config tauri.bundle.json：把 pyembed/python 作为 resources 打进 .app；
# 不直接写进 tauri.conf.json 是因为 wheel dev 模式不需要也不该带这坨。
# 注意必须从 repo root 跑——tauri CLI 只往**子目录**找 src-tauri/tauri.conf.json，
# 从 tauri-ui/ 里跑会 "Couldn't recognize the current folder as a Tauri project"。
cd "$REPO_ROOT"
"$REPO_ROOT/tauri-ui/node_modules/.bin/tauri" build \
    --config "$REPO_ROOT/src-tauri/tauri.bundle.json" \
    -- --profile bundle-release

# ---------- 6. 产物自检 ----------
APP=$(find "$REPO_ROOT/src-tauri/target" -maxdepth 4 -name "*.app" -path "*bundle-release*" | head -1)
[[ -n "$APP" ]] || { echo "❌ 没找到 .app 产物"; exit 1; }
BIN="$APP/Contents/MacOS/boss-zhipin"
echo "==> 自检：binary 应链接 @rpath/libpython3.x，不能出现 Python3.framework"
if otool -L "$BIN" | grep -q "Python3.framework"; then
    echo "❌ binary 链接到了系统 Python3.framework——PYO3_PYTHON 没生效？"
    otool -L "$BIN" | grep -i python
    exit 1
fi
otool -L "$BIN" | grep -i python || true
echo "✅ 构建完成：$APP"
