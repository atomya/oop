from dataclasses import dataclass
from decimal import Decimal

from exceptions import InvalidOperationError


@dataclass
class PortfolioPosition:
    asset_type: str
    amount: Decimal = Decimal("0.00")

    def add(self, amount: Decimal) -> None:
        if amount <= 0:
            raise InvalidOperationError("Portfolio amount must be positive")
        self.amount += amount

    def remove(self, amount: Decimal) -> None:
        if amount <= 0:
            raise InvalidOperationError("Portfolio amount must be positive")
        if amount > self.amount:
            raise InvalidOperationError("Cannot remove more than allocated")
        self.amount -= amount
