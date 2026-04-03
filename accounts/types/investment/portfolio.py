from decimal import Decimal

from accounts.types.investment.portfolio_position import PortfolioPosition
from accounts.types.investment.rules import InvestmentRules
from shared.exceptions import InvalidOperationError


class Portfolio:
    def __init__(self, supported_assets: tuple[str, ...] = ("stocks", "bonds", "etf")):
        self._positions = {
            asset_type: PortfolioPosition(asset_type=asset_type)
            for asset_type in supported_assets
        }

    def _normalize_asset_type(self, asset_type: str) -> str:
        normalized = asset_type.lower()
        if normalized not in self._positions:
            raise InvalidOperationError(f"Unsupported asset type: {asset_type}")
        return normalized

    def validate_asset_type(self, asset_type: str) -> str:
        return self._normalize_asset_type(asset_type)

    def invest(self, asset_type: str, amount: Decimal) -> str:
        normalized = self._normalize_asset_type(asset_type)
        self._positions[normalized].add(amount)
        return normalized

    def sell(self, asset_type: str, amount: Decimal) -> str:
        normalized = self._normalize_asset_type(asset_type)
        self._positions[normalized].remove(amount)
        return normalized

    def project_yearly_growth(self, growth_rates: dict[str, Decimal] | None = None) -> dict[str, Decimal]:
        rates = growth_rates or InvestmentRules.DEFAULT_GROWTH_RATES
        projection = {}

        for asset_type, amount in self.as_dict().items():
            rate = Decimal(str(rates.get(asset_type, Decimal("0.00"))))
            projection[asset_type] = amount * (Decimal("1.00") + rate)

        return projection

    def as_dict(self) -> dict[str, Decimal]:
        return {
            asset_type: position.amount
            for asset_type, position in self._positions.items()
        }

    def total_invested(self) -> Decimal:
        return sum((position.amount for position in self._positions.values()), start=Decimal("0.00"))
