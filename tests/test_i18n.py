"""后端用户文案本地化（gui.i18n.msg）。

重点：``msg`` 跟着用户在 Config 选的 ``BOSS_LANG`` 走，前端切英文后后端报错也该
是英文；占位符要能替换；缺 key / 未设语言要有合理回退（不能炸、不能露 key）。
"""
import pytest

from boss_zhipin.gui import i18n


@pytest.fixture(autouse=True)
def clean_lang(monkeypatch):
    """每个用例从"没设语言"起步，避免相互污染 os.environ。"""
    monkeypatch.delenv("BOSS_LANG", raising=False)


def test_defaults_to_zh_when_unset():
    assert i18n.msg("err.need_name") == "请先在「运行」页填写你的名字（招呼语署名用）"


def test_follows_selected_language(monkeypatch):
    monkeypatch.setenv("BOSS_LANG", "en")
    assert i18n.msg("err.need_name").startswith("Enter your name")


def test_var_substitution(monkeypatch):
    monkeypatch.setenv("BOSS_LANG", "en")
    assert i18n.msg("resume.not_found", src="/tmp/x.pdf") == "File not found: /tmp/x.pdf"


def test_unknown_lang_falls_back_to_zh(monkeypatch):
    # 脏值（比如手改 .env 写了 "fr"）不该炸，回退中文
    monkeypatch.setenv("BOSS_LANG", "fr")
    assert i18n.msg("resume.empty") == "文件是空的"


def test_unknown_key_returns_key_itself():
    # 漏翻的 key 回退成 key 本身——开发期一眼可见，运行期不抛异常
    assert i18n.msg("nope.not.a.key") == "nope.not.a.key"
