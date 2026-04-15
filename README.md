# Banking OOP Project

Учебный проект по ООП на Python.  
Сейчас в проекте реализованы Day 1, Day 2, Day 3, Day 4 и Day 5:
- базовые банковские счета и статусы;
- `SavingsAccount`, `PremiumAccount`, `InvestmentAccount`;
- система `Client` и управляющий класс `Bank`;
- транзакции, очередь и процессинг переводов;
- аудит и rule-based риск-анализ операций.

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

### Transaction
- `transaction_id`
- `transaction_type`
- `amount`
- `currency`
- `fee`
- `sender`
- `recipient`
- `priority`
- `status`
- `failure_reason`
- `created_at`
- `scheduled_for`
- `processed_at`
- `failed_at`
- `canceled_at`
- `retry_count`

### Audit и Risk
- `AuditJournal`
  - уровни важности `INFO`, `WARNING`, `ERROR`, `CRITICAL`
  - хранение записей в памяти
  - сохранение в файл `jsonl`
  - фильтрация
  - отчёты по suspicious operations, клиентскому риску и статистике ошибок
- `RiskAnalyzer`
  - крупная сумма
  - частые операции
  - новый получатель
  - ночная операция
  - уровни риска `LOW`, `MEDIUM`, `HIGH`
  - блокировка `HIGH` риска до исполнения транзакции

## Очередь и процессинг

### TransactionQueue
- хранит транзакции в in-memory очереди;
- поддерживает `add()`, `cancel()`, `remove()`, `get_next_ready()`;
- учитывает отложенные операции через `scheduled_for`;
- использует fair-cycle по приоритетам:

```text
HIGH -> NORMAL -> HIGH -> NORMAL -> LOW
```

Это позволяет:
- давать больший вес `HIGH`;
- не допускать бесконечного накопления `NORMAL` и `LOW`.

`get_next_ready()`:
- не удаляет транзакцию из очереди;
- только выбирает следующую готовую к исполнению транзакцию;
- удаление происходит позже, когда процессор уже завершил обработку.

`pending_transactions()`:
- возвращает только read-only представление через `get_transaction_info()`;
- не отдаёт наружу живые pending-объекты.

### TransactionProcessor
- берёт ready-транзакции из очереди;
- делает risk assessment до исполнения;
- блокирует опасные операции уровня `HIGH`;
- проверяет счета и банковые ограничения;
- считает комиссию;
- делает конвертацию валют;
- выполняет перевод;
- обрабатывает retry при временных ошибках;
- фиксирует `completed`, `failed`, `retry_scheduled`.

Обработка построена по принципу:
- сначала валидация и подготовка execution plan;
- потом изменение балансов;
- при ошибке после списания делается компенсационный возврат.

## Защита и правила

- после 3 неверных попыток входа клиент блокируется;
- подозрительные действия пишутся в журнал банка;
- операции банка запрещены с `00:00` до `05:00`;
- запрещены переводы с отрицательного баланса, кроме `PremiumAccount`;
- запрещены переводы по замороженным и закрытым счетам;
- комиссия применяется к внешним переводам;
- опасные операции уровня `HIGH` блокируются до исполнения;
- валидация входных данных выполняется до изменения состояния объектов;
- для счетов, клиентов и транзакций используются короткие уникальные ID;
- в `__str__()` у счетов показываются последние 4 цифры номера.

## Архитектура

- `accounts/` — иерархия счетов
- `domain/` — доменные сущности `Bank` и `Client`
- `transactions/` — транзакции и очередь
- `risk/` — rule-based анализ риска
- `services/` — application layer и процессоры
- `audit/` — журнал аудита, записи аудита и аудит-логгеры
- `shared/` — общие `enums` и `exceptions`
- `utils/` — общие утилиты валидации и ID
- `tests/` — unit-тесты

```text
accounts/
  base/
  types/
audit/
  audit_record.py
  audit_journal.py
  loggers/
    base_audit_logger.py
    account_audit_logger.py
    transaction_audit_logger.py
domain/
  bank.py
  client.py
risk/
  risk_analyzer.py
  risk_assessment.py
services/
  account_service.py
  transaction_processor.py
shared/
  enums.py
  exceptions.py
transactions/
  transaction.py
  transaction_queue.py
  rules.py
utils/
  unique_id.py
  validation.py
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
- обработку транзакций;
- delayed, cancel, fail и retry-сценарии;
- suspicious operations report;
- client risk profile;
- error statistics по аудиту;
- обработку доменных ошибок.
