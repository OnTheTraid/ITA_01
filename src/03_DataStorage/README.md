# 03_DataStorage_Versioning
Описание модуля и его назначения.
### **Data Storage & Versioning**

**2.3.1 Persistent Store (Database / Object Storage)** — хранит все исходные свечи, скрины, JSON-аннотации, модели и результаты; поддерживает метаданные и версии файлов.

- Файловая структура + optional DB (sqlite/postgres) для метаданных.
- Файлы: candles (parquet/csv), pngs, json results, models.

**2.3.2 Rule & Version Registry** — хранит версии правил/сетапов с уникальными IDs и метаданными (автор, дата, параметры), обеспечивает трассируемость бэктестов (*возможность проследить всю цепочку действий*). 

- Репозиторий правил (Notion table or YAML files).
- Каждый setup: `setup_id`, `version`, `author`, `params`, `date_created`, `active_flag`.

**Contract:** `rules/{setup_id}/v{X}.yaml`.

**2.3.3 Run Snapshot / Provenance** 

- snapshot данных (hash данных, data range), `git_commit_hash` of code, `rule_version`, `env` — прикреплять к каждому backtest/live run. Это обеспечивает воспроизводимость.

**2.3.4 Data retention / purge policy**

Добавить правило удаления старых raw/annotated PNG / vector pruning.

**Acceptance:** бэктест всегда указывает `setup_id` и `rule_version` в своих результатах.


## ⚙️ ASCII схема
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