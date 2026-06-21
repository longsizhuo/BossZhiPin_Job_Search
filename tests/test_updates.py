"""``gui.updates`` 单测——版本比较 + check_latest_release 的 happy / 降级路径。

不打真网络：用 monkeypatch 替掉 ``_fetch_latest_tag``。
"""
from __future__ import annotations

import pytest

from boss_zhipin.gui import updates


# ---------- is_newer ----------


@pytest.mark.parametrize(
    "latest, current, expected",
    [
        ("0.5.0", "0.4.1", True),     # happy：正常新版
        ("0.10.0", "0.9.0", True),    # edge：字符串比会错判，语义比正确
        ("0.4.1", "0.4.1", False),    # 相等不算新
        ("0.4.0", "0.4.1", False),    # 旧版不提示
        ("garbage", "0.4.1", False),  # edge：非法版本号 → 不乱提示
    ],
)
def test_is_newer(latest, current, expected):
    assert updates.is_newer(latest, current) is expected


# ---------- check_latest_release ----------


def test_check_latest_release_happy(monkeypatch):
    monkeypatch.setattr(updates, "current_version", lambda: "0.4.1")
    monkeypatch.setattr(
        updates,
        "_fetch_latest_tag",
        lambda timeout: ("0.5.0", "https://github.com/longsizhuo/BossZhiPin_Job_Search/releases/tag/v0.5.0"),
    )

    result = updates.check_latest_release()

    assert result["hasUpdate"] is True
    assert result["current"] == "0.4.1"
    assert result["latest"] == "0.5.0"
    assert "releases/tag/v0.5.0" in str(result["url"])


def test_check_latest_release_network_error_degrades(monkeypatch):
    """没网 / API 出错时静默降级：不抛异常，hasUpdate=False。"""
    monkeypatch.setattr(updates, "current_version", lambda: "0.4.1")

    def boom(timeout):
        raise OSError("network down")

    monkeypatch.setattr(updates, "_fetch_latest_tag", boom)

    result = updates.check_latest_release()

    assert result["hasUpdate"] is False
    assert result["latest"] == ""
    assert result["current"] == "0.4.1"
    # 降级也要给个可点的 releases 兜底链接
    assert str(result["url"]).startswith("https://github.com/longsizhuo/BossZhiPin_Job_Search/releases")
