# Day 3: Bank System

Учебный проект по ООП на Python.  
Текущий этап включает Day 1, Day 2 и Day 3:
- базовые счета и статусы;
- `SavingsAccount`, `PremiumAccount`, `InvestmentAccount`;
- систему `Client` и управляющий класс `Bank`.

## Что реализовано

### Счета
- `BankAccount`
- `SavingsAccount`
  - `min_balance`
  - `monthly_interest_rate`
  - `apply_monthly_interest()`
- `PremiumAccount`
  - `overdraft_limit`
  - `withdrawal_limit`
  - `fixed_fee`
- `InvestmentAccount`
  - портфель активов `stocks`, `bonds`, `etf`
  - `invest_in_asset()`
  - `sell_asset()`
  - `project_yearly_growth()`

### Client
- `full_name`
- `client_id`
- `birth_date`
- вычисляемый `age`
- `status`
- `contacts`
- `account_ids`
- `pin_code`
- проверка совершеннолетия с учетом текущей даты, месяца и дня

### Bank
- `add_client()`
- `open_account()`
- `close_account()`
- `freeze_account()`
- `unfreeze_account()`
- `authenticate_client()`
- `search_accounts()`
- `get_total_balance()`
- `get_clients_ranking()`

## Защита и правила

- после 3 неверных попыток входа клиент блокируется;
- подозрительные действия пишутся в журнал банка;
- операции банка запрещены с `00:00` до `05:00`;
- валидация входных данных сделана до изменения состояния объектов;
- для счетов и клиентов используется короткий уникальный ID;
- в `__str__()` у счетов показываются последние 4 цифры номера.

## Архитектура

- `accounts/` — иерархия счетов
- `domain/` — верхнеуровневые доменные сущности `Bank` и `Client`
- `shared/` — общие `enums` и `exceptions`
- `services/` — структурное логирование и application layer
- `tests/` — unit-тесты

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
domain/
  bank.py
  client.py
shared/
  enums.py
  exceptions.py
services/
  account_audit_logger.py
  account_service.py
tests/
  test_accounts.py
demo.py
```

## Быстрая проверка

Демо:

```bash
python3 demo.py
```

Тесты:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

## Что показывает демо

- операции по разным типам счетов;
- проценты по накопительному счету;
- овердрафт и комиссия в премиальном счете;
- инвестиции и прогноз роста портфеля;
- создание клиента и открытие счета через `Bank`;
- аутентификацию по `pin_code`;
- заморозку и разморозку счета;
- обработку доменных ошибок.
