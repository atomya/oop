from decimal import Decimal

from shared.enums import Currency


class TransactionRules:
    DEFAULT_EXTERNAL_TRANSFER_FEE_RATE = Decimal("0.02")
    DEFAULT_MAX_RETRIES = 2
    DEFAULT_RETRY_DELAY_MINUTES = 5
    BASE_EXCHANGE_RATES = {
        Currency.USD: Decimal("1.00"),
        Currency.EUR: Decimal("0.92"),
        Currency.RUB: Decimal("90.00"),
        Currency.KZT: Decimal("460.00"),
        Currency.CNY: Decimal("7.20"),
    }
