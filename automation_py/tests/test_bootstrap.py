"""WP0 引导测试：只验证模块可导入、素材存在，不访问网络/不启动浏览器。"""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def test_core_modules_importable() -> None:
    import core.assert_helper  # noqa: F401
    import core.browser  # noqa: F401
    import core.config  # noqa: F401
    import core.reporter  # noqa: F401
    import core.session  # noqa: F401


def test_python_version() -> None:
    assert sys.version_info >= (3, 10), f"需要 Python 3.10+，当前 {sys.version}"


def test_config_loads() -> None:
    from core.config import Config

    cfg = Config.load()
    assert cfg.base_url.startswith("http")
    assert Path(cfg.chromium_path).exists(), f"Chromium 不存在：{cfg.chromium_path}"


def test_fixtures_exist() -> None:
    files = PACKAGE_ROOT / "fixtures" / "files"
    pdf = files / "wjc测试文件.pdf"
    docx = files / "wjc测试文件.docx"
    assert pdf.exists() and pdf.read_bytes()[:4] == b"%PDF"
    assert docx.exists() and docx.read_bytes()[:2] == b"PK"


def test_webupload_files_are_small() -> None:
    """单文件限制 50MB，素材必须远小于限制。"""
    files = PACKAGE_ROOT / "fixtures" / "files"
    for name in ("wjc测试文件.pdf", "wjc测试文件.docx"):
        assert (files / name).stat().st_size < 50 * 1024 * 1024
