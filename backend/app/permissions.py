ROLE_PERMISSIONS = {
    "admin": {"*"},
    "finance": {
        "finance.accounts.write",
        "finance.receipts.write",
        "finance.payments.write",
        "finance.dashboard.read",
        "finance.reconciliation.export",
    },
    "sales": {
        "orders.create",
        "orders.read",
    },
    "warehouse": {
        "shipments.update",
        "shipments.read",
    },
}


def has_permission(role: str, permission: str) -> bool:
    perms = ROLE_PERMISSIONS.get(role, set())
    return "*" in perms or permission in perms
