"""配置加载：环境地址、Chromium 路径、业务参数、密码（环境变量/`.env.local`）。

原则：
- 密码只从环境变量或 `.env.local` 读取，绝不写入代码/仓库/日志。
- 业务参数从 `fixtures/flow_config.json` 读取（WP0 阶段可不存在，按默认值）。
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
FLOW_CONFIG_PATH = PACKAGE_ROOT / "fixtures" / "flow_config.json"
ENV_FILE_PATH = PACKAGE_ROOT / ".env.local"

# 固定环境路径（本机）
DEFAULT_BASE_URL = "http://127.0.0.1"
DEFAULT_CHROMIUM = (
    r"C:\Users\Grayson\AppData\Local\ms-playwright"
    r"\chromium-1234\chrome-win64\chrome.exe"
)
DEFAULT_PYTHON = (
    r"C:\Users\Grayson\.dsh\dsh-runtimes\dsh-primary-runtime"
    r"\dependencies\python\python.exe"
)


def load_env_file(path: Path | None = None) -> dict[str, str]:
    """解析 `.env.local`（KEY=VALUE，# 注释），不覆盖已存在的进程环境变量。"""
    path = path or ENV_FILE_PATH
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            data[key] = value
    return data


@dataclass
class Config:
    base_url: str = DEFAULT_BASE_URL
    chromium_path: str = DEFAULT_CHROMIUM
    python_path: str = DEFAULT_PYTHON
    env_file: dict[str, str] = field(default_factory=load_env_file)
    flow: dict = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        if FLOW_CONFIG_PATH.exists():
            cfg.flow = json.loads(FLOW_CONFIG_PATH.read_text(encoding="utf-8"))
        return cfg

    def env(self, key: str, default: str | None = None) -> str | None:
        """优先进程环境变量，其次 .env.local。"""
        value = os.environ.get(key)
        if value is None:
            value = self.env_file.get(key)
        return default if value is None else value

    def password(self, username: str) -> str:
        """按约定读取账号密码：HP_PASSWORD_<USERNAME 大写，- 换 _>；兼容 HP_PASS。"""
        key = "HP_PASSWORD_" + username.upper().replace("-", "_")
        value = self.env(key) or self.env("HP_PASS")
        if not value:
            raise EnvironmentError(
                f"密码未配置：{key}（或 HP_PASS）。请设置环境变量或 automation_py/.env.local"
            )
        return value


def ensure_package_on_path() -> None:
    """供 scripts/ 下脚本直接运行时使用。"""
    root = str(PACKAGE_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
