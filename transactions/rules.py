from decimal import Decimal

from utils.currency import BASE_EXCHANGE_RATES


class TransactionRules:
    DEFAULT_EXTERNAL_TRANSFER_FEE_RATE = Decimal("0.02")
    DEFAULT_MAX_RETRIES = 2
    DEFAULT_RETRY_DELAY_MINUTES = 5
    BASE_EXCHANGE_RATES = BASE_EXCHANGE_RATES
