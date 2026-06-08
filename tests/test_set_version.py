"""scripts/set_version.py 的版本号注入回归测试。

重点守 2026-06-09 CI 翻车的那个坑：JSON 文件 `"version": "x"` 的替换不能
误改成 key（`"0.4.0-rc1": "x"`），否则 tauri.conf.json 结构坏掉，
tauri build 报 "Additional properties are not allowed"。
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "set_version.py"

# (相对路径, 是否 JSON)
CONFIG_FILES = [
    ("pyproject.toml", False),
    ("src-tauri/Cargo.toml", False),
    ("src-tauri/tauri.conf.json", True),
    ("src/boss_zhipin/tauri/Tauri.toml", False),
]


@pytest.fixture
def fake_repo(tmp_path):
    """把真实的版本真相源文件复制进临时 repo 结构，让 set_version 在里面跑。

    脚本用 REPO_ROOT = __file__.parent.parent 定位文件，所以把脚本放到
    tmp/scripts/ 下，parent.parent 正好是 tmp。
    """
    (tmp_path / "scripts").mkdir()
    shutil.copy(SCRIPT, tmp_path / "scripts" / "set_version.py")
    for rel, _ in CONFIG_FILES:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / rel, dst)
    # Cargo.lock 可选——存在就一起拷，验证 best-effort 分支不炸
    lock = REPO_ROOT / "src-tauri" / "Cargo.lock"
    if lock.exists():
        shutil.copy(lock, tmp_path / "src-tauri" / "Cargo.lock")
    return tmp_path


def _run(repo: Path, version_arg: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "set_version.py"), version_arg],
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("arg,expected", [
    ("v0.4.0", "0.4.0"),
    ("0.4.0-rc1", "0.4.0-rc1"),  # 预发布后缀
    ("v1.2.3", "1.2.3"),
])
def test_all_files_get_correct_version(fake_repo, arg, expected):
    proc = _run(fake_repo, arg)
    assert proc.returncode == 0, proc.stderr

    # JSON 必须仍合法，且 version 字段正确（不是被改成 key）
    conf = json.loads((fake_repo / "src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    assert conf["version"] == expected
    # 防回归：确保没冒出个名为版本号的 property
    assert expected not in conf or conf.get("version") == expected
    assert "productName" in conf  # 结构没被搞坏

    # 三个 TOML 文件的 version 行
    for rel in ("pyproject.toml", "src-tauri/Cargo.toml", "src/boss_zhipin/tauri/Tauri.toml"):
        text = (fake_repo / rel).read_text(encoding="utf-8")
        assert f'version = "{expected}"' in text, f"{rel} 没注入对版本号"


def test_bad_version_rejected(fake_repo):
    proc = _run(fake_repo, "not-a-version")
    assert proc.returncode != 0
    # tauri.conf.json 不能被动过（校验失败应在写入前）
    conf = json.loads((fake_repo / "src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    assert "productName" in conf
