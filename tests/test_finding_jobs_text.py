"""finding_jobs 的纯文本处理（不碰浏览器的部分）。

``_strip_jd_noise`` 剥掉 JD 开头的页面 UI 噪声行（举报 / 微信扫码分享 / 职位描述…），
这些是 ``.job-detail-body`` 的 innerText 带进来的页面 chrome，不是 JD 正文。
"""

import asyncio

from boss_zhipin.website_oper import finding_jobs
from boss_zhipin.website_oper.finding_jobs import (
    _clear_singleton_locks,
    _is_logged_in_from_page_state,
    get_loaded_job_count,
    return_to_job_list,
    scroll_to_load_more_jobs,
    _strip_jd_noise,
)


def test_strips_leading_ui_noise():
    raw = "举报\n微信扫码分享\n职位描述\n\n1、参与 AI 功能模块设计\n岗位要求：本科"
    out = _strip_jd_noise(raw)
    assert out.startswith("1、参与 AI 功能模块设计")
    assert "举报" not in out
    assert "微信扫码分享" not in out


def test_only_strips_leading_run_not_body():
    # 正文里再出现"职位描述"不该被剥——只剥开头连续的噪声行
    raw = "举报\n职位描述\n这个职位描述很详细\n岗位要求"
    assert _strip_jd_noise(raw) == "这个职位描述很详细\n岗位要求"


def test_no_noise_unchanged():
    raw = "1、岗位职责\n2、岗位要求"
    assert _strip_jd_noise(raw) == raw


def test_empty_and_none():
    assert _strip_jd_noise("") == ""
    assert _strip_jd_noise(None) == ""


def test_clear_singleton_locks_removes_locks_keeps_cookies(tmp_path):
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket", "Cookies"):
        (tmp_path / name).write_text("x")
    _clear_singleton_locks(str(tmp_path))
    # 三个 Singleton 锁删掉；登录态文件（Cookies）保留
    assert not (tmp_path / "SingletonLock").exists()
    assert not (tmp_path / "SingletonCookie").exists()
    assert not (tmp_path / "SingletonSocket").exists()
    assert (tmp_path / "Cookies").exists()


def test_clear_singleton_locks_missing_ok(tmp_path):
    _clear_singleton_locks(str(tmp_path))  # 没有锁文件也不报错


def test_login_page_url_is_not_logged_in():
    assert (
        _is_logged_in_from_page_state(
            "https://www.zhipin.com/web/user/?ka=header-login", {}
        )
        is False
    )


def test_jobs_page_with_header_login_is_not_logged_in():
    assert (
        _is_logged_in_from_page_state(
            "https://www.zhipin.com/web/geek/jobs",
            {"headerLoginVisible": True},
        )
        is False
    )


def test_jobs_page_with_login_required_text_is_not_logged_in():
    assert (
        _is_logged_in_from_page_state(
            "https://www.zhipin.com/web/geek/jobs",
            {"loginRequiredVisible": True},
        )
        is False
    )


def test_jobs_page_without_login_signals_is_logged_in():
    assert (
        _is_logged_in_from_page_state(
            "https://www.zhipin.com/web/geek/job-recommend",
            {
                "loginWallVisible": False,
                "headerLoginVisible": False,
                "loginRequiredVisible": False,
            },
        )
        is True
    )


def test_get_loaded_job_count_reads_job_card_count(monkeypatch):
    async def scenario():
        async def fake_evaluate(js: str, timeout: float = 10):
            assert ".job-card-box" in js
            assert timeout == 5
            return {"count": 15}

        monkeypatch.setattr(finding_jobs, "_safe_evaluate", fake_evaluate)
        assert await get_loaded_job_count() == 15

    asyncio.run(scenario())


def test_scroll_to_load_more_jobs_returns_true_when_card_count_grows(monkeypatch):
    async def scenario():
        counts = iter([15, 30])
        evaluate_calls: list[str] = []

        async def fake_count():
            return next(counts)

        async def fake_evaluate(js: str, timeout: float = 10):
            evaluate_calls.append(js)
            return {
                "target": "left-list",
                "beforeTop": 0,
                "afterTop": 700,
                "beforeFirst": "old",
                "afterFirst": "old",
            }

        async def fake_sleep(delay: float):
            return None

        monkeypatch.setattr(finding_jobs, "get_loaded_job_count", fake_count)
        monkeypatch.setattr(finding_jobs, "_safe_evaluate", fake_evaluate)
        monkeypatch.setattr(finding_jobs.asyncio, "sleep", fake_sleep)

        assert await scroll_to_load_more_jobs(timeout=1.0) is True
        assert evaluate_calls
        assert "job-list-box" in evaluate_calls[0]

    asyncio.run(scenario())


def test_scroll_to_load_more_jobs_treats_visible_card_change_as_progress(monkeypatch):
    async def scenario():
        async def fake_count():
            return 15

        async def fake_evaluate(js: str, timeout: float = 10):
            return {
                "target": "left-list",
                "beforeTop": 0,
                "afterTop": 700,
                "beforeFirst": "old card",
                "afterFirst": "new card",
            }

        async def fake_sleep(delay: float):
            return None

        monkeypatch.setattr(finding_jobs, "get_loaded_job_count", fake_count)
        monkeypatch.setattr(finding_jobs, "_safe_evaluate", fake_evaluate)
        monkeypatch.setattr(finding_jobs.asyncio, "sleep", fake_sleep)

        assert await scroll_to_load_more_jobs(timeout=1.0) is True

    asyncio.run(scenario())

def test_scroll_to_load_more_jobs_ignores_window_scroll(monkeypatch):
    async def scenario():
        async def fake_count():
            return 15

        async def fake_evaluate(js: str, timeout: float = 10):
            return {
                "ok": True,
                "target": "window",
                "beforeTop": 0,
                "afterTop": 700,
                "beforeFirst": "old card",
                "afterFirst": "old card",
            }

        async def fake_sleep(delay: float):
            return None

        monkeypatch.setattr(finding_jobs, "get_loaded_job_count", fake_count)
        monkeypatch.setattr(finding_jobs, "_safe_evaluate", fake_evaluate)
        monkeypatch.setattr(finding_jobs.asyncio, "sleep", fake_sleep)

        assert await scroll_to_load_more_jobs(timeout=1.0) is False

    asyncio.run(scenario())


def test_scroll_to_load_more_jobs_accepts_window_scroll_when_count_grows(monkeypatch):
    async def scenario():
        counts = iter([15, 30])
        evaluate_calls: list[str] = []

        async def fake_count():
            return next(counts)

        async def fake_evaluate(js: str, timeout: float = 10):
            evaluate_calls.append(js)
            return {
                "ok": True,
                "target": "window",
                "beforeTop": 0,
                "afterTop": 1500,
                "beforeFirst": "old card",
                "afterFirst": "old card",
            }

        async def fake_sleep(delay: float):
            return None

        monkeypatch.setattr(finding_jobs, "get_loaded_job_count", fake_count)
        monkeypatch.setattr(finding_jobs, "_safe_evaluate", fake_evaluate)
        monkeypatch.setattr(finding_jobs.asyncio, "sleep", fake_sleep)

        assert await scroll_to_load_more_jobs(timeout=1.0) is True
        assert "window.scrollTo" in evaluate_calls[0]

    asyncio.run(scenario())


def test_return_to_job_list_retries_until_cards_are_visible(monkeypatch):
    async def scenario():
        back_calls: list[bool] = []
        visible_results = iter([False, True])

        async def fake_back():
            back_calls.append(True)

        async def fake_wait(selector: str, timeout: float = 50):
            assert selector == ".job-card-box"
            assert timeout == 12.0
            return next(visible_results)

        monkeypatch.setattr(finding_jobs, "navigate_back", fake_back)
        monkeypatch.setattr(finding_jobs, "wait_for_css", fake_wait)

        assert await return_to_job_list() is True
        assert len(back_calls) == 2

    asyncio.run(scenario())
