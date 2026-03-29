from decimal import Decimal


class InvestmentRules:
    DEFAULT_GROWTH_RATES = {
        "stocks": Decimal("0.12"),
        "bonds": Decimal("0.06"),
        "etf": Decimal("0.09"),
    }
