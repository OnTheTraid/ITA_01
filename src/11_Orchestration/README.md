# 11_Orchestration_Workflows
Описание модуля и его назначения.
### Orchestration & Workflows (Prefect 2.19)

- **Виды Flow**:
    - `backtest_flow` (запускается пользователем).
    - `live_scan_flow` (периодически или вручную).
    - `train_model_flow` (по расписанию).
- **Задачи Prefect** соответствуют модулям, перечисленным выше(Data ingest, Market Tools, Setup Manager, Backtester, Visualizer, LLM call, Notion upload).
- Регистрация deployments для ручного запуска и планирования - manual trigger + schedule.

**Acceptance:** каждый Flow включает в себя тесты, повторные попытки, логирование и метрики.
 

## ⚙️ ASCII схема
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