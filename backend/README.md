# Backend MVP (FastAPI + SQLite)

## Features in current step

- SQLite 持久化订单、应收、发货、收支流水
- 财务收款账户管理：新增/更新/查询启用账户
- 供应商收款账户管理：新增/查询启用账户
- 订单详情查询接口：聚合订单、发货、应收、收款记录
- 发货更新接口：`PATCH /orders/{id}/shipment`
- 发货管理接口：`GET /shipments`（支持状态/订单号/运单筛选）
- 发货分页接口：`GET /shipments/paged`（支持分页/排序/筛选）
- 发货异常标记：`PATCH /orders/{id}/shipment/exception`
- 订单状态机：`PENDING_PAYMENT -> PARTIAL_PAID -> PAID -> SHIPPED -> COMPLETED`
- 财务对账导出：`POST /finance/reconciliation/export-csv`
- 财务对账导出：`POST /finance/reconciliation/export-pdf`
- 订单列表筛选：`GET /orders`（支持客户/状态/日期区间）
- 订单列表分页：`GET /orders/paged`（支持分页/排序/筛选）
- 财务看板统计：`GET /finance/dashboard`（收入/支出/净现金流）
- 鉴权接口：`POST /auth/login`、`GET /auth/verify`
- 业务接口支持 Bearer 鉴权（订单创建、发货更新、收款登记等）
- RBAC 角色控制：`admin / finance / sales / warehouse`（不同接口有不同角色权限）
- 权限矩阵接口：`GET /rbac/matrix`、`GET /rbac/check`
- 用户角色管理：`GET /admin/users`、`POST /admin/users`、`POST /admin/users/{id}/roles`、`GET /admin/roles`
- 用户状态管理：`POST /admin/users/{id}/status`（启用/禁用）
- 密码加密存储（salt+hash）与登录失败锁定策略（连续失败 5 次锁定 15 分钟）
- 审计日志查询：`GET /audit/logs`
- `POST /orders/{id}/export-pdf` 会真实生成 PDF 文件到 `backend/storage/contracts/`
- 导出 PDF 时会自动带出默认收款账户信息

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Test

```bash
PYTHONPATH=. pytest -q tests/test_services.py
```

> 可用环境变量 `OMS_DB_PATH` 指定数据库路径。
