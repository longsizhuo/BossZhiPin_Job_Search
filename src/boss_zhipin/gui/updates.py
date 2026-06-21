"""检查 GitHub 上有没有新版本——给 GUI 顶部「有新版」横幅用。

**只提示，不自动下载安装**：standalone .app 体积 ~1.4 GB（嵌入式 Python +
torch），Tauri updater 没有增量更新，每次发版整包重下不现实。所以这里只做
"查最新 release tag → 比版本号 → 有新版给个下载链接"，下载/安装仍由用户手动
一步，对大包反而更可控。

设计：
- 走 GitHub 公开 API ``/releases/latest``（自动排除 draft / prerelease，
  用户只会被提示到正式版），未认证限速 60 次/小时/IP，每次启动只调一次够用。
- **任何异常都静默降级**成"无更新"：没网 / 限速 / API 改版都不该让 App 报错
  或卡住，顶多是这次没检查到。
- 版本号用 ``packaging.version`` 做语义比较（已是项目依赖），别用字符串比
  （"0.10.0" > "0.9.0" 字符串比会错）。
"""
from __future__ import annotations

import json
import logging
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from urllib.request import Request, urlopen

from packaging.version import InvalidVersion, Version

log = logging.getLogger(__name__)

# 发布仓库，跟 git remote 对齐。GitHub API 用同一个 owner/repo。
REPO = "longsizhuo/BossZhiPin_Job_Search"
_DIST_NAME = "boss-zhipin-job-search"
_API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
_RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"


def current_version() -> str:
    """当前安装的版本号（来自包元数据，set_version.py 维护的单一真相源）。

    源码运行（没正经装包）时元数据可能缺失，返回 ``"0.0.0"`` 兜底——会让
    任何线上 release 都判成"有新版"，但 dev 场景本就不靠这个提示。
    """
    try:
        return _pkg_version(_DIST_NAME)
    except PackageNotFoundError:
        return "0.0.0"


def is_newer(latest: str, current: str) -> bool:
    """latest 是否严格新于 current。任一不是合法版本号 → False（不乱提示）。"""
    try:
        return Version(latest) > Version(current)
    except InvalidVersion:
        return False


def _fetch_latest_tag(timeout: float) -> tuple[str, str]:
    """打 GitHub API，返回 ``(tag_name, html_url)``。失败由调用方兜异常。

    必须带 User-Agent，否则 GitHub API 直接 403。
    """
    req = Request(_API_URL, headers={
        "User-Agent": "boss-zhipin-updater",
        "Accept": "application/vnd.github+json",
    })
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 (固定 https GitHub API)
        data = json.load(resp)
    tag = str(data.get("tag_name", "")).lstrip("v")
    url = str(data.get("html_url") or _RELEASES_PAGE)
    return tag, url


def check_latest_release(timeout: float = 5.0) -> dict[str, object]:
    """查最新 release，返回前端横幅需要的全部字段。

    返回 ``{current, latest, url, hasUpdate}``。**永不抛异常**：网络/解析/限速
    出问题就当作"这次没查到新版"，``hasUpdate=False``、``latest=""``。
    """
    current = current_version()
    try:
        latest, url = _fetch_latest_tag(timeout)
    except Exception as exc:  # noqa: BLE001 (有意吞掉所有错误，静默降级)
        log.debug("检查更新失败（静默降级）：%s", exc)
        return {"current": current, "latest": "", "url": _RELEASES_PAGE, "hasUpdate": False}

    return {
        "current": current,
        "latest": latest,
        "url": url,
        "hasUpdate": is_newer(latest, current),
    }
