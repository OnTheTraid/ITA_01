# ASCII-схемы модулей

## ASCII-схемы модулей проекта, логика, входы и выходы

---

## МОДУЛЬ 2.1 — User Request & API

### START и Scheduler / Job Manager

## МОДУЛЬ: START / User Trigger

**module_name:** START (User Trigger / API Trigger / Manual Button)

**inputs:**

- source: USER_REQUEST (web UI Streamlit / HTTP API / CLI / Prefect trigger)
- data_type: JSON
- description: `{ setup_id, symbol, timeframe, start, end, mode("backtest"|"live"), options: {max_trades, rr_target, dry_run} }`

**ascii_diagram:**

```
┌───────────────────────────────┐
│            START / TRIGGER              │
├────────────────────────────────┤
│  • Приём пользовательского запроса         │
│  • Валидация параметров                       │
│  • Передача контекста в Setup Manager    │
└─────────────────────────────┘

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
┌───────────────────────────────┐
│          SCHEDULER / JOB MANAGER      │
├────────────────────────────────┤
│  • Хранит расписания  (cron / interval)    │
│  • Триггерит START или напрямую SetupMgr  │
│  • Управляет очередью запусков                │
└─────────────────────────────┘

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
│  • Приём запросов от пользователя             │
│  • Валидация параметров (symbol, tf, period)  │
│  • Создание Prefect run с уникальным run_id   │
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

---

## МОДУЛЬ 2.2 — Core Data & IO

### Подмодуль 2.2.1 — Data Ingest (MT5 Connector)

### **УСЛОВИЕ: BACKTEST режим**

******submodule_name:****** "2.2.1 **Data Ingest** MT5 Connector (BACKTEST)"

**condition:** "BACKTEST - загрузка исторических данных ТОЛЬКО если их нет в архиве или период расширяется"

**inputs:**

- **from_source:** Prefect Orchestrator (через validated request) + MT5 Terminal + ARCHIVE (проверка существующих данных)
- **data_type:** JSON (параметры запроса)
- **params:** symbol, timeframe, start, end
- **format:** `{"symbol": "GER40", "timeframe": "M15", "start": "2025-05-01", "end": "2025-10-31"}`
- **description:** Параметры для проверки наличия данных в архиве и загрузки недостающих

**ascii_diagram:**

`┌────────────────────────────────────────────────┐
│    MT5 CONNECTOR (BACKTEST MODE)               │
├────────────────────────────────────────────────┤
│  • СНАЧАЛА: проверка архива (есть ли данные?)  │
│  • IF данные есть → загрузить из архива        │
│  • IF данных нет/период расширен → MT5 load    │
│  • IF обновление (weekly) → только новые бары  │
│  • Сохранение в archive/raw/ для будущего      │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** Data Processor + ARCHIVE (если были загружены новые данные) OR return file path to Setup Manager
- **data_type:** DataFrame/ Parquet path + meta (dict),  CSV файл (только если нужны новые данные)
- **params:** symbol, timeframe, row_count, data_source (archive|mt5|cache)
- **format:** 
```
  DataFrame columns: [time (UTC tz-aware), open, high, low, close, volume]
  
  Response JSON: {
    "source": "archive",  // или "mt5" или "cache"
    "file_path": "archive/raw/GER40_M15_20250501_20251031.csv",
    "loaded_from_cache": true,
    "mt5_call_made": false,
    "rows": 10080
  }
```
- **description:** Исторические OHLCV данные из оптимального источника. `df_raw` and `meta: {source, tz, retrieved_at, rows, file_path, ingest_id}`

**logic_notes:**
- "**ПРИОРИТЕТ ИСТОЧНИКОВ:** 1) OnDiskCache (parquet - быстрее всего), 2) Archive CSV, 3) MT5 (только если данных нет)"
- "**Проверка покрытия периода:** если запрошен 2025-05-01 до 2025-10-31, а в архиве только до 2025-09-30 → загрузить с MT5 только октябрь и append"
- "**Weekly update (опционально):** раз в неделю можно обновить последние 7 дней для актуальности, НО это не обязательно для backtest на закрытой истории"
- "**Для закрытых периодов (например 2024 год) - НИКОГДА не обращаться к MT5, только архив**"
- "**Intelligent caching:** первый запрос → MT5 + save to archive, все последующие → архив"
- "КРИТИЧНО: избегать повторных загрузок одних и тех же данных - waste of time и MT5 requests"

---

## ДОПОЛНИТЕЛЬНО: Логика работы CSV/Archive Loader

**Подмодуль 2.2.2 теперь становится ОСНОВНЫМ источником для бэктестов:**

**submodule_name:** "2.2.2 CSV/Archive Loader"

**logic_notes (ОБНОВЛЕНО):**
- "**ОСНОВНОЙ источник для backtest:** 90% бэктестов работают с уже загруженными данными из archive/"
- "**MT5 Connector вызывается ТОЛЬКО если:**
  1) Данных вообще нет в архиве (первый запуск)
  2) Запрошенный период выходит за границы архивных данных
  3) Пользователь явно запросил 'force reload' (редкий случай, если подозрение на поврежденные данные)"
- "**Автообновление:** можно настроить автообновление последней недели раз в неделю, но это опционально"

---

## ИТОГО: Правильный flow для BACKTEST

```jsx
```
USER REQUEST (backtest 2025-05-01 to 2025-10-31)
    ↓
Data Ingest проверяет:
    ↓
OnDiskCache: есть GER40_M15_20250501_20251031.parquet?
    ├─ YES → LOAD (0.5 сек) → Data Processor
    └─ NO ↓
        Archive CSV: есть GER40_M15_20250501_20251031.csv?
            ├─ YES → LOAD (2 сек) → Data Processor
            └─ NO ↓
                MT5 Connector: загрузить (45 сек)
                    ↓
                Сохранить в Archive + Cache
                    ↓
                Data Processor
```

**Вывод:**

- Первый backtest на новых данных: 45 сек (MT5 загрузка)
- Все последующие: 0.5-2 сек (из cache/archive)
- **НИКОГДА не загружать повторно то, что уже есть**

### **УСЛОВИЕ: LIVE режим**

**submodule_name:** "2.2.1 **Data Ingest** MT5 Connector (LIVE)"

**condition:** "LIVE - постоянный поток данных, обновление каждую минуту"

**inputs:**
- **from_source:** Data Refresh Scheduler (триггер каждую минуту) + MT5 Terminal
- **data_type:** JSON (параметры запроса)
- **params:** symbol, timeframe, last_timestamp (для инкрементального обновления)
- **format:** `{"symbol": "GER40", "timeframe": "M1", "last_timestamp": "2025-10-31T09:59:00Z"}`
- **description:** Запрос только НОВЫХ баров/свечей с последнего обновления

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       MT5 CONNECTOR (LIVE MODE)                │
├────────────────────────────────────────────────┤
│  • Инкрементальная загрузка (только новые бары)│
│  • Частота: каждую минуту                      │
│  • Append к InMemoryBuffer                     │
│  • Асинхронное сохранение snapshot на диск     │
│  • НЕ перезагружает всю историю                │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** InMemoryBuffer (подмодуль MT5 Data Cache) + Data Processor
- **data_type:** DataFrame (только новые свечи)
- **params:** symbol, timeframe, new_bars_count, last_close_price
- **format:** 
```
  DataFrame: [time, open, high, low, close, volume] (только новые N свечей)
```
- **description:** Только новые бары для добавления к существующему буферу

**logic_notes:**
- "Использует last_timestamp для запроса только новых данных - критично для производительности"
- "При отсутствии новых данных возвращает пустой DataFrame (не ошибку)"
- "Retry logic: 3 попытки с exponential backoff при сбое подключения к MT5"
- "InMemoryBuffer обновляется немедленно, disk cache - асинхронно (каждые 5 минут или при накоплении 100+ свечей)"

`---`

### Подмодуль 2.2.2 — CSV/Archive Loader

**submodule_name:** "2.2.2 CSV/Archive Loader"

**inputs:**
- **from_source:** ARCHIVE (локальная папка archive/raw/) или USER_REQUEST (загрузка пользовательского CSV)
- **data_type:** CSV файл
- **params:** file_path или (symbol, timeframe, start, end) для поиска в архиве
- **format:** CSV с колонками: time, open, high, low, close, volume (могут быть вариации названий)
- **description:** Импорт исторических данных из CSV файлов для бэктестов

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│        CSV/ARCHIVE LOADER                      │
├────────────────────────────────────────────────┤
│  • Чтение CSV файлов из archive/raw/Parquet    │
│  • Валидация формата (наличие OHLCV колонок)   │
│  • Парсинг различных форматов дат              │
│  • Добавление метаданных (source, instrument)  │
│  • Унификация формата → DataFrame              │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** Data Processor
- **data_type:** DataFrame + metadata JSON
- **params:** symbol, timeframe, row_count, time_range, source
- **format:** 
```
  DataFrame: [time, open, high, low, close, volume]
  Metadata: {"source": "archive|user_upload", "instrument": "GER40", "timeframe": "M15", "rows": 50000}
```
- **description:** Унифицированный DataFrame с историческими данными и метаданными источника

**logic_notes:**
- "Поддержка различных форматов CSV: MetaTrader, TradingView, custom user exports"
- "Автоопределение разделителя (,;tab) и формата даты"
- "Если file_path не указан - автопоиск в archive/raw/ по паттерну {symbol}_{tf}_{start}_{end}.csv"
- "При отсутствии обязательных колонок (OHLCV) - возврат ошибки валидации"

---

### Подмодуль 2.2.3 — Data Processor (Cleaning & Feature Layer)

**submodule_name:** "2.2.3 Data Processor"

**inputs:**
- **from_source:** MT5 Connector (2.2.1) или CSV Loader (2.2.2)
- **data_type:** DataFrame (raw OHLCV)
- **params:** symbol, timeframe
- **format:** `[time, open, high, low, close, volume]` (могут быть NaN, дубликаты, неупорядоченность)
- **description:** Сырые свечные данные, требующие очистки и обогащения

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         DATA PROCESSOR                         │
├────────────────────────────────────────────────┤
│  • Нормализация временных индексов (UTC)       │
│  • Удаление дубликатов и сортировка            │
│  • Обработка NaN (правило: >50% drop, иначе FF)│
│  • Расчёт технических признаков (ATR, ranges)  │
│  • Определение торговых сессий                 │
│  • Добавление session, new_day, pdh, pdl и тд  │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** Market Tools (все детекторы), Session Engine (для уточнения сессий), InMemoryBuffer (для live режима)
- **data_type:** DataFrame (enriched/cleaned)
- **params:** symbol, timeframe, features_added
- **format:** 
```
  [time(UTC tz-aware), open, high, low, close, volume, atr, body_pct, shadow_ratio, 
   session, new_day, pdh, pdl, pwh, pwl, volatility, ...]
```
- **description:** Чистый, обогащённый DataFrame с техническими признаками и метаданными сессий

**logic_notes:**
- "Правило NaN: если более 50% значений в свече отсутствует - drop строку, иначе forward-fill"
- "normalize_time_index: конвертация в UTC, ресемплинг при необходимости, сортировка, дедупликация"
- "Для LIVE режима: использует InMemoryBuffer (быстрый доступ), для BACKTEST: может использовать disk cache"
- "ATR рассчитывается с периодом 14 (configurable), body_pct = abs(close-open)/range"
- "ДОБАВЛЕНО: поле 'data_quality_score' (0-1) для оценки надёжности свечи"

---

### Подмодуль 2.2.4 — Session Engine

**submodule_name:** "2.2.4 Session Engine"

**inputs:**
- **from_source:** Data Processor (enriched DataFrame)
- **data_type:** DataFrame
- **params:** symbol, broker_timezone, session_definitions (Asia/Frankfurt/London/NY boundaries)
- **format:** DataFrame с time (UTC) и OHLCV
- **description:** Обогащённые данные для определения границ торговых сессий

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         SESSION ENGINE                         │
├────────────────────────────────────────────────┤
│  • Определение временных рамок сессий          │
│  • Asia/Frankfurt/London/NY boundaries         │
│  • Daily/Weekly Open, NY Midnight              │
│  • Учёт серверного времени брокера             │
│  • Формирование JSON для каждой сессии         │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Market Tools (Detect_sessions), Context Visualizer, Dash Visualizer
- **data_type:** JSON массив сессий
- **params:** session_name, start, end, high, low, timezone
- **format:**

json

  `[
    {
      "session_name": "Asia",
      "start": "2025-10-31T00:00:00Z",
      "end": "2025-10-31T08:00:00Z",
      "high": 15850.5,
      "low": 15820.3,
      "timezone": "UTC"
    },
    ...
  ]`

- **description:** Структурированные данные о торговых сессиях с ценовыми границами

**logic_notes:**

- "Учитывает DST (daylight saving time) для корректного определения границ сессий"
- "Broker timezone configurable (по умолчанию GMT+2/+3 для большинства европейских брокеров)"
- "NY Midnight = 00:00 NY time (UTC-5/UTC-4 с учётом DST) - важный уровень для ICT методологии"
- "High/Low рассчитываются как абсолютные максимум/минимум в границах сессии"

### Подмодуль 2.2.4.1 — Data Refresh Scheduler

**submodule_name:** "2.2.4.1 Data Refresh Scheduler"

**inputs:**

- **from_source:** Prefect Scheduler (cron trigger) или Manual trigger (для backtest)
- **data_type:** JSON (schedule config)
- **params:** mode (live|backtest), interval (1min for live, manual for backtest), symbols[], timeframes[]
- **format:**

json

  `{
    "mode": "live",
    "interval": "1min",
    "symbols": ["GER40", "EURUSD"],
    "timeframes": ["M1", "M5", "M15"]
  }
````
- **description:** Конфигурация расписания обновления данных

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      DATA REFRESH SCHEDULER                    │
├────────────────────────────────────────────────┤
│  • Мониторинг расписания (каждую минуту/неделю)│
│  • Триггер MT5 Loader при наступлении времени  │
│  • LIVE: каждую минуту                         │
│  • BACKTEST: вручную по запросу                │
│  • Health check MT5 connection                 │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** MT5 Connector (2.2.1) - триггер загрузки
- **data_type:** JSON (trigger event)
- **params:** symbols[], timeframes[], last_update_timestamp, force_reload (bool)
- **format:**

json

  `{
    "trigger": "scheduled|manual",
    "symbols": ["GER40"],
    "timeframes": ["M1"],
    "last_update": "2025-10-31T10:00:00Z",
    "force_reload": false
  }
````
- **description:** Событие запуска загрузки данных

**logic_notes:**
- "LIVE mode: Prefect schedule 'every 1 minute', проверка только на закрытие новой свечи"
- "BACKTEST mode: manual trigger через Streamlit кнопку 'Refresh Data' или перед запуском backtest"
- "Health check: если MT5 не отвечает 3 раза подряд - отправка alert в Telegram"
- "Пропуск обновления если рынок закрыт (weekend) - configurable для каждого символа"

---

### Подмодуль 2.2.5 — MT5 Data Cache

**submodule_name:** "2.2.5.1 InMemoryBuffer (подмодуль Cache)"

**inputs:**
- **from_source:** MT5 Connector (2.2.1 LIVE mode) - новые свечи
- **data_type:** DataFrame (incremental data)
- **params:** symbol, timeframe, new_bars
- **format:** DataFrame с новыми свечами для append
- **description:** Поток новых свечей для добавления в оперативную память

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       INMEMORY BUFFER (CACHE L1)               │
├────────────────────────────────────────────────┤
│  • Ring buffer (collections.deque)             │
│  • Хранит последние N свечей (configurable)    │
│  • Ultra-fast доступ для детекторов            │
│  • Append новых свечей без перезагрузки        │
│  • TTL не требуется (живёт до рестарта)        │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** Data Processor (для live детекторов), OnDiskCache (для периодического сохранения)
- **data_type:** DataFrame (последние N свечей)
- **params:** symbol, timeframe, buffer_size, last_timestamp
- **format:** DataFrame с последними N свечами (например 5000 для M1, 1000 для M15)
- **description:** Буфер последних свечей для быстрого анализа в реальном времени

**logic_notes:**
- "Buffer size configurable: M1=5000 свечей (~3.5 дня), M15=1000 (~10 дней), H1=500 (~20 дней)"
- "Реализация через collections.deque с maxlen - автоматическое удаление старых при переполнении"
- "КРИТИЧНО для производительности: детекторы работают только с этим буфером в live режиме, НЕ обращаются к диску"
- "Thread-safe: использовать threading.Lock при append/read для избежания race conditions"

---

### Подмодуль 2.2.5.2 OnDiskCache (подмодуль Cache)

**submodule_name:** "2.2.5.2 OnDiskCache (подмодуль Cache)"

**inputs:**
- **from_source:** InMemoryBuffer (snapshot для сохранения) или MT5 Connector (для backtest mode)
- **data_type:** DataFrame
- **params:** symbol, timeframe, start, end
- **format:** DataFrame для сохранения в Parquet
- **description:** Данные для долгосрочного хранения на диске

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│        ONDISK CACHE (CACHE L2)                 │
├────────────────────────────────────────────────┤
│  • Persistent storage (Parquet files)          │
│  • Cache key: symbol_tf_start_end.parquet      │
│  • TTL: configurable (по умолчанию 30 дней)    │
│  • Асинхронное сохранение из InMemory          │
│  • Для backtest: прямая загрузка больших данных│
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** ARCHIVE (data/cache/) + возврат в Data Processor при cache hit
- **data_type:** Parquet файл + DataFrame (при чтении)
- **params:** file_path, cache_key, row_count, last_modified
- **format:** 
```
  Path: data/cache/{symbol}_{tf}_{start}_{end}.parquet
  DataFrame при чтении: [time, open, high, low, close, volume]
```
- **description:** Кешированные данные для быстрого доступа при повторных запросах

**logic_notes:**
- "Проверка cache hit ПЕРЕД обращением к MT5 - экономия времени на повторных бэктестах"
- "Асинхронное сохранение (каждые 5 минут или при накоплении 100+ новых свечей в InMemory)"
- "TTL управляется через metadata файл рядом с parquet: {cache_key}_meta.json с timestamp"
- "Purge старых файлов: cron job раз в день удаляет файлы старше TTL"
- "BACKTEST mode: прямая загрузка из OnDiskCache минуя InMemoryBuffer для больших объёмов (год+ данных)"

---

### Подмодуль 2.2.5.3 IncrementalUpdater (подмодуль Cache)

**submodule_name:** "2.2.5.3 IncrementalUpdater (подмодуль Cache)"

**inputs:**
- **from_source:** MT5 Connector (только новые бары), InMemoryBuffer (текущее состояние)
- **data_type:** DataFrame (incremental)
- **params:** symbol, timeframe, last_timestamp
- **format:** Только новые свечи с timestamp > last_timestamp
- **description:** Логика инкрементального обновления кеша

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      INCREMENTAL UPDATER                       │
├────────────────────────────────────────────────┤
│  • Получает новые бары от MT5                  │
│  • Append к InMemoryBuffer                     │
│  • Периодически flush snapshot на OnDiskCache  │
│  • НЕ перезагружает всю историю                │
│  • Использует last_timestamp для sync          │
└────────────────────────────────────────────────┘`
```

**outputs:**
- **destination:** InMemoryBuffer (immediate update), OnDiskCache (async persist)
- **data_type:** DataFrame (updated buffer state)
- **params:** updated_rows_count, last_timestamp, sync_status
- **format:** Обновлённый буфер + подтверждение синхронизации
- **description:** Результат инкрементального обновления

**logic_notes:**
- "Критическая логика для live режима: избегает reload всей истории, работает только с дельтами"
- "Использует last_timestamp из InMemoryBuffer для запроса get_new_from_mt5(last_ts)"
- "Async persist: отдельный thread сохраняет snapshot каждые 5 минут (configurable)"
- "При restart приложения: восстановление из OnDiskCache + догрузка missing bars с MT5"

---

---

## МОДУЛЬ 2.3 — Data Storage & Versioning

### Подмодуль 2.3.1 — Persistent Store

**submodule_name:** "2.3.1 Persistent Store (Database / Object Storage)"

**inputs:**
- **from_source:** Любой модуль проекта (Market Tools, Backtester, Visualizer, GPT Vision и тд)
- **data_type:** Множественный: CSV/Parquet (candles), PNG (screenshots), JSON (results/annotations), pickle (models)
- **params:** file_type, metadata (symbol, timeframe, run_id, rule_version, timestamp)
- **format:** 
```
  Files: candles.parquet, screenshot.png, result.json, model.pkl
  Metadata DB: {file_id, file_path, type, symbol, timeframe, run_id, created_at, hash}
```
- **description:** Любые файлы и данные, требующие долгосрочного хранения с метаданными

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│        PERSISTENT STORE                        │
├────────────────────────────────────────────────┤
│  • Хранение всех исходных файлов               │
│  • Candles (parquet/csv), PNGs, JSONs, models  │
│  • SQLite/Postgres для метаданных              │
│  • Версионирование файлов (hash + timestamp)   │
│  • Организация по структуре папок              │
└────────────────────────────────────────────────┘
```

**outputs:**
- **destination:** ARCHIVE (файловая система D:/ITA/ITA_1.0/exchange/) + Database (metadata)
- **data_type:** Путь к сохранённому файлу + metadata record
- **params:** file_id, file_path, hash, metadata_json
- **format:** 
```
  File path: D:/ITA/ITA_1.0/exchange/archive/{type}/{symbol}_{run_id}_{timestamp}.{ext}
  DB record: {file_id: UUID, path: str, hash: str, metadata: JSON, created_at: datetime}`

- **description:** Подтверждение сохранения с уникальным идентификатором и путём

**logic_notes:**

- "Структура папок: archive/raw/ (исходные свечи), archive/results/ (backtest JSON), to_vision/ (для LLM), annotated/ (от LLM)"
- "Все файлы сопровождаются записью в metadata DB для быстрого поиска и трассируемости"
- "Hash (SHA256) используется для проверки целостности и предотвращения дублирования"
- "Optional: sync с S3/Google Drive через rclone (конфигурируемо, но изначально локально)"
- "ДОБАВЛЕНО: retention policy - автоудаление файлов старше X месяцев (кроме результатов бэктестов)"

### Подмодуль 2.3.2 — Rule & Version Registry

**submodule_name:** "2.3.2 Rule & Version Registry"

**inputs:**

- **from_source:** Setup Manager (при создании/обновлении правил) или USER_REQUEST (ручное редактирование)
- **data_type:** YAML файл + metadata JSON
- **params:** setup_id, version, author, params, active_flag
- **format:**

yaml

  `*# rules/{setup_id}/v{X}.yaml*
  setup_id: Frank_raid_v1
  version: 1.2
  author: "trader_1"
  created: "2025-10-15"
  components: [Detect_Sessions, Detect_FVG, ...]
  rules: {...}
  targets: {tp: 2.0, sl: 1.0}
```
- **description:** Определение торгового сетапа в структурированном формате

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      RULE & VERSION REGISTRY                   │
├────────────────────────────────────────────────┤
│  • Хранение всех версий правил/сетапов         │
│  • YAML файлы + metadata (author, date, params)│
│  • Уникальные IDs: setup_id + version          │
│  • Трассируемость бэктестов к версии правила   │
│  • Active/Inactive flag для управления         │
└────────────────────────────────────────────────┘
```

**outputs:**
- **destination:** ARCHIVE (rules/ папка) + DATABASE (metadata table) + Setup Manager (для использования)
- **data_type:** YAML файл + database record
- **params:** setup_id, version, file_path, active, created_at, metadata
- **format:** 
```
  File: rules/{setup_id}/v{version}.yaml
  DB record: {id, setup_id, version, file_path, author, active: bool, created_at, params_hash}`

- **description:** Сохранённая версия правила с метаданными для трассируемости

**logic_notes:**

- "КАЖДОЕ изменение правила создаёт новую версию (v1.0 → v1.1 → v2.0)"
- "params_hash используется для автодетекта изменений параметров без открытия файла"
- "Active flag: только активные правила используются в live режиме, неактивные - только для backtest review"
- "Связь с бэктестами: каждый backtest ОБЯЗАТЕЛЬНО ссылается на rule_version для воспроизводимости"
- "ДОБАВЛЕНО: поле 'deprecation_reason' для отключенных правил (почему перестало работать)"

### Подмодуль 2.3.3 — Run Snapshot / Provenance

**submodule_name:** "2.3.3 Run Snapshot / Provenance"

**inputs:**

- **from_source:** Prefect Orchestrator (при запуске любого flow: backtest/live/train)
- **data_type:** JSON (контекст запуска)
- **params:** run_id, flow_type, data_range, rule_id, rule_version, git_commit, env_config
- **format:**

json

  `{
    "run_id": "run_2025_10_31_001",
    "flow_type": "backtest_flow",
    "symbol": "GER40",
    "timeframe": "M15",
    "data_range": ["2025-05-01", "2025-10-31"],
    "data_hash": "sha256:abc123...",
    "rule_id": "IB_raid_v1",
    "rule_version": "v1.2",
    "git_commit": "a3f5b2c",
    "env": {"python": "3.11.5", "prefect": "2.19.0", ...}
  }
```
- **description:** Полный контекст запуска для обеспечения воспроизводимости

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│     RUN SNAPSHOT / PROVENANCE                  │
├────────────────────────────────────────────────┤
│  • Snapshot данных (hash, range)               │
│  • Git commit hash кода проекта                │
│  • Версия правила (rule_version)               │
│  • Environment (Python, libs versions)         │
│  • Прикрепление к каждому run для repro        │
└────────────────────────────────────────────────┘
```

**outputs:**
- **destination:** DATABASE (provenance table) + ARCHIVE (snapshot JSON)
- **data_type:** JSON файл + database record
- **params:** run_id, snapshot_json, created_at
- **format:** 
```
  File: archive/provenance/{run_id}_snapshot.json
  DB: {run_id, flow_type, data_hash, rule_version, git_commit, env_json, timestamp}`

- **description:** Полный snapshot для возможности точного воспроизведения результата

**logic_notes:**

- "Критично для научного подхода: любой результат должен быть воспроизводим"
- "Data hash рассчитывается от входных данных (candles CSV) - гарантия одних и тех же данных"
- "Git commit автоматически определяется при запуске (subprocess git rev-parse HEAD)"
- "Environment capture: версии всех критичных библиотек (pandas, numpy, prefect, langchain, openai)"
- "При попытке воспроизвести результат - проверка совпадения всех параметров snapshot"

### Подмодуль 2.3.4 — Data Retention / Purge Policy

**submodule_name:** "2.3.4 Data Retention / Purge Policy"

**inputs:**

- **from_source:** Scheduler (cron daily job) + Configuration (retention rules)
- **data_type:** JSON (retention policy config)
- **params:** file_types[], retention_days, purge_strategy (archive|delete), exceptions[]
- **format:**

json

  `{
    "raw_candles": {"retain_days": 365, "strategy": "archive_to_s3"},
    "annotated_pngs": {"retain_days": 90, "strategy": "delete"},
    "backtest_results": {"retain_days": null, "strategy": "keep_forever"},
    "vector_embeddings": {"retain_days": 180, "strategy": "prune_old"}
  }
```
- **description:** Правила хранения и удаления различных типов данных

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│    DATA RETENTION / PURGE POLICY               │
├────────────────────────────────────────────────┤
│  • Автоудаление старых файлов (по типу/возрасту│
│  • Raw candles: 1 год, annotated PNG: 90 дней  │
│  • Backtest results: хранить всегда            │
│  • Vector DB: pruning старых embeddings        │
│  • Exceptions: важные runs помечаются для keep │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** ARCHIVE (удаление файлов) + DATABASE (обновление status deleted) + Logs (audit trail)
- **data_type:** JSON (purge report)
- **params:** purged_files_count, freed_space_gb, purge_date, affected_file_ids[]
- **format:**

json

  `{
    "purge_date": "2025-10-31",
    "total_files_purged": 1243,
    "freed_space_gb": 15.7,
    "by_type": {"annotated_pngs": 980, "temp_cache": 263},
    "audit_log_path": "logs/purge_2025_10_31.log"
  }`

- **description:** Отчёт об удалённых файлах и освобождённом пространстве

**logic_notes:**

- "Exceptions: файлы с тегом 'important' или связанные с активными правилами НЕ удаляются"
- "Backtest results НИКОГДА не удаляются автоматически - только ручной purge администратором"
- "Soft delete: сначала файлы помечаются deleted в DB, физическое удаление через 7 дней (safety window)"
- "Уведомление в Telegram перед масштабным purge (>10GB) для подтверждения"
- "ДОБАВЛЕНО: backup старых файлов в S3 перед удалением (опционально, configurable)"

---

## МОДУЛЬ 2.4 — Market Tools

### Подмодуль 2.4.1 — Detect_sessions

**submodule_name:** "2.4.1 Detect_sessions"

**inputs:**

- **from_source:** Data Processor (enriched DataFrame) + Session Engine (session boundaries JSON)
- **data_type:** DataFrame + JSON
- **params:** symbol, timeframe, session_names[] (Asia/Frankfurt/London/NY)
- **format:**

  `DataFrame: [time(UTC), open, high, low, close, volume, session, ...]
  Session JSON: [{session_name, start, end, timezone}, ...]
```
- **description:** Обогащённые данные со временными метками для детекции сессий

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         DETECT_SESSIONS                        │
├────────────────────────────────────────────────┤
│  • Детекция торговых сессий (Asia/Frank/Lon/NY)│
│  • Определение High/Low каждой сессии          │
│  • Выявление raid (пробоя границ сессии)       │
│  • Возврат зон в стандартизированном JSON      │
│  • Учёт временных зон и DST                    │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Setup Manager (для rule evaluation) + Persistent Store (сохранение результатов) + Dash Visualizer (для отрисовки)
- **data_type:** JSON массив зон
- **params:** type, session_name, start, end, price_low, price_high, confidence, meta
- **format:**

json

  `[
    {
      "type": "session_zone",
      "session_name": "Asia",
      "start": "2025-10-31T00:00:00Z",
      "end": "2025-10-31T08:00:00Z",
      "price_low": 15820.3,
      "price_high": 15850.5,
      "confidence": 1.0,
      "meta": {"raid_detected": false, "direction": null}
    }
  ]
```
- **description:** Стандартизированный список зон сессий с ценовыми границами

**logic_notes:**
- "Связан с Session Engine (2.2.4) - использует его JSON как базу, дополняет анализом raid/sweep"
- "Raid detection: если цена выходит за boundaries сессии и возвращается - meta.raid_detected = true"
- "Confidence = 1.0 для четких сессий с полными данными, <1.0 если есть пропуски в данных"
- "ДОБАВЛЕНО: поле meta.volume_profile - распределение объёма внутри сессии (high/low/mid)"

---

### Подмодуль 2.4.2 — Detect_Opening_Levels

**submodule_name:** "2.4.2 Detect_Opening_Levels"

**inputs:**
- **from_source:** Data Processor (enriched DataFrame с new_day флагами)
- **data_type:** DataFrame
- **params:** symbol, timeframe, level_types[] (daily_open, weekly_open, ny_midnight)
- **format:** DataFrame с колонками [time, open, new_day, new_week, ...]
- **description:** Данные для определения ключевых открытий (daily/weekly/NY midnight)

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      DETECT_OPENING_LEVELS                     │
├────────────────────────────────────────────────┤
│  • Daily Open (начало торгового дня)           │
│  • Weekly Open (понедельник)                   │
│  • NY Midnight (00:00 NY time)                 │
│  • Определение ценовых уровней открытий        │
│  • Трассировка уровней через время             │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Setup Manager + Dash Visualizer + Persistent Store
- **data_type:** JSON массив уровней
- **params:** type, level_name, timestamp, price, confidence, meta
- **format:**

json

  `[
    {
      "type": "opening_level",
      "level_name": "daily_open",
      "start": "2025-10-31T00:00:00Z",
      "end": null,
      "price_low": 15835.0,
      "price_high": 15835.0,
      "confidence": 1.0,
      "meta": {"day": "2025-10-31", "valid_until": "2025-11-01T00:00:00Z"}
    }
  ]
```
- **description:** Уровни открытий для использования в анализе и визуализации

**logic_notes:**
- "Daily Open = первая свеча дня (определяется по new_day флагу из Data Processor)"
- "Weekly Open = первая свеча понедельника (после выходных)"
- "NY Midnight = 00:00 по NY времени (критичный уровень в ICT методологии)"
- "end = null означает что уровень действителен до следующего открытия (next daily/weekly open)"
- "ДОБАВЛЕНО: детекция gap между close предыдущего дня и open текущего (meta.gap_pips)"

---

### Подмодуль 2.4.3 — Detect_PDX_PWX

**submodule_name:** "2.4.3 Detect_PDX_PWX"

**inputs:**
- **from_source:** Data Processor (enriched DataFrame с pdh, pdl, pwh, pwl колонками)
- **data_type:** DataFrame
- **params:** symbol, timeframe, lookback_days (по умолчанию 2 для PD, 1 неделя для PW)
- **format:** DataFrame с [time, high, low, pdh, pdl, pwh, pwl, ...]
- **description:** Данные для определения границ Previous Day/Week High/Low

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         DETECT_PDX_PWX                         │
├────────────────────────────────────────────────┤
│  • Previous Day High/Low (PDH, PDL)            │
│  • Previous Week High/Low (PWH, PWL)           │
│  • Lookback: 2 предыдущих дня для PD           │
│  • 1 предыдущая неделя для PW                  │
│  • Определение зон для liquidity analysis      │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Setup Manager + Dash Visualizer + Detect_Liquidity (для комбинированного анализа)
- **data_type:** JSON массив зон
- **params:** type, level_name, start, end, price_low, price_high, confidence, meta
- **format:**

json

  `[
    {
      "type": "pdx_pwx_zone",
      "level_name": "PDH",
      "start": "2025-10-30T00:00:00Z",
      "end": "2025-10-31T00:00:00Z",
      "price_low": 15860.0,
      "price_high": 15860.0,
      "confidence": 1.0,
      "meta": {"day": "2025-10-30", "touches": 0, "swept": false}
    }
  ]
```
- **description:** Уровни PDH/PDL/PWH/PWL для liquidity hunting анализа

**logic_notes:**
- "PDH/PDL рассчитываются от 2 предыдущих дней (configurable) - более надёжный уровень"
- "PWH/PWL = абсолютные high/low предыдущей недели (понедельник-пятница)"
- "meta.touches отслеживает количество касаний уровня (>3 touches = сильный уровень)"
- "meta.swept = true если цена пробила уровень и вернулась (liquidity sweep)"
- "ДОБАВЛЕНО: интеграция с Detect_Liquidity для определения confluence зон (PDH + liquidity pool)"

---

### Подмодуль 2.4.4 — BOS_CHOCH_SHIFT Detector

**submodule_name:** "2.4.4 BOS_CHOCH_SHIFT Detector"

**inputs:**
- **from_source:** Data Processor (enriched DataFrame)
- **data_type:** DataFrame
- **params:** symbol, timeframe, swing_detection_params (min_swing_size, lookback_period)
- **format:** DataFrame [time, high, low, close, atr, ...]
- **description:** Данные для детекции структурных сдвигов рынка (BOS/CHoCH)

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      BOS_CHOCH_SHIFT DETECTOR                  │
├────────────────────────────────────────────────┤
│  • Break of Structure (BOS) - пробой структуры │
│  • Change of Character (CHoCH) - смена характера│
│  • Определение ключевых свингов (highs/lows)   │
│  • Детекция смены тренда                       │
│  • Confidence на основе силы пробоя            │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Setup Manager + Dash Visualizer + Persistent Store
- **data_type:** JSON массив событий
- **params:** type, event_name, start, end, price_low, price_high, confidence, meta
- **format:**

json

  `[
    {
      "type": "structure_shift",
      "event_name": "BOS_bullish",
      "start": "2025-10-31T09:15:00Z",
      "end": "2025-10-31T09:30:00Z",
      "price_low": 15825.0,
      "price_high": 15855.0,
      "confidence": 0.85,
      "meta": {
        "swing_high": 15845.0,
        "swing_low": 15820.0,
        "break_strength": 1.2,
        "trend_before": "bearish",
        "trend_after": "bullish"
      }
    }
  ]
```
- **description:** События пробоя структуры с метаданными о смене тренда

**logic_notes:**
- "BOS = пробой предыдущего swing high/low в направлении тренда (confirmation)"
- "CHoCH = пробой counter-trend swing (возможная смена тренда, требует подтверждения)"
- "min_swing_size = минимальный размер свинга в ATR (обычно 1.5*ATR) для фильтрации шума"
- "confidence зависит от break_strength: >2*ATR = high conf (0.9), 1-2*ATR = medium (0.7)"
- "ДОБАВЛЕНО: поле meta.liquidity_sweep - был ли sweep ликвидности перед BOS (усиливает сигнал)"

---

### Подмодуль 2.4.5 — Detect_Liquidity

**submodule_name:** "2.4.5 Detect_Liquidity"

**inputs:**
- **from_source:** Data Processor + Detect_PDX_PWX (для confluence) + BOS_CHOCH Detector (для структурного контекста)
- **data_type:** DataFrame + JSON (PDX/PWX zones, structure shifts)
- **params:** symbol, timeframe, liquidity_types[] (htf_fractals, equal_highs_lows, stop_clusters)
- **format:** 
```
  DataFrame: [time, high, low, close, volume, ...]
  Zones JSON: PDX/PWX уровни для confluence
```
- **description:** Данные для определения зон накопления ликвидности

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         DETECT_LIQUIDITY                       │
├────────────────────────────────────────────────┤
│  • HTF фракталы (Higher Timeframe swing points)│
│  • Equal Highs/Lows (потенциальные stop pools) │
│  • Stop loss clusters (зоны накопления стопов) │
│  • Confluence с PDH/PDL/PWH/PWL                │
│  • Приоритизация по вероятности sweep          │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Setup Manager + Dash Visualizer + ML Scoring Module (feature для вероятности)
- **data_type:** JSON массив зон ликвидности
- **params:** type, liquidity_type, start, end, price_low, price_high, confidence, meta
- **format:**

json

  `[
    {
      "type": "liquidity_zone",
      "liquidity_type": "equal_highs",
      "start": "2025-10-31T08:00:00Z",
      "end": "2025-10-31T12:00:00Z",
      "price_low": 15858.0,
      "price_high": 15862.0,
      "confidence": 0.78,
      "meta": {
        "touches_count": 3,
        "confluence": ["PDH", "htf_fractal"],
        "priority": "high",
        "expected_sweep_direction": "upward"
      }
    }
  ]
```
- **description:** Приоритизированные зоны ликвидности для hunting стратегий

**logic_notes:**
- "Equal highs/lows = 3+ свечи с high/low в диапазоне <0.2% друг от друга (tight cluster)"
- "HTF fractals = swing points на старших таймфреймах (H4/D1) - сильные уровни"
- "Confluence увеличивает confidence: PDH+equal_highs = +0.2 к базовому confidence"
- "Priority (high/medium/low) определяется комбинацией: touches_count + confluence + proximity to structure"
- "ДОБАВЛЕНО: поле meta.swept_history - был ли этот уровень swept ранее (снижает приоритет)"

---

### Подмодуль 2.4.6 — Detect_FVG

**submodule_name:** "2.4.6 Detect_FVG (Fair Value Gap)"

**inputs:**
- **from_source:** Data Processor (enriched DataFrame)
- **data_type:** DataFrame
- **params:** symbol, timeframe, min_gap_pct (минимальный размер гэпа, обычно 0.2%), direction (bullish/bearish/both)
- **format:** DataFrame [time, open, high, low, close, body_pct, ...]
- **description:** Данные для детекции Fair Value Gap (imbalance)

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         DETECT_FVG                             │
├────────────────────────────────────────────────┤
│  • Детекция Fair Value Gap (3-свечной паттерн) │
│  • Bullish FVG: gap между свечой 1 high и 3 low│
│  • Bearish FVG: gap между свечой 1 low и 3 high│
│  • Фильтр по min_gap_pct (удаление шума)       │
│  • Трекинг заполнения FVG (mitigation)         │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Setup Manager + Dash Visualizer + Persistent Store
- **data_type:** JSON массив FVG зон
- **params:** type, fvg_direction, start, end, price_low, price_high, confidence, meta
- **format:**

json

  `[
    {
      "type": "fvg",
      "fvg_direction": "bullish",
      "start": "2025-10-31T10:00:00Z",
      "end": "2025-10-31T10:15:00Z",
      "price_low": 15830.0,
      "price_high": 15840.0,
      "confidence": 0.82,
      "meta": {
        "gap_size_pct": 0.35,
        "mitigation_status": "open",
        "candle_indices": [145, 146, 147],
        "created_by_impulse": true
      }
    }
  ]
```
- **description:** FVG зоны для использования в mean reversion или continuation стратегиях

**logic_notes:**
- "FVG = 3-свечной паттерн: gap между high свечи 1 и low свечи 3 (bullish) или наоборот (bearish)"
- "min_gap_pct фильтрует шум: если gap < 0.2% от цены - не считается FVG"
- "mitigation_status: 'open' (не заполнен), 'partial' (частично), 'filled' (полностью закрыт ценой)"
- "created_by_impulse = true если gap создан импульсной свечой (body > 70% range) - сильнее сигнал"
- "ДОБАВЛЕНО: поле meta.confluence_with_structure - совпадение FVG с BOS/CHoCH (повышает confidence)"

---`

### Подмодуль 2.4.8 — Schema Validator (Market Tools)

**submodule_name:** "2.4.8 Schema Validator (Market Tools)"

**inputs:**
- **from_source:** Все детекторы Market Tools (Detect_sessions, FVG, OB, BOS и тд)
- **data_type:** JSON (выходы детекторов)
- **params:** schema_type (signal_schema / zone_schema / event_schema)
- **format:** Любой JSON output от детектора
- **description:** Валидация структуры и полей выходных данных детекторов

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      SCHEMA VALIDATOR (Market Tools)           │
├────────────────────────────────────────────────┤
│  • Валидация JSON schema (pydantic models)     │
│  • Проверка обязательных полей                 │
│  • Типы: signal_schema, zone_schema, event     │
│  • Логирование ошибок валидации                │
│  • Блокировка невалидных данных до Setup Mgr   │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Setup Manager (только валидные данные) + Logs (ошибки валидации)
- **data_type:** JSON (validated) или Error object
- **params:** is_valid (bool), validated_data (JSON), errors[] (если есть)
- **format:**

json

  `{
    "is_valid": true,
    "validated_data": {...детектор output...},
    "schema_used": "zone_schema_v1",
    "timestamp": "2025-10-31T10:00:00Z"
  }
  OR
  {
    "is_valid": false,
    "errors": ["Missing field: confidence", "Invalid type: price_low must be float"],
    "raw_data": {...},
    "detector": "Detect_FVG"
  }`

- **description:** Валидированные данные или список ошибок

**logic_notes:**

- "Обязательные поля для всех детекторов: type, start, end, price_low, price_high, confidence, meta"
- "Pydantic models для каждого schema типа: ZoneSchema, SignalSchema, EventSchema"
- "При ошибке валидации: логирование + блокировка прохода в Setup Manager + alert в Telegram"
- "Confidence должен быть 0.0-1.0, цены должны быть float > 0, timestamps в ISO format"
- "ДОБАВЛЕНО: versioning schemas (zone_schema_v1, v2...) для обратной совместимости при изменении структуры"

---

## МОДУЛЬ 2.5 — Setup Manager / Rule Logic

### Общая схема модуля

## МОДУЛЬ: Setup Manager / Rule Logic (Центральный дирижёр)

**module_name:** Setup Manager / Rule Logic

**inputs:**

- source: START (User Trigger) / Scheduler
- data_type: JSON
- description: `{setup_id, symbol, timeframe, start, end, mode, run_id, options}`

**ascii_diagram:**

```
┌───────────────────────────────┐
│         SETUP MANAGER / RULE LOGIC     │
├────────────────────────────────┤
│  • Загружает YAML rule для setup_id     │
│  • Парсит required Market Tools         │
│  • Формирует pipeline spec              │
│  • Вызывает Data Ingest → Processor     │
│  • Вызывает Market Tools Dispatcher     │
│  • Оценивает правило → signals          │
│  • Отправляет в Backtester/LiveHandler  │
└─────────────────────────────┘

```

**outputs:**

- destination: Data Ingest (or read from cache), Market Tools Dispatcher, Backtester Manager, Live Handler
- data_type: JSON (pipeline spec, signals, trace logs)
- description: `pipeline_spec {tools: [...], params}`, `processed_context`, or `signals list`

**logic_notes:**

- **Ключ**: Setup Manager управляет очередностью. Он **сначала** проверяет кэш/ingest registry: если данные за период уже доступны — он может пропустить Data Ingest и сразу передать `processed_path` в Data Processor или Market Tools.
- Если нет кэша — он вызывает Data Ingest и ждёт завершения Data Processor прежде чем вызывать Market Tools. Это важный порядок: Market Tools ожидают уже нормализованные/обогащённые данные.
- Setup Manager формирует список `required_tools` на основе YAML (например `required_tools: [Detect_Sessions, Detect_FVG, Detect_Liquidity]`) и передаёт их Market Tools Dispatcher.
- Setup Manager логирует все шаги (tool calls, durations, run_id) и сохраняет в Persistent Store.

### Подмодуль 2.5.1 — Parser YAML → Executable Rule

**submodule_name:** "2.5.1 Parser YAML → Executable Rule"

**inputs:**

- **from_source:** Rule & Version Registry (2.3.2) - YAML файлы правил
- **data_type:** YAML файл
- **params:** setup_id, version
- **format:**

yaml

  `setup_id: Frank_raid_v1
  version: 1.2
  components: [Detect_Sessions(Frankfurt), Detect_FVG(TF_m1, min_gap_pct:0.2)]
  rules:
    - condition: "Frankfurt raid AND reverse AND inversion fvg m1"
  targets: {tp: 2.0, sl: 1.0}
````
- **description:** YAML файл с определением сетапа

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│   PARSER YAML → EXECUTABLE RULE                │
├────────────────────────────────────────────────┤
│  • Парсинг YAML в Python dict                  │
│  • Извлечение components (какие детекторы)     │
│  • Парсинг rules (условия для сигнала)         │
│  • Компиляция в executable Python функцию      │
│  • Validation: все components доступны         │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Rule Executor (2.5.2)
- **data_type:** Python dict + executable function object
- **params:** setup_id, version, components_list[], rule_function, targets
- **format:**

python

  `{
    "setup_id": "Frank_raid_v1",
    "version": "1.2",
    "components": ["Detect_Sessions", "Detect_FVG"],
    "rule_function": <compiled_function>,
    "targets": {"tp": 2.0, "sl": 1.0},
    "meta": {"author": "trader_1", "created": "2025-10-15"}
  }`

- **description:** Исполняемое представление правила для Rule Executor

**logic_notes:**

- "Парсинг components: извлекает список детекторов и их параметры (например Detect_FVG с min_gap_pct:0.2)"
- "Rule compilation: превращает текстовое условие ('Frankfurt raid AND fvg') в Python логику (AST transformation)"
- "Validation: проверка что все указанные детекторы существуют в Market Tools модуле"
- "Если парсинг fails - возврат ошибки БЕЗ запуска backtest/live flow"
- "ДОБАВЛЕНО: caching скомпилированных правил (rule_id + version) для избежания повторного парсинга"

### Подмодуль 2.5.2 — Rule Executor

**submodule_name:** "2.5.2 Rule Executor"

**inputs:**

- **from_source:** Parser (2.5.1) - executable rule + Market Tools (детекторы outputs JSON) + Data Processor (DataFrame)
- **data_type:** Python dict (rule) + JSON array (tools outputs) + DataFrame
- **params:** setup_id, version, tools_json[], candles_df
- **format:**

python

  `rule = {rule_function, targets, ...}
  tools_json = [{type:"fvg", ...}, {type:"session_zone", ...}, ...]
  candles_df = DataFrame[time, ohlcv, ...]
```
- **description:** Данные для проверки условий правила и генерации сигналов

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         RULE EXECUTOR                          │
├────────────────────────────────────────────────┤
│  • Применение rule_function к tools_json       │
│  • Проверка условий (AND/OR логика)            │
│  • Расчёт entry, SL, TP на основе targets      │
│  • Генерация signals[] с confidence            │
│  • Добавление meta (rule_id, version, detectors│
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Backtester (если backtest mode) ИЛИ ML Scoring Module + Decision Logic (если live mode)
- **data_type:** JSON массив сигналов
- **params:** signal_id, symbol, tf, entry_price, sl_price, tp_price, confidence, rule_id, rule_version, meta
- **format:**

json

  `[
    {
      "signal_id": "sig_20251031_001",
      "symbol": "GER40",
      "tf": "M15",
      "entry_price": 15840.0,
      "sl_price": 15800.0,
      "tp_price": 15900.0,
      "confidence": 0.78,
      "rule_id": "Frank_raid_v1",
      "rule_version": "v1.2",
      "meta": {
        "detectors": ["Detect_Sessions", "Detect_FVG"],
        "candles_analyzed": 3,
        "entry_timestamp": "2025-10-31T10:15:00Z"
      }
    }
  ]`

- **description:** Сигналы для торговли с полной трассируемостью к правилу

**logic_notes:**

- "Rule function получает tools_json и возвращает bool (условие выполнено?) + entry/sl/tp координаты"
- "Entry/SL/TP расчёт: обычно на основе зон от детекторов (например entry = OB low, SL = OB high + buffer)"
- "Confidence наследуется от детекторов: берётся минимальный confidence среди использованных зон"
- "Meta всегда включает rule_id + version для трассировки результата к конкретной версии правила"
- "ДОБАВЛЕНО: поле meta.context_snapshot - краткий JSON с рыночным контекстом (trend, volatility) для анализа"

### Подмодуль 2.5.3 — Versioning (Setup Manager)

**submodule_name:** "2.5.3 Versioning (Setup Manager)"

**inputs:**

- **from_source:** USER_REQUEST (изменение правила через Streamlit UI или ручное редактирование YAML) или Learning Module (автоматические предложения)
- **data_type:** YAML (modified rule) + JSON (change description)
- **params:** setup_id, old_version, new_version, changes_description, author
- **format:**

json

  `{
    "setup_id": "Frank_raid_v1",
    "old_version": "v1.1",
    "new_version": "v1.2",
    "changes": [
      {"field": "components.Detect_FVG.min_gap_pct", "old": 0.2, "new": 0.3},
      {"field": "targets.tp", "old": 1.8, "new": 2.0}
    ],
    "author": "trader_1",
    "reason": "Increased TP based on backtest analysis"
  }
````
- **description:** Запрос на создание новой версии правила с описанием изменений

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      VERSIONING (Setup Manager)                │
├────────────────────────────────────────────────┤
│  • Создание новой версии при изменении правила │
│  • Автоинкремент версии (v1.1 → v1.2)          │
│  • Сохранение changelog (что изменилось)       │
│  • Архивация старой версии (не удаляется)      │
│  • Связывание с Rule & Version Registry        │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** Rule & Version Registry (2.3.2) - сохранение новой версии + DATABASE (версионная запись)
- **data_type:** YAML файл (новая версия) + JSON (metadata record)
- **params:** setup_id, version, file_path, created_at, changes_log
- **format:** 
````
  File: rules/Frank_raid_v1/v1.2.yaml
  DB record: {
    id, setup_id, version: "v1.2", 
    file_path, author, created_at,
    changes_log: [{field, old, new}, ...],
    parent_version: "v1.1"
  }`

- **description:** Новая версия правила с полной историей изменений

**logic_notes:**

- "КАЖДОЕ изменение создаёт новую версию - даже изменение одного параметра"
- "Semantic versioning: major.minor.patch (например v2.0.0 для радикальных изменений стратегии)"
- "Старые версии НИКОГДА не удаляются - архивируются для воспроизводимости прошлых бэктестов"
- "Changelog автоматически генерируется через diff между old и new YAML"
- "ДОБАВЛЕНО: поле 'reason' - обязательное текстовое описание ПОЧЕМУ было изменено (для future reference)"

### Подмодуль 2.5.4 — Rule Profiler

**submodule_name:** "2.5.4 Rule Profiler"

**inputs:**

- **from_source:** Backtester (результаты бэктестов) + Rule & Version Registry (параметры правил)
- **data_type:** JSON (backtest results) + YAML (rule params)
- **params:** setup_id, version, backtest_results[], param_variations[]
- **format:**

json

  `{
    "setup_id": "Frank_raid_v1",
    "versions_tested": ["v1.0", "v1.1", "v1.2"],
    "backtest_results": [
      {"version": "v1.0", "winrate": 0.58, "avg_rr": 1.6, "params": {...}},
      {"version": "v1.2", "winrate": 0.61, "avg_rr": 1.8, "params": {...}}
    ]
  }
````
- **description:** Результаты множественных бэктестов для анализа влияния параметров

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         RULE PROFILER                          │
├────────────────────────────────────────────────┤
│  • Сбор статистики по всем версиям правила     │
│  • Анализ winrate vs params (какой параметр ↑) │
│  • Корреляция между параметрами и метриками    │
│  • Генерация рекомендаций по оптимизации       │
│  • Визуализация param sensitivity              │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Learning Module (для автоматических предложений) + Streamlit Dashboard (визуализация) + DATABASE (сохранение статистики)
- **data_type:** JSON (profiling report)
- **params:** setup_id, best_version, param_sensitivity, recommendations[]
- **format:**

json

  `{
    "setup_id": "Frank_raid_v1",
    "best_version": "v1.2",
    "best_metrics": {"winrate": 0.61, "avg_rr": 1.8, "expectancy": 0.58},
    "param_sensitivity": {
      "min_gap_pct": {"impact": "high", "correlation_with_winrate": 0.72},
      "tp": {"impact": "medium", "correlation_with_avg_rr": 0.45}
    },
    "recommendations": [
      "Increase min_gap_pct from 0.2 to 0.3 (projected winrate +3%)",
      "Keep tp at 2.0 (optimal risk/reward balance)"
    ]
  }
````
- **description:** Аналитический отчёт о влиянии параметров на эффективность правила

**logic_notes:**
- "Собирает данные ВСЕХ бэктестов для конкретного setup_id (все версии)"
- "Param sensitivity: вычисляет корреляцию между изменением параметра и изменением winrate/RR"
- "Recommendations основаны на statistical significance (>50 trades для надёжности)"
- "Визуализация в Streamlit: heatmap param vs winrate, линейные графики версий"
- "ДОБАВЛЕНО: детекция overfitting - если новая версия +10% winrate но только на одном периоде - warning"

---

``

---

## МОДУЛЬ 2.6 — Backtester Manager

### Подмодуль 2.6.1 — Backtester Core

**УСЛОВИЕ: BACKTEST режим**

**submodule_name:** "2.6.1 Backtester Core"

**condition:** "BACKTEST - симуляция торговли на исторических данных"

**inputs:**
- **from_source:** Rule Executor (signals[]) + Data Processor (historical candles DataFrame) + Config (execution rules: slippage, spread)
- **data_type:** JSON (signals) + DataFrame (candles) + JSON (config)
- **params:** signals[], candles_df, slippage_pips, spread_pips, execution_logic
- **format:** 
```
  signals: [{signal_id, entry_price, sl_price, tp_price, entry_timestamp, ...}, ...]
  candles_df: [time, ohlcv, ...]
  config: {"slippage": 1.0, "spread": 2.0, "execution": "next_candle_open"}
```
- **description:** Сигналы и исторические данные для симуляции торговли

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       BACKTESTER CORE (BACKTEST)               │
├────────────────────────────────────────────────┤
│  • Симуляция входов на next candle после signal│
│  • Трекинг SL/TP достижения через историю      │
│  • Расчёт P/L для каждой сделки                │
│  • Вычисление метрик: winrate, RR, drawdown    │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Backtest Runner (aggregated results) + Persistent Store (trades CSV + backtest JSON) + Visualizer (для создания PNG samples)
- **data_type:** JSON (backtest summary) + CSV (individual trades)
- **params:** run_id, trades_count, winrate, avg_rr, max_drawdown, total_pnl, trades_list[]
- **format:**

json

  `{
    "run_id": "bt_2025_10_31_001",
    "setup_id": "Frank_raid_v1",
    "rule_version": "v1.2",
    "symbol": "GER40",
    "timeframe": "M15",
    "period": ["2025-05-01", "2025-10-31"],
    "trades_count": 234,
    "wins": 143,
    "losses": 91,
    "winrate": 0.61,
    "avg_rr": 1.8,
    "max_drawdown": 0.12,
    "total_pnl": +1520.50,
    "trades_csv": "archive/results/bt_2025_10_31_001_trades.csv",
    "sample_pngs": ["exchange/to_vision/sample_001.png", ...]
  }`

CSV trades format:

csv

  `trade_id,signal_id,entry_time,entry_price,exit_time,exit_price,exit_reason,pnl,rr
  1,sig_001,2025-05-02 10:15,15840.0,2025-05-02 12:30,15870.0,TP,+30.0,2.0`

- **description:** Полный отчёт о бэктесте с метриками и список всех сделок

**logic_notes:**

- "Execution logic: entry на open следующей свечи после сигнала (реалистично, не на close той же свечи)"
- "Slippage применяется к entry: actual_entry = signal_entry + slippage (configurable, по умолчанию 1 pip)"
- "SL/TP трекинг: сделка закрывается когда high/low достигает SL или TP (внутри свечи)"
- "Drawdown рассчитывается как максимальное снижение от пика equity кривой"
- "Sample PNGs: для каждого N-го сигнала (например каждый 10-й) создаётся PNG через Visualizer для проверки"
- "ДОБАВЛЕНО: поле trades_by_month - разбивка результатов по месяцам для детекции сезонности"

### Подмодуль 2.6.2 — Backtest Runner / Batch Processor

**submodule_name:** "2.6.2 Backtest Runner / Batch Processor"

**inputs:**

- **from_source:** USER_REQUEST (batch config через Streamlit) или Prefect Scheduler (автоматические batch runs)
- **data_type:** JSON (batch configuration)
- **params:** symbols[], timeframes[], periods[], rule_ids[], parallel (bool)
- **format:**

json

  `{
    "batch_id": "batch_2025_10_31",
    "symbols": ["GER40", "EURUSD", "GBPUSD"],
    "timeframes": ["M15", "H1"],
    "periods": [
      {"start": "2025-01-01", "end": "2025-06-30"},
      {"start": "2025-07-01", "end": "2025-10-31"}
    ],
    "rule_ids": ["Frank_raid_v1", "Asia_fvg_break_v2"],
    "parallel": true,
    "max_workers": 4
  }
````
- **description:** Конфигурация для массового прогона бэктестов (множество комбинаций)

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│   BACKTEST RUNNER / BATCH PROCESSOR            │
├────────────────────────────────────────────────┤
│  • Управление очередью бэктестов               │
│  • Параллелизация (multiprocessing/Prefect)    │
│  • Batch: symbols × periods × rules            │
│  • Логирование прогресса (N of M completed)    │
│  • Aggregation результатов в сводный отчёт     │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** DATABASE (batch results aggregation) + Persistent Store (individual backtest JSONs) + Notion (batch summary report) + Streamlit Dashboard
- **data_type:** JSON (batch summary) + multiple backtest JSONs
- **params:** batch_id, total_runs, completed, failed, aggregated_metrics
- **format:**

json

  `{
    "batch_id": "batch_2025_10_31",
    "total_runs": 12,
    "completed": 11,
    "failed": 1,
    "failed_runs": ["GER40_M15_Frank_raid_v1_period2"],
    "execution_time_minutes": 45,
    "aggregated_metrics": {
      "avg_winrate": 0.59,
      "avg_rr": 1.75,
      "best_run": {
        "run_id": "bt_...",
        "symbol": "EURUSD",
        "rule": "Asia_fvg_break_v2",
        "winrate": 0.67
      }
    },
    "individual_results": [
      {"run_id": "bt_001", "symbol": "GER40", "winrate": 0.61, ...},
      ...
    ]
  }`

- **description:** Сводный отчёт batch прогона с указанием успешных и проваленных runs

**logic_notes:**

- "Parallelization через Prefect mapped tasks или Python multiprocessing (configurable max_workers)"
- "Queue management: runs добавляются в очередь, executor забирает по мере доступности workers"
- "Failed runs логируются с причиной (например: недостаточно данных, ошибка детектора) - НЕ останавливают batch"
- "Progress tracking: обновление в реальном времени через Prefect UI или Streamlit progress bar"
- "ДОБАВЛЕНО: поле estimated_time_remaining - прогноз времени завершения batch на основе скорости выполнения"

### Подмодуль 2.6.3 — Backtest Validator (QA)

**submodule_name:** "2.6.3 Backtest Validator (QA)"

**inputs:**

- **from_source:** Backtester Core (backtest results + trades CSV) + Visualizer (sample PNGs)
- **data_type:** JSON (backtest summary) + CSV (trades) + PNG files
- **params:** run_id, trades_csv_path, sample_pngs_paths[], validation_criteria
- **format:**

json

  `{
    "run_id": "bt_2025_10_31_001",
    "trades_csv": "path/to/trades.csv",
    "sample_pngs": ["sample_001.png", "sample_015.png", ...],
    "validation_criteria": {
      "min_trades": 20,
      "visual_check_sample_size": 10,
      "expected_metrics_range": {"winrate": [0.5, 0.7], "avg_rr": [1.5, 2.5]}
    }
  }
```
- **description:** Данные бэктеста для контроля качества и валидации

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      BACKTEST VALIDATOR (QA)                   │
├────────────────────────────────────────────────┤
│  • Случайная выборка N сделок для визуального  │
│  • Проверка recall/precision детекторов        │
│  • Acceptance tests: metrics в ожидаемых рамках│
│  • Визуальное подтверждение entry/sl/tp точек  │
│  • Генерация QA отчёта (pass/fail с причинами) │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** DATABASE (QA report) + Notion (для ручного review) + USER_INTERFACE (Streamlit для visual check)
- **data_type:** JSON (QA report) + annotated PNGs (с отметками для проверки)
- **params:** run_id, qa_status (pass/fail/review), issues_found[], visual_check_results
- **format:**

json

  `{
    "run_id": "bt_2025_10_31_001",
    "qa_status": "review_required",
    "checks_performed": {
      "trades_count": {"result": "pass", "value": 234, "min_required": 20},
      "metrics_range": {"result": "pass", "winrate": 0.61, "expected": [0.5, 0.7]},
      "visual_check": {"result": "pending", "samples_to_review": 10}
    },
    "issues_found": [
      "Sample trade #5: entry price не соответствует OB zone (manual review needed)"
    ],
    "visual_check_url": "streamlit://qa_review/bt_2025_10_31_001"
  }`

- **description:** QA отчёт с результатами автоматических проверок и ссылкой на ручной review

**logic_notes:**

- "Автоматические checks: min_trades, metrics в expected range, no duplicate trades, valid timestamps"
- "Visual check: случайная выборка 10-20 сделок, трейдер вручную подтверждает корректность через Streamlit UI"
- "Recall/Precision для детекторов: сравнение найденных зон с ground truth (если есть размеченные данные)"
- "QA status: 'pass' (все checks ok), 'fail' (критичные ошибки), 'review_required' (нужна ручная проверка)"
- "ДОБАВЛЕНО: автоматическая детекция аномалий (например: все сделки закрылись по SL - подозрительно)"

### Подмодуль 2.6.4 — Manual Backtester

**submodule_name:** "2.6.4 Manual Backtester"

**inputs:**

- **from_source:** USER_REQUEST (через Streamlit/Plotly интерфейс) + Data Processor (historical candles)
- **data_type:** JSON (user config) + DataFrame (candles)
- **params:** symbol, timeframe, start_date, playback_speed, session_jump_enabled
- **format:**

json

  `{
    "symbol": "GER40",
    "timeframe": "M15",
    "period": ["2025-05-01", "2025-10-31"],
    "playback_speed": "1x|2x|manual",
    "session_jumps": ["Asia", "London", "NY"],
    "screenshot_enabled": true
  }
```
- **description:** Конфигурация для ручного прохода по истории свеча за свечой

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       MANUAL BACKTESTER                        │
├────────────────────────────────────────────────┤
│  • Plotly интерфейс в стиле TradingView        │
│  • Прокрутка свечей по очереди (candle by one) │
│  • Быстрые переходы по сессиям/дням            │
│  • Возможность скриншота текущего графика      │
│  • Ручная разметка entry/sl/tp точек           │
│  • Автозаполнение журнала в Notion (на будущее)│
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** ARCHIVE (screenshots PNG) + Notion Journal (ручные записи сделок) + DATABASE (manual trades log)
- **data_type:** PNG (screenshots) + JSON (manual trade records)
- **params:** trade_id, entry_time, entry_price, exit_time, exit_price, screenshot_path, notes
- **format:**

json

  `{
    "manual_trade_id": "mt_2025_10_31_001",
    "symbol": "GER40",
    "timeframe": "M15",
    "entry_time": "2025-05-15T10:15:00Z",
    "entry_price": 15840.0,
    "exit_time": "2025-05-15T12:30:00Z",
    "exit_price": 15870.0,
    "exit_reason": "TP_hit",
    "pnl": +30.0,
    "screenshot_path": "archive/manual_backtest/mt_001.png",
    "trader_notes": "Отличный Frank raid setup, чистый OB retest"
  }
````
- **description:** Записи ручных сделок с скриншотами и заметками трейдера

**logic_notes:**
- "Plotly Dash интерфейс: candlestick chart с кнопками 'Next Candle', 'Jump to Session', 'Screenshot'"
- "Playback modes: manual (по клику), 1x (реальная скорость), 2x-10x (ускоренная)"
- "Session jumps: кнопки для мгновенного перехода к началу Asia/London/NY сессий"
- "Screenshot: сохраняет текущий видимый график как PNG с timestamp в имени файла"
- "Ручная разметка: клик по графику для установки entry/sl/tp - координаты сохраняются"
- "БУДУЩЕЕ: автозаполнение Notion - при закрытии сделки автоматически создаётся запись в журнале с PNG"

---

---

## МОДУЛЬ 2.7 — Visualisation Engine

### Подмодуль 2.7.1 — Dash Visualizer (Plotly-based)

**submodule_name:** "2.7.1 Dash Visualizer (Plotly-based)"

**inputs:**
- **from_source:** Data Processor (candles DataFrame) + Market Tools (zones JSON: FVG, OB, sessions, liquidity) + Rule Executor (signals JSON с entry/sl/tp)
- **data_type:** DataFrame (candles) + JSON (zones) + JSON (signals)
- **params:** symbol, timeframe, zones[], signals[], style_config
- **format:** 
```
  candles_df: [time, ohlcv, ...]
  zones: [{type, start, end, price_low, price_high, ...}, ...]
  signals: [{entry_price, sl_price, tp_price, entry_timestamp, ...}, ...]
  style_config: {"theme": "tv_dark", "colors": {...}}
```
- **description:** Данные для визуализации графика со всеми зонами и сигналами

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│     DASH VISUALIZER (Plotly-based)             │
├────────────────────────────────────────────────┤
│  • Plotly candlestick chart                    │
│  • Overlay зон (FVG, OB, sessions как boxes)   │
│  • Entry/SL/TP маркеры на графике              │
│  • TradingView-подобный стиль                  │
│  • Генерация PNG и интерактивного HTML         │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** Visual Formatter (для постобработки) + ARCHIVE (to_vision/ папка) + GPT Vision Adapter (для анализа)
- **data_type:** PNG файл + HTML (интерактивный график)
- **params:** file_path, width, height, zones_count, signals_count
- **format:** 
````
  PNG: D:/ITA/ITA_1.0/exchange/to_vision/{symbol}_{tf}_{timestamp}.png
  HTML: D:/ITA/ITA_1.0/exchange/interactive/{symbol}_{tf}_{timestamp}.html
  Metadata JSON: {
    "file_path": "...",
    "symbol": "GER40",
    "timeframe": "M15",
    "time_range": ["2025-10-31T08:00", "2025-10-31T12:00"],
    "zones_rendered": 5,
    "signals_rendered": 2
  }`

- **description:** Визуализированный график в PNG и HTML форматах с метаданными

**logic_notes:**

- "Zones рендерятся как прозрачные прямоугольники с цветом по типу: FVG=blue, OB=orange, sessions=grey"
- "Entry/SL/TP как markers: entry=green circle, sl=red line, tp=green line"
- "TradingView стиль: тёмный фон, зелёные/красные свечи, чистая сетка"
- "PNG размер: стандартно 1920x1080 для GPT Vision (configurable)"
- "HTML для интерактивного просмотра: с zoom, pan, hover tooltips"
- "ДОБАВЛЕНО: watermark с run_id в углу PNG для трассируемости"

### Подмодуль 2.7.2 — TV-like Styling Module

**submodule_name:** "2.7.2 TV-like Styling Module"

**inputs:**

- **from_source:** Configuration файл (style/theme.yaml) или USER_REQUEST (кастомная тема через UI)
- **data_type:** YAML файл
- **params:** theme_name, colors, fonts, transparency_levels, candlestick_style
- **format:**

yaml

  `theme_name: "tv_dark"
  background_color: "#131722"
  grid_color: "#363c4e"
  candle_colors:
    up: "#26a69a"
    down: "#ef5350"
  zone_colors:
    fvg: "rgba(33, 150, 243, 0.3)"
    ob: "rgba(255, 152, 0, 0.3)"
    session: "rgba(158, 158, 158, 0.2)"
  fonts:
    main: "Arial, sans-serif"
    size: 12
````
- **description:** Параметры стиля для унификации визуализации под TradingView

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      TV-LIKE STYLING MODULE                    │
├────────────────────────────────────────────────┤
│  • Централизованное хранение параметров стиля  │
│  • TradingView тема (dark/light)               │
│  • Цвета свечей, фон, сетка, зоны              │
│  • Шрифты, размеры, прозрачности               │
│  • Применение темы ко всем визуализациям       │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Dash Visualizer (применение стиля при рендере) + Visual Formatter (для постобработки)
- **data_type:** Python dict (parsed YAML)
- **params:** theme_name, style_config_dict
- **format:**

python

  `{
    "theme_name": "tv_dark",
    "background_color": "#131722",
    "candle_colors": {"up": "#26a69a", "down": "#ef5350"},
    "zone_colors": {...},
    "fonts": {...}
  }`

- **description:** Готовый конфиг стиля для применения к Plotly графикам

**logic_notes:**

- "Единая тема для ВСЕХ визуализаций - гарантирует консистентность для обучения GPT Vision"
- "TradingView dark - эталон стиля (большинство трейдеров привыкли к этому виду)"
- "Transparency levels: зоны полупрозрачные (0.2-0.3 alpha) чтобы не закрывать свечи"
- "Theme switching: возможность переключения dark/light через UI (но default всегда dark)"
- "ДОБАВЛЕНО: preset themes - несколько готовых тем (tv_dark, tv_light, custom_1) для выбора"

### Подмодуль 2.7.3 — Visual Formatter

**submodule_name:** "2.7.3 Visual Formatter"

**inputs:**

- **from_source:** Dash Visualizer (raw PNG файлы)
- **data_type:** PNG файл
- **params:** file_path, target_size, normalization_rules, crop_margins, watermark_config
- **format:**

json

  `{
    "input_png": "to_vision/raw_ger40_m15.png",
    "target_size": [1920, 1080],
    "normalization": {
      "color_space": "RGB",
      "contrast": "auto_adjust"
    },
    "crop": {"top": 50, "bottom": 50, "left": 0, "right": 0},
    "watermark": {"text": "run_id", "position": "bottom_right"}
  }
````
- **description:** Сырой PNG для постобработки и стандартизации

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         VISUAL FORMATTER                       │
├────────────────────────────────────────────────┤
│  • Нормализация размера PNG (resize to target) │
│  • Нормализация цветов (RGB, contrast)         │
│  • Crop лишних элементов (margins)             │
│  • Добавление watermark (run_id, timestamp)    │
│  • Добавление labels (symbol, timeframe)       │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** ARCHIVE (to_vision/ финальные PNG) + GPT Vision Adapter (для анализа)
- **data_type:** PNG файл (formatted)
- **params:** output_path, processing_applied[], file_size_kb
- **format:** 
````
  Output PNG: to_vision/formatted_ger40_m15_20251031.png
  Metadata: {
    "original_file": "raw_ger40_m15.png",
    "size": [1920, 1080],
    "processing": ["resize", "crop", "watermark", "contrast_adjust"],
    "file_size_kb": 245,
    "ready_for_llm": true
  }`

- **description:** Стандартизированный PNG готовый для подачи в GPT Vision

**logic_notes:**

- "Resize: все PNG приводятся к 1920x1080 (оптимально для GPT-4V, не слишком большой размер)"
- "Crop: удаление пустых margins сверху/снизу если есть (для фокуса на графике)"
- "Contrast auto_adjust: усиление контраста если изображение слишком тёмное/светлое"
- "Watermark: run_id в правом нижнем углу малозаметным шрифтом для трассировки"
- "Labels: добавление текста в верхний угол: 'GER40 M15' для идентификации без метаданных"
- "ДОБАВЛЕНО: детекция и удаление артефактов (например glitches от Plotly rendering)"

### Подмодуль 2.7.4 — Annotation Service

**submodule_name:** "2.7.4 Annotation Service"

**inputs:**

- **from_source:** GPT Vision Adapter (annotation commands JSON) + Dash Visualizer (original PNG)
- **data_type:** JSON (commands) + PNG (base image)
- **params:** png_path, annotation_commands[]
- **format:**

json

  `{
    "input_png": "to_vision/formatted_ger40_m15.png",
    "annotation_commands": [
      {
        "op": "line",
        "x1": "2025-10-31T10:00", "y1": 15840.0,
        "x2": "2025-10-31T11:00", "y2": 15840.0,
        "color": "red",
        "width": 2,
        "label": "Liquidity level"
      },
      {
        "op": "arrow",
        "x1": "2025-10-31T10:30", "y1": 15850.0,
        "x2": "2025-10-31T10:30", "y2": 15830.0,
        "color": "green",
        "label": "Entry direction"
      },
      {
        "op": "text",
        "x": "2025-10-31T10:15", "y": 15860.0,
        "text": "OB zone confirmed",
        "color": "yellow"
      }
    ]
  }
```
- **description:** Команды от LLM для отрисовки анализа на графике

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       ANNOTATION SERVICE                       │
├────────────────────────────────────────────────┤
│  • Приём команд аннотаций от GPT Vision        │
│  • Рендеринг: line, arrow, rectangle, text     │
│  • Overlay на исходный PNG                     │
│  • Координаты: time+price → pixel conversion   │
│  • Сохранение annotated PNG                    │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** ARCHIVE (annotated/ папка) + Notion Uploader (для журнала) + Backtester Core (для включения в отчёт)
- **data_type:** PNG (annotated) + JSON (metadata)
- **params:** output_png_path, annotations_applied[], annotation_json_path
- **format:** 
```
  PNG: exchange/annotated/ger40_m15_20251031_annotated.png
  `Metadata JSON: {
    "original_png": "to_vision/formatted_ger40_m15.png",
    "annotated_png": "annotated/ger40_m15_annotated.png",
    "annotations_count": 3,
    "annotations": [{op, x1, y1, ...}, ...],
    "created_by": "GPT_Vision_Adapter",
    "timestamp": "2025-10-31T10:20:00Z"
  }
````
- **description:** Аннотированный PNG с анализом LLM визуализированным на графике

**logic_notes:**
- "Coordinate conversion: time+price (из annotation commands) → x,y pixels с учётом масштаба графика"
- "Supported ops: line, arrow, rectangle, circle, text - основные примитивы для разметки"
- "Colors: используются контрастные цвета (red, green, yellow) для видимости поверх графика"
- "Overlay: аннотации рисуются ПОВЕРХ исходного PNG без изменения оригинала"
- "Validation: проверка что coordinates в пределах графика (не за границами time/price range)"
- "ДОБАВЛЕНО: opacity control для аннотаций - полупрозрачные элементы не закрывают свечи"

---

---

## МОДУЛЬ 2.8 — GPT Integration & Vision Flow

### Подмодуль 2.8.1 — GPT Prompt Manager

**submodule_name:** "2.8.1 GPT Prompt Manager"

**inputs:**
- **from_source:** Configuration (prompts/ папка с шаблонами) или USER_REQUEST (кастомные промпты)
- **data_type:** Text файлы (prompts templates) + JSON (variables)
- **params:** prompt_type (signal_analysis, backtest_interpretation, image_annotation), variables{}
- **format:** 
```
  Template file: prompts/signal_analysis_v1.txt
  Content:
  "Analyze the trading chart for {symbol} on {timeframe}.
  Detected zones: {zones_summary}.
  Signal: entry={entry}, sl={sl}, tp={tp}.
  Provide: 1) confirmation/rejection, 2) risk factors, 3) annotation commands."
  
  `Variables JSON: {
    "symbol": "GER40",
    "timeframe": "M15",
    "zones_summary": "FVG at 15835, OB at 15830, PDH at 15860",
    "entry": 15840, "sl": 15800, "tp": 15900
  }
````
- **description:** Шаблоны промптов и переменные для подстановки

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       GPT PROMPT MANAGER                       │
├────────────────────────────────────────────────┤
│  • Централизованное хранилище промптов         │
│  • Шаблоны с переменными {var}                 │
│  • Версионирование промптов (v1, v2...)        │
│  • Генерация финального промпта с подстановкой │
│  • Поддержка multimodal (text + image)         │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Vision Adapter (финальный промпт для LLM) + DATABASE (prompt usage log)
- **data_type:** String (final prompt) + JSON (metadata)
- **params:** prompt_id, prompt_version, final_text, variables_used
- **format:**

json

  `{
    "prompt_id": "signal_analysis",
    "version": "v1.2",
    "template": "prompts/signal_analysis_v1.txt",
    "final_prompt": "Analyze the trading chart for GER40 on M15...",
    "variables": {"symbol": "GER40", ...},
    "character_count": 487,
    "timestamp": "2025-10-31T10:15:00Z"
  }`

- **description:** Готовый промпт с подставленными переменными для отправки в LLM

**logic_notes:**

- "Template engine: простая подстановка {variable} через Python string.format() или Jinja2"
- "Версионирование: каждый промпт имеет версию (v1.0, v1.1...) для A/B тестирования"
- "Prompt types: signal_analysis, backtest_interpretation, annotation_generation, theory_query"
- "Usage logging: каждый вызов логируется для анализа эффективности промптов"
- "ДОБАВЛЕНО: поле 'expected_output_schema' - описание какой формат ответа ожидается от LLM"

### Подмодуль 2.8.2 — Vision Adapter

**submodule_name:** "2.8.2 Vision Adapter"

**inputs:**

- **from_source:** Prompt Manager (final prompt) + Visual Formatter (formatted PNG) + Market Tools (zones JSON для контекста)
- **data_type:** String (prompt) + PNG (image) + JSON (tools data)
- **params:** prompt, image_path, tools_summary_json, model (gpt-4-vision/gpt-4o)
- **format:**

`json`

  `{
    "prompt": "Analyze the trading chart for GER40...",
    "image": "to_vision/formatted_ger40_m15.png",
    "tools_summary": {
      "fvg": [{price_low: 15835, price_high: 15840, ...}],
      "ob": [{price_low: 15830, ...}],
      "sessions": [...]
    },
    "model": "gpt-4-vision-preview",
    "max_tokens": 1000
  }
````
- **description:** Multimodal входные данные для GPT Vision анализа

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         VISION ADAPTER                         │
├────────────────────────────────────────────────┤
│  • Multimodal prompt: image + text + JSON data │
│  • Base64 encoding PNG для OpenAI API          │
│  • Вызов GPT-4V через LangChain/OpenAI SDK     │
│  • Парсинг ответа: text + annotation_commands  │
│  • Возврат analysis + confidence + annotations │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Decision Reconciler (для финального вердикта) + Annotation Service (для визуализации) + Persistent Store (для хранения)
- **data_type:** JSON (LLM response parsed)
- **params:** analysis_text, annotation_commands[], confidence_score, proposed_tweaks
- **format:**

`json`

  `{
    "run_id": "run_2025_10_31_001",
    "signal_id": "sig_001",
    "llm_model": "gpt-4-vision-preview",
    "analysis_text": "Setup confirmed. Frankfurt session high swept, clean OB retest at 15830. FVG aligns with entry. Risk: low liquidity period ahead.",
    "confidence_score": 0.82,
    "recommendation": "entry_approved",
    "risk_factors": ["Low liquidity 12:00-13:00 GMT", "News event at 14:00"],
    "annotation_commands": [
      {"op": "line", "x1": ..., "label": "Liquidity sweep"},
      {"op": "arrow", "x1": ..., "label": "Entry direction"}
    ],
    "proposed_rule_tweak": null,
    "tokens_used": 876,
    "response_time_sec": 3.2
  }`

- **description:** Структурированный анализ от LLM с рекомендациями и командами аннотаций

**logic_notes:**

- "Image encoding: PNG → base64 для OpenAI API (или URL если hosted)"
- "Tools summary включается в prompt как контекст: 'Python detected FVG at 15835, OB at 15830...'"
- "LLM должен возвращать JSON с полями: analysis_text, confidence, recommendation, annotation_commands"
- "Parsing response: regex или JSON mode (OpenAI function calling) для извлечения structured data"
- "Rate limiting: max 10 requests/min (configurable), exponential backoff при 429 errors"
- "ДОБАВЛЕНО: retry logic с 3 попытками при API errors, fallback на simplified prompt если timeout"

### Подмодуль 2.8.3 — LLM Chains & Agents (LangChain)

**submodule_name:** "2.8.3 LLM Chains & Agents"

**inputs:**

- **from_source:** Vision Adapter (для vision chain) или User Query (для theory search) + ChromaDB (для retrieval)
- **data_type:** String (query) + PNG (optional) + JSON (context from retrieval)
- **params:** chain_type (vision|summarizer|classifier|retrieval), input_data, tools[]
- **format:**

json

  `{
    "chain_type": "retrieval_qa",
    "query": "Что такое Order Block в SMC методологии?",
    "retrieval_source": "chroma_theory_docs",
    "tools": ["chroma.query", "summarizer"],
    "max_results": 5
  }
````
- **description:** Конфигурация LangChain chain для различных задач

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      LLM CHAINS & AGENTS (LangChain)           │
├────────────────────────────────────────────────┤
│  • Vision chain: image → analyzer → output     │
│  • Summarizer chain: long text → concise       │
│  • Classifier chain: signal → category/quality │
│  • Retrieval QA: query → Chroma → answer       │
│  • Agent: tool-using (notion_upload, chroma.q) │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** зависит от chain type: Vision Adapter, User Interface, Notion, Database
- **data_type:** JSON или String (chain output)
- **params:** chain_type, output, intermediate_steps[], tokens_used
- **format:**

`json`

  `{
    "chain_type": "retrieval_qa",
    "query": "Что такое Order Block?",
    "answer": "Order Block - это последняя противоположная свеча перед сильным импульсом. В SMC методологии используется как зона интереса для входа...",
    "sources": [
      {"doc_id": "theory_smc_v1", "chunk": 3, "score": 0.89},
      {"doc_id": "ict_concepts", "chunk": 12, "score": 0.76}
    ],
    "intermediate_steps": [
      "Retrieved 5 documents from Chroma",
      "Summarized top 2 most relevant",
      "Generated answer based on context"
    ],
    "tokens_used": 645
  }`

- **description:** Результат выполнения LangChain chain с трассировкой шагов

**logic_notes:**

- "Vision chain: используется в Vision Adapter для image→text→structured_output pipeline"
- "Retrieval QA: для ответов на вопросы пользователя с приоритетом на theory_docs из Chroma"
- "Classifier chain: определяет качество сигнала (A/B/C grade) на основе features"
- "Agent mode: LangChain agent с tools=[chroma.query, notion_upload, web_search] для сложных задач"
- "ДОБАВЛЕНО: chain versioning - каждая chain имеет версию для A/B тестирования различных конфигураций"

### Подмодуль 2.8.4 — Prompt Version Registry

**submodule_name:** "2.8.4 Prompt Version Registry"

**inputs:**

- **from_source:** Prompt Manager (при создании/обновлении промпта)
- **data_type:** Text (prompt template) + JSON (metadata)
- **params:** prompt_id, version, template_text, variables[], created_by
- **format:**

json

  `{
    "prompt_id": "signal_analysis",
    "version": "v1.2",
    "template_file": "prompts/signal_analysis_v1_2.txt",
    "template_text": "Analyze the trading chart...",
    "variables": ["symbol", "timeframe", "zones_summary", "entry", "sl", "tp"],
    "created_by": "user_admin",
    "created_at": "2025-10-15T14:00:00Z",
    "hash": "sha256:abc123...",
    "parent_version": "v1.1",
    "changes": "Added risk_factors section to output"
  }
````
- **description:** Новая версия промпта с метаданными и историей изменений

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      PROMPT VERSION REGISTRY                   │
├────────────────────────────────────────────────┤
│  • Хранение всех версий промптов               │
│  • Hash для идентификации изменений            │
│  • Связь parent_version → child_version        │
│  • Usage tracking (сколько раз использовался)  │
│  • Performance metrics по версиям              │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** DATABASE (prompt versions table) + ARCHIVE (prompts/ папка)
- **data_type:** Database record + Text file
- **params:** prompt_id, version, file_path, hash, usage_count, avg_performance
- **format:** 
````
  DB record: {
    id, prompt_id, version, file_path, hash,
    created_at, created_by, parent_version, changes,
    usage_count: 0, avg_response_time: null, avg_quality_score: null
  }
  File: prompts/signal_analysis_v1_2.txt`

- **description:** Версионированный промпт с трассируемостью и метриками использования

**logic_notes:**

- "Hash рассчитывается от template_text для детекта изменений (если hash совпадает - та же версия)"
- "Parent version: v1.2 ссылается на v1.1 - можно восстановить историю эволюции промпта"
- "Usage tracking: инкрементируется каждый раз при использовании промпта"
- "Performance metrics: avg_quality_score обновляется на основе feedback (✅/❌ от трейдера)"
- "ДОБАВЛЕНО: A/B testing support - возможность сравнения двух версий промпта side-by-side"

### Подмодуль 2.8.5 — Prompt Testing Harness

**submodule_name:** "2.8.5 Prompt Testing Harness"

**inputs:**

- **from_source:** Prompt Version Registry (промпты для тестирования) + Test Dataset (контрольные данные)
- **data_type:** List of prompts + JSON (test cases)
- **params:** prompts_to_test[], test_dataset[], expected_outputs[]
- **format:**

json

  `{
    "test_id": "prompt_test_001",
    "prompts": ["signal_analysis_v1.1", "signal_analysis_v1.2"],
    "test_dataset": [
      {
        "case_id": "test_case_1",
        "symbol": "GER40",
        "image": "test_data/ger40_frank_raid.png",
        "zones": {...},
        "expected_output": {
          "recommendation": "approve",
          "confidence": ">0.7",
          "annotation_commands_count": ">2"
        }
      },
      ...
    ]
  }
````
- **description:** Набор промптов и тестовых кейсов для сравнительного тестирования

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      PROMPT TESTING HARNESS                    │
├────────────────────────────────────────────────┤
│  • Unit tests для промптов на control dataset  │
│  • Сравнение output разных версий промпта      │
│  • Метрики: accuracy, precision, response_time │
│  • Automated regression testing при изменениях │
│  • Визуализация результатов (pass/fail report) │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** DATABASE (test results) + Streamlit Dashboard (визуализация) + Logs
- **data_type:** JSON (test report)
- **params:** test_id, prompts_tested, pass_rate, metrics_by_prompt
- **format:**

json

  `{
    "test_id": "prompt_test_001",
    "test_date": "2025-10-31",
    "prompts_tested": ["v1.1", "v1.2"],
    "test_cases_count": 20,
    "results": {
      "v1.1": {
        "pass_rate": 0.75,
        "avg_confidence": 0.72,
        "avg_response_time": 3.5,
        "failed_cases": ["test_case_5", "test_case_12"]
      },
      "v1.2": {
        "pass_rate": 0.85,
        "avg_confidence": 0.78,
        "avg_response_time": 3.2,
        "failed_cases": ["test_case_12"]
      }
    },
    "winner": "v1.2",
    "recommendation": "Deploy v1.2 as default"
  }`

- **description:** Сравнительный отчёт эффективности промптов

**logic_notes:**

- "Control dataset: 20-50 размеченных кейсов с known good/bad signals для consistent testing"
- "Pass criteria: output должен совпадать с expected (например confidence >0.7, recommendation=approve)"
- "Automated testing: запускается при каждом изменении промпта (CI/CD style)"
- "Regression detection: если новая версия промпта хуже предыдущей - alert"
- "ДОБАВЛЕНО: cost tracking - расчёт стоимости каждого промпта (tokens used × price)"

### Подмодуль 2.8.6 — API Adapter (Rate-limit / Retry / Backoff)

**submodule_name:** "2.8.6 API Adapter"

**inputs:**

- **from_source:** Vision Adapter или LLM Chains (API запросы к OpenAI/LLM)
- **data_type:** JSON (API request)
- **params:** endpoint, payload, headers, retry_config
- **format:**

json

  `{
    "endpoint": "https://api.openai.com/v1/chat/completions",
    "method": "POST",
    "payload": {...},
    "headers": {"Authorization": "Bearer sk-..."},
    "retry_config": {
      "max_retries": 3,
      "backoff_factor": 2,
      "retry_on": [429, 500, 502, 503]
    }
  }
````
- **description:** API запрос с конфигурацией retry логики

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      API ADAPTER (Rate-limit/Retry/Backoff)    │
├────────────────────────────────────────────────┤
│  • Обработка rate limits (429 errors)          │
│  • Exponential backoff при ошибках API         │
│  • Retry logic (max 3 attempts)                │
│  • Timeout handling (30 sec default)           │
│  • Circuit breaker pattern при длительных сбоях│
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Вызывающий модуль (Vision Adapter/Chains) + Logs (error tracking)
- **data_type:** JSON (API response) или Error object
- **params:** success (bool), response_data, attempts_made, error_details
- **format:**

json

  `{
    "success": true,
    "response": {...LLM output...},
    "attempts_made": 1,
    "response_time_sec": 3.2,
    "tokens_used": 876,
    "cost_usd": 0.0263
  }
  OR (при ошибке):
  {
    "success": false,
    "error_type": "RateLimitError",
    "error_message": "Rate limit exceeded (429)",
    "attempts_made": 3,
    "retry_after_sec": 60,
    "circuit_breaker_triggered": false
  }`

- **description:** Успешный ответ API или детали ошибки с retry информацией

**logic_notes:**

- "Rate limit handling: при 429 ошибке - exponential backoff (1s, 2s, 4s, 8s...)"
- "Retryable errors: 429 (rate limit), 500/502/503 (server errors), timeout"
- "Non-retryable: 400 (bad request), 401 (auth), 403 (forbidden) - немедленный fail"
- "Circuit breaker: если 10 подряд requests failed - остановка на 5 минут (configurable)"
- "Timeout: default 30 sec для API calls, configurable per endpoint"
- "ДОБАВЛЕНО: request queuing - при rate limit добавление запроса в очередь вместо immediate fail"

### Подмодуль 2.8.7 — Decision Reconciler

**submodule_name:** "2.8.7 Decision Reconciler"

**inputs:**

- **from_source:** Rule Executor (Python-based signal) + Vision Adapter (LLM analysis) + ML Scoring Module (probability score)
- **data_type:** JSON (signal from Python) + JSON (LLM analysis) + float (ML score)
- **params:** python_signal, llm_analysis, ml_probability, reconciliation_rules
- **format:**

json

  `{
    "python_signal": {
      "signal_id": "sig_001",
      "entry": 15840, "sl": 15800, "tp": 15900,
      "confidence": 0.75,
      "detectors_used": ["Detect_FVG", "Detect_OB"]
    },
    "llm_analysis": {
      "recommendation": "entry_approved",
      "confidence": 0.82,
      "risk_factors": [...]
    },
    "ml_probability": 0.68,
    "reconciliation_rules": {
      "min_agreement": 0.7,
      "require_llm_approval": true
    }
  }
````
- **description:** Три источника оценки сигнала для агрегации финального решения

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       DECISION RECONCILER                      │
├────────────────────────────────────────────────┤
│  • Агрегация: Python signal + LLM + ML score   │
│  • Проверка согласованности (agreement check)  │
│  • Расчёт финального confidence (weighted avg) │
│  • Вердикт: approve/reject/review_required     │
│  • Логирование разногласий для анализа         │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Live Handler (если live mode) или Backtester (если backtest) + DATABASE (decision log)
- **data_type:** JSON (final decision)
- **params:** decision, final_confidence, reasons[], disagreements[]
- **format:**

json

  `{
    "signal_id": "sig_001",
    "decision": "approve",
    "final_confidence": 0.75,
    "confidence_breakdown": {
      "python_detector": 0.75,
      "llm_analysis": 0.82,
      "ml_model": 0.68,
      "weighted_avg": 0.75
    },
    "reasons": [
      "All three sources agree on entry direction",
      "LLM confirmed setup with high confidence",
      "ML probability above threshold (>0.6)"
    ],
    "disagreements": [],
    "timestamp": "2025-10-31T10:20:00Z"
  }`

- **description:** Финальное решение с обоснованием и уровнем уверенности

**logic_notes:**

- "Agreement check: если Python и LLM не согласны (противоположные recommendation) → decision='review_required'"
- "Weighted average: Python confidence 40%, LLM 40%, ML 20% (configurable weights)"
- "Threshold: final_confidence > 0.7 для approve, <0.5 для reject, между = review_required"
- "Disagreements логируются для последующего анализа (почему источники расходятся)"
- "ДОБАВЛЕНО: поле 'dominant_source' - какой источник имел решающий вес в финальном решении"

### Подмодуль 2.8.8 — Safety / Sanity Checks

**submodule_name:** "2.8.8 Safety / Sanity Checks"

**inputs:**

- **from_source:** Vision Adapter (LLM output JSON) перед использованием
- **data_type:** JSON (LLM response)
- **params:** response_json, expected_schema, sanity_rules
- **format:**

json

  `{
    "response": {
      "analysis_text": "...",
      "confidence": 0.82,
      "annotation_commands": [...]
    },
    "expected_schema": {
      "required_fields": ["analysis_text", "confidence", "annotation_commands"],
      "types": {"confidence": "float", "annotation_commands": "array"}
    },
    "sanity_rules": {
      "confidence_range": [0.0, 1.0],
      "max_annotation_commands": 10,
      "forbidden_ops": ["delete", "execute"]
    }
  }
````
- **description:** LLM output для валидации перед применением

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      SAFETY / SANITY CHECKS                    │
├────────────────────────────────────────────────┤
│  • Валидация JSON schema LLM output            │
│  • Проверка annotation_commands безопасности   │
│  • Sanity checks: confidence в [0,1], coords   │
│  • Forbidden operations filter                 │
│  • Блокировка dangerous commands               │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Annotation Service (validated commands) ИЛИ Error Handler (если validation failed)
- **data_type:** JSON (validated) или Error object
- **params:** is_valid (bool), validated_data, errors[], warnings[]
- **format:**

json

  `{
    "is_valid": true,
    "validated_data": {...},
    "errors": [],
    "warnings": ["Confidence close to upper limit (0.99), verify manually"],
    "timestamp": "2025-10-31T10:20:00Z"
  }
  OR:
  {
    "is_valid": false,
    "errors": [
      "Missing required field: annotation_commands",
      "Invalid confidence value: 1.5 (must be 0.0-1.0)",
      "Forbidden op detected: 'execute' in annotation_commands"
    ],
    "raw_response": {...}
  }`

- **description:** Результат валидации с детализацией ошибок

**logic_notes:**

- "Schema validation через pydantic models - строгая проверка типов и required fields"
- "Annotation commands safety: проверка что операции только draw-related (line, arrow, text), НЕ execute/delete/modify"
- "Sanity checks: confidence в [0, 1], coordinates в пределах графика, max 10 annotation commands"
- "Warnings vs Errors: warnings не блокируют использование, errors - блокируют"
- "ДОБАВЛЕНО: injection protection - детекция попыток code injection в annotation text/labels"

### Подмодуль 2.8.9 — LLM Call Logger

**submodule_name:** "2.8.9 LLM Call Logger"

**inputs:**

- **from_source:** Vision Adapter, LLM Chains (каждый вызов LLM)
- **data_type:** JSON (call metadata)
- **params:** call_id, model, prompt_id, tokens_used, cost, response_time, success
- **format:**

json

  `{
    "call_id": "llm_call_2025_10_31_001",
    "timestamp": "2025-10-31T10:15:30Z",
    "model": "gpt-4-vision-preview",
    "prompt_id": "signal_analysis_v1.2",
    "prompt_hash": "sha256:abc...",
    "input_tokens": 450,
    "output_tokens": 426,
    "total_tokens": 876,
    "cost_usd": 0.0263,
    "response_time_sec": 3.2,
    "success": true,
    "error": null,
    "run_id": "run_2025_10_31_001"
  }
````
- **description:** Метаданные каждого вызова LLM для анализа стоимости и качества

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       LLM CALL LOGGER                          │
├────────────────────────────────────────────────┤
│  • Логирование каждого LLM API вызова          │
│  • Трекинг tokens used и cost (USD)            │
│  • Response time monitoring                    │
│  • Связь с prompt_id и run_id (трассировка)    │
│  • Агрегация статистики (daily cost, usage)    │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** DATABASE (llm_calls table) + Monitoring Dashboard + Cost Analytics
- **data_type:** Database record per call + aggregated metrics JSON
- **params:** call_id, timestamp, model, tokens, cost, связь с run_id/prompt_id
- **format:** 
````
  DB record per call: {call_id, timestamp, model, prompt_id, tokens, cost, response_time, success, run_id}
  
  Aggregated daily: {
    "date": "2025-10-31",
    "total_calls": 234,
    "total_tokens": 205340,
    "total_cost_usd": 6.16,
    "avg_response_time": 3.1,
    "success_rate": 0.97,
    "by_model": {
      "gpt-4-vision": {"calls": 120, "cost": 4.50},
      "gpt-4": {"calls": 114, "cost": 1.66}
    }
  }`

- **description:** Детальный лог вызовов + агрегированная статистика по периодам

**logic_notes:**

- "Cost calculation: tokens × pricing (например gpt-4-vision: $0.03/1K tokens input, $0.06/1K output)"
- "Связь с run_id: возможность посчитать стоимость конкретного backtest run"
- "Связь с prompt_id: анализ какие промпты самые дорогие/медленные"
- "Daily limits: alert если daily_cost > threshold (например $50/day)"
- "ДОБАВЛЕНО: quality metrics - связь с feedback (✅/❌) для анализа cost vs quality"

---

## МОДУЛЬ 2.9 — Learning Module / Training & Memory Subsystem

### Подмодуль 2.9.1 — Labeling & Annotation Manager

**submodule_name:** "2.9.1 Labeling & Annotation Manager"

**inputs:**

- **from_source:** USER_REQUEST (через Streamlit UI для маркировки) + Backtester (сделки для labeling) + Vision Adapter (LLM предложения)
- **data_type:** PNG (trades screenshots) + JSON (trade metadata + LLM suggestions)
- **params:** trade_id, screenshot_path, llm_suggestion, user_feedback_ui

**format:**

json

`{
  "trade_id": "trade_001",
  "screenshot": "archive/results/trade_001.png",
  "trade_data": {
    "entry": 15840, "sl": 15800, "tp": 15900,
    "result": "win", "pnl": +60
  },
  "llm_suggestion": {
    "quality": "A",
    "confidence": 0.82,
    "comment": "Clean setup, all criteria met"
  },
  "user_feedback_ui": {
    "buttons": ["✅ Approve", "❌ Reject", "⚠️ Review", "✏️ Add Comment"]
  }
}
````
- **description:** Сделка с LLM предложением для быстрой маркировки трейдером

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│   LABELING & ANNOTATION MANAGER                │
├────────────────────────────────────────────────┤
│  • Streamlit UI для быстрой маркировки         │
│  • Просмотр PNG + LLM suggestions              │
│  • Кнопки: ✅/❌/⚠️ + текстовый комментарий    │
│  • Сохранение labels в labels/ + Chroma meta   │
│  • Bulk labeling (массовая маркировка)         │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** ARCHIVE (labels/ папка) + ChromaDB (metadata update) + DATABASE (labels table) + ML Training Pipeline
- **data_type:** JSON (label record)
- **params:** trade_id, label, user_feedback, comment, timestamp, labeler_id
- **format:**

json

`{
  "trade_id": "trade_001",
  "screenshot": "archive/results/trade_001.png",
  "label": "approved",
  "quality_grade": "A",
  "user_comment": "Perfect Frank raid setup, exactly as expected",
  "llm_agreed": true,
  "labeler_id": "trader_1",
  "timestamp": "2025-10-31T15:30:00Z",
  "chroma_vector_id": "vec_001"
}`

- **description:** Сохранённая метка с комментарием для обучения

**logic_notes:**

- "Streamlit UI: grid view с PNG preview, LLM suggestion справа, кнопки снизу"
- "Quick labeling: keyboard shortcuts (Y/N/R) для быстрой маркировки без мыши"
- "Bulk mode: возможность отметить 10-20 похожих сделок одним действием"
- "Labels сохраняются как JSON файлы в labels/{trade_id}_label.json + запись в DB"
- "Chroma metadata update: добавление user_label и quality_grade к embedding записи"
- "ДОБАВЛЕНО: disagreement tracking - если user_label != llm_suggestion, пометить для review"

### Подмодуль 2.9.2 — Vector DB / Semantic Memory (Chroma)

**submodule_name:** "2.9.2 Vector DB / Semantic Memory (ChromaDB)"

**inputs:**

- **from_source:** Multiple sources: Theory Docs (PDF/text), Trade Cases (PNG + JSON), Prompts History, Backtest Results
- **data_type:** Множественный: Text, PNG (embeddings), JSON (metadata)
- **params:** collection_name, document/image, metadata, embedding_model
- **format:**

`json`

`{
  "collection": "theory_docs",
  "document": {
    "type": "text",
    "content": "Order Block definition: последняя противоположная свеча...",
    "source_file": "theory/smc_concepts.pdf",
    "page": 15
  },
  "metadata": {
    "doc_id": "smc_concepts_p15",
    "topic": "order_block",
    "author": "ICT",
    "date_added": "2025-10-15"
  },
  "embedding_model": "openai/text-embedding-ada-002"
}
```
- **description:** Документы/изображения для векторизации и хранения

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│   VECTOR DB / SEMANTIC MEMORY (ChromaDB)       │
├────────────────────────────────────────────────┤
│  • Collections: theory_docs, trade_cases,      │
│    prompts_history                             │
│  • Text embeddings (theory, backtest summaries)│
│  • Image embeddings (CLIP-like для PNG)        │
│  • Metadata rich (run_id, rule_version, labels)│
│  • Semantic search & retrieval                 │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** ChromaDB storage (локальная папка) + Retrieval queries (для LLM context)
- **data_type:** Vector embeddings + metadata records
- **params:** vector_id, collection, embedding[], metadata, similarity_score (при query)
- **format:** 
````
Storage: data/chroma/{collection_name}/
Record structure: {
  "id": "vec_theory_001",
  "embedding": [0.123, -0.456, ...] (dim 1536 for text-embedding-ada-002),
  "metadata": {
    "type": "text|image",
    "source_file": "...",
    "run_id": "...",
    "rule_version": "...",
    "timestamp": "...",
    "user_label": "approved"
  },
  "document": "original text or image path"
}

Query result: {
  "results": [
    {"id": "vec_001", "distance": 0.23, "metadata": {...}, "document": "..."},
    ...
  ],
  "query_embedding": [...],
  "top_k": 5
}`

- **description:** Векторное хранилище с rich metadata для semantic retrieval

**logic_notes:**

- "Collections разделены по типам: theory_docs (теория), trade_cases (сделки с PNG), prompts_history"
- "Text embeddings: OpenAI text-embedding-ada-002 (1536 dim) для теории и JSON summaries"
- "Image embeddings: CLIP model (512 dim) для PNG screenshots - возможность visual similarity search"
- "Metadata ОБЯЗАТЕЛЬНО включает: source, timestamp, type, и связь с run_id/rule_version для трассировки"
- "Retrieval: semantic search по query → top-k наиболее похожих векторов"
- "ДОБАВЛЕНО: hybrid search - комбинация semantic (vector) + keyword (metadata filters) для точности"

### Подмодуль 2.9.2.1 — Image Embedding Pipeline

**submodule_name:** "2.9.2.1 Image Embedding Pipeline"

**inputs:**

- **from_source:** Dash Visualizer (PNG files) + Annotation Service (annotated PNG)
- **data_type:** PNG files
- **params:** image_path, embedding_model (CLIP), batch_mode (bool)
- **format:**

json

`{
  "images": [
    "to_vision/ger40_m15_001.png",
    "annotated/ger40_m15_001_annotated.png"
  ],
  "embedding_model": "openai/clip-vit-base-patch32",
  "batch_size": 10,
  "metadata": {
    "run_id": "run_001",
    "symbol": "GER40",
    "timeframe": "M15"
  }
}
````
- **description:** PNG файлы для генерации embeddings

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│     IMAGE EMBEDDING PIPELINE                   │
├────────────────────────────────────────────────┤
│  • Batch processing PNG → embeddings           │
│  • CLIP model (512 dim vectors)                │
│  • Online mode: immediate embed при создании   │
│  • Batch mode: periodic processing накопленных │
│  • Upsert to ChromaDB с metadata               │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** ChromaDB (trade_cases collection) + DATABASE (vector_id ↔ file_path mapping)
- **data_type:** Vector embeddings + metadata records
- **params:** vector_ids[], embeddings[][], file_paths[], processing_time
- **format:**

json

`{
  "processed_images": 10,
  "embeddings_generated": 10,
  "chroma_records": [
    {
      "vector_id": "img_vec_001",
      "embedding": [0.23, -0.45, ...],
      "metadata": {
        "file_path": "to_vision/ger40_m15_001.png",
        "run_id": "run_001",
        "type": "image",
        "image_type": "original",
        "timestamp": "2025-10-31T10:15:00Z"
      }
    },
    ...
  ],
  "processing_time_sec": 2.3
}`

- **description:** Сгенерированные embeddings с метаданными в ChromaDB

**logic_notes:**

- "Online mode: при создании PNG сразу генерируется embedding и добавляется в Chroma (для live режима)"
- "Batch mode: для backtest - накопление PNG, затем batch processing (быстрее)"
- "CLIP model: используется для visual similarity - поиск похожих паттернов на графике"
- "Два типа embeddings: original PNG и annotated PNG - разные векторы для разных целей"
- "ДОБАВЛЕНО: thumbnail storage в Chroma metadata - маленькое preview изображения (base64) для быстрого просмотра"

### Подмодуль 2.9.2.2 — JSON Schema Embedding

**submodule_name:** "2.9.2.2 JSON Schema Embedding"

**inputs:**

- **from_source:** Market Tools (zones JSON), Backtester (backtest results JSON), Rule Executor (signals JSON)
- **data_type:** JSON objects
- **params:** json_object, schema_type (zone|signal|backtest_result), key_fields[]
- **format:**

`json`

`{
  "json_object": {
    "type": "fvg",
    "price_low": 15835.0,
    "price_high": 15840.0,
    "confidence": 0.82,
    "meta": {"gap_size_pct": 0.35}
  },
  "schema_type": "zone",
  "key_fields": ["type", "price_low", "price_high", "confidence"],
  "embedding_strategy": "key_fields_to_text"
}
```
- **description:** JSON данные для конвертации в text embeddings

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│     JSON SCHEMA EMBEDDING                      │
├────────────────────────────────────────────────┤
│  • Конвертация JSON key fields → text         │
│  • Text embedding (ada-002)                    │
│  • Сохранение в ChromaDB с original JSON      │
│  • Retrieval по семантике (zone type, params)  │
│  • Связь JSON ↔ image embedding (same run_id)  │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** ChromaDB (соответствующая collection) + DATABASE (mapping record)
- **data_type:** Text embedding + JSON metadata
- **params:** vector_id, embedding[], original_json, schema_type
- **format:**

json

`{
  "vector_id": "json_vec_001",
  "embedding": [0.123, -0.456, ...],
  "text_representation": "FVG zone at 15835.0-15840.0, confidence 0.82, gap size 0.35%",
  "original_json": {...},
  "metadata": {
    "schema_type": "zone",
    "zone_type": "fvg",
    "run_id": "run_001",
    "timestamp": "2025-10-31T10:15:00Z"
  }
}`

- **description:** Text embedding JSON данных для semantic search

**logic_notes:**

- "Key fields extraction: берутся только важные поля (type, prices, confidence), игнорируется meta для краткости"
- "Text representation: 'FVG zone at 15835-15840, confidence 0.82' - human-readable для embedding"
- "Связь с image: run_id позволяет найти соответствующий PNG для визуализации"
- "Use case: retrieval похожих сетапов по семантике ('find all FVG zones with high confidence')"
- "ДОБАВЛЕНО: normalized fields - prices нормализуются для сравнения (relative positions, не absolute values)"

### Подмодуль 2.9.3 — Model Training Pipeline

**submodule_name:** "2.9.3 Model Training Pipeline"

**inputs:**

- **from_source:** DATABASE (labeled trades) + ChromaDB (embeddings) + Backtester (historical results)
- **data_type:** CSV (training dataset) + JSON (config)
- **params:** training_data_path, model_type (classifier|regressor), features[], target_variable
- **format:**

csv

`# training_data.csv
trade_id,fvg_confidence,ob_confidence,liquidity_proximity,session,ml_score,winrate,result
trade_001,0.82,0.75,0.3,London,0.68,0.61,win
trade_002,0.65,0.80,0.5,NY,0.55,0.61,loss
...

# config.json
{
  "model_type": "classifier",
  "algorithm": "lightgbm",
  "features": ["fvg_confidence", "ob_confidence", "liquidity_proximity", "session_encoded"],
  "target": "result",
  "train_test_split": 0.8,
  "hyperparams": {"n_estimators": 100, "max_depth": 5}
}
````
- **description:** Подготовленный датасет и конфигурация для обучения ML модели

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│     MODEL TRAINING PIPELINE                    │
├────────────────────────────────────────────────┤
│  • Feature extraction (from trades JSON)       │
│  • Train/test split (80/20)                    │
│  • Model training (LightGBM/sklearn)           │
│  • Evaluation: ROC-AUC, precision, recall      │
│  • Model versioning & persistence (pickle)     │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** ARCHIVE (models/ папка) + DATABASE (model registry) + ML Scoring Module
- **data_type:** Pickle file (trained model) + JSON (metrics report)
- **params:** model_id, version, metrics, feature_importance, file_path
- **format:** 
````
Model file: models/signal_classifier_v1.pkl

Metrics JSON: {
  "model_id": "signal_classifier",
  "version": "v1.0",
  "algorithm": "lightgbm",
  "training_date": "2025-10-31",
  "dataset_size": 1500,
  "train_test_split": [1200, 300],
  "metrics": {
    "roc_auc": 0.72,
    "accuracy": 0.68,
    "precision": 0.71,
    "recall": 0.65,
    "f1_score": 0.68
  },
  "feature_importance": {
    "fvg_confidence": 0.35,
    "ob_confidence": 0.28,
    "liquidity_proximity": 0.22,
    "session_encoded": 0.15
  },
  "model_path": "models/signal_classifier_v1.pkl"
}`

- **description:** Обученная модель с метриками и feature importance

**logic_notes:**

- "Feature engineering: извлечение признаков из JSON (confidence scores, proximity metrics, session encoding)"
- "Algorithm: LightGBM для табличных данных (быстро, хорошая точность), sklearn для baseline"
- "Train/test split: 80/20 с stratification по target для balanced classes"
- "Baseline threshold: ROC-AUC > 0.65 для acceptance (лучше случайного 0.5)"
- "Model versioning: каждое переобучение создаёт новую версию с timestamp"
- "ДОБАВЛЕНО: cross-validation (5-fold) для robust оценки, не только single train/test split"

### Подмодуль 2.9.4 — ML Scoring Module

**submodule_name:** "2.9.4 ML Scoring Module"

**inputs:**

- **from_source:** Rule Executor (signal features) + Model Training Pipeline (trained model)
- **data_type:** JSON (signal features) + Pickle (model)
- **params:** signal_id, features{}, model_path
- **format:**

json

`{
  "signal_id": "sig_001",
  "features": {
    "fvg_confidence": 0.82,
    "ob_confidence": 0.75,
    "liquidity_proximity": 0.3,
    "session": "London",
    "atr_normalized": 0.65
  },
  "model_path": "models/signal_classifier_v1.pkl"
}
````
- **description:** Признаки сигнала для предсказания вероятности успеха

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       ML SCORING MODULE                        │
├────────────────────────────────────────────────┤
│  • Загрузка trained model (pickle)             │
│  • Feature preprocessing (encoding, scaling)   │
│  • Prediction: p_success (вероятность win)     │
│  • Explainability: feature contributions       │
│  • Integration в Decision Reconciler           │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Decision Reconciler (для финального решения) + DATABASE (prediction log)
- **data_type:** JSON (prediction result)
- **params:** signal_id, p_success, feature_contributions, model_version
- **format:**

json

`{
  "signal_id": "sig_001",
  "ml_prediction": {
    "p_success": 0.68,
    "p_failure": 0.32,
    "confidence_interval": [0.63, 0.73]
  },
  "feature_contributions": {
    "fvg_confidence": +0.12,
    "ob_confidence": +0.08,
    "liquidity_proximity": -0.03,
    "session": +0.05
  },
  "model_version": "v1.0",
  "prediction_time_ms": 15,
  "timestamp": "2025-10-31T10:20:00Z"
}`

- **description:** Вероятность успеха сигнала с объяснением вклада признаков

**logic_notes:**

- "Feature preprocessing: session encoding (London=1, NY=2...), scaling numeric features если требуется"
- "p_success = вероятность класса 'win' из classifier (0.0-1.0)"
- "Feature contributions: SHAP values или feature importance × feature value для explainability"
- "Confidence interval: bootstrap estimation для uncertainty quantification"
- "Integration: p_success передаётся в Decision Reconciler как один из трёх источников (Python, LLM, ML)"
- "ДОБАВЛЕНО: model warm-up - загрузка модели при старте приложения, не при каждом prediction (performance)"

---

## МОДУЛЬ 2.10 — Outputs & Integrations

### Подмодуль 2.10.1 — Notion Uploader

**submodule_name:** "2.10.1 Notion Uploader"

**inputs:**

- **from_source:** Backtester Core (backtest results + trades CSV) + Annotation Service (annotated PNG) + Live Handler (live signals)
- **data_type:** JSON (backtest summary) + CSV (trades) + PNG files (screenshots)
- **params:** run_id, notion_page_id, data_to_upload (summary|trades|images|all)
- **format:**

`json`

`{
  "run_id": "bt_2025_10_31_001",
  "notion_database_id": "abc123...",
  "data": {
    "summary": {
      "setup_id": "Frank_raid_v1",
      "rule_version": "v1.2",
      "symbol": "GER40",
      "period": ["2025-05-01", "2025-10-31"],
      "winrate": 0.61,
      "avg_rr": 1.8,
      "total_trades": 234
    },
    "trades_csv": "archive/results/bt_001_trades.csv",
    "screenshots": [
      "exchange/annotated/sample_001.png",
      "exchange/annotated/sample_015.png"
    ]
  }
}
````
- **description:** Данные бэктеста для загрузки в Notion журнал

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       NOTION UPLOADER                          │
├────────────────────────────────────────────────┤
│  • Создание Notion pages/database entries      │
│  • Upload PNG (через Notion API or embed URL)  │
│  • Прикрепление trades CSV как table/file      │
│  • Bulk uploads (batch создание записей)       │
│  • Связь run_id ↔ Notion page_id для traceab.  │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Notion Database + DATABASE (notion_uploads log с page_id)
- **data_type:** Notion page_id + upload status
- **params:** run_id, notion_page_id, upload_status, page_url
- **format:**

`json`

`{
  "run_id": "bt_2025_10_31_001",
  "notion_page_id": "abc123-def456...",
  "notion_page_url": "https://notion.so/abc123...",
  "upload_status": "success",
  "uploaded_items": {
    "summary": true,
    "trades_table": true,
    "screenshots": 2
  },
  "timestamp": "2025-10-31T11:00:00Z"
}`

- **description:** Подтверждение загрузки с ссылкой на Notion страницу

**logic_notes:**

- "Notion API: использование notion-client (Python SDK) для создания database entries"
- "PNG upload: два варианта - embed как URL (если PNG hosted) или upload через Notion files API"
- "Trades table: конвертация CSV → Notion table (ограничение: макс 100 rows in-page, остальное как file attachment)"
- "Bulk mode: для batch backtest - создание множества записей за один API call (batch API)"
- "Traceability: run_id в Notion как property для связи с локальными данными"
- "ДОБАВЛЕНО: template pages - использование Notion template для consistent formatting журнала"

### Подмодуль 2.10.2 — Telegram Notifier

**submodule_name:** "2.10.2 Telegram Notifier"

**inputs:**

- **from_source:** Live Handler (live signals) + Decision Reconciler (approved signals) + Alert triggers (system events)
- **data_type:** JSON (alert data) + PNG (screenshot - optional)
- **params:** alert_type (signal|warning|error), priority, message, image_path
- **format:**

`json`

`{
  "alert_type": "signal",
  "priority": "high",
  "message": {
    "title": "🚨 New Signal: GER40 M15",
    "body": "Setup: Frank_raid_v1\nEntry: 15840\nSL: 15800 | TP: 15900\nConfidence: 0.75\nML Score: 0.68",
    "footer": "View in Notion: https://notion.so/abc123"
  },
  "image": "exchange/annotated/live_signal_001.png",
  "chat_id": "user_telegram_chat_id"
}
````
- **description:** Данные для отправки уведомления в Telegram

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       TELEGRAM NOTIFIER                        │
├────────────────────────────────────────────────┤
│  • Отправка сообщений через telegram-bot API  │
│  • Сжатие PNG перед отправкой (<1MB)           │
│  • Шаблоны по типам: INFO/WARN/ALERT/SIGNAL    │
│  • Priority levels (low/medium/high)           │
│  • Rate limiting (макс 20 msg/min)             │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Telegram (user chat) + DATABASE (sent_notifications log)
- **data_type:** JSON (send status)
- **params:** notification_id, chat_id, message_id (Telegram), send_status, timestamp
- **format:**

json

`{
  "notification_id": "notif_001",
  "alert_type": "signal",
  "chat_id": "123456789",
  "telegram_message_id": "987654",
  "send_status": "success",
  "message_text": "🚨 New Signal: GER40 M15...",
  "image_attached": true,
  "timestamp": "2025-10-31T10:20:15Z",
  "delivery_time_sec": 0.8
}`

- **description:** Подтверждение отправки с Telegram message_id

**logic_notes:**

- "Telegram Bot API: python-telegram-bot library для отправки"
- "Image compression: если PNG >1MB - resize/compress перед отправкой (Telegram limit 10MB, но оптимально <1MB)"
- "Message templates: emoji icons по типу (🚨 signal, ⚠️ warning, ❌ error)"
- "Priority: high priority = immediate send, low = buffered (раз в 5 мин summary)"
- "Rate limiting: не более 20 сообщений в минуту (Telegram limit 30, оставляем буфер)"
- "ДОБАВЛЕНО: inline buttons - кнопки '✅ Mark as Taken' / '❌ Skip' для быстрой обратной связи"

### Подмодуль 2.10.3 — Reporting Dashboard / Exporter

**submodule_name:** "2.10.3 Reporting Dashboard / Exporter"

**inputs:**

- **from_source:** DATABASE (aggregated backtest results, ML metrics, LLM usage) + Backtester (individual runs)
- **data_type:** SQL queries results + JSON (aggregated data)
- **params:** report_type (setup_performance|monthly_summary|cost_analysis), period, filters{}
- **format:**

json

`{
  "report_type": "setup_performance",
  "period": ["2025-01-01", "2025-10-31"],
  "filters": {
    "setup_ids": ["Frank_raid_v1", "Asia_fvg_break"],
    "symbols": ["GER40", "EURUSD"],
    "min_trades": 20
  },
  "aggregation": "by_setup_and_month"
}
````
- **description:** Параметры для генерации отчёта

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│   REPORTING DASHBOARD / EXPORTER               │
├────────────────────────────────────────────────┤
│  • Streamlit dashboard с агрегированными данными│
│  • Графики: winrate trends, PnL curves, metrics│
│  • Filters: by setup, symbol, timeframe, period│
│  • Export: CSV/Excel для детального анализа    │
│  • Benchmarks: сравнение setup'ов между собой  │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Streamlit UI (визуализация) + ARCHIVE (exported CSV/Excel files)
- **data_type:** JSON (report data) + CSV/Excel files
- **params:** report_id, charts[], export_files[]
- **format:**

json

`{
  "report_id": "report_2025_10_31",
  "report_type": "setup_performance",
  "generated_at": "2025-10-31T12:00:00Z",
  "data": {
    "by_setup": [
      {
        "setup_id": "Frank_raid_v1",
        "total_trades": 234,
        "winrate": 0.61,
        "avg_rr": 1.8,
        "total_pnl": +1520.50,
        "best_month": "2025-08",
        "worst_month": "2025-06"
      },
      ...
    ],
    "monthly_breakdown": [...],
    "cost_summary": {
      "total_llm_calls": 1243,
      "total_cost_usd": 37.25
    }
  },
  "charts": [
    {"type": "line", "title": "Winrate Trend", "data": [...]},
    {"type": "bar", "title": "PnL by Setup", "data": [...]}
  ],
  "export_files": [
    "reports/setup_performance_2025_10_31.csv",
    "reports/monthly_summary_2025_10_31.xlsx"
  ]
}`

- **description:** Отчёт с визуализациями и экспортированными файлами

**logic_notes:**

- "Streamlit dashboard: multi-page app с фильтрами, графиками (Plotly), таблицами (pandas)"
- "Aggregation levels: by setup, by month, by symbol, by timeframe - configurable"
- "Charts: line (trends over time), bar (comparison), scatter (correlation), heatmap (param sensitivity)"
- "Export formats: CSV (raw data), Excel (formatted с charts), PDF (full report с визуализациями)"
- "Benchmarks: сравнение нескольких setup'ов side-by-side (winrate, RR, drawdown)"
- "ДОБАВЛЕНО: automated reports - scheduled generation (еженедельно) и отправка в Telegram/Email"

---

## МОДУЛЬ 2.11 — Orchestration & Workflows (Prefect 2.19)

### Подмодуль 2.11.1 — Backtest Flow

**submodule_name:** "2.11.1 Backtest Flow"

**condition:** "BACKTEST - оркестрация полного цикла бэктестирования"

**inputs:**

- **from_source:** User Request (через Request Handler 2.1.1) + Configuration (flow parameters)
- **data_type:** JSON (validated request)
- **params:** run_id, symbol, timeframe, period, setup_id, rule_version, execution_params
- **format:**

json

`{
  "run_id": "bt_2025_10_31_001",
  "flow_type": "backtest_flow",
  "symbol": "GER40",
  "timeframe": "M15",
  "period": ["2025-05-01", "2025-10-31"],
  "setup_id": "Frank_raid_v1",
  "rule_version": "v1.2",
  "execution_params": {
    "slippage": 1.0,
    "spread": 2.0,
    "parallel": false
  }
}
````
- **description:** Валидированный запрос на запуск backtest flow

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       BACKTEST FLOW (Prefect)                  │
├────────────────────────────────────────────────┤
│  • Task 1: Data Ingest (MT5/CSV)               │
│  • Task 2: Data Processor (cleaning)           │
│  • Task 3: Market Tools (detectors)            │
│  • Task 4: Setup Manager (rule evaluation)     │
│  • Task 5: Backtester Core (simulation)        │
│  • Task 6: Visualizer (PNG samples)            │
│  • Task 7: GPT Analysis (optional LLM)         │
│  • Task 8: Notion Upload + Telegram notify     │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** DATABASE (flow run record) + ARCHIVE (results JSON + trades CSV + PNGs) + Notion + Telegram
- **data_type:** JSON (flow result summary)
- **params:** run_id, flow_status, tasks_completed, execution_time, results_summary
- **format:**

json

`{
  "run_id": "bt_2025_10_31_001",
  "flow_type": "backtest_flow",
  "flow_status": "completed",
  "start_time": "2025-10-31T10:00:00Z",
  "end_time": "2025-10-31T10:15:30Z",
  "execution_time_minutes": 15.5,
  "tasks_completed": [
    {"task": "data_ingest", "status": "success", "duration_sec": 45},
    {"task": "data_processor", "status": "success", "duration_sec": 30},
    {"task": "market_tools", "status": "success", "duration_sec": 120},
    {"task": "backtester_core", "status": "success", "duration_sec": 180},
    {"task": "visualizer", "status": "success", "duration_sec": 60},
    {"task": "notion_upload", "status": "success", "duration_sec": 25}
  ],
  "results_summary": {
    "trades_count": 234,
    "winrate": 0.61,
    "total_pnl": +1520.50,
    "notion_page_url": "https://notion.so/abc123"
  },
  "artifacts": {
    "backtest_json": "archive/results/bt_001.json",
    "trades_csv": "archive/results/bt_001_trades.csv",
    "sample_pngs": ["exchange/annotated/sample_001.png", ...]
  }
}`

- **description:** Полный отчёт о выполнении backtest flow

**logic_notes:**

- "Sequential execution: tasks выполняются последовательно с передачей данных через Prefect artifacts"
- "Retry logic: каждая task имеет max_retries=3 с exponential backoff при сбоях"
- "Logging: каждая task логирует входы/выходы для debugging"
- "GPT Analysis optional: если в config указано analyze_with_llm=true - добавляется task LLM анализа"
- "Failure handling: если критическая task fails (например data_ingest) - весь flow останавливается с ошибкой"
- "ДОБАВЛЕНО: caching - промежуточные результаты tasks кешируются, при перезапуске flow пропускаются уже выполненные"

### Подмодуль 2.11.2 — Live Scan Flow

**submodule_name:** "2.11.2 Live Scan Flow"

**condition:** "LIVE - мониторинг рынка в реальном времени, запуск каждую минуту"

**inputs:**

- **from_source:** Data Refresh Scheduler (триггер каждую минуту) + Configuration (active setups)
- **data_type:** JSON (trigger event + active setups config)
- **params:** trigger_timestamp, symbols[], timeframes[], active_setup_ids[]
- **format:**

json

`{
  "trigger": "scheduled_1min",
  "trigger_timestamp": "2025-10-31T10:15:00Z",
  "symbols": ["GER40", "EURUSD"],
  "timeframes": ["M1", "M5", "M15"],
  "active_setup_ids": ["Frank_raid_v1", "Asia_fvg_break_v2"],
  "mode": "live"
}
````
- **description:** Триггер для запуска live scan с активными сетапами

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       LIVE SCAN FLOW (Prefect)                 │
├────────────────────────────────────────────────┤
│  • Task 1: MT5 Loader (incremental update)     │
│  • Task 2: Data Processor (enrich новые бары)  │
│  • Task 3: Market Tools (детекторы на новых)   │
│  • Task 4: Setup Manager (rule check)          │
│  • Task 5: ML Scoring (p_success для сигналов) │
│  • Task 6: Decision Reconciler (approve?)      │
│  • Task 7: IF approved: Visualizer → LLM       │
│  • Task 8: Telegram Notify (< 30 sec от close) │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** InMemoryBuffer (обновлённые данные) + Telegram (уведомление) + DATABASE (live signals log) + Notion (опционально)
- **data_type:** JSON (flow result)
- **params:** run_id, signals_found, signals_approved, notifications_sent
- **format:**

json

`{
  "run_id": "live_2025_10_31_101500",
  "flow_type": "live_scan_flow",
  "trigger_time": "2025-10-31T10:15:00Z",
  "execution_time_sec": 8.5,
  "symbols_scanned": ["GER40", "EURUSD"],
  "signals_found": 2,
  "signals_approved": 1,
  "results": [
    {
      "signal_id": "sig_live_001",
      "symbol": "GER40",
      "setup": "Frank_raid_v1",
      "decision": "approved",
      "confidence": 0.75,
      "ml_score": 0.68,
      "telegram_sent": true,
      "telegram_delivery_time_sec": 1.2
    },
    {
      "signal_id": "sig_live_002",
      "symbol": "EURUSD",
      "setup": "Asia_fvg_break_v2",
      "decision": "rejected",
      "confidence": 0.52,
      "reason": "ML score below threshold"
    }
  ]
}`

- **description:** Результат live scan с найденными сигналами и notifications

**logic_notes:**

- "Execution time КРИТИЧНО < 30 сек (от close свечи до Telegram уведомления)"
- "Incremental update: MT5 Loader загружает только новые бары с last_timestamp"
- "InMemoryBuffer: детекторы работают на буфере (быстро), не обращаются к диску"
- "Parallel scanning: если несколько symbols - параллельные tasks (Prefect mapped tasks)"
- "Decision threshold: только approved signals (confidence >0.7 && ml_score >0.6) идут в Telegram"
- "ДОБАВЛЕНО: cooldown period - не отправлять повторные уведомления по тому же setup в течение 15 минут"

### Подмодуль 2.11.3 — Train Model Flow

**submodule_name:** "2.11.3 Train Model Flow"

**inputs:**

- **from_source:** User Request (ручной запуск) или Scheduler (автоматически раз в неделю) + DATABASE (labeled trades dataset)
- **data_type:** JSON (train config) + CSV (training data)
- **params:** model_type, training_data_path, hyperparams, schedule
- **format:**

json

`{
  "flow_type": "train_model_flow",
  "trigger": "scheduled_weekly",
  "model_type": "signal_classifier",
  "training_data": {
    "source": "database",
    "query": "SELECT * FROM labeled_trades WHERE label IS NOT NULL",
    "min_samples": 500
  },
  "hyperparams": {
    "algorithm": "lightgbm",
    "n_estimators": 100,
    "max_depth": 5,
    "cross_validation_folds": 5
  },
  "schedule": "weekly_sunday_03:00"
}
````
- **description:** Конфигурация для запуска переобучения ML модели

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       TRAIN MODEL FLOW (Prefect)               │
├────────────────────────────────────────────────┤
│  • Task 1: Data Collection (labeled trades)    │
│  • Task 2: Feature Engineering                 │
│  • Task 3: Train/Test Split                    │
│  • Task 4: Model Training (LightGBM)           │
│  • Task 5: Evaluation (ROC-AUC, metrics)       │
│  • Task 6: Model Versioning & Save             │
│  • Task 7: IF better: Deploy новой модели      │
│  • Task 8: Notification (metrics report)       │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** ARCHIVE (models/ новая версия) + DATABASE (model registry update) + ML Scoring Module (deployment) + Telegram (metrics report)
- **data_type:** Pickle (model file) + JSON (training report)
- **params:** model_version, metrics, deployment_status, comparison_with_previous
- **format:**

json

`{
  "flow_type": "train_model_flow",
  "model_id": "signal_classifier",
  "new_version": "v2.0",
  "training_date": "2025-10-31",
  "training_data_size": 1850,
  "metrics": {
    "roc_auc": 0.74,
    "accuracy": 0.70,
    "precision": 0.73,
    "recall": 0.68
  },
  "comparison_with_v1": {
    "previous_auc": 0.72,
    "improvement": +0.02,
    "significant": true
  },
  "deployment_status": "deployed",
  "model_path": "models/signal_classifier_v2.pkl",
  "notification_sent": true
}`

- **description:** Отчёт о переобучении с метриками и deployment status

**logic_notes:**

- "Scheduled: запуск каждое воскресенье в 03:00 (низкая активность рынка)"
- "Min samples check: если labeled_trades < 500 - пропуск обучения, недостаточно данных"
- "Comparison: новая модель сравнивается с текущей production версией"
- "Deployment decision: новая модель деплоится ТОЛЬКО если ROC-AUC improvement >0.02 (statistical significance)"
- "Rollback capability: старая версия модели остаётся в models/ для возможности rollback"
- "ДОБАВЛЕНО: A/B testing mode - возможность запуска обеих версий параллельно для сравнения на live данных"

### Подмодуль 2.11.4 — Flow Registry & Deployment Management

**submodule_name:** "2.11.4 Flow Registry & Deployment Management"

**inputs:**

- **from_source:** Python code (flow definitions) + Configuration (deployment params)
- **data_type:** Python code + YAML (deployment config)
- **params:** flow_name, schedule, work_pool, tags[], parameters{}
- **format:**

yaml

`*# deployment_config.yaml*
deployments:
  - name: "backtest_flow_prod"
    flow: "flows.backtest_flow"
    schedule: null  *# manual trigger only*
    work_pool: "local_pool"
    tags: ["backtest", "production"]
    parameters:
      default_slippage: 1.0
      default_spread: 2.0
    
  - name: "live_scan_flow_prod"
    flow: "flows.live_scan_flow"
    schedule: "*/1 * * * *"  *# every 1 minute*
    work_pool: "live_pool"
    tags: ["live", "production"]
    parameters:
      active_setups: ["Frank_raid_v1", "Asia_fvg_break_v2"]
    
  - name: "train_model_flow_prod"
    flow: "flows.train_model_flow"
    schedule: "0 3 * * 0"  *# Sundays 03:00*
    work_pool: "training_pool"
    tags: ["ml", "training"]
````
- **description:** Определения и расписания всех Prefect deployments

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│   FLOW REGISTRY & DEPLOYMENT MANAGEMENT        │
├────────────────────────────────────────────────┤
│  • Регистрация всех flows в Prefect            │
│  • Deployment configurations (schedule, params)│
│  • Work pools management (local/training/live) │
│  • Flow versioning (code changes tracking)     │
│  • Deployment updates (apply changes)          │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Prefect Server (deployment registry) + DATABASE (deployment metadata)
- **data_type:** Deployment records
- **params:** deployment_id, flow_name, version, schedule, status (active/paused)
- **format:**

json

`{
  "deployments": [
    {
      "deployment_id": "dep_001",
      "name": "backtest_flow_prod",
      "flow_name": "backtest_flow",
      "version": "v1.2",
      "schedule": null,
      "status": "active",
      "last_run": "2025-10-31T10:00:00Z",
      "next_run": null,
      "tags": ["backtest", "production"]
    },
    {
      "deployment_id": "dep_002",
      "name": "live_scan_flow_prod",
      "flow_name": "live_scan_flow",
      "version": "v1.5",
      "schedule": "*/1 * * * *",
      "status": "active",
      "last_run": "2025-10-31T10:15:00Z",
      "next_run": "2025-10-31T10:16:00Z",
      "tags": ["live", "production"]
    }
  ]
}`

- **description:** Реестр всех deployments с их статусами и расписаниями

**logic_notes:**

- "Flow versioning: при изменении кода flow автоматически создаётся новая версия"
- "Work pools: разделение по типам задач (local для backtest, live для real-time, training для ML)"
- "Deployment apply: команда `prefect deployment apply deployment_config.yaml` обновляет все deployments"
- "Pause/Resume: возможность временной остановки deployment без удаления (например live на выходных)"
- "ДОБАВЛЕНО: deployment templates - готовые шаблоны для быстрого создания новых deployments"

---

## МОДУЛЬ 2.12 — Security & Config

### Подмодуль 2.12.1 — Secrets Management

**submodule_name:** "2.12.1 Secrets Management"

**inputs:**

- **from_source:** .env файл или Prefect Secrets или Environment Variables
- **data_type:** Key-value pairs (credentials)
- **params:** secret_name, secret_value, scope (local|prefect|env)
- **format:**

env

`# .env file
OPENAI_API_KEY=sk-proj-...
NOTION_API_KEY=secret_...
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
MT5_LOGIN=12345678
MT5_PASSWORD=SecurePass123
MT5_SERVER=Broker-Demo
DATABASE_URL=sqlite:///data/ita.db
CHROMA_PATH=data/chroma/
```
- **description:** Конфиденциальные credentials для всех внешних сервисов

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       SECRETS MANAGEMENT                       │
├────────────────────────────────────────────────┤
│  • .env файл для локальной разработки          │
│  • Prefect Secrets для production deployments  │
│  • Environment variables для Docker/cloud      │
│  • Rotation policy (ключи обновлять раз в 90д) │
│  • Audit log доступа к secrets                 │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Modules (через environment variables или Prefect context)
- **data_type:** String values (credentials)
- **params:** secret_name, masked_value (для логов)
- **format:**

python

`*# Usage in code:*
import os
openai_key = os.getenv("OPENAI_API_KEY")
notion_key = os.getenv("NOTION_API_KEY")

*# Or via Prefect:*
from prefect import get_run_context
context = get_run_context()
openai_key = context.parameters["openai_key"]`

- **description:** Безопасный доступ к credentials из кода

**logic_notes:**

- ".env файл НЕ коммитится в Git (в .gitignore), каждый разработчик имеет свою копию"
- "Prefect Secrets: для production - хранятся в Prefect Cloud/Server, не в коде"
- "Rotation policy: OpenAI/Notion API keys должны обновляться каждые 90 дней (reminder в Telegram)"
- "Audit: логирование каждого доступа к secrets (кто, когда, какой ключ) для security"
- "ДОБАВЛЕНО: encrypted .env - возможность шифрования .env файла с master password"

### Подмодуль 2.12.2 — Access Control & RBAC

**submodule_name:** "2.12.2 Access Control & RBAC"

**inputs:**

- **from_source:** Configuration (users config) + USER_REQUEST (с user_id)
- **data_type:** YAML (users & roles config)
- **params:** user_id, role, permissions[]
- **format:**

`yaml`

`*# users_config.yaml*
users:
  - user_id: "trader_1"
    name: "Main Trader"
    role: "admin"
    permissions: ["run_backtest", "run_live", "train_model", "edit_rules", "view_all"]
    
  - user_id: "trader_2"
    name: "Junior Trader"
    role: "analyst"
    permissions: ["run_backtest", "view_results"]
    
  - user_id: "dev_1"
    name: "Developer"
    role: "developer"
    permissions: ["run_backtest", "edit_code", "view_logs", "train_model"]

roles:
  admin: ["all"]
  analyst: ["run_backtest", "view_results", "export_data"]
  developer: ["run_backtest", "edit_code", "view_logs", "train_model"]
```
- **description:** Определение пользователей, ролей и разрешений

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│     ACCESS CONTROL & RBAC                      │
├────────────────────────────────────────────────┤
│  • User authentication (local для начала)      │
│  • Role-based permissions                      │
│  • Permission checks перед операциями          │
│  • Audit log всех действий (кто что запустил)  │
│  • Multi-user support (separate workspaces)    │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** DATABASE (users table, audit_log table) + Logs
- **data_type:** Boolean (permission granted/denied) + audit record
- **params:** user_id, action, permission_check_result, timestamp
- **format:**

json

`{
  "user_id": "trader_2",
  "action": "run_live_scan",
  "permission_required": "run_live",
  "permission_granted": false,
  "reason": "User role 'analyst' does not have 'run_live' permission",
  "timestamp": "2025-10-31T10:00:00Z",
  "ip_address": "192.168.1.100"
}`

- **description:** Результат проверки разрешений с audit записью

**logic_notes:**

- "Локальный RBAC: пока работает только на локальных машинах разработчиков, нет облачной авторизации"
- "Permission checks: перед каждым критичным действием (run_live, train_model) проверка разрешений"
- "Audit log: ВСЕ действия логируются (run_id, user_id, action, timestamp) для traceability"
- "Multi-user: каждый трейдер может иметь свой workspace (separate data folders), но общая база знаний в Chroma"
- "БУДУЩЕЕ: OAuth integration для cloud deployment, SSO для команды"

### Подмодуль 2.12.3 — Configuration Management

**submodule_name:** "2.12.3 Configuration Management"

**inputs:**

- **from_source:** config.yaml файл + Environment-specific overrides
- **data_type:** YAML файл
- **params:** environment (dev|prod), config_sections{}
- **format:**

yaml

`*# config.yaml*
environment: "dev"

paths:
  data_root: "D:/ITA/ITA_1.0/"
  exchange: "D:/ITA/ITA_1.0/exchange/"
  archive: "D:/ITA/ITA_1.0/exchange/archive/"
  chroma: "D:/ITA/ITA_1.0/data/chroma/"

mt5:
  login: "${MT5_LOGIN}"  *# from .env*
  password: "${MT5_PASSWORD}"
  server: "${MT5_SERVER}"
  timeout_sec: 30

backtester:
  default_slippage_pips: 1.0
  default_spread_pips: 2.0
  sample_png_every_n_trades: 10

live:
  scan_interval_minutes: 1
  cooldown_minutes: 15
  max_signals_per_hour: 10

llm:
  model: "gpt-4-vision-preview"
  max_tokens: 1000
  temperature: 0.3
  rate_limit_rpm: 10

thresholds:
  min_confidence: 0.7
  min_ml_score: 0.6
  min_trades_for_backtest: 20

retention:
  raw_candles_days: 365
  annotated_pngs_days: 90
  backtest_results_days: null  *# never delete*
```
- **description:** Централизованная конфигурация всех параметров системы

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│     CONFIGURATION MANAGEMENT                   │
├────────────────────────────────────────────────┤
│  • config.yaml - single source of truth        │
│  • Environment-specific overrides (dev/prod)   │
│  • Variables substitution (${VAR} from .env)   │
│  • Validation при загрузке (schema check)      │
│  • Hot reload возможность (без рестарта)       │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Все модули проекта (читают config при инициализации)
- **data_type:** Python dict (parsed YAML)
- **params:** config object with sections
- **format:**

python

`*# Usage in code:*
from config import load_config
config = load_config()

mt5_login = config["mt5"]["login"]
slippage = config["backtester"]["default_slippage_pips"]
min_confidence = config["thresholds"]["min_confidence"]`

- **description:** Parsed конфигурация доступная в коде

**logic_notes:**

- "Single source of truth: ВСЕ настройки в config.yaml, не хардкодятся в коде"
- "Environment overrides: config_prod.yaml может override значения из config.yaml для production"
- "Variables substitution: ${VAR} заменяется значениями из .env (например ${MT5_LOGIN})"
- "Schema validation: pydantic model для config - проверка типов и required fields при загрузке"
- "Hot reload: возможность перезагрузки config без рестарта (через signal или API endpoint)"
- "ДОБАВЛЕНО: config versioning - config.yaml также версионируется в Git для traceability изменений"

---

## МОДУЛЬ 2.13 — Deploy & Infra (local-first)

### Подмодуль 2.13.1 — Local Development Setup

**submodule_name:** "2.13.1 Local Development Setup"

**inputs:**

- **from_source:** Git repository + requirements.txt + setup scripts
- **data_type:** Code files + dependencies list
- **params:** python_version, dependencies[], setup_scripts[]
- **format:**

txt

`# requirements.txt
python==3.11.5
prefect==2.19.0
langchain==0.1.0
openai==1.5.0
chromadb==0.4.18
pandas==2.1.3
plotly==5.18.0
streamlit==1.29.0
MetaTrader5==5.0.45
notion-client==2.2.1
python-telegram-bot==20.7
scikit-learn==1.3.2
lightgbm==4.1.0
pydantic==2.5.2
loguru==0.7.2
```
- **description:** Список зависимостей для установки локального окружения

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│     LOCAL DEVELOPMENT SETUP                    │
├────────────────────────────────────────────────┤
│  • Python 3.11.x venv                          │
│  • requirements.txt - pinned versions          │
│  • setup.sh script (Linux/Mac) / setup.bat (Win│
│  • IDE: VSCode с расширениями                  │
│  • Git repository structure                    │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Local machine (venv папка)
- **data_type:** Installed Python packages
- **params:** venv_path, installed_packages[], setup_status
- **format:**

bash

`*# setup.sh#!/bin/bash*
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
mkdir -p data/chroma data/cache exchange/archive logs
cp config.yaml.example config.yaml
cp .env.example .env
echo "Setup complete! Edit .env with your credentials."`

- **description:** Скрипт для автоматической настройки окружения

**logic_notes:**

- "Python 3.11.x requirement - критично для совместимости библиотек"
- "Pinned versions в requirements.txt - избежание breaking changes при обновлениях"
- "VSCode recommended extensions: Python, Pylance, Prefect, YAML"
- "Git structure: /flows, /modules, /config, /data, /exchange, /tests, /docs"
- "ДОБАВЛЕНО: pre-commit hooks - автоматическая проверка кода (linting, formatting) перед commit"

### Подмодуль 2.13.2 — Docker Compose (Optional Services)

**submodule_name:** "2.13.2 Docker Compose (Optional Services)"

**inputs:**

- **from_source:** docker-compose.yml файл
- **data_type:** YAML (Docker services definition)
- **params:** services[], volumes[], networks[]
- **format:**

yaml

`*# docker-compose.yml*
version: '3.8'

services:
  prefect-server:
    image: prefecthq/prefect:2.19.0-python3.11
    ports:
      - "4200:4200"
    volumes:
      - prefect-data:/root/.prefect
    command: prefect server start
    
  chroma:
    image: chromadb/chroma:0.4.18
    ports:
      - "8000:8000"
    volumes:
      - chroma-data:/chroma/chroma
    environment:
      - CHROMA_SERVER_HOST=0.0.0.0
      
  streamlit:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./:/app
      - ./data:/app/data
    command: streamlit run app.py
    depends_on:
      - prefect-server
      - chroma

volumes:
  prefect-data:
  chroma-data:`

- **description:** Docker Compose для опциональных сервисов (не обязательно для локальной разработки)

**ascii_diagram:**

`┌────────────────────────────────────────────────┐
│   DOCKER COMPOSE (Optional Services)           │
├────────────────────────────────────────────────┤
│  • Prefect Server (Orion UI на :4200)          │
│  • ChromaDB (vector DB на :8000)               │
│  • Streamlit (UI на :8501)                     │
│  • Persistent volumes для данных               │
│  • Опционально: для изоляции или cloud deploy  │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Docker containers (running services)
- **data_type:** Running services status
- **params:** container_ids[], ports[], volumes_mounted[]
- **format:**

json

`{
  "services_running": [
    {
      "service": "prefect-server",
      "container_id": "abc123...",
      "status": "running",
      "ports": ["4200:4200"],
      "url": "http://localhost:4200"
    },
    {
      "service": "chroma",
      "container_id": "def456...",
      "status": "running",
      "ports": ["8000:8000"],
      "url": "http://localhost:8000"
    }
  ],
  "volumes": ["prefect-data", "chroma-data"]
}`

- **description:** Статус запущенных Docker сервисов

**logic_notes:**

- "OPTIONAL: Docker НЕ обязателен для локальной разработки, можно всё запускать напрямую в venv"
- "Use case: полезно для изоляции сервисов или при подготовке к cloud deployment"
- "Persistent volumes: данные Prefect и Chroma сохраняются между перезапусками контейнеров"
- "Development mode: volumes mount локальный код для hot reload при изменениях"
- "ДОБАВЛЕНО: docker-compose-prod.yml - отдельный compose для production с дополнительными сервисами (monitoring, backup)"

### Подмодуль 2.13.3 — Monitoring & Healthchecks

**submodule_name:** "2.13.3 Monitoring & Healthchecks"

**inputs:**

- **from_source:** All running services + Prefect Agent + System metrics
- **data_type:** JSON (service status) + metrics
- **params:** service_name, endpoint, check_interval_sec
- **format:**

json

`{
  "checks": [
    {
      "service": "prefect_agent",
      "type": "process_check",
      "check_interval_sec": 60
    },
    {
      "service": "mt5_connection",
      "type": "api_call",
      "endpoint": "mt5.initialize()",
      "check_interval_sec": 300
    },
    {
      "service": "chromadb",
      "type": "http_health",
      "endpoint": "http://localhost:8000/api/v1/heartbeat",
      "check_interval_sec": 120
    },
    {
      "service": "disk_space",
      "type": "system_metric",
      "threshold_gb": 10,
      "check_interval_sec": 3600
    }
  ]
}
```
- **description:** Конфигурация healthchecks для всех критичных сервисов

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│     MONITORING & HEALTHCHECKS                  │
├────────────────────────────────────────────────┤
│  • Prefect Agent monitoring (alive?)           │
│  • MT5 connection health (can connect?)        │
│  • ChromaDB availability (API responding?)     │
│  • Disk space checks (>10GB free?)             │
│  • Alerting в Telegram при падении сервисов    │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Logs + Telegram (alerts) + Monitoring Dashboard
- **data_type:** JSON (health status reports)
- **params:** timestamp, service_checks[], alerts_triggered[]
- **format:**

json

`{
  "timestamp": "2025-10-31T12:00:00Z",
  "overall_status": "healthy",
  "service_checks": [
    {
      "service": "prefect_agent",
      "status": "healthy",
      "last_heartbeat": "2025-10-31T11:59:30Z",
      "uptime_hours": 168.5
    },
    {
      "service": "mt5_connection",
      "status": "healthy",
      "last_successful_call": "2025-10-31T11:55:00Z",
      "response_time_ms": 125
    },
    {
      "service": "disk_space",
      "status": "warning",
      "free_space_gb": 12.3,
      "threshold_gb": 10,
      "alert_sent": false
    }
  ],
  "alerts_triggered": []
}`

- **description:** Сводный отчёт о здоровье системы

**logic_notes:**

- "Process checks: проверка что Prefect Agent процесс запущен (через psutil)"
- "API healthchecks: HTTP GET на /health endpoints сервисов"
- "System metrics: disk space, memory usage, CPU load - базовый мониторинг"
- "Alert thresholds: disk <10GB, MT5 не отвечает >5 мин, Prefect Agent down - instant Telegram alert"
- "Logs: все checks логируются в logs/health_checks.log для history"
- "ДОБАВЛЕНО: recovery actions - автоматический restart Prefect Agent при падении (watchdog)"

---

## МОДУЛЬ 2.14 — QA / Testing

### Подмодуль 2.14.1 — Unit Tests

**submodule_name:** "2.14.1 Unit Tests"

**inputs:**

- **from_source:** Python test files (tests/ папка) + pytest framework
- **data_type:** Python code (test functions)
- **params:** test_file, test_function, fixtures
- **format:**

python

`*# tests/test_market_tools.py*
import pytest
from modules.market_tools import Detect_FVG

def test_detect_fvg_bullish():
    """Test FVG detection для bullish паттерна"""
    *# Arrange*
    candles = load_test_data("fvg_bullish_sample.csv")
    detector = Detect_FVG(min_gap_pct=0.2)
    
    *# Act*
    result = detector.detect(candles)
    
    *# Assert*
    assert len(result) == 1
    assert result[0]["type"] == "fvg"
    assert result[0]["fvg_direction"] == "bullish"
    assert result[0]["confidence"] > 0.7
    assert "gap_size_pct" in result[0]["meta"]

def test_detect_fvg_no_gap():
    """Test что детектор не находит FVG когда gap отсутствует"""
    candles = load_test_data("no_gap_sample.csv")
    detector = Detect_FVG(min_gap_pct=0.2)
    
    result = detector.detect(candles)
    
    assert len(result) == 0
```
- **description:** Unit tests для индивидуальных компонентов (детекторы, парсеры, и тд)

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         UNIT TESTS (pytest)                    │
├────────────────────────────────────────────────┤
│  • Tests для каждого детектора Market Tools    │
│  • Tests для Data Processor функций            │
│  • Tests для Rule Parser (YAML → executable)   │
│  • Mock external APIs (MT5, OpenAI, Notion)    │
│  • Coverage target: >80% для core modules      │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Test reports (console + HTML) + Coverage report
- **data_type:** Test results JSON + coverage metrics
- **params:** tests_run, passed, failed, skipped, coverage_percent
- **format:**

json

`{
  "test_session": "2025-10-31T14:00:00Z",
  "tests_run": 87,
  "passed": 85,
  "failed": 2,
  "skipped": 0,
  "duration_sec": 12.5,
  "failed_tests": [
    "test_market_tools.py::test_detect_ob_edge_case",
    "test_visualizer.py::test_png_generation_large_dataset"
  ],
  "coverage": {
    "total_percent": 82.5,
    "by_module": {
      "market_tools": 89.2,
      "data_processor": 91.5,
      "backtester": 78.3,
      "llm_integration": 65.1
    }
  }
}`

- **description:** Результаты прогона unit tests с coverage метриками

**logic_notes:**

- "pytest framework: стандарт для Python testing"
- "Test data: папка tests/data/ с CSV samples для детерминированных тестов"
- "Mocking: использовать unittest.mock для MT5, OpenAI, Notion API calls (не делать real calls в tests)"
- "Coverage target: минимум 80% для core modules (Market Tools, Backtester, Data Processor)"
- "CI integration: тесты запускаются автоматически при каждом commit (GitHub Actions или local git hook)"
- "ДОБАВЛЕНО: parametrized tests - для проверки multiple scenarios с разными параметрами"

### Подмодуль 2.14.2 — Integration Tests

**submodule_name:** "2.14.2 Integration Tests"

**inputs:**

- **from_source:** Test scenarios (end-to-end workflows) + small test dataset
- **data_type:** Test scenarios JSON + CSV (test candles)
- **params:** scenario_name, test_data_path, expected_output
- **format:**

json

`{
  "scenario": "backtest_frank_raid_small_dataset",
  "description": "End-to-end backtest на маленьком датасете",
  "test_data": "tests/data/ger40_m15_1month.csv",
  "setup_config": {
    "setup_id": "Frank_raid_v1",
    "rule_version": "v1.2"
  },
  "expected_output": {
    "trades_count_range": [5, 15],
    "winrate_range": [0.5, 0.7],
    "execution_time_max_sec": 60
  }
}
```
- **description:** Сценарий integration test для проверки end-to-end workflow

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       INTEGRATION TESTS                        │
├────────────────────────────────────────────────┤
│  • End-to-end backtest flow test               │
│  • Live scan flow test (mocked MT5 data)       │
│  • Data pipeline: Ingest → Process → Detect    │
│  • LLM integration test (с mock или real API)  │
│  • Notion upload test (test database)          │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Test reports + Logs
- **data_type:** Test results JSON
- **params:** scenario_name, status, duration, issues_found[]
- **format:**

json

`{
  "scenario": "backtest_frank_raid_small_dataset",
  "status": "passed",
  "start_time": "2025-10-31T14:05:00Z",
  "end_time": "2025-10-31T14:05:45Z",
  "duration_sec": 45,
  "results": {
    "trades_count": 8,
    "winrate": 0.625,
    "backtest_json_created": true,
    "trades_csv_created": true,
    "sample_pngs_count": 2
  },
  "checks": [
    {"check": "trades_count_in_range", "result": "pass"},
    {"check": "winrate_in_range", "result": "pass"},
    {"check": "execution_time_ok", "result": "pass"},
    {"check": "outputs_exist", "result": "pass"}
  ],
  "issues_found": []
}
```
- **description:** Результаты integration test с детализацией проверок

**logic_notes:**
- "Small dataset: 1 месяц данных M15 (~3000 свечей) для быстрого прогона"
- "End-to-end: тест проходит через ВСЕ этапы: Data Ingest → Process → Detect → Backtest → Visualize → Upload"
- "Assertions: проверка что outputs (JSON, CSV, PNG) созданы и содержат ожидаемые данные"
- "Mock vs Real: для LLM можно использовать mock ответы (быстрее) или real API с test account (дороже но реалистичнее)"
- "ДОБАВЛЕНО: smoke tests - быстрые integration tests для базовой проверки что система работает (запускаются перед full test suite)"

---

### Подмодуль 2.14.3 — Acceptance Test Dataset

**submodule_name:** "2.14.3 Acceptance Test Dataset (Control Set)"

**inputs:**
- **from_source:** Manually labeled data + Ground truth annotations
- **data_type:** PNG files + JSON (labels)
- **params:** screenshot_path, ground_truth_zones[], expected_signals[]
- **format:** 
```
# Control dataset structure:
tests/acceptance_dataset/
  ├── case_001_frank_raid_perfect/
  │   ├── screenshot.png
  │   ├── ground_truth.json
  │   └── expected_output.json
  ├── case_002_false_fvg/
  │   ├── screenshot.png
  │   ├── ground_truth.json
  │   └── expected_output.json
  ...

# ground_truth.json example:
{
  "case_id": "case_001",
  "description": "Perfect Frank raid setup",
  "zones": [
    {"type": "session", "session_name": "Frankfurt", "price_low": 15820, "price_high": 15850},
    {"type": "fvg", "price_low": 15835, "price_high": 15840},
    {"type": "ob", "price_low": 15830, "price_high": 15835}
  ],
  "expected_signal": {
    "should_trigger": true,
    "entry_range": [15838, 15842],
    "confidence_min": 0.7
  }
}
```
- **description:** Контрольный датасет с ground truth для валидации детекторов

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│   ACCEPTANCE TEST DATASET (Control Set)        │
├────────────────────────────────────────────────┤
│  • 20-50 размеченных скриншотов (ground truth) │
│  • Позитивные cases (должен детектировать)     │
│  • Негативные cases (НЕ должен детектировать)  │
│  • Edge cases (граничные условия)              │
│  • Manual validation трейдером (acceptance)    │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Test reports + Precision/Recall metrics
- **data_type:** JSON (test results with metrics)
- **params:** cases_tested, precision, recall, f1_score, failed_cases[]
- **format:**

json

`{
  "dataset": "acceptance_test_v1",
  "cases_tested": 25,
  "results": {
    "true_positives": 18,
    "false_positives": 2,
    "true_negatives": 4,
    "false_negatives": 1,
    "precision": 0.90,
    "recall": 0.95,
    "f1_score": 0.92
  },
  "failed_cases": [
    {
      "case_id": "case_012",
      "issue": "Missed FVG (false negative)",
      "reason": "Gap size 0.18% < threshold 0.2%"
    }
  ],
  "acceptance_status": "pass"
}`

- **description:** Метрики качества детекторов на контрольном датасете

**logic_notes:**

- "Ground truth: размечен вручную трейдером - 'золотой стандарт' для сравнения"
- "Positive cases: где сетап действительно есть и должен быть найден"
- "Negative cases: где визуально похоже, но сетап НЕ валидный (детектор НЕ должен срабатывать)"
- "Acceptance criteria: precision >0.85, recall >0.80 для базовых детекторов"
- "Manual review: трейдер проверяет failed cases и решает - это bug детектора или проблема ground truth"
- "ДОБАВЛЕНО: version tracking - датасет версионируется, при улучшении детекторов добавляются новые cases"

---

## МОДУЛЬ 2.15 — UX / Non-dev Interfaces

### Подмодуль 2.15.1 — Streamlit Admin Panel

**submodule_name:** "2.15.1 Streamlit Admin Panel"

**inputs:**

- **from_source:** USER_REQUEST (через web browser) + DATABASE (data for display)
- **data_type:** HTTP requests + SQL queries
- **params:** page_name, user_action, filters{}
- **format:**

python

`*# Streamlit app structure:# app.py (main)# pages/#   ├── 1_Backtest_Runner.py#   ├── 2_Live_Monitor.py#   ├── 3_Results_Viewer.py#   ├── 4_Rule_Editor.py#   ├── 5_Labeling_Tool.py#   └── 6_Analytics_Dashboard.py*
```
- **description:** Структура Streamlit multi-page приложения

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│     STREAMLIT ADMIN PANEL                      │
├────────────────────────────────────────────────┤
│  • Page 1: Start Backtest / Live Scan          │
│  • Page 2: View Flow Runs (Prefect integration)│
│  • Page 3: Results Viewer (backtest reports)   │
│  • Page 4: Rule Editor (YAML editing)          │
│  • Page 5: Labeling Tool (trades marking)      │
│  • Page 6: Analytics Dashboard (charts)        │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Prefect (flow triggers) + DATABASE (updates) + User browser (UI updates)
- **data_type:** HTML (rendered UI) + JSON (API responses)
- **params:** page_state, user_actions_log
- **format:**

python

`*# Example: Backtest Runner page*
import streamlit as st
from prefect import get_client

st.title("🚀 Backtest Runner")

*# Inputs*
symbol = st.selectbox("Symbol", ["GER40", "EURUSD", "GBPUSD"])
timeframe = st.selectbox("Timeframe", ["M5", "M15", "H1"])
start_date = st.date_input("Start Date")
end_date = st.date_input("End Date")
setup = st.selectbox("Setup", get_available_setups())

*# Action*
if st.button("Run Backtest"):
    with st.spinner("Running backtest..."):
        run_id = trigger_backtest_flow(symbol, timeframe, start_date, end_date, setup)
        st.success(f"Backtest started! Run ID: {run_id}")
        st.markdown(f"[View in Prefect](http://localhost:4200/runs/{run_id})")`

- **description:** Интерактивный UI для управления системой без кода

**logic_notes:**

- "Multi-page app: каждая страница - отдельный файл в pages/ (Streamlit auto-discovery)"
- "Prefect integration: st.button → API call to Prefect для запуска flows"
- "Real-time updates: polling Prefect API для отображения flow status (running/completed/failed)"
- "Rule Editor: Monaco editor widget для YAML editing с syntax highlighting"
- "Labeling Tool: grid view с PNG preview + кнопки ✅/❌/⚠️"
- "ДОБАВЛЕНО: user session management - каждый user имеет свои настройки и фильтры (сохраняются в session state)"

### Подмодуль 2.15.2 — Rule Editor (YAML UI)

**submodule_name:** "2.15.2 Rule Editor (YAML UI)"

**inputs:**

- **from_source:** USER_REQUEST (через Streamlit) + Rule & Version Registry (existing rules)
- **data_type:** YAML (rule file content) + JSON (metadata)
- **params:** setup_id, version, yaml_content
- **format:**

yaml

`*# Editing in Streamlit:*
setup_id: Frank_raid_v1
version: 1.3  *# auto-incremented*
components:
  - Detect_Sessions:
      session: Frankfurt
  - Detect_FVG:
      timeframe: M1
      min_gap_pct: 0.3  *# changed from 0.2*
  - Detect_OB:
      proximity_pips: 5
rules:
  - condition: "Frankfurt raid AND reverse AND inversion fvg m1"
targets:
  tp: 2.0
  sl: 1.0
```
- **description:** YAML контент правила для редактирования

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       RULE EDITOR (YAML UI)                    │
├────────────────────────────────────────────────┤
│  • List existing rules (с версиями)            │
│  • Select rule → load YAML в editor            │
│  • Monaco editor с syntax highlighting         │
│  • Validation перед сохранением                │
│  • Save as new version (автоинкремент)         │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Rule & Version Registry (новый YAML файл + DB record) + Versioning Module
- **data_type:** YAML file + JSON (version metadata)
- **params:** setup_id, new_version, file_path, changes_summary
- **format:**

json

`{
  "setup_id": "Frank_raid_v1",
  "old_version": "v1.2",
  "new_version": "v1.3",
  "file_path": "rules/Frank_raid_v1/v1.3.yaml",
  "changes": [
    {
      "field": "components.Detect_FVG.min_gap_pct",
      "old_value": 0.2,
      "new_value": 0.3
    }
  ],
  "edited_by": "trader_1",
  "timestamp": "2025-10-31T15:00:00Z",
  "reason": "Increased min_gap to reduce false positives"
}`

- **description:** Сохранённая новая версия правила с changelog

**logic_notes:**

- "Monaco editor (streamlit-monaco): web-based YAML editor с подсветкой синтаксиса"
- "Validation: перед сохранением парсинг YAML → проверка что все components существуют"
- "Auto-increment version: v1.2 → v1.3 автоматически при сохранении"
- "Reason field: обязательное текстовое поле 'Почему изменено' для future reference"
- "Preview mode: возможность test run правила на sample data перед сохранением"
- "ДОБАВЛЕНО: diff viewer - показ изменений между версиями side-by-side"

---

## МОДУЛЬ 2.16 — Feedback Loop & Continuous Learning

### Подмодуль 2.16.1 — Signal Feedback Collector

**submodule_name:** "2.16.1 Signal Feedback Collector"

**inputs:**

- **from_source:** USER_REQUEST (✅/❌ feedback через Streamlit или Telegram) + DATABASE (signal records)
- **data_type:** JSON (feedback event)
- **params:** signal_id, user_feedback, comment (optional)
- **format:**

json

`{
  "signal_id": "sig_live_001",
  "symbol": "GER40",
  "timestamp": "2025-10-31T10:15:00Z",
  "signal_data": {
    "entry": 15840, "sl": 15800, "tp": 15900,
    "confidence": 0.75, "ml_score": 0.68
  },
  "user_feedback": "approved",
  "feedback_type": "taken_trade",
  "user_comment": "Excellent setup, clean entry",
  "trade_result": null,  # will be updated later
  "feedback_by": "trader_1",
  "feedback_timestamp": "2025-10-31T10:20:00Z"
}
```
- **description:** Feedback от трейдера на live signal

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│     SIGNAL FEEDBACK COLLECTOR                  │
├────────────────────────────────────────────────┤
│  • Streamlit UI: ✅ Took Trade / ❌ Skipped    │
│  • Telegram inline buttons для feedback        │
│  • Optional comment field                      │
│  • Сохранение feedback в labels/ + DB          │
│  • Связь signal → feedback → trade_result      │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** DATABASE (feedback table) + ChromaDB (metadata update) + Learning Module (training data)
- **data_type:** JSON (feedback record)
- **params:** signal_id, feedback, comment, linked_to_training_set
- **format:**

json

`{
  "feedback_id": "fb_001",
  "signal_id": "sig_live_001",
  "feedback": "approved",
  "comment": "Excellent setup",
  "trade_taken": true,
  "trade_result": {
    "outcome": "win",
    "pnl": +60.0,
    "exit_time": "2025-10-31T12:30:00Z",
    "exit_reason": "TP_hit"
  },
  "feedback_by": "trader_1",
  "timestamp": "2025-10-31T10:20:00Z",
  "added_to_training": true
}`

- **description:** Полный feedback record с результатом сделки

**logic_notes:**

- "Two-stage feedback: 1) immediate (took/skipped), 2) later (trade result после закрытия)"
- "Telegram inline buttons: быстрый способ дать feedback прямо из уведомления"
- "Comment optional: но рекомендуется для качественных insights"
- "Training data: approved signals с trade_result автоматически добавляются в training dataset"
- "Feedback stats: используются для Rule Profiler (winrate по rule versions)"
- "ДОБАВЛЕНО: disagreement tracking - если user skipped но ML score high → пометить для review"

### Подмодуль 2.16.2 — Policy Update Manager

**submodule_name:** "2.16.2 Policy Update Manager"

**inputs:**

- **from_source:** Learning Module (анализ feedback + backtest results) + Rule Profiler (param sensitivity)
- **data_type:** JSON (suggested changes)
- **params:** setup_id, current_version, suggested_changes[], confidence_in_change
- **format:**

json

`{
  "setup_id": "Frank_raid_v1",
  "current_version": "v1.2",
  "analysis_period": ["2025-08-01", "2025-10-31"],
  "analysis_summary": {
    "total_signals": 156,
    "user_taken": 89,
    "wins": 58,
    "losses": 31,
    "winrate": 0.65,
    "avg_rr": 1.85
  },
  "suggested_changes": [
    {
      "parameter": "components.Detect_FVG.min_gap_pct",
      "current_value": 0.2,
      "suggested_value": 0.25,
      "rationale": "Signals with gap >0.25% have 72% winrate vs 58% for 0.2-0.25%",
      "expected_improvement": "+7% winrate, -15% signal count",
      "confidence": 0.82
    }
  ],
  "recommendation": "create_draft_version",
  "requires_manual_approval": true
}
```
- **description:** Автоматически сгенерированные предложения по улучшению правил

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│     POLICY UPDATE MANAGER                      │
├────────────────────────────────────────────────┤
│  • Анализ feedback + backtest stats            │
│  • Генерация suggested parameter tweaks        │
│  • Сохранение как draft (НЕ auto-deploy)       │
│  • Manual approval required от трейдера        │
│  • A/B testing option (старая vs новая версия) │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Rule & Version Registry (draft version) + Streamlit UI (review panel) + DATABASE (suggestions log)
- **data_type:** YAML (draft rule) + JSON (suggestion metadata)
- **params:** suggestion_id, setup_id, draft_version, approval_status
- **format:**

json

`{
  "suggestion_id": "sugg_001",
  "setup_id": "Frank_raid_v1",
  "draft_version": "v1.3_draft",
  "draft_file": "rules/Frank_raid_v1/v1.3_draft.yaml",
  "suggested_changes": [...],
  "status": "pending_review",
  "created_at": "2025-10-31T16:00:00Z",
  "review_deadline": "2025-11-07T00:00:00Z",
  "approval_required_by": "trader_1",
  "approval_status": null,
  "notes": "System suggests increasing FVG gap threshold based on recent performance"
}`

- **description:** Draft версия правила ожидающая review трейдером

**logic_notes:**

- "НИКОГДА не auto-deploy: все изменения правил требуют manual approval трейдера"
- "Draft versions: сохраняются с суффиксом _draft, не используются в live/backtest до approval"
- "Rationale обязателен: каждое предложение должно иметь статистическое обоснование"
- "Confidence threshold: предложения с confidence <0.7 помечаются как 'low confidence' - требуют особого внимания"
- "A/B testing mode: возможность запуска backtest на одних и тех же данных со старой и новой версией для сравнения"
- "Review deadline: если через 7 дней не было review - reminder в Telegram"
- "ДОБАВЛЕНО: rollback plan - если после deployment новой версии performance падает - автоматический rollback к предыдущей"

### Подмодуль 2.16.3 — Continuous Improvement Tracker

**submodule_name:** "2.16.3 Continuous Improvement Tracker"

**inputs:**

- **from_source:** DATABASE (все backtest results, feedback, rule versions за всю историю)
- **data_type:** SQL aggregation queries + time-series data
- **params:** metric_name, time_period, grouping (by_setup|by_month|by_version)
- **format:**

json

`{
  "tracking_period": ["2025-01-01", "2025-10-31"],
  "metrics_tracked": [
    "avg_winrate_by_month",
    "total_signals_generated",
    "user_approval_rate",
    "ml_model_accuracy_trend",
    "rule_versions_created",
    "feedback_volume"
  ],
  "grouping": "by_month"
}
```
- **description:** Конфигурация для трекинга метрик улучшения системы

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│   CONTINUOUS IMPROVEMENT TRACKER               │
├────────────────────────────────────────────────┤
│  • Трекинг winrate trends (по месяцам)         │
│  • ML model performance evolution              │
│  • Rule versions effectiveness comparison      │
│  • User feedback volume & quality              │
│  • System learning curve visualization         │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Analytics Dashboard (Streamlit) + Monthly Reports (PDF/Notion) + DATABASE (metrics history)
- **data_type:** JSON (metrics snapshot) + Charts (Plotly)
- **params:** period, metrics{}, improvement_indicators[], charts[]
- **format:**

json

`{
  "report_period": "2025-10-01 to 2025-10-31",
  "metrics": {
    "avg_winrate": {
      "current_month": 0.63,
      "previous_month": 0.59,
      "change": +0.04,
      "trend": "improving"
    },
    "ml_model_auc": {
      "current": 0.74,
      "baseline_3months_ago": 0.72,
      "improvement": +0.02
    },
    "feedback_volume": {
      "signals_with_feedback": 89,
      "total_signals": 156,
      "feedback_rate": 0.57
    },
    "rule_iterations": {
      "Frank_raid": 3,
      "Asia_fvg_break": 2,
      "total_versions_created": 5
    }
  },
  "improvement_indicators": [
    {
      "indicator": "Learning velocity",
      "value": "High",
      "explanation": "5 rule versions in 1 month with clear performance improvement"
    },
    {
      "indicator": "Data quality",
      "value": "Good",
      "explanation": "57% feedback rate, sufficient for training"
    }
  ],
  "charts": [
    {
      "type": "line",
      "title": "Winrate Trend (6 months)",
      "data": [[0.55], [0.57], [0.59], [0.61], [0.59], [0.63]]
    }
  ]
}
```
- **description:** Отчёт о непрерывном улучшении системы

**logic_notes:**
- "Monthly snapshots: каждый месяц сохраняется snapshot метрик для long-term trend analysis"
- "Baseline comparison: текущие метрики сравниваются с baseline (первый месяц или 3 месяца назад)"
- "Improvement indicators: качественная оценка (High/Medium/Low) learning velocity системы"
- "Trend detection: автоматическое определение improving/stable/declining trends"
- "Alerts: если winrate падает 2 месяца подряд - alert в Telegram для investigation"
- "ДОБАВЛЕНО: knowledge base growth - трекинг размера ChromaDB (embeddings count) как индикатор накопления знаний"

---`

---

## ЗАКЛЮЧИТЕЛЬНЫЕ ЗАМЕЧАНИЯ

Добавленные элементы (не были явно указаны, но необходимы для полноты архитектуры)

**ДОБАВЛЕНО в различных модулях:**

1. **InMemoryBuffer (2.2.5.1)** - критичен для live режима, не был детально описан в исходных документах
2. **Schema Validator (2.4.8)** - необходим для гарантии целостности данных между модулями
3. **Decision Reconciler (2.8.7)** - агрегация трёх источников (Python, LLM, ML) в единое решение
4. **Prompt Version Registry (2.8.4)** - версионирование промптов для A/B testing
5. **Prompt Testing Harness (2.8.5)** - QA для промптов
6. **API Adapter (2.8.6)** - обработка rate limits и retry логики
7. **LLM Call Logger (2.8.9)** - трекинг стоимости и usage
8. **Safety Checks (2.8.8)** - валидация LLM outputs перед применением
9. **Image Embedding Pipeline (2.9.2.1)** - CLIP embeddings для PNG
10. **JSON Schema Embedding (2.9.2.2)** - text embeddings для JSON данных
11. **Secrets Management (2.12.1)** - безопасное хранение credentials
12. **Access Control (2.12.2)** - RBAC для multi-user
13. **Configuration Management (2.12.3)** - централизованный config
14. **Monitoring & Healthchecks (2.13.3)** - system health monitoring
15. **Continuous Improvement Tracker (2.16.3)** - долгосрочный трекинг прогресса

### Важные взаимосвязи (критичные для понимания)

**Поток данных BACKTEST:**
```
User Request → Setup Manager (rule eval) → Data Ingest (MT5/CSV) → Data Processor → Market Tools (детекторы) 
→ Backtester Core → Visualizer (PNG) 
→ Vision Adapter (LLM analysis) → Annotation Service → Notion Upload
```

**Поток данных LIVE:**
```
Scheduler (1 min) → Setup Manager → MT5 Loader (incremental) → InMemoryBuffer → Data Processor 
→ Market Tools → ML Scoring → Decision Reconciler 
→ IF approved: Visualizer → LLM → Telegram (<30 sec)
```

**Поток обучения:**
```
Backtests + Live Signals → User Feedback → Labeling Tool → ChromaDB (embeddings) 
→ Training Pipeline → ML Model → Deployment → Live Scoring → Feedback (cycle)

**Критичные временные ограничения:**

- Live scan execution: **<30 секунд** от close свечи до Telegram уведомления
- InMemoryBuffer: критичен для достижения этого требования
- API rate limits: OpenAI 10 RPM, Telegram 20 msg/min
- Backtest execution: зависит от размера dataset, но должен быть <15 минут для 6 месяцев M15