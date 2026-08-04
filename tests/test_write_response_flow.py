"""write_response 主循环的浏览器控制流回归测试。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from boss_zhipin.audit import ValidationResult
from boss_zhipin.website_oper import write_response


LETTER = "您好，我对这个岗位很感兴趣，也具备相关项目经验，期待进一步沟通。"


@dataclass
class BrowserPatch:
    sleeps: list[float]
    events: list[tuple[str, dict]]


def _patch_common_browser(monkeypatch) -> BrowserPatch:
    sleeps: list[float] = []
    events: list[tuple[str, dict]] = []

    async def noop(*args, **kwargs):
        return None

    async def fake_sleep(delay: float):
        sleeps.append(delay)

    async def cards_ready(timeout: float = 30):
        return True

    monkeypatch.setattr(write_response.finding_jobs, "open_browser_with_options", noop)
    monkeypatch.setattr(write_response.finding_jobs, "log_in", noop)
    monkeypatch.setattr(write_response.finding_jobs, "select_dropdown_option", noop)
    # 主循环开跑前会等岗位卡真正渲染出来；这里直接放行，各用例只关心之后的控制流
    monkeypatch.setattr(
        write_response.finding_jobs, "wait_for_real_job_cards", cards_ready
    )
    monkeypatch.setattr(write_response.finding_jobs, "reload_page", noop)
    monkeypatch.setattr(write_response.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(
        write_response,
        "_emit_progress",
        lambda kind, **payload: events.append((kind, payload)),
    )
    monkeypatch.setattr(write_response, "current_provider_label", lambda: "test")
    monkeypatch.setattr(write_response, "generate_letter", lambda *args: LETTER)
    monkeypatch.setattr(
        write_response, "validate_letter", lambda text: ValidationResult(ok=True)
    )
    monkeypatch.setattr(write_response, "log_attempt", lambda **kwargs: None)

    return BrowserPatch(sleeps=sleeps, events=events)


def test_missing_job_scrolls_and_retries_same_index(monkeypatch):
    async def scenario():
        patch = _patch_common_browser(monkeypatch)
        requested: list[int] = []
        scrolls: list[bool] = []

        async def get_jd(index: int):
            requested.append(index)
            if index == 1:
                return "岗位1 JD Go Redis 后端开发"
            if index == 2 and len([i for i in requested if i == 2]) == 1:
                return None
            if index == 2:
                return "岗位2 JD Python AI 应用开发"
            return None

        async def get_text(selector: str, timeout: float = 5):
            return "继续沟通"

        async def loaded_count():
            return 1

        async def scroll_more():
            scrolls.append(True)
            return len(scrolls) == 1

        monkeypatch.setattr(
            write_response.finding_jobs, "get_job_description_by_index", get_jd
        )
        monkeypatch.setattr(write_response.finding_jobs, "get_text_by_css", get_text)
        monkeypatch.setattr(
            write_response.finding_jobs, "get_loaded_job_count", loaded_count
        )
        monkeypatch.setattr(
            write_response.finding_jobs, "scroll_to_load_more_jobs", scroll_more
        )

        await write_response.send_job_descriptions_to_chat(
            usr_name="测试",
            url="https://example.test",
            browser_type="chrome",
            label="",
            dry_run=True,
        )

        assert requested[:3] == [1, 2, 2]
        assert scrolls
        assert any(
            kind == "job_found" and payload["index"] == 2
            for kind, payload in patch.events
        )

    asyncio.run(scenario())


def test_never_rendered_job_list_reports_error_not_feed_exhausted(monkeypatch):
    """岗位卡始终没渲染出来时，必须报 error 收尾，不能误报「已到 feed 底部」。

    回归的是这个真实故障：profile 缓存里存了 SPA 脚本的错误响应，页面死在
    「加载中，请稍候」，骨架屏空卡却点得动 —— 老逻辑会空转 5 轮然后上报
    feed_exhausted，让用户以为正常跑完了。
    """

    async def scenario():
        patch = _patch_common_browser(monkeypatch)
        reloads: list[bool] = []
        requested: list[int] = []

        async def never_ready(timeout: float = 30):
            return False

        async def reload():
            reloads.append(True)

        async def get_jd(index: int):
            requested.append(index)
            return None

        monkeypatch.setattr(
            write_response.finding_jobs, "wait_for_real_job_cards", never_ready
        )
        monkeypatch.setattr(write_response.finding_jobs, "reload_page", reload)
        monkeypatch.setattr(
            write_response.finding_jobs, "get_job_description_by_index", get_jd
        )

        await write_response.send_job_descriptions_to_chat(
            usr_name="测试",
            url="https://example.test",
            browser_type="chrome",
            label="",
            dry_run=True,
        )

        kinds = [kind for kind, _ in patch.events]
        assert "error" in kinds
        assert "feed_exhausted" not in kinds
        # 直接收尾，一轮岗位都不该去抓
        assert requested == []
        # 失败前刷新过一次
        assert reloads == [True]

    asyncio.run(scenario())


def test_reload_reapplies_label_filter(monkeypatch):
    """刷新会冲掉客户端筛选状态，必须重新选一次 label。

    否则用户选的 tag 悄悄退化成 BOSS 默认推荐 feed，招呼语会发给一批他没打算投的岗位。
    """

    async def scenario():
        _patch_common_browser(monkeypatch)
        selected: list[str] = []
        ready_calls: list[int] = []

        async def select_label(label: str):
            selected.append(label)

        async def ready_on_second_try(timeout: float = 30):
            ready_calls.append(1)
            return len(ready_calls) > 1

        async def get_jd(index: int):
            return None

        monkeypatch.setattr(
            write_response.finding_jobs, "select_dropdown_option", select_label
        )
        monkeypatch.setattr(
            write_response.finding_jobs, "wait_for_real_job_cards", ready_on_second_try
        )
        monkeypatch.setattr(
            write_response.finding_jobs, "get_job_description_by_index", get_jd
        )
        monkeypatch.setattr(
            write_response.finding_jobs,
            "scroll_to_load_more_jobs",
            lambda: _false(),
        )

        await write_response.send_job_descriptions_to_chat(
            usr_name="测试",
            url="https://example.test",
            browser_type="chrome",
            label="后端开发",
            dry_run=True,
        )

        # 首次一次 + reload 后补选一次
        assert selected == ["后端开发", "后端开发"]

    asyncio.run(scenario())


async def _false() -> bool:
    return False


def test_virtual_job_list_uses_visible_card_index_after_scroll(monkeypatch):
    async def scenario():
        patch = _patch_common_browser(monkeypatch)
        requested: list[int] = []
        scrolls: list[bool] = []

        async def get_jd(index: int):
            requested.append(index)
            if index <= 15:
                return f"可见岗位{index} JD Go Redis 后端开发"
            return None

        async def get_text(selector: str, timeout: float = 5):
            return "继续沟通"

        async def loaded_count():
            return 15

        async def scroll_more():
            scrolls.append(True)
            return len(scrolls) == 1

        monkeypatch.setattr(
            write_response.finding_jobs, "get_job_description_by_index", get_jd
        )
        monkeypatch.setattr(write_response.finding_jobs, "get_text_by_css", get_text)
        monkeypatch.setattr(
            write_response.finding_jobs, "get_loaded_job_count", loaded_count
        )
        monkeypatch.setattr(
            write_response.finding_jobs, "scroll_to_load_more_jobs", scroll_more
        )

        await write_response.send_job_descriptions_to_chat(
            usr_name="测试",
            url="https://example.test",
            browser_type="chrome",
            label="",
            dry_run=True,
        )

        assert requested[:17] == [*range(1, 16), 16, 15]
        assert any(
            kind == "job_found" and payload["index"] == 16
            for kind, payload in patch.events
        )

    asyncio.run(scenario())


def test_send_response_requires_return_to_job_list(monkeypatch):
    async def scenario():
        sent: list[str] = []

        async def send_message(text: str):
            sent.append(text)

        async def return_to_list():
            return False

        async def fake_sleep(delay: float):
            return None

        monkeypatch.setattr(
            write_response.finding_jobs, "send_chat_message", send_message
        )
        monkeypatch.setattr(
            write_response.finding_jobs, "return_to_job_list", return_to_list
        )
        monkeypatch.setattr(write_response.asyncio, "sleep", fake_sleep)

        with pytest.raises(RuntimeError, match="发送后未能返回岗位列表"):
            await write_response.send_response_and_go_back("hello")
        assert sent == ["hello"]

    asyncio.run(scenario())


def test_sent_greeting_is_logged_even_when_return_to_list_fails(monkeypatch):
    """招呼语已发出、返回列表失败：仍必须记 sent=True 并干净收尾，不能吞掉这条发送。"""

    async def scenario():
        patch = _patch_common_browser(monkeypatch)
        logged: list[dict] = []

        async def get_jd(index: int):
            return f"岗位{index} JD Go Redis 后端开发"

        async def get_text(selector: str, timeout: float = 5):
            return "立即沟通"

        async def click(xpath: str, timeout: float = 10):
            return True

        async def wait(selector: str, timeout: float = 50):
            return True

        async def send_message(text: str):
            return None

        async def return_to_list():
            return False

        monkeypatch.setattr(
            write_response.finding_jobs, "get_job_description_by_index", get_jd
        )
        monkeypatch.setattr(write_response.finding_jobs, "get_text_by_css", get_text)
        monkeypatch.setattr(write_response.finding_jobs, "click_by_xpath", click)
        monkeypatch.setattr(write_response.finding_jobs, "wait_for_css", wait)
        monkeypatch.setattr(
            write_response.finding_jobs, "send_chat_message", send_message
        )
        monkeypatch.setattr(
            write_response.finding_jobs, "return_to_job_list", return_to_list
        )
        monkeypatch.setattr(
            write_response, "log_attempt", lambda **kwargs: logged.append(kwargs)
        )

        await write_response.send_job_descriptions_to_chat(
            usr_name="测试",
            url="https://example.test",
            browser_type="chrome",
            label="",
            dry_run=False,
        )

        # 消息发出去了 → 恰好一条 sent=True，然后 break 收尾（而不是异常冒泡吞掉记录）。
        sent_records = [kw for kw in logged if kw.get("sent")]
        assert len(sent_records) == 1
        assert any(
            kind == "letter_sent" and payload.get("status") == "sent"
            for kind, payload in patch.events
        )
        assert not any(kind == "error" for kind, _ in patch.events)

    asyncio.run(scenario())


def test_send_limit_stops_after_configured_successful_sends(monkeypatch):
    async def scenario():
        patch = _patch_common_browser(monkeypatch)
        sent: list[str] = []

        async def get_jd(index: int):
            return f"岗位{index} JD Go Redis 后端开发"

        async def get_text(selector: str, timeout: float = 5):
            return "立即沟通"

        async def click(xpath: str, timeout: float = 10):
            return True

        async def wait(selector: str, timeout: float = 50):
            return True

        async def send_response(response: str):
            sent.append(response)

        monkeypatch.setenv("BOSS_AUTO_SEND_MAX_SENT", "2")
        monkeypatch.setattr(
            write_response.finding_jobs, "get_job_description_by_index", get_jd
        )
        monkeypatch.setattr(write_response.finding_jobs, "get_text_by_css", get_text)
        monkeypatch.setattr(write_response.finding_jobs, "click_by_xpath", click)
        monkeypatch.setattr(write_response.finding_jobs, "wait_for_css", wait)
        monkeypatch.setattr(write_response, "send_response_and_go_back", send_response)

        await write_response.send_job_descriptions_to_chat(
            usr_name="测试",
            url="https://example.test",
            browser_type="chrome",
            label="",
            dry_run=False,
        )

        assert sent == [LETTER, LETTER]
        assert any(
            kind == "feed_exhausted" and payload["total"] == 2
            for kind, payload in patch.events
        )

    asyncio.run(scenario())


def test_successful_send_waits_random_delay_between_jobs(monkeypatch):
    async def scenario():
        patch = _patch_common_browser(monkeypatch)
        sent: list[str] = []

        async def get_jd(index: int):
            if index <= 2:
                return f"岗位{index} JD Go Redis 后端开发"
            return None

        async def get_text(selector: str, timeout: float = 5):
            return "立即沟通"

        async def click(xpath: str, timeout: float = 10):
            return True

        async def wait(selector: str, timeout: float = 50):
            return True

        async def send_response(response: str):
            sent.append(response)

        async def no_scroll():
            return False

        monkeypatch.setenv("BOSS_AUTO_SEND_MAX_SENT", "3")
        monkeypatch.setenv("BOSS_AUTO_SEND_DELAY_MIN", "10")
        monkeypatch.setenv("BOSS_AUTO_SEND_DELAY_MAX", "60")
        monkeypatch.setattr(write_response.random, "uniform", lambda low, high: 23.5)
        monkeypatch.setattr(
            write_response.finding_jobs, "get_job_description_by_index", get_jd
        )
        monkeypatch.setattr(write_response.finding_jobs, "get_text_by_css", get_text)
        monkeypatch.setattr(write_response.finding_jobs, "click_by_xpath", click)
        monkeypatch.setattr(write_response.finding_jobs, "wait_for_css", wait)
        monkeypatch.setattr(
            write_response.finding_jobs, "scroll_to_load_more_jobs", no_scroll
        )
        monkeypatch.setattr(write_response, "send_response_and_go_back", send_response)

        await write_response.send_job_descriptions_to_chat(
            usr_name="测试",
            url="https://example.test",
            browser_type="chrome",
            label="",
            dry_run=False,
        )

        assert sent == [LETTER, LETTER]
        assert 23.5 in patch.sleeps

    asyncio.run(scenario())
