#!/usr/bin/env python3
"""肥料订单生成器（命令行版）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class FertilizerOrder:
    order_id: str
    customer_name: str
    fertilizer_type: str
    quantity: float
    unit_price: float
    salesperson: str
    contact_phone: str
    delivery_address: str
    notes: str = ""

    @property
    def total_amount(self) -> float:
        return self.quantity * self.unit_price

    def render(self) -> str:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return (
            "=" * 50
            + "\n"
            + "            肥 料 订 单\n"
            + "=" * 50
            + f"\n订单号：{self.order_id}"
            + f"\n创建时间：{created_at}"
            + f"\n客户名称：{self.customer_name}"
            + f"\n业务员：{self.salesperson}"
            + f"\n联系电话：{self.contact_phone}"
            + "\n"
            + "-" * 50
            + f"\n肥料品种：{self.fertilizer_type}"
            + f"\n数量（吨）：{self.quantity:.2f}"
            + f"\n单价（元/吨）：{self.unit_price:.2f}"
            + f"\n金额合计（元）：{self.total_amount:.2f}"
            + f"\n送货地址：{self.delivery_address}"
            + "\n"
            + "-" * 50
            + f"\n备注：{self.notes or '无'}"
            + "\n"
            + "=" * 50
            + "\n"
        )


def ask_text(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("输入不能为空，请重试。")


def ask_positive_number(prompt: str) -> float:
    while True:
        raw = input(prompt).strip()
        try:
            value = float(raw)
            if value <= 0:
                raise ValueError
            return value
        except ValueError:
            print("请输入大于 0 的数字。")


def save_order(order: FertilizerOrder) -> Path:
    output_dir = Path("orders")
    output_dir.mkdir(exist_ok=True)
    safe_customer = order.customer_name.replace(" ", "_")
    filename = f"{order.order_id}_{safe_customer}.txt"
    output_path = output_dir / filename
    output_path.write_text(order.render(), encoding="utf-8")
    return output_path


def main() -> None:
    print("欢迎使用肥料订单生成系统\n")

    order = FertilizerOrder(
        order_id=ask_text("请输入订单号："),
        customer_name=ask_text("请输入客户名称："),
        fertilizer_type=ask_text("请输入肥料品种："),
        quantity=ask_positive_number("请输入数量（吨）："),
        unit_price=ask_positive_number("请输入单价（元/吨）："),
        salesperson=ask_text("请输入业务员姓名："),
        contact_phone=ask_text("请输入联系电话："),
        delivery_address=ask_text("请输入送货地址："),
        notes=input("请输入备注（可留空）：").strip(),
    )

    order_text = order.render()
    print("\n订单预览：")
    print(order_text)

    output_path = save_order(order)
    print(f"订单已生成：{output_path}")


if __name__ == "__main__":
    main()
