"""GUI「AI 服务商」选择器的读/写——选一家 + 填一个 key，存进 ``.env``。

替代以前 Config 页并排的三个 API key 输入框（小白会以为三个都要填）。现在：
- 选服务商 → 存 ``BOSS_PROVIDER``
- 只填**当前选中那家**的 key → 存对应的 ``*_API_KEY``

**为什么读 ``.env`` 文件而不是 ``os.environ``**：GUI（PyTauri standalone）启动时
入口不调 ``load_dotenv``，models 的 import-time load 要等首次 run 才触发，所以
app 刚起来 ``os.environ`` 里没有 .env 的 key。Config 要展示"哪些已配/选了哪家"
必须以**文件**为准（跟 ``env_io.read_env`` 一致）。run 路径不受影响：run_provider
会 import models 触发 load_dotenv，key 那时已在 os.environ。
"""
from __future__ import annotations

from dotenv import dotenv_values

from boss_zhipin.gui.env_io import _env_path, write_env
from boss_zhipin.providers import (
    PROVIDER_ENV_KEYS,
    PROVIDER_LABELS,
    PROVIDER_SIGNUP,
)


def _file_values() -> dict[str, str | None]:
    path = _env_path()
    return dotenv_values(path) if path.is_file() else {}


def read_provider_config() -> dict[str, object]:
    """返回前端服务商选择器需要的全部信息。

    ``{active, providers: [{name, label, signupUrl, hasKey}]}``。``active`` 是
    用户选过的 ``BOSS_PROVIDER``；没选过 / 非法时回退到第一个已配 key 的服务商，
    都没配就 ``deepseek``（让用户有个默认落点）。
    """
    raw = _file_values()
    configured = {
        name for name, env in PROVIDER_ENV_KEYS.items()
        if (raw.get(env) or "").strip()
    }

    active = (raw.get("BOSS_PROVIDER") or "").strip()
    if active not in PROVIDER_ENV_KEYS:
        active = next((n for n in PROVIDER_ENV_KEYS if n in configured), "deepseek")

    return {
        "active": active,
        "providers": [
            {
                "name": name,
                "label": PROVIDER_LABELS[name],
                "signupUrl": PROVIDER_SIGNUP[name],
                "hasKey": name in configured,
            }
            for name in PROVIDER_ENV_KEYS
        ],
    }


def write_provider_config(active: str, api_key: str | None) -> None:
    """存选定的服务商（+ 可选地存它的 key）。

    - ``active`` 非法 → ``ValueError``（前端 catch 可见）。
    - ``api_key`` 为 ``None`` / 空串 → **只切服务商、不动已存的 key**。这样用户
      切来切去看不同家时，不会把之前填好的 key 误清空（区别于 env_io 的
      "空=删除"语义，这里刻意不删）。
    - ``api_key`` 非空 → 连同写进对应 ``*_API_KEY``。
    写操作复用 ``env_io.write_env``：落盘 + 同步 ``os.environ``（存完即时生效，
    切回运行页不用重启）。
    """
    if active not in PROVIDER_ENV_KEYS:
        raise ValueError(f"unknown provider: {active!r}")

    updates: dict[str, str] = {"BOSS_PROVIDER": active}
    if api_key:
        updates[PROVIDER_ENV_KEYS[active]] = api_key
    write_env(updates)
