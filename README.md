# Day 2: Продвинутые типы банковских счетов

Короткий учебный проект по ООП на Python.

## Что реализовано

- `SavingsAccount`
  - `min_balance`
  - `monthly_interest_rate`
  - `apply_monthly_interest()`
- `PremiumAccount`
  - `overdraft_limit`
  - `withdrawal_limit`
  - `fixed_fee`
- `InvestmentAccount`
  - инвестиционный портфель
  - активы `stocks`, `bonds`, `etf`
  - `project_yearly_growth()`

## ООП и архитектура

- инкапсуляция через защищенные поля и `@property`
- наследование от базового `BankAccount`
- полиморфизм через переопределение `withdraw()`, `get_account_info()`, `__str__()`
- абстракция через `AbstractAccount`
- доменная модель для инвестиционного портфеля
- структурное логирование вынесено в сервисный слой
- код подготовлен к unit-тестированию

## Структура

```text
accounts/
  base/
    abstract_account.py
    bank_account.py
  types/
    savings_account.py
    premium_account.py
    investment/
      investment_account.py
      portfolio.py
      portfolio_position.py
      rules.py
services/
  account_audit_logger.py
  account_service.py
tests/
  test_accounts.py
demo.py
```

## Быстрая проверка

Запуск демо:

```bash
python3 demo.py
```

Запуск тестов:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

## Что показывает демо

- создание обычного, накопительного, премиального и инвестиционного счетов
- пополнение и снятие средств
- проценты по `SavingsAccount`
- овердрафт и комиссия в `PremiumAccount`
- инвестиции в `stocks`, `bonds`, `etf`
- прогноз годового роста портфеля
- обработку доменных ошибок
