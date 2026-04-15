from decimal import Decimal, ROUND_HALF_UP

from shared.enums import Currency
from shared.exceptions import InvalidOperationError


BASE_EXCHANGE_RATES = {
    Currency.USD: Decimal("1.00"),
    Currency.EUR: Decimal("0.92"),
    Currency.RUB: Decimal("90.00"),
    Currency.KZT: Decimal("460.00"),
    Currency.CNY: Decimal("7.20"),
}


def validate_exchange_rates(exchange_rates: dict[Currency, Decimal]) -> dict[Currency, Decimal]:
    if not isinstance(exchange_rates, dict) or not exchange_rates:
        raise InvalidOperationError("Exchange rates must be a non-empty dictionary")

    normalized_rates = {}
    for currency, rate in exchange_rates.items():
        if not isinstance(currency, Currency):
            raise InvalidOperationError("Exchange rate keys must be Currency enums")
        if isinstance(rate, bool) or not isinstance(rate, (int, float, Decimal)):
            raise InvalidOperationError("Exchange rate values must be numeric")

        decimal_rate = Decimal(str(rate))
        if decimal_rate <= 0:
            raise InvalidOperationError("Exchange rates must be positive")
        normalized_rates[currency] = decimal_rate

    return normalized_rates


def quantize_money(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def convert_currency_amount(
    amount: Decimal,
    from_currency: Currency,
    to_currency: Currency,
    exchange_rates: dict[Currency, Decimal],
) -> Decimal:
    if from_currency == to_currency:
        return quantize_money(amount)

    from_rate = exchange_rates[from_currency]
    to_rate = exchange_rates[to_currency]
    converted_amount = (amount / from_rate) * to_rate
    return quantize_money(converted_amount)
