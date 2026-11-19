"""环境账号配置：local（本地栈）/ online（线上 172.16.29.215）。

只存账号名/平台/角色关键字，不存密码（密码从环境变量/`.env.local` 读取）。
"""
from __future__ import annotations

import os

LOCAL_ACCOUNTS = {
    "applicant": ("cbbm1", "采购交易系统", "承办部门经办"),
    "supervisor": ("jjzr", "纪检监察平台", "纪检监察主任"),
    "director": ("zhaoliu", "采购交易系统", "承办部门主任"),
    "auditor": ("sjyj", "纪检监察平台", "审计员"),
    "auditDirector": ("sjbzr", "纪检监察平台", "审计部主任"),
    "finance": ("zhoujiu", "采购交易系统", "财务部主任"),
    "hpAuditDirector": ("sjbzr", "采购交易系统", "审计部主任"),
    "procurementDirector": ("bailu", "采购交易系统", "采购执行部门主任"),
    "jjjcDirector": ("jjzr", "采购交易系统", "纪检主任"),
    "officeDirector": ("baiqi", "采购交易系统", "医院办公室主任"),
    "deptLeader": ("libai", "采购交易系统", "承办部门分管院领导"),
    "viceLeader": ("fgld", "采购交易系统", "分管领导"),
    "vicePresident": ("fgyld", "采购交易系统", "分管院领导"),
    "supplier1": ("ybjcsgys1", "采购交易系统", "供应商"),
    "supplier2": ("ybjcsgys2", "采购交易系统", "供应商"),
    "supplier3": ("ybjcsgys3", "采购交易系统", "供应商"),
}

ONLINE_ACCOUNTS = {
    "applicant": ("cbbm1", "采购交易系统", "承办部门经办"),
    "supervisor": ("jjzr", "纪检监察平台", "纪检监察主任"),
    "director": ("zhaoliu", "采购交易系统", "承办部门主任"),
    "auditor": ("sjyj", "纪检监察平台", "审计员"),
    "auditDirector": ("sjbzr", "纪检监察平台", "审计部主任"),
    "finance": ("zhoujiu", "采购交易系统", "财务部主任"),
    "hpAuditDirector": ("sjbzr", "采购交易系统", "审计部主任"),
    "procurementDirector": ("bailu", "采购交易系统", "采购执行部门主任"),
    "jjjcDirector": ("jjzr", "采购交易系统", "纪检主任"),
    "officeDirector": ("baiqi", "采购交易系统", "医院办公室主任"),
    "deptLeader": ("libai", "采购交易系统", "承办部门分管院领导"),
    "viceLeader": ("fgld", "采购交易系统", "分管领导"),
    "vicePresident": ("fgyld", "采购交易系统", "分管院领导"),
    # 线上供应商测试账号（与本地一致的团队测试账号，密码见 .env.local 的 HP_PASSWORD_YBJCSGYS*）
    "supplier1": ("ybjcsgys1", "采购交易系统", "供应商"),
    "supplier2": ("ybjcsgys2", "采购交易系统", "供应商"),
    "supplier3": ("ybjcsgys3", "采购交易系统", "供应商"),
}


def environment() -> str:
    return os.environ.get("HP_ENV", "local").strip().lower() or "local"


def accounts() -> dict:
    return ONLINE_ACCOUNTS if environment() == "online" else LOCAL_ACCOUNTS
