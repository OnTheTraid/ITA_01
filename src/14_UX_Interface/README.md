# 14_UX_Interface
Описание модуля и его назначения.
### UX / Non-dev Interfaces

Интерфейсы, не связанные с разработкой.
Streamlit admin:

- Start backtest / live scan.
- Визуализация flows, открытие результатов `run_id`, label trades, approve LLM suggestions.
- Rule editor (Редактор правил): YAML editor for setups, with `save as vX`.

Для визуализации добавить Библотеку REACTFLOW


## ⚙️ ASCII схема
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