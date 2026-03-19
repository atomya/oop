import logging

from accounts.bank_account import BankAccount
from enums import Currency, AccountStatus


logging.basicConfig(level=logging.INFO)


# активный счёт
acc1 = BankAccount("Alice", Currency.USD)
acc1.deposit(500)
acc1.withdraw(200)


# замороженный счёт
acc2 = BankAccount("Bob", Currency.EUR, status=AccountStatus.FROZEN)

try:
    acc2.deposit(100)
except Exception as e:
    print(e)


print(acc1)
print(acc2)