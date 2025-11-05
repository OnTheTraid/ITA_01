# 12_Config_Security
Описание модуля и его назначения.
### Security & Config

- Все ключи и пароли хранить в `.env` или Prefect Secrets (ключ OpenAI, ключ Notion, токен Telegram).
- RBAC: пока локальный — работает только на комп. машинах разработчиков.
- Audit logs: (Журналы аудита) каждое изменение правил и запуск флоу сохраняются.
- **Access control & secrets management -** Prefect Secrets, `.env` management, doc «как rotate keys».

## ⚙️ ASCII схема
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

