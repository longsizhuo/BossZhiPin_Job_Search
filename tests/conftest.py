"""pytest 公共配置。

- 把项目根目录加进 ``sys.path``，让 ``import main`` / ``import audit`` 这种顶层
  导入不依赖 ``uv pip install -e .`` 也能跑。
- 自动加载根目录的 ``.env``（如果存在），但 **测试用例里出现的 env 变量永远要用
  ``monkeypatch`` 覆盖**，不要依赖本机 .env 的真实 key。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# 跑 pytest 时让 dotenv 不污染测试环境：明确清掉那几个 provider key，
# 用例需要时各自再 monkeypatch.setenv 上去。
for _key in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
             "BOSS_USR_NAME", "BOSS_LABEL", "RESUME_PATH",
             "OPENAI_BASE_URL", "CHATGPT_MODEL"):
    os.environ.pop(_key, None)
