class AccountFrozenError(Exception):
    def __init__(self):
        super().__init__("Account is frozen")


class AccountClosedError(Exception):
    def __init__(self):
        super().__init__("Account is closed")


class InvalidOperationError(Exception):
    def __init__(self, message="Invalid operation"):
        super().__init__(message)


class InsufficientFundsError(Exception):
    def __init__(self):
        super().__init__("Insufficient funds")


class TemporaryProcessingError(Exception):
    def __init__(self, message="Temporary processing error"):
        super().__init__(message)
