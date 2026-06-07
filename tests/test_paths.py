"""``boss_zhipin.paths`` 的单测——standalone 数据目录解析。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from boss_zhipin import paths

# Linux 分支用例会 ``monkeypatch.setattr(os, "name", "posix")``——
# Python 3.13 起在 Windows 上禁止实例化 PosixPath，这两个用例在 Windows
# 上必失败但行为正确，跳过即可（CI 的 Linux runner 仍会跑）。
_skip_on_windows = pytest.mark.skipif(
    os.name == "nt", reason="Linux 分支需要 PosixPath，Win 上 Python 3.13+ 禁止实例化"
)


class TestIsStandalone:
    def test_unset_is_false(self, monkeypatch):
        monkeypatch.delenv("BOSS_TAURI_STANDALONE", raising=False)
        assert paths.is_standalone() is False

    def test_one_is_true(self, monkeypatch):
        monkeypatch.setenv("BOSS_TAURI_STANDALONE", "1")
        assert paths.is_standalone() is True

    def test_other_values_false(self, monkeypatch):
        # 只认 "1"——跟 main.rs set_var 的值精确对齐
        monkeypatch.setenv("BOSS_TAURI_STANDALONE", "true")
        assert paths.is_standalone() is False


class TestAppDataDir:
    def test_env_override_wins(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BOSS_APP_DATA_DIR", str(tmp_path / "custom"))
        assert paths.app_data_dir() == tmp_path / "custom"

    def test_darwin_default(self, monkeypatch):
        monkeypatch.delenv("BOSS_APP_DATA_DIR", raising=False)
        monkeypatch.setattr(sys, "platform", "darwin")
        result = paths.app_data_dir()
        assert result == Path.home() / "Library" / "Application Support" / paths.APP_IDENTIFIER

    @_skip_on_windows
    def test_linux_xdg_default(self, monkeypatch, tmp_path):
        monkeypatch.delenv("BOSS_APP_DATA_DIR", raising=False)
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(os, "name", "posix")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
        assert paths.app_data_dir() == tmp_path / "xdg" / paths.APP_IDENTIFIER

    def test_identifier_matches_tauri_conf(self):
        # APP_IDENTIFIER 必须跟 src-tauri/tauri.conf.json 的 identifier 一致，
        # 否则 .app 的数据目录跟 Tauri 自己（WebView cache 等）的不在一处
        import json
        conf = json.loads(
            (Path(__file__).parent.parent / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8")
        )
        assert paths.APP_IDENTIFIER == conf["identifier"]


class TestEnsureAppDataCwd:
    def test_creates_dir_and_chdirs(self, monkeypatch, tmp_path):
        target = tmp_path / "appdata" / "nested"
        monkeypatch.setenv("BOSS_APP_DATA_DIR", str(target))
        monkeypatch.chdir(tmp_path)  # teardown 时 pytest 会把 CWD 还原
        result = paths.ensure_app_data_cwd()
        assert result == target
        assert target.is_dir()
        assert Path.cwd() == target

    def test_idempotent(self, monkeypatch, tmp_path):
        target = tmp_path / "appdata"
        monkeypatch.setenv("BOSS_APP_DATA_DIR", str(target))
        monkeypatch.chdir(tmp_path)
        paths.ensure_app_data_cwd()
        # 目录已存在时再调不报错
        assert paths.ensure_app_data_cwd() == target
