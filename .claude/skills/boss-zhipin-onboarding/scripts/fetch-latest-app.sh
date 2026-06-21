#!/usr/bin/env bash
# 给非开发者用的"帮我下对的安装包"脚本（Path A 配套）。
#
# 做什么：自动识别平台 + 架构 → 用 GitHub API 解析【最新 release】里【带版本号】
# 的正确资产（asset 名形如 BOSS.Zhipin.Helper_0.4.2_aarch64.dmg，版本号会变，
# 所以必须按后缀匹配，不能拼死链接）→ 下载到 ~/Downloads → 打开安装窗口。
#
# 做到哪一步（有意为之）：下载 + 打开安装器就停手。最后"拖到 Applications /
# 过 Gatekeeper / 过 SmartScreen"留给用户自己点——不替用户绕过系统安全提示
# （见 SKILL.md 红线）。装完怎么过 Gatekeeper 见 SKILL.md 的 A2。
#
# 用法：bash .claude/skills/boss-zhipin-onboarding/scripts/fetch-latest-app.sh
# 零依赖（只要 curl）；装了 gh 也行，但本脚本走公开 API 免鉴权，不强制 gh。
set -euo pipefail

REPO="longsizhuo/BossZhiPin_Job_Search"
API="https://api.github.com/repos/${REPO}/releases/latest"

# ── 1. 识别平台 → 选资产后缀 ────────────────────────────────────────────
os="$(uname -s)"
arch="$(uname -m)"
case "$os" in
  Darwin)
    if [ "$arch" = "arm64" ]; then
      pattern="_aarch64.dmg"; kind="dmg"
    else
      echo "✗ Intel Mac（$arch）暂无桌面发布版。请走 Path B：clone + uv 跑命令行。" >&2
      exit 2
    fi ;;
  MINGW*|MSYS*|CYGWIN*)
    pattern="_x64-setup.exe"; kind="exe" ;;
  Linux)
    echo "✗ Linux 暂无桌面发布版。请走 Path B：clone + uv 跑命令行。" >&2
    exit 2 ;;
  *)
    echo "✗ 未知平台 $os。去 release 页手动下载：https://github.com/${REPO}/releases/latest" >&2
    exit 2 ;;
esac

command -v curl >/dev/null 2>&1 || { echo "✗ 找不到 curl，请先装 curl。" >&2; exit 1; }

# ── 2. API 解析最新 tag + 匹配资产的真实下载 URL ────────────────────────
echo "→ 查询 ${REPO} 最新 release ..."
json=""
for attempt in 1 2 3 4 5; do
  if json="$(curl -fsSL "$API" 2>/dev/null)" && [ -n "$json" ]; then
    break
  fi
  echo "  GitHub API 暂时没响应（504/限流），重试 $attempt/5 ..." >&2
  sleep 2
  json=""
done
if [ -z "$json" ]; then
  echo "✗ 连不上 GitHub API（可能网络/限流）。去 release 页手动下载：" >&2
  echo "  https://github.com/${REPO}/releases/latest" >&2
  exit 1
fi

tag="$(printf '%s' "$json" \
  | grep -o '"tag_name"[[:space:]]*:[[:space:]]*"[^"]*"' \
  | head -1 | sed 's/.*"\([^"]*\)"$/\1/')"

url="$(printf '%s' "$json" \
  | grep -o '"browser_download_url"[[:space:]]*:[[:space:]]*"[^"]*"' \
  | sed 's/.*"\(https[^"]*\)"$/\1/' \
  | grep -- "$pattern" | head -1)"

if [ -z "${url:-}" ]; then
  echo "✗ 在最新 release（${tag:-未知}）里没找到匹配 *${pattern} 的安装包。" >&2
  echo "  去 release 页手动看一眼：https://github.com/${REPO}/releases/latest" >&2
  exit 1
fi

# ── 3. 下载到 ~/Downloads（没有就放当前目录）────────────────────────────
dest="$HOME/Downloads"
[ -d "$dest" ] || dest="$PWD"
file="$dest/$(basename "$url")"

echo "→ 最新版本：${tag}"
echo "→ 下载 $(basename "$url") 到 $dest ..."
curl -fL --progress-bar -o "$file" "$url"
echo "✓ 下载完成：$file"

# ── 4. 打开安装器（最后一步系统安全提示交给用户）──────────────────────
if [ "$kind" = "dmg" ]; then
  echo "→ 挂载 DMG ..."
  mp="$(hdiutil attach "$file" -nobrowse | grep -o '/Volumes/[^[:cntrl:]]*' | tail -1)"
  open "$mp" 2>/dev/null || true
  echo "✓ 安装窗口已弹出。接下来你自己操作："
  echo "    1) 把「BOSS Zhipin Helper」拖到 Applications 文件夹"
  echo "    2) 首次启动【别双击】——去 Applications 里【右键 →「打开」】过 Gatekeeper"
  echo "    （装完可以在 Finder 侧边栏把挂载的安装盘推出/Eject）"
else
  echo "→ 启动安装器 ..."
  ( start "" "$file" ) 2>/dev/null \
    || ( cmd.exe /c start "" "$(cygpath -w "$file" 2>/dev/null || echo "$file")" ) 2>/dev/null \
    || echo "  自动启动失败，请到资源管理器双击运行：$file"
  echo "✓ 若 SmartScreen 弹「Windows 已保护你的电脑」：点【更多信息】→【仍要运行】。"
fi
