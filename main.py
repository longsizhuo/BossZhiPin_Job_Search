"""向后兼容的 CLI 入口——``uv run main.py`` 仍然能跑。

实际逻辑在 ``boss_zhipin.cli``；本文件只是把 if-name-main 那段委托过去，
避免破坏现有的 README / 用户脚本 / .alias。
"""
from boss_zhipin.cli import _cli_main

if __name__ == "__main__":
    _cli_main()
