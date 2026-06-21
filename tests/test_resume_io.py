"""resume_io 的复制 + 校验 + RESUME_PATH 持久化行为。

重点回归：运行页拖入的简历必须**复制进** ``resume/`` 成为 app 自己持有的副本
并落进 ``RESUME_PATH``（.env + os.environ），这样用户清掉源文件后下次跑也不会
``找不到简历文件``——这是"点开始没反应"那类 standalone 缺简历 bug 的正解
（2026-06-08 实测：standalone .app 的 CWD 是数据目录，repo 的 resume/ 不在那儿）。
"""
import os

import pytest
from pypdf import PdfWriter

from boss_zhipin.gui import resume_io


@pytest.fixture
def in_tmp_cwd(tmp_path, monkeypatch):
    """cwd 切到临时目录——resume_io 用相对路径 ``resume/`` 和 ``.env``。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("RESUME_PATH", raising=False)
    return tmp_path


def _make_pdf(path) -> str:
    """造一个最小有效 PDF（一页空白），返回路径字符串。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with open(path, "wb") as f:
        writer.write(f)
    return str(path)


class TestStoreResume:
    def test_copies_into_resume_dir_and_persists(self, in_tmp_cwd):
        src = _make_pdf(in_tmp_cwd / "downloads" / "cv.pdf")
        info = resume_io.store_resume(src)

        # 复制到了 resume/ 下
        dest = in_tmp_cwd / "resume" / "cv.pdf"
        assert dest.is_file()
        assert info["filename"] == "cv.pdf"
        assert os.path.samefile(info["path"], dest)
        # RESUME_PATH 即时进 os.environ + 落 .env（绝对路径）
        assert os.getenv("RESUME_PATH") == info["path"]
        assert os.path.isabs(info["path"])
        assert "RESUME_PATH" in (in_tmp_cwd / ".env").read_text()

    def test_survives_source_deletion(self, in_tmp_cwd):
        """复制语义的意义：删掉源文件，托管副本仍在 → current_resume 仍可用。"""
        src = _make_pdf(in_tmp_cwd / "cv.pdf")
        resume_io.store_resume(src)
        os.remove(src)
        assert resume_io.current_resume() is not None

    def test_redrop_managed_copy_is_noop(self, in_tmp_cwd):
        """把已托管的那份再拖一次：源==目标，不能 SameFileError。"""
        src = _make_pdf(in_tmp_cwd / "cv.pdf")
        first = resume_io.store_resume(src)
        again = resume_io.store_resume(first["path"])
        assert again["path"] == first["path"]

    def test_rejects_non_pdf(self, in_tmp_cwd):
        bad = in_tmp_cwd / "notes.txt"
        bad.write_text("not a pdf")
        with pytest.raises(ValueError):
            resume_io.store_resume(str(bad))

    def test_rejects_missing_file(self, in_tmp_cwd):
        with pytest.raises(ValueError):
            resume_io.store_resume(str(in_tmp_cwd / "nope.pdf"))

    def test_rejects_pdf_extension_but_garbage_content(self, in_tmp_cwd):
        """扩展名是 .pdf 但内容不是 PDF——pypdf 解析失败，应拒。"""
        fake = in_tmp_cwd / "fake.pdf"
        fake.write_text("totally not a pdf")
        with pytest.raises(ValueError):
            resume_io.store_resume(str(fake))


class TestStoreResumeBytes:
    """文件选择器路径：webview 给不到真实路径，只能传字节。"""

    def _pdf_bytes(self, tmp_path) -> bytes:
        return (tmp_path / "src.pdf").read_bytes() if (tmp_path / "src.pdf").is_file() \
            else open(_make_pdf(tmp_path / "src.pdf"), "rb").read()

    def test_writes_into_resume_dir_and_persists(self, in_tmp_cwd):
        data = self._pdf_bytes(in_tmp_cwd)
        info = resume_io.store_resume_bytes("cv.pdf", data)

        dest = in_tmp_cwd / "resume" / "cv.pdf"
        assert dest.is_file()
        assert info["filename"] == "cv.pdf"
        assert os.path.samefile(info["path"], dest)
        assert os.getenv("RESUME_PATH") == info["path"]
        assert os.path.isabs(info["path"])

    def test_strips_path_components_from_filename(self, in_tmp_cwd):
        """文件名里带目录（路径穿越尝试）只取 basename，不逃出 resume/。"""
        data = self._pdf_bytes(in_tmp_cwd)
        info = resume_io.store_resume_bytes("../../evil.pdf", data)
        assert info["filename"] == "evil.pdf"
        assert (in_tmp_cwd / "resume" / "evil.pdf").is_file()
        assert not (in_tmp_cwd.parent.parent / "evil.pdf").exists()

    def test_rejects_non_pdf_name(self, in_tmp_cwd):
        with pytest.raises(ValueError):
            resume_io.store_resume_bytes("notes.txt", b"%PDF-1.4 ...")

    def test_rejects_empty(self, in_tmp_cwd):
        with pytest.raises(ValueError):
            resume_io.store_resume_bytes("cv.pdf", b"")

    def test_rejects_pdf_name_but_garbage_bytes(self, in_tmp_cwd):
        with pytest.raises(ValueError):
            resume_io.store_resume_bytes("cv.pdf", b"totally not a pdf")
        # 坏内容不能留下半个文件当成当前简历
        assert not (in_tmp_cwd / "resume" / "cv.pdf").exists()


class TestCurrentResume:
    def test_none_when_nothing_set(self, in_tmp_cwd):
        assert resume_io.current_resume() is None

    def test_reads_back_env_override(self, in_tmp_cwd, monkeypatch):
        src = _make_pdf(in_tmp_cwd / "elsewhere" / "r.pdf")
        monkeypatch.setenv("RESUME_PATH", src)
        info = resume_io.current_resume()
        assert info is not None
        assert info["filename"] == "r.pdf"

    def test_falls_back_to_default_path(self, in_tmp_cwd):
        # 默认 resume/my_cover.pdf 存在时无需设 env 也能认出来
        _make_pdf(in_tmp_cwd / "resume" / "my_cover.pdf")
        info = resume_io.current_resume()
        assert info is not None
        assert info["filename"] == "my_cover.pdf"
