"""``utils/retry.py`` 的单测。

需要 ``BOSS_RETRY_BASE_DELAY=0.01`` 之类的环境变量来加速 —— conftest.py 已经
把它们清掉了，每个用例自己用 monkeypatch.setenv 控制。
"""
from __future__ import annotations

import pytest

from boss_zhipin.utils.retry import retry_with_backoff


class TestRetryWithBackoff:
    def test_succeeds_first_attempt(self):
        @retry_with_backoff(max_attempts=3, base_delay=0.0)
        def fn():
            return "ok"
        assert fn() == "ok"

    def test_retries_then_succeeds(self):
        calls = {"n": 0}

        @retry_with_backoff(max_attempts=3, base_delay=0.0, jitter=False)
        def flaky():
            calls["n"] += 1
            if calls["n"] < 2:
                raise RuntimeError("transient")
            return "ok"

        assert flaky() == "ok"
        assert calls["n"] == 2

    def test_all_attempts_fail_raises_last(self):
        @retry_with_backoff(max_attempts=2, base_delay=0.0, jitter=False)
        def always_fails():
            raise ValueError("nope")
        with pytest.raises(ValueError, match="nope"):
            always_fails()

    def test_non_matching_exception_not_retried(self):
        calls = {"n": 0}

        @retry_with_backoff(max_attempts=3, base_delay=0.0, exceptions=ValueError)
        def picky():
            calls["n"] += 1
            raise RuntimeError("wrong type")

        with pytest.raises(RuntimeError):
            picky()
        # 只跑一次，没重试
        assert calls["n"] == 1

    def test_max_attempts_must_be_positive(self):
        with pytest.raises(ValueError):
            retry_with_backoff(max_attempts=0)(lambda: None)

    def test_preserves_function_metadata(self):
        @retry_with_backoff(max_attempts=2, base_delay=0.0)
        def named_function():
            """foo docstring"""
            return 1

        assert named_function.__name__ == "named_function"
        assert "foo docstring" in (named_function.__doc__ or "")

    def test_args_kwargs_passed_through(self):
        @retry_with_backoff(max_attempts=2, base_delay=0.0)
        def add(a, b, *, c):
            return a + b + c
        assert add(1, 2, c=3) == 6

    def test_env_overrides_pick_up_defaults(self, monkeypatch):
        # 不指定 max_attempts 时读 env
        monkeypatch.setenv("BOSS_RETRY_MAX_ATTEMPTS", "5")
        monkeypatch.setenv("BOSS_RETRY_BASE_DELAY", "0.001")
        monkeypatch.setenv("BOSS_RETRY_MAX_DELAY", "0.005")
        # 必须重新 import 才能读到新 env
        import importlib

        from boss_zhipin.utils import retry as r
        importlib.reload(r)

        calls = {"n": 0}

        @r.retry_with_backoff()
        def repeatedly_fails():
            calls["n"] += 1
            raise RuntimeError("x")

        with pytest.raises(RuntimeError):
            repeatedly_fails()
        assert calls["n"] == 5  # 读到了 env 里的 5

        # 清理：reload 回原始 defaults，避免污染其他用例
        monkeypatch.delenv("BOSS_RETRY_MAX_ATTEMPTS", raising=False)
        monkeypatch.delenv("BOSS_RETRY_BASE_DELAY", raising=False)
        monkeypatch.delenv("BOSS_RETRY_MAX_DELAY", raising=False)
        importlib.reload(r)
