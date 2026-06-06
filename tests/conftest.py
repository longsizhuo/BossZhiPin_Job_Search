"""pytest 公共配置。

- Phase D-pre 后：项目以 src/ 布局变成可安装 package，``uv sync`` 会把
  ``boss_zhipin`` editable install 进 .venv，``from boss_zhipin import X``
  不需要 sys.path 注入也能 import。这里不再 manipulate sys.path。
- **主动清空所有项目相关 env 变量**，让测试不被本机 .env / shell export
  污染。包括 provider key、用户输入兜底、以及 retry 装饰器在 import time
  读取的 ``BOSS_RETRY_*`` 那几个。
- 我们**不**调 ``load_dotenv()`` —— 测试应当通过 ``monkeypatch.setenv`` 显式
  控制环境，依赖 .env 真实值的测试是不可复现的。
"""
from __future__ import annotations

import os


# 项目所有读 env 的位置（provider key / 用户输入兜底 / retry 默认值 /
# telemetry 路径 / letter 长度边界 / log 路径）都清掉，用例需要时各自再
# ``monkeypatch.setenv`` 上去。
_PROJECT_ENV_VARS = (
    # provider 凭据
    "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    # 用户输入兜底
    "BOSS_USR_NAME", "BOSS_LABEL", "RESUME_PATH",
    # OpenAI / 模型选项
    "OPENAI_BASE_URL", "CHATGPT_MODEL",
    # retry 装饰器在 import time 读这些，本机有 export 会影响装饰器默认值
    "BOSS_RETRY_BASE_DELAY", "BOSS_RETRY_MAX_DELAY", "BOSS_RETRY_MAX_ATTEMPTS",
    # 落盘路径
    "LETTER_LOG_PATH", "BOSS_LLM_TELEMETRY_PATH", "BOSS_CHROME_PROFILE",
    # letter 校验边界
    "LETTER_MIN_LEN", "LETTER_MAX_LEN",
    # main.py 用的全局 log 级
    "LOGLEVEL", "DRY_RUN",
)
for _key in _PROJECT_ENV_VARS:
    os.environ.pop(_key, None)
