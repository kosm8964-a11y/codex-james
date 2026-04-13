from datetime import date
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

from .auth import create_token, verify_token
from .permissions import ROLE_PERMISSIONS, has_permission
from .schemas import CreateOrderIn, FinanceAccountIn, PaymentIn, ReceiptIn, ShipmentExceptionIn, ShipmentUpdateIn, SupplierBankAccountIn, UnitConvertIn, UnitConvertOut
from .services import (
    export_cash_ledger_csv,
    export_cash_ledger_pdf,
    finance_dashboard,
    convert_unit,
    list_orders,
    list_orders_paged,
    list_shipments_paged,
    list_shipments,
    mark_shipment_exception,
    create_finance_account,
    create_user,
    create_order,
    create_supplier_bank_account,
    export_order_pdf,
    get_order_detail,
    list_active_finance_accounts,
    list_active_supplier_bank_accounts,
    list_audit_logs,
    list_roles,
    list_users,
    register_payment,
    register_receipt,
    resolve_price,
    store,
    update_finance_account,
    update_shipment,
    assign_user_roles,
    authenticate_user,
    set_user_status,
)

app = FastAPI(title="Fertilizer OMS MVP API", version="0.4.0")


class LoginIn(BaseModel):
    username: str
    password: str


class UserIn(BaseModel):
    username: str
    password: str
    displayName: str | None = None
    status: int = 1


class UserRolesIn(BaseModel):
    roleCodes: list[str]


class UserStatusIn(BaseModel):
    status: int


def require_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        return verify_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def require_roles(*roles: str):
    def _checker(user: dict = Depends(require_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="insufficient role")
        return user

    return _checker


@app.post("/auth/login")
def login(payload: LoginIn) -> dict:
    try:
        auth = authenticate_user(payload.username, payload.password)
        token = create_token(auth["username"], role=auth["roles"][0])
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"accessToken": token, "tokenType": "Bearer"}


@app.get("/auth/verify")
def auth_verify(token: str) -> dict:
    try:
        return verify_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/rbac/matrix")
def rbac_matrix(_user: dict = Depends(require_roles("admin"))) -> dict:
    return {k: sorted(list(v)) for k, v in ROLE_PERMISSIONS.items()}


@app.get("/rbac/check")
def rbac_check(permission: str, _user: dict = Depends(require_user)) -> dict:
    role = _user.get("role", "")
    return {"role": role, "permission": permission, "allowed": has_permission(role, permission)}


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/orders")
def create_order_api(payload: CreateOrderIn, user: dict = Depends(require_roles("admin", "sales"))) -> dict:
    try:
        body = payload.model_dump()
        body["operator"] = user["sub"]
        return create_order(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/orders/{order_id}")
def order_detail(order_id: int) -> dict:
    try:
        return get_order_detail(order_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/orders")
def orders(
    customerId: int | None = None,
    status: str | None = None,
    dateFrom: date | None = None,
    dateTo: date | None = None,
    ) -> list[dict]:
    return list_orders(
        customer_id=customerId,
        status=status,
        date_from=str(dateFrom) if dateFrom else None,
        date_to=str(dateTo) if dateTo else None,
    )


@app.get("/orders/paged")
def orders_paged(
    page: int = 1,
    size: int = 20,
    customerId: int | None = None,
    status: str | None = None,
    dateFrom: date | None = None,
    dateTo: date | None = None,
    sortBy: str = "id",
    sortDir: str = "desc",
) -> dict:
    return list_orders_paged(
        page=page,
        size=size,
        customer_id=customerId,
        status=status,
        date_from=str(dateFrom) if dateFrom else None,
        date_to=str(dateTo) if dateTo else None,
        sort_by=sortBy,
        sort_dir=sortDir,
    )


@app.patch("/orders/{order_id}/shipment")
def patch_shipment(order_id: int, payload: ShipmentUpdateIn, user: dict = Depends(require_roles("admin", "warehouse"))) -> dict:
    try:
        body = payload.model_dump()
        body["operator"] = user["sub"]
        return update_shipment(order_id, body)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/shipments")
def get_shipments(status: str | None = None, orderId: int | None = None, trackingNo: str | None = None) -> list[dict]:
    return list_shipments(status=status, order_id=orderId, tracking_no=trackingNo)


@app.get("/shipments/paged")
def get_shipments_paged(
    page: int = 1,
    size: int = 20,
    status: str | None = None,
    orderId: int | None = None,
    trackingNo: str | None = None,
    sortBy: str = "id",
    sortDir: str = "desc",
) -> dict:
    return list_shipments_paged(
        page=page,
        size=size,
        status=status,
        order_id=orderId,
        tracking_no=trackingNo,
        sort_by=sortBy,
        sort_dir=sortDir,
    )


@app.patch("/orders/{order_id}/shipment/exception")
def patch_shipment_exception(order_id: int, payload: ShipmentExceptionIn) -> dict:
    try:
        return mark_shipment_exception(order_id, payload.exceptionNote)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/pricing/resolve")
def pricing_resolve(customerId: int, productId: int) -> dict:
    rule, price = resolve_price(customerId, productId)
    return {"pricingRule": rule, "unitPrice": price, "taxRate": 13}


@app.post("/unit/convert", response_model=UnitConvertOut)
def unit_convert(payload: UnitConvertIn) -> UnitConvertOut:
    try:
        pack_qty, ton_qty, ratio = convert_unit(payload.productId, payload.inputUnit, payload.qty)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UnitConvertOut(packQty=pack_qty, tonQty=ton_qty, ratio=ratio)


@app.post("/orders/{order_id}/export-pdf")
def export_pdf(order_id: int) -> dict:
    try:
        return export_order_pdf(order_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/finance/accounts/active")
def get_active_accounts() -> list[dict]:
    return list_active_finance_accounts()


@app.post("/finance/accounts")
def create_account(payload: FinanceAccountIn, _user: dict = Depends(require_roles("admin", "finance"))) -> dict:
    return create_finance_account(payload.model_dump())


@app.put("/finance/accounts/{account_id}")
def update_account(account_id: int, payload: FinanceAccountIn, _user: dict = Depends(require_roles("admin", "finance"))) -> dict:
    try:
        return update_finance_account(account_id, payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/finance/supplier-accounts/active")
def get_active_supplier_accounts(supplierId: int | None = None) -> list[dict]:
    return list_active_supplier_bank_accounts(supplierId)


@app.post("/finance/supplier-accounts")
def create_supplier_account(payload: SupplierBankAccountIn, _user: dict = Depends(require_roles("admin", "finance"))) -> dict:
    return create_supplier_bank_account(payload.model_dump())


@app.post("/finance/receipts")
def create_receipt(payload: ReceiptIn, user: dict = Depends(require_roles("admin", "finance"))) -> dict:
    try:
        body = payload.model_dump()
        body["operator"] = user["sub"]
        return register_receipt(body)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/finance/payments")
def create_payment(payload: PaymentIn, _user: dict = Depends(require_roles("admin", "finance"))) -> dict:
    return register_payment(payload.model_dump())


@app.get("/finance/cash-ledger")
def get_cash_ledger(dateFrom: date | None = Query(default=None), dateTo: date | None = Query(default=None)) -> dict:
    rows = store.cash_ledger
    if dateFrom:
        rows = [x for x in rows if x["occurDate"] >= str(dateFrom)]
    if dateTo:
        rows = [x for x in rows if x["occurDate"] <= str(dateTo)]
    return {"total": len(rows), "rows": rows}


@app.get("/finance/dashboard")
def get_finance_dashboard(
    dateFrom: date | None = Query(default=None),
    dateTo: date | None = Query(default=None),
    _user: dict = Depends(require_roles("admin", "finance")),
) -> dict:
    return finance_dashboard(
        date_from=str(dateFrom) if dateFrom else None,
        date_to=str(dateTo) if dateTo else None,
    )


@app.get("/audit/logs")
def audit_logs(moduleName: str | None = None, limit: int = 100, _user: dict = Depends(require_roles("admin"))) -> list[dict]:
    return list_audit_logs(module_name=moduleName, limit=limit)


@app.get("/admin/roles")
def admin_roles(_user: dict = Depends(require_roles("admin"))) -> list[dict]:
    return list_roles()


@app.get("/admin/users")
def admin_users(_user: dict = Depends(require_roles("admin"))) -> list[dict]:
    return list_users()


@app.post("/admin/users")
def admin_create_user(payload: UserIn, _user: dict = Depends(require_roles("admin"))) -> dict:
    return create_user(
        username=payload.username,
        password=payload.password,
        display_name=payload.displayName,
        status=payload.status,
    )


@app.post("/admin/users/{user_id}/roles")
def admin_assign_roles(user_id: int, payload: UserRolesIn, _user: dict = Depends(require_roles("admin"))) -> dict:
    try:
        return assign_user_roles(user_id, payload.roleCodes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/admin/users/{user_id}/status")
def admin_set_user_status(user_id: int, payload: UserStatusIn, _user: dict = Depends(require_roles("admin"))) -> dict:
    try:
        return set_user_status(user_id, payload.status)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/finance/reconciliation/export-csv")
def export_reconciliation_csv(
    dateFrom: date | None = Query(default=None),
    dateTo: date | None = Query(default=None),
    _user: dict = Depends(require_roles("admin", "finance")),
) -> dict:
    return export_cash_ledger_csv(
        date_from=str(dateFrom) if dateFrom else None,
        date_to=str(dateTo) if dateTo else None,
    )


@app.post("/finance/reconciliation/export-pdf")
def export_reconciliation_pdf(
    dateFrom: date | None = Query(default=None),
    dateTo: date | None = Query(default=None),
    _user: dict = Depends(require_roles("admin", "finance")),
) -> dict:
    return export_cash_ledger_pdf(
        date_from=str(dateFrom) if dateFrom else None,
        date_to=str(dateTo) if dateTo else None,
    )
