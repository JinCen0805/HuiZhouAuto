"""通用重试：仅用于网络/超时类瞬时错误；业务校验失败不重试。"""
from __future__ import annotations

import functools
import time


def retry(times: int = 3, delay: float = 1.0, backoff: float = 2.0,
          exceptions: tuple[type[BaseException], ...] = (Exception,)):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            wait = delay
            last = None
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last = exc
                    if attempt == times:
                        break
                    time.sleep(wait)
                    wait *= backoff
            raise last  # type: ignore[misc]
        return wrapper
    return decorator
