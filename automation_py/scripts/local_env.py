"""本地环境辅助：同步纪委/审计账号的登录 key 到 discipline 使用的 Redis DB。

discipline-supervision 本地通过 SPRING_REDIS_DATABASE=7 读取登录态，而 registers 写入 DB9；
未同步时纪检/审计接口会 401。仅本地测试使用。
"""
from __future__ import annotations

import subprocess

MYSQL_CONTAINER = "hospital-local-stack-mysql-1"
REDIS_CONTAINER = "hospital-local-stack-redis-1"
SOURCE_DB = 9
TARGET_DB = 7


def _docker_env(container: str, name: str) -> str:
    result = subprocess.run(
        ["docker", "exec", container, "printenv", name],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
    )
    value = (result.stdout or "").strip()
    if result.returncode != 0 or not value:
        raise RuntimeError(f"读取容器环境变量失败：{container}/{name}")
    return value


def sync_redis_keys(users: list[str]) -> list[str]:
    """把指定账号在 DB9 的登录 key 复制到 DB7（TTL 48h）。返回成功账号列表。"""
    password = _docker_env(REDIS_CONTAINER, "LOCAL_REDIS_PASSWORD")
    synced = []
    for user in users:
        get = subprocess.run(
            ["docker", "exec", REDIS_CONTAINER, "redis-cli", "-a", password,
             "--no-auth-warning", "-n", str(SOURCE_DB), "GET", user],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
        )
        value = (get.stdout or "").strip()
        if not value or not value.startswith("{"):
            continue
        subprocess.run(
            ["docker", "exec", REDIS_CONTAINER, "redis-cli", "-a", password,
             "--no-auth-warning", "-n", str(TARGET_DB), "SET", user, value, "EX", "172800"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
        )
        synced.append(user)
    return synced
