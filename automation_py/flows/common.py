"""流程公共工具：轮询等待业务状态。"""
from __future__ import annotations

import time


def wait_until(predicate, timeout_s: float = 20.0, interval_s: float = 1.0,
               message: str = "等待超时"):
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval_s)
    raise TimeoutError(f"{message}（{timeout_s}s）；最后结果：{last!r}")
