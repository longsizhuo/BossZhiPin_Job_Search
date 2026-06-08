"""GUI 运行页用——把用户拖进来的简历 PDF 收编成 app 自己持有的副本。

为什么是"复制进来"而不是"记住路径"：拖拽给的是用户磁盘上随便一个位置
（多半是 ``~/Downloads``）。只存路径的话，用户哪天清了 Downloads，下次跑就
``找不到简历文件``。所以拖入即 ``shutil.copy`` 到数据目录下的 ``resume/``，
``RESUME_PATH`` 指向这份托管副本——上传一次，之后不用再传。

落盘位置跟着 CWD 走（见 ``boss_zhipin.paths``）：
- dev 模式：repo root 的 ``resume/``（``.gitignore`` 已忽略 ``resume/*.pdf``）。
- standalone .app：``ensure_app_data_cwd()`` 已把 CWD 切到应用数据目录，
  ``resume/`` 自然落在那里。
存进 ``RESUME_PATH`` 的是**绝对路径**，不受之后 chdir 影响。

**不 import ``vectorization``**：那个模块 top-level 拉 sentence_transformers →
torch，import 一次 3-10 秒，会卡住 portal loop（见 ``tauri.detect_providers``
的同款告警）。校验"是不是个能读的 PDF"只用轻量的 ``pypdf``。
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from dotenv import set_key

# 托管副本的落点（CWD 相对，跟 cli.DEFAULT_RESUME_PATH 的 ``resume/`` 对齐）。
RESUME_DIR = "resume"

# 默认简历路径。**故意不从 ``boss_zhipin.cli`` import**：cli top-level 会拉起
# vectorization → torch（3-10s），而 ``current_resume`` 在运行页一挂载就被调，
# 会卡住 portal loop（见 ``tauri.detect_providers`` 同款告警）。这里跟
# ``cli.DEFAULT_RESUME_PATH`` 保持同值即可。
DEFAULT_RESUME_PATH = "resume/my_cover.pdf"


def _env_path() -> Path:
    return Path(".env")


def _persist_resume_path(abs_path: str) -> None:
    """把 RESUME_PATH 写进 .env + 同步 os.environ，让同进程即时生效。

    自己写而不走 ``env_io.write_env``：RESUME_PATH 已从 Config 表单的
    KNOWN_KEYS 移除（改由运行页拖拽管理），不在 ``write_env`` 的白名单里。
    """
    path = _env_path()
    path.touch(exist_ok=True)
    set_key(str(path), "RESUME_PATH", abs_path, quote_mode="never")
    os.environ["RESUME_PATH"] = abs_path


def _is_readable_pdf(path: Path) -> bool:
    """轻量校验：扩展名是 .pdf 且 pypdf 能解析出至少一页。"""
    if path.suffix.lower() != ".pdf":
        return False
    try:
        from pypdf import PdfReader  # 局部 import，避免无谓开销

        return len(PdfReader(str(path)).pages) > 0
    except Exception:
        return False


def store_resume(src: str) -> dict[str, str]:
    """把拖进来的 PDF 复制到 ``resume/`` 并设为当前简历。

    返回 ``{"filename": ..., "path": ...}``（path 是绝对路径）。
    校验失败抛 ``ValueError``，前端 catch 后提示用户。
    """
    src_path = Path(src.strip()).expanduser()
    if not src_path.is_file():
        raise ValueError(f"文件不存在：{src}")
    if not _is_readable_pdf(src_path):
        raise ValueError("不是一个能读取的 PDF（需要 .pdf 且至少一页）")

    dest_dir = Path(RESUME_DIR)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = (dest_dir / src_path.name).resolve()

    # 用户把已托管的那份又拖了一次 → 源和目标同一个文件，copy 会 SameFileError。
    if src_path.resolve() != dest:
        shutil.copyfile(src_path, dest)

    abs_path = str(dest)
    _persist_resume_path(abs_path)
    return {"filename": dest.name, "path": abs_path}


def current_resume() -> dict[str, str] | None:
    """返回当前简历 ``{"filename", "path"}``，没设置 / 文件不在则返回 None。

    优先读 RESUME_PATH env；空则回退到默认 ``resume/my_cover.pdf``，跟
    ``cli.ensure_resume_path`` 的解析口径一致。
    """
    raw = os.environ.get("RESUME_PATH", "").strip() or DEFAULT_RESUME_PATH
    path = Path(raw)
    if not path.is_file():
        return None
    return {"filename": path.name, "path": str(path.resolve())}
