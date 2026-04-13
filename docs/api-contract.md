# API Contract（MVP）

## 1) 创建订单（自动生成应收/发货）
- `POST /orders`

请求体（示例）
```json
{
  "customerId": 101,
  "plannedDeliveryDate": "2026-04-20",
  "items": [
    {
      "productId": 501,
      "inputUnit": "PACK",
      "qty": 25
    }
  ],
  "discountAmount": 0,
  "freightAmount": 200
}
```

返回体（示例）
```json
{
  "orderId": 90001,
  "orderNo": "SO202604130001",
  "orderStatus": "PENDING_PAYMENT",
  "totalAmount": 12800,
  "receivableId": 30001,
  "shipmentRecordId": 40001
}
```

## 2) 解析客户产品价格
- `GET /pricing/resolve?customerId=101&productId=501`

返回（示例）
```json
{
  "pricingRule": "CUSTOMER_SPECIAL",
  "unitPrice": 500,
  "taxRate": 13
}
```

## 3) 单位换算（包/吨）
- `POST /unit/convert`

请求（示例）
```json
{
  "productId": 501,
  "inputUnit": "PACK",
  "qty": 25
}
```

返回（示例）
```json
{
  "packQty": 25,
  "tonQty": 1,
  "ratio": 25
}
```

## 4) 导出订单 PDF（购销合同）
- `POST /orders/{id}/export-pdf`

返回（示例）
```json
{
  "exportId": 70001,
  "fileUrl": "https://oss-example.oss-cn-hangzhou.aliyuncs.com/contracts/SO202604130001.pdf"
}
```

## 5) 收款账户管理
- `GET /finance/accounts/active`
- `POST /finance/accounts`
- `PUT /finance/accounts/{id}`

## 6) 收款登记
- `POST /finance/receipts`

请求（示例）
```json
{
  "receivableId": 30001,
  "orderId": 90001,
  "financeAccountId": 80001,
  "receiptAmount": 12800,
  "receiptDate": "2026-04-21"
}
```

## 7) 付款登记（供应商）
- `POST /finance/payments`

请求（示例）
```json
{
  "payableId": 50001,
  "supplierId": 201,
  "supplierBankAccountId": 82001,
  "paymentAmount": 6800,
  "paymentDate": "2026-04-22"
}
```

## 8) 资金流水查询
- `GET /finance/cash-ledger?dateFrom=2026-04-01&dateTo=2026-04-30`
