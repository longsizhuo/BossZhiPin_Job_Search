"""招呼语 prompt 模板：默认风格 + 可配置覆盖（BOSS_LETTER_PROMPT）。"""
import pytest

from boss_zhipin.models.prompts import (
    DEFAULT_LETTER_PROMPT,
    LETTER_PROMPT_ENV,
    assistant_instructions,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv(LETTER_PROMPT_ENV, raising=False)


def test_default_used_when_unset():
    p = assistant_instructions("晓喻")
    assert "晓喻" in p              # usr_name 替换进去
    assert "{usr_name}" not in p    # 占位符已全部替换
    assert "真人" in p              # 默认强调"像真人发的"，去 AI 腔


def test_env_override_takes_over():
    import os
    os.environ[LETTER_PROMPT_ENV] = "随便写，署名 {usr_name}"
    assert assistant_instructions("晓喻") == "随便写，署名 晓喻"


def test_blank_override_falls_back_to_default():
    import os
    os.environ[LETTER_PROMPT_ENV] = "   "  # 全空白 = 视为没设
    assert assistant_instructions("X") == DEFAULT_LETTER_PROMPT.replace("{usr_name}", "X")


def test_literal_braces_in_custom_prompt_do_not_crash():
    # 自定义模板里有 JSON 大括号也不能炸（我们用 replace 不用 str.format）
    import os
    os.environ[LETTER_PROMPT_ENV] = '输出 {"k": 1}，署名 {usr_name}'
    assert assistant_instructions("晓喻") == '输出 {"k": 1}，署名 晓喻'
