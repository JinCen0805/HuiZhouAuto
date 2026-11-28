"""步骤执行方式开关：每个步骤可走 UI（默认）或接口直调（回退）。

优先级：ctx[f"{step}_mode"] > 环境变量 HP_<STEP>_MODE > 环境变量 HP_STEP_MODE > default。
取值 ``ui`` / ``api``。线上旧前端未升级时可整体设 ``HP_STEP_MODE=api`` 回到接口路径。
"""
from __future__ import annotations

import os


def use_ui(step: str, ctx: dict | None = None, default: str = "ui") -> bool:
    key = f"{step.lower()}_mode"
    mode = ((ctx or {}).get(key)
            or os.environ.get(f"HP_{step.upper()}_MODE")
            or os.environ.get("HP_STEP_MODE")
            or default)
    mode = str(mode).strip().lower()
    if mode not in ("ui", "api"):
        raise ValueError(f"{step} 执行方式只支持 ui/api：{mode}")
    return mode == "ui"
