# ITA Prefect ASCII Backtest Flow (v1.1)

Горизонтальная ASCII-схема потока задач Prefect для режима **Backtest**.
Отражает все основные этапы, типы данных и взаимодействие модулей ITA.

```
┌──────────────┐       ┌──────────────┐       ┌────────────────┐       ┌─────────────────────┐      ┌──────────────────────┐
│ Trader Input │ --->  │ FastAPI Layer│ --->  │ Setup Manager  │ --->  │ Prefect Orchestrator│ ---> │ Data Ingest / Loader │
│ setup_name,  │       │ validate &   │       │ parse YAML →   │       │ backtest_flow start │      │ CSV/MT5 → [DF]       │
│ symbol, tf   │       │ build JSON   │       │ JSON context   │       │ state/logs monitor  │      │ normalize data       │
└──────────────┘       └──────────────┘       └────────────────┘       └─────────────────────┘      └──────────────────────┘
                                                                                                           │
                                                                                                           ▼
                                                                                                  ┌─────────────────────┐
                                                                                                  │ Market Tools        │
                                                                                                  │ Dispatcher          │
                                                                                                  │ static/dynamic YAML │
                                                                                                  │ detect_* → [JSON]   │
                                                                                                  └─────────────────────┘
                                                                                                           │
                                                                                                           ▼
                                                                                                  ┌─────────────────────┐
                                                                                                  │ Backtester Manager  │
                                                                                                  │ auto_mode run()     │
                                                                                                  │ calc RR, winrate,   │
                                                                                                  │ drawdown → [JSON]   │
                                                                                                  └─────────────────────┘
                                                                                                           │
                                                                                                           ▼
                                                                                                  ┌─────────────────────┐
                                                                                                  │ Visualizer Engine   │
                                                                                                  │ Plotly/Dash render  │
                                                                                                  │ annotate charts →   │
                                                                                                  │ PNG + JSON summary  │
                                                                                                  └─────────────────────┘
                                                                                                           │
                                                                                                           ▼
                                                                                                  ┌─────────────────────┐
                                                                                                  │ Notion / Telegram   │
                                                                                                  │ send report + image │
                                                                                                  │ → [JSON][IMG]       │
                                                                                                  └─────────────────────┘
                                                                                                           │
                                                                                                           ▼
                                                                                                  ┌─────────────────────┐
                                                                                                  │ Feedback Collector  │
                                                                                                  │ trader rating [INT] │
                                                                                                  │ comment [STR]       │
                                                                                                  │ → ML labels [JSON]  │
                                                                                                  └─────────────────────┘
```

**Типы данных:**  
- `[JSON]` — обмен между тасками Prefect.  
- `[DF]` — pandas DataFrame (исторические данные).  
- `[IMG]` — визуализация графиков.  
- `[YAML]` — правила трейдера.  

**Ключевые зависимости:**  
- Setup Manager → Market Tools → Backtester → Visualizer.  
- Все шаги управляются Prefect Orchestrator с логированием состояния.

⚙️ Технические обозначения в схемах

| Обозначение | Значение                                |
| ----------- | --------------------------------------- |
| `[JSON]`    | стандарт обмена между тасками Prefect   |
| `[DF]`      | pandas DataFrame (OHLCV или результаты) |
| `[IMG]`     | визуализация Plotly/Dash (PNG)          |
| `[YAML]`    | трейдерские правила                     |
| `(task)`    | узел Prefect                            |
| `→`         | направление потока данных               |

