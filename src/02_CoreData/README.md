# 02_CoreData_IO
Описание модуля и его назначения.
### **Core Data & IO (Input/Output)**

Модуль обеспечивает импорт исторических данных графика, их очистку и подготовку:

Загрузка МТ5 данные нужна:

Для бектестов загрузить данные котировок с МТ5 и обновлять, когда я делаю бектест, скажем 1 раз в неделю. 

Для лайв торговли мне нужно обновлять данные, скажем 1 раз в минуту

| Режим | Что делает | Что требуется от Data Flow |
| --- | --- | --- |
| **Бэктестинг** | Берёт *исторические данные* (CSV или MT5), анализирует сетапы и сохраняет результаты. | Одноразовая загрузка больших объёмов данных (например, 1 год M15). Обновление раз в неделю. |
| **Лайв** | Анализирует *новые данные в реальном времени*. | Постоянный поток (или периодический запрос, каждые N минут) с MT5. Нужно уметь обновлять DataFrame частично — не всё заново. |

Подмодули

**2.2.1 Data Ingest (MT5 Connector)** — подключение к MT5, получение OHLCV/tick-данных и истории; отвечает за нормализацию временных зон и формат pandas DataFrame/JSON.

- Подключение к MT5 терминалу или чтение CSV.
- Функции: `get_ohlcv(symbol, timeframe, start, end) -> pd.DataFrame`.

**Вход/Выход:** 

вход — параметры, выход — DataFrame + сохранение CSV в `archive/raw/`.

**Acceptance:**

- DataFrame без NaN - в результирующем DataFrame **нет пустых значений** в столбцах `open, high, low, close, volume, time`. 
Правило заполнения NaN (например: "если более 50% свечи пустая — drop, иначе forward-fill"), и добавь тесты проверки отсутствия NaN.
- по OHLC, таймстампы унифицированы - привести все временные метки в **одну временну́ю зону и формат**

вернуть DataFrame с tz-aware UTC (временные метки в **одной временной зоне и формате**) - уточнить не делает ли это **Session Engine**

**2.2.2 CSV/Archive Loader** — импорт историй из CSV/экспортов (для бэктестов), включает валидацию формата и метаданные (инструмент, таймфрейм, источник).

**2.2.3 Data Processor (Cleaning & Feature Layer) -** Очищает и аналитически подготавливает данные после загрузки. Удаляет дубликаты и пропуски, корректирует временные ряды, рассчитывает технические признаки — ATR, диапазоны, волатильность, соотношение тела/тени, торговые сессии. Создаёт унифицированный, “обогащённый” DataFrame, на основе которого работают все Market Tools инструменты (Detect_DO, (Detect_sessions и др.).

«normalize_time_index»:

1. конвертировать в UTC (`df['time'] = pd.to_datetime(df['time']).dt.tz_convert('UTC')`),
2. ресемплировать в нужный tf при необходимости (`df.resample('15T', on='time').agg(...)`),
3. сортировать и дедуплицировать,
4. заполнение/удаление NaN по правилам (конфигурируемо).

Возвращает «enriched» DataFrame (с колонками `session, new_day, pdh, pdl, ...`).

В **Data Processor**: использовать сначала **InMemoryBuffer** для детекторов (быстрее), только при batch/backtest обращаться к disk cache.

- **Почему:** уменьшает I/O, ускоряет отклик live-монитора и уменьшает риск race conditions.

**Acceptance update:** описать в документе правило заполнения NaN (например: "если более 50% свечи пустая — drop, иначе forward-fill"), и добавить тесты проверки отсутствия NaN.

 **2.2.4 Session Engine** — подмодуль в **Data Processor**. Его задача — корректно определить временные рамки торговых сессий (Asia, Frankfurt, London, New York) и основные временные уровни (Daily Open, Weekly Open, NY Midnight) на основе данных MT5 и серверного времени брокера. Модуль формирует унифицированный JSON для дальнейшего использования в **Market Tools**, **Context Visualizator** и **Dash Visualizer**.

Формирует JSON: `{session_name, start, end, high, low, timezone}`.

     Дополнительные функции для лайв торговли:
**2.2.4.1** **Data Refresh Scheduler** - обновление котировок. 
Следит за расписанием (каждую минуту / раз в неделю) и триггерит `MT5 Loader`.

- Для Live режима ставишь `Every 1 minute`.
- Для Backtest — вручную, когда запускаешь тест.

Если надо полную гибкость, можно усовершенствовать.

**2.2.5** **MT5 Data Cash** - кеширование данных (Python)

Локальная кеш-система: cache key = symbol_timeframe_start_end.json. TTL configurable.

Во Flask-сервисе можно добавить кеширование. избежать лишней загрузки и ускорить обновления при лайв-анализе.

**Storage paths:** `data/cache/{symbol}_{tf}_{start}_{end}.parquet`.

- Нужен **двухуровневый кэш**:
    1. **In-memory ring buffer (оперативная память)** — для последних N свечей (и/или последних M тиков) для ultra-fast проверок и частых обновлений (подмодуль: `InMemoryBuffer` реализовать через `collections.deque`).
    2. **Persistent disk cache** — parquet/CSV для истории и восстановления (подмодуль: `OnDiskCache`).
    3. **IncrementalUpdater** (логика: get_new_from_mt5(last_ts) → append → persist async).
- **Поведение при live Trading:** на каждой итерации (каждую минуту) MT5 Loader:
    - подтягивает только **новые бары/тики**, добавляет в **InMemoryBuffer** (append), и асинхронно/периодически сохраняет snapshot на диск (перезапись / апенд в parquet).
    - **Не** перезагружать всю историю каждый раз — использовать `last_timestamp` и incremental load.

```


## ⚙️ ASCII схема
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

`┌───────────────────────────────────────────────┐
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
- **description:** Исторические OHLCV данные из оптимального источника. df_raw and meta: {source, tz, retrieved_at, rows, file_path, ingest_id}

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

