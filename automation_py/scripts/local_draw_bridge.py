#!/usr/bin/env python
"""本地专用：把 HP 的抽取建项 outbox 消息桥接到 RabbitMQ（仅测试/本地环境）。

背景：
- HP 本地 profile 关闭了 Spring 定时任务，`draw_integration_outbox` 的 relay 不会执行；
- professor 本地 profile 默认隔离 MQ（现已按 WP5 方案 A 打开 listener 并共用 HP vhost）。
- 本脚本读取 outbox 中 status=0 的待发布消息，直接通过 RabbitMQ 管理 API 发布，
  使 professor 能收到 `draw.command.create` 并建项。

仅用于本地测试；不修改任何业务数据（outbox 状态保持原样）。
凭据从本地 Docker 容器环境变量读取，不写入文件。
"""
from __future__ import annotations

import json
import subprocess
from urllib.parse import quote

import requests

MYSQL_CONTAINER = "hospital-local-stack-mysql-1"
RABBIT_CONTAINER = "hospital-local-stack-rabbitmq-1"
RABBIT_API = "http://127.0.0.1:15672/api"
VHOST = "/local-hospital-procurement"
EXCHANGE = "integration.draw.exchange"
RESULT_QUEUE = "hospital.draw.result.queue"

_published: set[str] = set()


def ensure_result_bindings() -> int:
    """在 HP vhost 上补齐 professor 回传事件的队列绑定（本地栈 HP 侧未声明）。

    HP 本地 profile 关闭了 Rabbit 容器自动启动，`hospital.draw.result.queue` 的
    `draw.event.*` 绑定不会自动创建；professor 发布抽取进度/结果时会 NO_ROUTE 并回滚。
    这里通过 RabbitMQ 管理 API 补 `draw.event.#` 绑定。
    """
    user, password = _rabbit_credentials()
    url = (f"{RABBIT_API}/bindings/{quote(VHOST, safe='')}/e/{EXCHANGE}"
           f"/q/{RESULT_QUEUE}")
    body = {"routing_key": "draw.event.#", "arguments": {}}
    resp = requests.post(url, json=body, auth=(user, password), timeout=15)
    # 已存在时会返回 400/409，同样视为可用
    if resp.status_code not in (200, 201, 204):
        if "already exists" in (resp.text or "").lower():
            return 0
        raise RuntimeError(f"创建绑定失败：{resp.status_code} {resp.text[:300]}")
    return 1


def _docker_env(container: str, name: str) -> str:
    result = subprocess.run(
        ["docker", "exec", container, "printenv", name],
        capture_output=True, text=True, timeout=20,
    )
    value = (result.stdout or "").strip()
    if result.returncode != 0 or not value:
        raise RuntimeError(f"读取容器环境变量失败：{container}/{name}")
    return value


def _mysql_root_password() -> str:
    return _docker_env(MYSQL_CONTAINER, "MYSQL_ROOT_PASSWORD")


def _rabbit_credentials() -> tuple[str, str]:
    return (
        _docker_env(RABBIT_CONTAINER, "RABBITMQ_DEFAULT_USER"),
        _docker_env(RABBIT_CONTAINER, "RABBITMQ_DEFAULT_PASS"),
    )


def pending_events(limit: int = 50) -> list[dict]:
    """读取 HP outbox 中待发布的抽取建项消息。"""
    password = _mysql_root_password()
    sql = (
        "SELECT event_id, routing_key, payload "
        "FROM hospital_procurement.draw_integration_outbox "
        f"WHERE status='0' ORDER BY create_time ASC LIMIT {limit}"
    )
    result = subprocess.run(
        ["docker", "exec", MYSQL_CONTAINER, "mysql", "-uroot", f"-p{password}",
         "-N", "--batch", "--raw", "-e", sql],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"查询 outbox 失败：{result.stderr[:300]}")
    events = []
    for line in (result.stdout or "").splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        events.append({"event_id": parts[0], "routing_key": parts[1], "payload": parts[2]})
    return events


def publish(event: dict) -> bool:
    user, password = _rabbit_credentials()
    url = f"{RABBIT_API}/exchanges/{quote(VHOST, safe='')}/{EXCHANGE}/publish"
    body = {
        "properties": {},
        "routing_key": event["routing_key"],
        "payload": event["payload"],
        "payload_encoding": "string",
    }
    resp = requests.post(url, json=body, auth=(user, password), timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"RabbitMQ 发布失败：{resp.status_code} {resp.text[:300]}")
    data = resp.json()
    return bool(data.get("routed"))


def publish_pending(max_rounds: int = 3) -> int:
    """发布当前所有待处理消息；返回成功发布条数（同一进程内 event_id 去重）。"""
    count = 0
    for _ in range(max_rounds):
        events = [e for e in pending_events() if e["event_id"] not in _published]
        if not events:
            break
        for event in events:
            if publish(event):
                _published.add(event["event_id"])
                count += 1
    return count


if __name__ == "__main__":
    published = publish_pending()
    print(f"published={published}")
