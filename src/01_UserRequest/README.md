# 01_UserRequest_API
Описание модуля и его назначения.

### 2.1 User Request & API

**Функции:**

- Приём запросов (CLI / Streamlit UI / Telegram bot trigger).
- Валидация входных параметров (symbol, timeframe, period, setup_id, mode=[backtest/live]).
- Создаёт Prefect run: `prefect deployment apply` или запускает flow напрямую.

**Интерфейс:**

- REST (Streamlit кнопка → Prefect run), или Prefect API call.

**Acceptance:**

- Для любого валидного запроса в логах должен появиться `run_id` и начата задача.

**Примечание:** сделать шаблоны запросов в Streamlit (Backtest / Live watch / One-shot analysis).

**Scheduler (Scheduler/Agent):** может запускать START по расписанию (например, ночные бэктесты, или каждую минуту для live poll). Scheduler не вызывает детекторы напрямую — он запускает flows (через Setup Manager), чтобы централизованно сохранять трассируемость и логи.


## ⚙️ ASCII схема

### START и Scheduler / Job Manager

## МОДУЛЬ: START / User Trigger

**module_name:** START (User Trigger / API Trigger / Manual Button)

**inputs:**

- source: USER_REQUEST (web UI Streamlit / HTTP API / CLI / Prefect trigger)
- data_type: JSON
- description: `{ setup_id, symbol, timeframe, start, end, mode("backtest"|"live"), options: {max_trades, rr_target, dry_run} }`

**ascii_diagram:**

```
┌───────────────────────────────────────────┐
│            START / TRIGGER                │
├───────────────────────────────────────────┤
│  • Приём пользовательского запроса        │
│  • Валидация параметров                   │
│  • Передача контекста в Setup Manager     │
└───────────────────────────────────────────┘

```

**outputs:**

- destination: Setup Manager
- data_type: JSON
- description: same payload forwarded + `run_id` (если создан заранее)

**logic_notes:**

- START может быть manual UI button, HTTP POST webhook или scheduler-initiated.
- Перед отправкой в Setup Manager создаётся `run_id` и запись про запуск (traceability).
- Если `dry_run=true` — Setup Manager выполняет только план (no heavy calculations).

---

## МОДУЛЬ: Scheduler / Job Manager (Prefect or internal)

**module_name:** Scheduler / Job Manager

**inputs:**

- source: USER_REQUEST or Cron config or Prefect schedule
- data_type: JSON / schedule object
- description: задания/расписания для запуска flows: `{flow_name, cron, payload}`

**ascii_diagram:**

```
┌────────────────────────────────────────────────┐
│          SCHEDULER / JOB MANAGER               │
├────────────────────────────────────────────────┤
│  • Хранит расписания  (cron / interval)        │
│  • Триггерит START или напрямую SetupManager   │
│  • Управляет очередью запусков                 │
└────────────────────────────────────────────────┘

```

**outputs:**

- destination: START or Setup Manager
- data_type: JSON
- description: schedule-triggered payload (как от пользователя)

**logic_notes:**

- Scheduler стартует flows по расписанию; всегда инициирует через START/SetupManager, чтобы сохранить единую точку входа и логирование.
- Для live polling можно настроить Agent, который отправляет `mode: live` каждые N секунд/минут.
- Scheduler также может запускать ночные batch backtests (batch jobs через Backtest Runner).



### Подмодуль 2.1.1 — Request Handler

**submodule_name:** "2.1.1 Request Handler"

**inputs:**

- **from_source:** USER_REQUEST (через Streamlit UI / CLI / Telegram bot)
- **data_type:** JSON
- **params:** mode (backtest/live), symbol, timeframe, period (start/end), setup_id, extra_params
- **format:**

json

  `{
    "mode": "backtest|live",
    "symbol": "GER40",
    "timeframe": "M15",
    "start": "2025-05-01",
    "end": "2025-10-31",
    "setup_id": "IB_raid_v1",
    "extra": {}
  }
````

- **description:** Пользовательский запрос на анализ (бэктест или лайв-мониторинг)

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         REQUEST HANDLER                        │
├────────────────────────────────────────────────┤
│  • Приём запросов от пользователя              │
│  • Валидация параметров (symbol, tf, period)   │
│  • Создание Prefect run с уникальным run_id    │
│  • Логирование запроса                         │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Prefect Orchestrator (запуск flow)
- **data_type:** JSON (validated request) + run_id (string)
- **params:** run_id, validated_request, timestamp
- **format:**

json

  `{
    "run_id": "run_2025_10_31_001",
    "request": {...validated params...},
    "timestamp": "2025-10-31T10:00:00Z",
    "flow_type": "backtest_flow|live_scan_flow"
  }
````

- **description:** Валидированный запрос с присвоенным run_id для запуска соответствующего Prefect flow

**logic_notes:**
- "Валидация обязательна: symbol должен быть в списке доступных, timeframe в [M1,M5,M15,H1,H4,D1], setup_id должен существовать в Rule Registry"
- "При ошибке валидации возвращает error response пользователю БЕЗ запуска flow"
- "Логирует каждый запрос в audit log с timestamp и user identifier"

---