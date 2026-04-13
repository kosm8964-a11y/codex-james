from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field
from typing import Literal, Optional


class OrderItemIn(BaseModel):
    productId: int
    inputUnit: Literal["PACK", "TON"]
    qty: Decimal = Field(gt=0)


class CreateOrderIn(BaseModel):
    customerId: int
    plannedDeliveryDate: Optional[date] = None
    items: list[OrderItemIn]
    discountAmount: Decimal = Decimal("0")
    freightAmount: Decimal = Decimal("0")


class UnitConvertIn(BaseModel):
    productId: int
    inputUnit: Literal["PACK", "TON"]
    qty: Decimal = Field(gt=0)


class UnitConvertOut(BaseModel):
    packQty: Decimal
    tonQty: Decimal
    ratio: Decimal


class FinanceAccountIn(BaseModel):
    accountName: str
    bankName: str
    bankAccountNo: str
    status: int = 1
    isDefault: int = 0


class SupplierBankAccountIn(BaseModel):
    supplierId: int
    accountName: str
    bankName: str
    bankAccountNo: str
    status: int = 1
    isDefault: int = 0


class ShipmentUpdateIn(BaseModel):
    shipmentStatus: Literal["PENDING", "SHIPPED", "DELIVERED"]
    shippedQtyPack: Decimal = Decimal("0")
    shippedQtyTon: Decimal = Decimal("0")
    trackingNo: Optional[str] = None


class ShipmentExceptionIn(BaseModel):
    exceptionNote: str


class ReceiptIn(BaseModel):
    receivableId: int
    orderId: int
    financeAccountId: int
    receiptAmount: Decimal = Field(gt=0)
    receiptDate: date


class PaymentIn(BaseModel):
    payableId: int
    supplierId: int
    supplierBankAccountId: int
    paymentAmount: Decimal = Field(gt=0)
    paymentDate: date
