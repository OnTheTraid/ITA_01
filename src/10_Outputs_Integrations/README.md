# 10_Outputs_Integrations
Описание модуля и его назначения.
### Outputs & Integrations

Выходные данные и интеграция
**2.10.1 Notion Uploader**

Cоздаёт страницы/записи в Notion: сохраняет скрин, JSON метаданные, метрики бэктеста и ссылку на `rule_id`; поддерживает bulk uploads и ссылка traceability.

Схема Notion: `run_id, symbol, timeframe, rule_id, rule_version, winrate, rr, png_url.`

получает backtest JSON и **отправляет в Notion**: прикрепляет `png_original` и/или `png_annotated`, добавляет таблицу с результатом, то есть 
при загрузке отчёта от ЛЛМ анализа прикладывать **оба** png (ориг + аннот) и ссылку на `annotation_json`.

**2.10.2 Telegram Notifier**

Шаблоны коротких оповещений: symbol, timeframe, short comment, ссылка на Notion.

Уровни приоритета: INFO / WARN / ALERT (настраивается).

Отправляет изображения (сжатые) и короткий текст.

**2.10.3 Reporting Dashboard / Exporter**

**Streamlit** page с агрегированными метриками: по настройке, timeframe, symbol, month.

Конечные точки экспорта CSV/Excel.

**Acceptance:** Каждое оповещение должно содержать `run_id` и ссылку на Notion; журналы отправленных оповещений сохраняются.

## ⚙️ ASCII схема
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
