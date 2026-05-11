"""LLM 调用通用重试装饰器（指数退避）。

为什么不用 ``tenacity``：
    多一个依赖的成本 > 写一个 20 行的指数退避。LLM provider 偶发 5xx /
    429 / 网络抖动，重试两次大概率就过；不需要复杂的 retry policy DSL。

参数走环境变量是为了让 CI 把 ``BOSS_RETRY_BASE_DELAY=0.01`` 拨到极小，
测试就不用等真实的 2-30s 退避。

使用方式：

.. code-block:: python

    from utils.retry import retry_with_backoff

    @retry_with_backoff(max_attempts=3)
    def call_llm(...):
        return client.chat.completions.create(...)

或者命中具体异常类型才重试：

.. code-block:: python

    @retry_with_backoff(max_attempts=3, exceptions=(httpx.HTTPError, TimeoutError))
    def call_llm(...): ...
"""
from __future__ import annotations

import functools
import logging
import os
import random
import time
from typing import Callable, TypeVar

log = logging.getLogger(__name__)

# 默认值，可通过环境变量覆盖；测试场景把 BASE_DELAY 拨到 0.01s 加速
DEFAULT_BASE_DELAY = float(os.getenv("BOSS_RETRY_BASE_DELAY", "2.0"))
DEFAULT_MAX_DELAY = float(os.getenv("BOSS_RETRY_MAX_DELAY", "30.0"))
DEFAULT_MAX_ATTEMPTS = int(os.getenv("BOSS_RETRY_MAX_ATTEMPTS", "3"))

T = TypeVar("T")


def retry_with_backoff(
    *,
    max_attempts: int | None = None,
    base_delay: float | None = None,
    max_delay: float | None = None,
    exceptions: type[BaseException] | tuple[type[BaseException], ...] = Exception,
    jitter: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """指数退避重试装饰器。

    第 N 次失败后等 ``min(base_delay * 2**(N-1), max_delay)`` 秒再试。
    ``jitter=True`` 时再叠 0~50% 随机抖动，防止多 worker 同步退避撞墙。

    Args:
        max_attempts: 包括首次尝试在内的总次数，达到后抛出最后一次异常。
            None → 读 ``BOSS_RETRY_MAX_ATTEMPTS``，默认 3。
        base_delay: 第一次重试前等待秒数。None → 读 ``BOSS_RETRY_BASE_DELAY``，
            默认 2.0。
        max_delay: 单次重试间最大等待秒数。None → 读 ``BOSS_RETRY_MAX_DELAY``，
            默认 30.0。
        exceptions: 命中这些异常时才重试，其它直接抛。默认 ``Exception``。
        jitter: 是否叠加 0~50% 抖动。

    Raises:
        最后一次尝试时仍命中的异常，原样向上抛。
    """
    final_max_attempts = max_attempts if max_attempts is not None else DEFAULT_MAX_ATTEMPTS
    final_base_delay = base_delay if base_delay is not None else DEFAULT_BASE_DELAY
    final_max_delay = max_delay if max_delay is not None else DEFAULT_MAX_DELAY

    if final_max_attempts < 1:
        raise ValueError("max_attempts 必须 >= 1")

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> T:
            last_exc: BaseException | None = None
            for attempt in range(1, final_max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt >= final_max_attempts:
                        log.warning(
                            "%s 已达最大重试次数 (%d)，向上抛 %s: %s",
                            fn.__name__, final_max_attempts, type(e).__name__, e,
                        )
                        raise
                    delay = min(final_base_delay * (2 ** (attempt - 1)), final_max_delay)
                    if jitter:
                        delay *= (1 + random.random() * 0.5)
                    log.info(
                        "%s 第 %d/%d 次失败 (%s: %s)，%.2fs 后重试",
                        fn.__name__, attempt, final_max_attempts,
                        type(e).__name__, e, delay,
                    )
                    time.sleep(delay)
            # 理论上到不了这里：循环里要么 return 要么 raise
            assert last_exc is not None
            raise last_exc  # pragma: no cover

        return wrapper

    return decorator
