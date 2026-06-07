# Phase D：Windows 上打 standalone .exe / NSIS / MSI（macOS .app 的等价物）。
#
# 跟 build_standalone.sh 平行——固化"嵌入式 Python 组装 + 业务包安装 +
# Rust 链接参数 + tauri bundle"整条流程。**不要手工拆步骤跑**：漏掉
# PYO3_PYTHON / RUSTFLAGS 会让 pyo3 自动探测到系统 Python，bundle 后启动
# 直接 LoadLibrary 失败（参考 macOS 同样的坑，见 ADR-005）。
#
# 用法（PowerShell）：
#   .\scripts\build_standalone.ps1
#   $env:BOSS_PYEMBED_REBUILD = '1'; .\scripts\build_standalone.ps1   # 强制重建 pyembed
#
# 产物：
#   src-tauri\target\bundle-release\boss-zhipin.exe                  （raw exe）
#   src-tauri\target\bundle-release\bundle\nsis\*-setup.exe          （NSIS 安装器）
#   src-tauri\target\bundle-release\bundle\msi\*.msi                 （MSI 安装器）
#
# 前置：
#   - Visual Studio Build Tools（含 "Desktop development with C++" workload）
#   - uv（用于装嵌入式 Python + 业务包）
#   - pnpm（前端构建）
#   - 不需要 install_name_tool / otool：Windows PE 解析 DLL 是同目录优先，
#     bundle 后 python313.dll 跟 boss-zhipin.exe 同级即可

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $RepoRoot

$PyembedDir   = Join-Path $RepoRoot 'src-tauri\pyembed'
$PythonSeries = '3.13'   # 跟 pyproject requires-python 对齐
$EmbedPy      = Join-Path $PyembedDir 'python\python.exe'

# ---------- 0. 前置工具链检查 ----------
# Cargo.lock 在 mac 端用 Cargo >=1.78 生成（lockfile v4），低版本直接
# "lock file version 4 ... does not understand"。在 step 5 才炸太晚——
# 已经花了几十分钟拉 torch 和编前端，这里 fail-fast。
$CargoVersionLine = (& cargo --version) 2>$null
if ($LASTEXITCODE -ne 0 -or -not $CargoVersionLine) {
    throw "找不到 cargo——装 Visual Studio Build Tools + rustup 之后重跑"
}
if ($CargoVersionLine -match 'cargo (\d+)\.(\d+)') {
    $major = [int]$Matches[1]; $minor = [int]$Matches[2]
    if ($major -lt 1 -or ($major -eq 1 -and $minor -lt 78)) {
        throw "Cargo $major.$minor 太老（需要 >=1.78 解析 Cargo.lock v4），跑 ``rustup update stable``"
    }
}

# ---------- 1. 嵌入式 Python（python-build-standalone，经 uv 下载） ----------
if ($env:BOSS_PYEMBED_REBUILD -eq '1') {
    if (Test-Path $PyembedDir) {
        Write-Host "==> BOSS_PYEMBED_REBUILD=1，清空 $PyembedDir"
        Remove-Item -Recurse -Force $PyembedDir
    }
}

if (-not (Test-Path $EmbedPy)) {
    Write-Host "==> 下载嵌入式 Python $PythonSeries（python-build-standalone）"
    New-Item -ItemType Directory -Path $PyembedDir -Force | Out-Null
    $DownloadDir = Join-Path $PyembedDir '_download'
    $env:UV_PYTHON_INSTALL_DIR = $DownloadDir
    try {
        uv python install $PythonSeries
        if ($LASTEXITCODE -ne 0) { throw "uv python install 失败（exit $LASTEXITCODE）" }
        # uv 落盘目录名带完整版本号（cpython-3.13.x-x86_64-pc-windows-msvc-shared），
        # 规范成 python/ 让后续路径稳定
        $SrcDir = Get-ChildItem -Path $DownloadDir -Directory -Filter 'cpython-*' |
                  Select-Object -First 1
        if (-not $SrcDir) { throw "没找到 uv 下载的 cpython 目录" }
        Move-Item -Path $SrcDir.FullName -Destination (Join-Path $PyembedDir 'python')
        Remove-Item -Recurse -Force $DownloadDir
    } finally {
        Remove-Item Env:UV_PYTHON_INSTALL_DIR -ErrorAction SilentlyContinue
    }
}

$PyVersion = & $EmbedPy --version
if ($LASTEXITCODE -ne 0) { throw "嵌入式 python.exe 跑不起来：$EmbedPy" }
Write-Host "==> 嵌入式 Python: $PyVersion"

# ---------- 2. macOS：libpython install_name 打 @rpath 补丁 ----------
# Windows 不需要。PE 加载器优先在 exe 同目录找 DLL，pyembed 的 python313.dll
# 在 bundle 里跟 boss-zhipin.exe 拷一起就行（见 tauri.bundle.json resources）。

# ---------- 3. 把业务包 + 依赖装进嵌入式环境 ----------
# --break-system-packages：uv 把自己装的 python-build-standalone 标成 PEP 668
# "externally managed"，默认拒绝 pip 写入。本场景就是要往里写，加 flag 放行。
# （macOS 的 .sh 没踩到大概是早期 uv 没强制，新版 uv 两边都会拦。）
Write-Host "==> 安装 boss_zhipin + 依赖到 pyembed（首次会拉 torch，较慢）"
$env:PYTAURI_STANDALONE = '1'
uv pip install --exact --compile-bytecode --break-system-packages `
    "--python=$EmbedPy" `
    --reinstall-package=boss-zhipin-job-search `
    "$RepoRoot[standalone]"
if ($LASTEXITCODE -ne 0) { throw "uv pip install 失败（exit $LASTEXITCODE）" }

# ---------- 3.5 删掉 pyembed 里的 BUILD 标记文件 ----------
# python-build-standalone 自带一个 8 字节的 BUILD 元数据文件。Windows 文件系统
# 大小写不敏感，tauri-build 的 copy_resources 把它拷到 target\bundle-release\BUILD
# 时正好撞上 cargo 自己的 build\ 目录，fs::copy 往目录上写 → "拒绝访问 (os error 5)"。
# Python 运行时不读这个文件，删掉无副作用。
$BuildMarker = Join-Path $PyembedDir 'python\BUILD'
if (Test-Path -PathType Leaf $BuildMarker) {
    Write-Host "==> 删除 pyembed BUILD 标记文件（避开 cargo build\ 目录大小写冲突）"
    Remove-Item -Force $BuildMarker
}

# ---------- 4. Rust 链接参数 ----------
# PYO3_PYTHON：不设的话 pyo3 自动探测系统 Python → 链到 PATH 上的 python.exe
# 或注册表里的 Python → bundle 后启动 LoadLibrary 拿错版本。
# RUSTFLAGS -L：python313.lib 在 python-build-standalone 的 libs/ 子目录下，
# 给 pyo3 链接期找 import library 用。
$env:PYO3_PYTHON = $EmbedPy
$PythonLibs = Join-Path $PyembedDir 'python\libs'
if (-not (Test-Path $PythonLibs)) {
    throw "$PythonLibs 不存在——python-build-standalone 该带 libs/python313.lib 给 pyo3 链"
}
# 注意：RUSTFLAGS 按 whitespace 切，路径里如果有空格会炸。本仓库默认装 E:\
# 下没空格，没空格就别提前优化；以后真踩到再用 CARGO_ENCODED_RUSTFLAGS。
$env:RUSTFLAGS = "-L native=$PythonLibs"

# ---------- 5. 前端 + tauri bundle ----------
Write-Host "==> pnpm install（tauri-ui）"
$TauriUiDir = Join-Path $RepoRoot 'tauri-ui'
pnpm --dir $TauriUiDir install --frozen-lockfile
if ($LASTEXITCODE -ne 0) { throw "pnpm install 失败（exit $LASTEXITCODE）" }

Write-Host "==> tauri build（bundle-release profile）"
# --config tauri.bundle.json：把 pyembed/python 作为 resources 打进 bundle；
# 必须从 repo root 跑——tauri CLI 只往**子目录**找 src-tauri/tauri.conf.json。
$TauriBin = Join-Path $TauriUiDir 'node_modules\.bin\tauri.cmd'
if (-not (Test-Path $TauriBin)) { throw "tauri CLI 没装：$TauriBin（pnpm install 失败？）" }
& $TauriBin build `
    --config (Join-Path $RepoRoot 'src-tauri\tauri.bundle.json') `
    -- --profile bundle-release
if ($LASTEXITCODE -ne 0) { throw "tauri build 失败（exit $LASTEXITCODE）" }

# ---------- 6. 产物自检 ----------
$TargetRoot = Join-Path $RepoRoot 'src-tauri\target'
$ExeMatches = Get-ChildItem -Path $TargetRoot -Recurse -Filter 'boss-zhipin.exe' `
    -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match 'bundle-release' }
if (-not $ExeMatches) { throw "没找到 boss-zhipin.exe 产物——cargo build 没成？" }
$Exe = $ExeMatches[0].FullName
Write-Host "==> raw exe: $Exe"

# bundle installer 列举：NSIS / MSI 看 tauri.conf.json bundle targets
$Bundles = Get-ChildItem -Path $TargetRoot -Recurse `
    -Include '*.msi', '*-setup.exe' -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match 'bundle-release' }
if ($Bundles) {
    foreach ($b in $Bundles) {
        Write-Host "[OK] 安装器：$($b.FullName)"
    }
} else {
    Write-Warning "没生成 NSIS/MSI 安装器，检查 tauri.conf.json 的 bundle.targets"
    Write-Host  "（raw exe 已生成，但 python313.dll 等 resources 只在 installer 里拷齐）"
}

# 提醒：dumpbin 检查 IMPORTS 是 nice-to-have，但 import 只记 DLL 文件名
# （python313.dll），不记路径——能不能链对靠 bundle 后跟 DLL 同目录。
# 装一遍 installer，开 .exe，看 Process Explorer 里加载的 python313.dll 路径
# 是不是装目录下那份。
Write-Host "[OK] 构建完成"
