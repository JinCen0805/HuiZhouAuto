#!/usr/bin/env python
"""本地测试数据种子：给指定部门克隆若干“可发起”的预算计划（project_reserve）。

背景：本地库是开发快照，反复跑自动化后目标部门的可发起计划会被消耗完
（表现为 S01 保存草稿报“首个储备项目不存在或不可引用”）。
本脚本仅在本地栈 MySQL 中插入 `UI自动化-种子` 计划，供本地回归使用。

用法：
    python scripts/seed_local_plan.py                     # 默认给医务部种 3 条
    python scripts/seed_local_plan.py --count 5
    python scripts/seed_local_plan.py --department-id CO6... --department-name 医务部
"""
from __future__ import annotations

import argparse
import subprocess
import uuid
from datetime import datetime, timedelta

import pymysql

MYSQL_CONTAINER = "hospital-local-stack-mysql-1"
DB = "hospital_procurement"
TARGET_DEPT_ID = "CO6AGR1786413569276"
TARGET_DEPT_NAME = "医务部"
TARGET_USER_ID = "1a22429f0ef64170968122b6f65c2606"  # cbbm1


def mysql_password() -> str:
    result = subprocess.run(
        ["docker", "exec", MYSQL_CONTAINER, "printenv", "MYSQL_ROOT_PASSWORD"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
    )
    password = (result.stdout or "").strip()
    if result.returncode != 0 or not password:
        raise RuntimeError("无法读取本地 MySQL 密码（容器是否在运行？）")
    return password


def connect():
    return pymysql.connect(host="127.0.0.1", port=3307, user="root",
                           password=mysql_password(), database=DB,
                           charset="utf8mb4", autocommit=True,
                           cursorclass=pymysql.cursors.DictCursor)


def main() -> int:
    parser = argparse.ArgumentParser(description="本地预算计划种子（仅本地开发库）")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--department-id", default=TARGET_DEPT_ID)
    parser.add_argument("--department-name", default=TARGET_DEPT_NAME)
    parser.add_argument("--amount", type=float, default=100000.0)
    args = parser.parse_args()

    conn = connect()
    try:
        with conn.cursor() as cur:
            # 找一个健康的来源计划（其他部门的 active/approved 储备项目）
            cur.execute("""
                SELECT * FROM project_reserve
                WHERE is_deleted=0 AND status IN ('未执行','储备中','active')
                  AND approval_status='APPROVED' AND is_quoted=0
                  AND government_procurement IN ('是','否')
                ORDER BY create_time DESC LIMIT 1
            """)
            source = cur.fetchone()
            if not source:
                print("没有找到可克隆的健康预算计划，请先检查本地库 project_reserve。")
                return 1

            now = datetime.now()
            # 注意：本地 MySQL 容器时区可能是 UTC，valid_from 用 NULL 避免“未来生效”校验失败
            valid_from = None
            valid_until = datetime(2035, 12, 31, 23, 59, 59)
            seeded = []
            for index in range(args.count):
                stamp = now.strftime("%Y%m%d%H%M%S") + f"{index:02d}"
                row = dict(source)
                row.update({
                    "uuid": uuid.uuid4().hex,
                    "reserve_code": f"YJ-UI-AUTO-{stamp}",
                    "source_budget_detail_id": None,
                    "project_name": f"UI自动化-种子预算计划-{stamp}",
                    "department_id": args.department_id,
                    "department": args.department_name,
                    "budget_amount": args.amount,
                    "available_amount": args.amount,
                    "unit_price": args.amount,
                    "quantity": 1,
                    "budget_year": str(now.year),
                    "valid_from": valid_from,
                    "valid_until": valid_until,
                    "status": "未执行",
                    "approval_status": "APPROVED",
                    "is_quoted": 0,
                    "is_deleted": 0,
                    "owner_purchase_request_id": None,
                    "purchase_application_code": None,
                    "government_procurement": "否",
                    "sme_reserve": "否",
                    "create_user": TARGET_USER_ID,
                    "create_time": now,
                    "modify_user": TARGET_USER_ID,
                    "modify_time": now,
                    "approval_time": now,
                    "submitted_user_id": TARGET_USER_ID,
                    "submitted_time": now,
                    "version": 1,
                })
                columns = ", ".join(f"`{key}`" for key in row)
                placeholders = ", ".join(["%s"] * len(row))
                cur.execute(f"INSERT INTO project_reserve ({columns}) VALUES ({placeholders})",
                            list(row.values()))
                seeded.append(row["reserve_code"])

            print(f"已为 {args.department_name} 种入 {len(seeded)} 条预算计划：")
            for code in seeded:
                print("  ", code)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
