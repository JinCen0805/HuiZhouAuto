#!/usr/bin/env python
"""清理本地测试数据（默认只预览，加 --apply 才执行）。

只处理本地栈 MySQL（Docker 容器 hospital-local-stack-mysql-1，127.0.0.1:3307），
按采购申请名称前缀（默认 `UI自动化-`）软删除相关数据，避免误删业务数据。

用法：
    python scripts/cleanup_test_data.py                 # 预览匹配数据量
    python scripts/cleanup_test_data.py --apply         # 执行软删除
    python scripts/cleanup_test_data.py --prefix "UI自动化-20261118-" --apply
    python scripts/cleanup_test_data.py --run-id UI自动化-20261118-232939-liw --apply
"""
from __future__ import annotations

import argparse
import subprocess
import sys

MYSQL_CONTAINER = "hospital-local-stack-mysql-1"

# (schema, table, where 子句模板, 软删除字段, 时间字段)
TABLES = [
    ("hospital_procurement", "hospital_purchase_request",
     "request_name LIKE '{prefix}%'", "is_deleted", "update_time"),
    ("hospital_procurement", "hp_survey_project",
     "source_request_id IN ({request_ids})", "is_deleted", "modify_time"),
    ("hospital_procurement", "hp_survey_argument",
     "survey_project_uuid IN ({survey_ids})", "is_deleted", "modify_time"),
    ("hospital_procurement", "hospital_purchase_audit",
     "purchase_request_id IN ({request_ids})", "is_deleted", "update_time"),
    ("hospital_procurement", "hospital_document_approval",
     "request_id IN ({request_ids})", "is_deleted", "update_time"),
    ("hospital_procurement", "purchase_document_instance",
     "purchase_request_id IN ({request_ids})", "is_deleted", "modify_time"),
    ("hospital_procurement", "hospital_purchase_demand_review_task",
     "purchase_request_id IN ({request_ids})", "is_deleted", "modify_time"),
    ("hospital_procurement", "hpr_procurement_method_approval",
     "purchase_request_id IN ({request_ids})", "is_deleted", "update_time"),
    ("procurement_execution", "purchase_project",
     "source_apply_id IN ({request_ids})", "is_deleted", "modify_time"),
]

# 无 is_deleted 字段的表：用 disabled=1 标记
DISABLED_TABLES = [
    ("baseserver", "jjjc_purchaseaudit", "projectName LIKE '{prefix}%'"),
]


def mysql_root_password() -> str:
    result = subprocess.run(
        ["docker", "exec", MYSQL_CONTAINER, "printenv", "MYSQL_ROOT_PASSWORD"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
    )
    password = (result.stdout or "").strip()
    if result.returncode != 0 or not password:
        raise RuntimeError(f"无法读取本地 MySQL 密码（容器 {MYSQL_CONTAINER} 是否在运行？）")
    return password


def mysql(sql: str) -> list[list[str]]:
    password = mysql_root_password()
    result = subprocess.run(
        ["docker", "exec", MYSQL_CONTAINER, "mysql", "-uroot", f"-p{password}",
         "--default-character-set=utf8mb4", "-N", "--batch", "--raw", "-e", sql],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"SQL 执行失败：{result.stderr[:500]}")
    rows = []
    for line in (result.stdout or "").splitlines():
        if line.strip():
            rows.append(line.split("\t"))
    return rows


def quote(text: str) -> str:
    return "'" + str(text).replace("\\", "\\\\").replace("'", "''") + "'"


def main() -> int:
    parser = argparse.ArgumentParser(description="本地测试数据清理（默认预览）")
    parser.add_argument("--prefix", default="UI自动化-", help="申请名称前缀")
    parser.add_argument("--run-id", default="", help="仅清理某次运行（等价于前缀=runId）")
    parser.add_argument("--apply", action="store_true", help="执行软删除（默认只预览）")
    args = parser.parse_args()
    prefix = args.run_id or args.prefix

    requests = mysql(
        "SELECT uuid, request_code, request_name FROM hospital_procurement.hospital_purchase_request "
        f"WHERE request_name LIKE {quote(prefix + '%')} AND is_deleted=0;"
    )
    request_ids = [row[0] for row in requests]
    if not request_ids:
        print(f"未找到名称以 {prefix!r} 开头的采购申请，无需清理。")
        return 0
    request_codes = [row[1] for row in requests]
    print(f"匹配采购申请 {len(requests)} 条（前缀 {prefix!r}）")
    for row in requests[:10]:
        print(f"  - {row[1]}  {row[2]}")
    if len(requests) > 10:
        print(f"  ... 其余 {len(requests) - 10} 条省略")

    ids_sql = ", ".join(quote(i) for i in request_ids)
    survey_rows = mysql(
        "SELECT uuid FROM hospital_procurement.hp_survey_project "
        f"WHERE source_request_id IN ({ids_sql}) AND is_deleted=0;"
    )
    survey_ids = [row[0] for row in survey_rows]
    survey_ids_sql = ", ".join(quote(i) for i in survey_ids) if survey_ids else "''"

    plan = []
    for schema, table, where_tpl, _field, _time_field in TABLES:
        where = where_tpl.format(prefix=prefix, request_ids=ids_sql, survey_ids=survey_ids_sql)
        count = mysql(f"SELECT COUNT(*) FROM {schema}.{table} WHERE {where};")[0][0]
        plan.append((schema, table, where, int(count)))
    disabled_plan = []
    for schema, table, where_tpl in DISABLED_TABLES:
        where = where_tpl.format(prefix=prefix)
        count = mysql(f"SELECT COUNT(*) FROM {schema}.{table} WHERE {where};")[0][0]
        disabled_plan.append((schema, table, where, int(count)))

    print("\n待软删除数据量：")
    total = 0
    for schema, table, _where, count in plan + disabled_plan:
        total += count
        print(f"  {schema}.{table}: {count}")
    print(f"合计：{total}")

    if not args.apply:
        print("\n当前为预览模式；确认无误后加 --apply 执行软删除。")
        return 0

    statements = ["START TRANSACTION;"]
    time_fields = {(s, tb): tf for s, tb, _w, _f, tf in TABLES}
    for schema, table, where, _count in plan:
        time_field = time_fields.get((schema, table), "update_time")
        statements.append(
            f"UPDATE {schema}.{table} SET is_deleted=1, {time_field}=NOW() WHERE {where};"
        )
    for schema, table, where, _count in disabled_plan:
        statements.append(f"UPDATE {schema}.{table} SET disabled=1 WHERE {where};")
    statements.append("COMMIT;")
    mysql(" ".join(statements))
    print(f"\n已软删除 {total} 条测试数据（前缀 {prefix!r}）。")
    print("提示：附件文件仍在本地文件服务目录，如需彻底清理可再手动删除。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
