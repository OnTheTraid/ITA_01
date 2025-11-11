# 06_Backtester_Manager
Описание модуля и его назначения.
### **Backtester Manager**

**2.6.1 Backtester Core** — симуляция входов/стопов/тейков по истории с учётом исполнения (правила входа, слippage config опционально), считает P/L, RR, winrate, drawdown.

- Вход: signals + candles. Вычисляет PnL, drawdown, trade list.
- Конфиг исполнения: slippage, spread (configurable).

**2.6.2 Backtest Runner / Batch Processor** — массовое прогонка правил по набору периодов/пар с управлением очередью, логированием и сохранением отчётов в DB/Notion.

- Управление батчами (symbols × periods × rule_versions).
- Параллелизация (multiprocessing / Prefect mapped tasks).

**Backtester Core / Backtest Runner**:

- основной результат бэктеста — trades, метрики и **ссылки** на скрины (обычно `png_original` и, если есть ЛЛМ обработка то `png_annotated`).
- **Backtester Core** формирует backtest JSON и CSV trades и **включает в результат пути** к PNG.

**consume** `png_original` and `png_annotated` — включать их в backtest JSON output and `trades.csv`.

**2.6.3 Backtest Validator (QA)** — случайная выборка входов/выходов с визуальной проверкой, acceptance tests и recall/precision метриками.

- Случайная проверка N входов (визуал).
- Метрики: winrate, avg_rr, expectancy, max_drawdown.

**2.6.4** Manual backtester - реализация бектестирования для пользователя в ручном режиме по заданному временному периоду/ торговой паре/ тайм фреймах. Реализовать в Плотлай интерфейс бектестинга как на Трейдинг Вью, прокрутку свечей по очереди, быстрые переходы по сессиям/дням. Сделать возможность скриншота. На будущее - заполнение журнала Ноушен автоматически.

**Output:** backtest JSON + CSV trades + annotated PNGs per sample.

**Acceptance:** reproducible results, report contains `rule_version`, data snapshot id.

## ⚙️ ASCII схема
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
