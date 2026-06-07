#!/usr/bin/env python3
"""把一个版本号写进所有"版本真相源"文件，供 CI 在 build 前从 git tag 注入。

single source of truth = git tag。仓库里 committed 的版本号（pyproject /
Cargo.toml / tauri.conf.json / wheel Tauri.toml）只是本地 dev build 的占位
默认值；release workflow 打 `v0.4.0` tag 时会用这个脚本把它们全部覆盖成
`0.4.0`，避免"tag 写 v0.4.0、产物里却还是 0.3.1"的漂移。

用法：
    python scripts/set_version.py v0.4.0        # 前缀 v 会被剥掉
    python scripts/set_version.py 0.4.0-rc1     # 预发布后缀原样保留

semver 的预发布串（`0.4.0-rc1`）四个文件都吃得下：
  - Cargo / tauri：合法 semver；tauri 给 Windows MSI 生成 4 段版本号时会
    忽略 `-rc1` 这种 prerelease 段。
  - setuptools(PEP 440)：`0.4.0-rc1` 归一化成 `0.4.0rc1`。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Windows runner 的 Python stdout/stderr 默认 cp1252，编不了脚本里的
# emoji / 全角箭头（→ ❌ ✅），happy path 的 print 直接 UnicodeEncodeError
# 崩掉（2026-06-08 CI 实测）。把两个流重配成 UTF-8 一次性兜住所有路径；
# 老 Python / 非 TextIOWrapper 流静默跳过。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent

# (相对路径, 匹配 version 行的正则, 这个文件是否必须命中)。
# 正则都只替换**第一处**命中，避免误伤依赖项的 version 字段（比如
# Cargo.toml 里 `tauri-build = { version = "2" }` 不在行首，不会被 `^version` 命中）。
TARGETS: list[tuple[str, str, bool]] = [
    ("pyproject.toml", r'(?m)^version = "[^"]*"', True),
    ("src-tauri/Cargo.toml", r'(?m)^version = "[^"]*"', True),
    ("src-tauri/tauri.conf.json", r'"version":\s*"[^"]*"', True),
    ("src/boss_zhipin/tauri/Tauri.toml", r'(?m)^version = "[^"]*"', True),
]


def normalize(raw: str) -> str:
    """剥掉前缀 v，做一次最基本的 semver 形状校验。"""
    version = raw.strip()
    if version.startswith("v"):
        version = version[1:]
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)*", version):
        raise SystemExit(f"❌ 不像合法版本号：{raw!r}（期望 x.y.z 或 x.y.z-rc1）")
    return version


def patch_line(path: Path, pattern: str, version: str, required: bool) -> bool:
    """把 path 里第一处匹配 pattern 的 version 行换成 version。命中返回 True。"""
    if not path.exists():
        if required:
            raise SystemExit(f"❌ 找不到必须的版本文件：{path}")
        return False

    text = path.read_text(encoding="utf-8")
    # 重建匹配行：保留原来的 key/标点，只换引号里的值。
    new_text, n = re.subn(
        pattern,
        lambda m: re.sub(r'"[^"]*"', f'"{version}"', m.group(0), count=1),
        text,
        count=1,
    )
    if n == 0:
        if required:
            raise SystemExit(f"❌ {path} 里没找到 version 行（正则 {pattern!r} 没命中）")
        return False
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return True


def patch_cargo_lock(version: str) -> bool:
    """同步 Cargo.lock 里 boss-zhipin 这一项的版本，免得 cargo build 还要改 lockfile。

    best-effort：lockfile 不在 / 没这一项就跳过（cargo 会在非 --locked 下自愈）。
    """
    lock = REPO_ROOT / "src-tauri" / "Cargo.lock"
    if not lock.exists():
        return False
    text = lock.read_text(encoding="utf-8")
    new_text, n = re.subn(
        r'(name = "boss-zhipin"\nversion = )"[^"]*"',
        lambda m: f'{m.group(1)}"{version}"',
        text,
        count=1,
    )
    if n and new_text != text:
        lock.write_text(new_text, encoding="utf-8")
        return True
    return False


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("用法：python scripts/set_version.py <version|tag>")
    version = normalize(argv[1])

    for rel, pattern, required in TARGETS:
        if patch_line(REPO_ROOT / rel, pattern, version, required):
            print(f"==> {rel} → {version}")
    if patch_cargo_lock(version):
        print(f"==> src-tauri/Cargo.lock (boss-zhipin) → {version}")

    print(f"✅ 版本号已统一为 {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
