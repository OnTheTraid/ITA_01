# ITA Prefect ASCII Live Flow (v1.1)

Горизонтальная ASCII-схема потока задач Prefect для режима **Live Trading**.
Включает FastAPI, Vision Interpreter, Feedback и ML REST API.

```
┌──────────────┐       ┌──────────────┐       ┌────────────────┐       ┌────────────────────┐       ┌─────────────────────┐
│ Trader Input │ --->  │ Streamlit UI │ --->  │ FastAPI Backend│ --->  │ Setup Manager      │ --->  │ Prefect Orchestrator│
│ symbol, mode │       │ click 'Start'│       │ build JSON     │       │ parse YAML → JSON  │       │ launch live_flow    │
└──────────────┘       └──────────────┘       └────────────────┘       └────────────────────┘       └─────────────────────┘
                                                                                                           │
                                                                                                           ▼
                                                                                                  ┌─────────────────────┐
                                                                                                  │ Core Data Engine    │
                                                                                                  │ MT5 Live → [DF]     │
                                                                                                  │ clean, normalize    │
                                                                                                  │ output [DF]         │
                                                                                                  └─────────────────────┘
                                                                                                           │
                                                                                                           ▼
                                                                                                  ┌─────────────────────┐
                                                                                                  │ Market Tools        │
                                                                                                  │ Dispatcher          │
                                                                                                  │ detect_* static/    │
                                                                                                  │ dynamic → [JSON]    │
                                                                                                  └─────────────────────┘
                                                                                                           │
                                                                                                           ▼
                                                                                                  ┌─────────────────────┐
                                                                                                  │ GPT Vision Flow     │
                                                                                                  │ Vision Interpreter  │
                                                                                                  │ analyze screenshot  │
                                                                                                  │ annotate → [JSON]   │
                                                                                                  └─────────────────────┘
                                                                                                           │
                                                                                                           ▼
                                                                                                  ┌─────────────────────┐
                                                                                                  │ Decision Reconciler │
                                                                                                  │ merge LLM + Python  │
                                                                                                  │ → signal [JSON]     │
                                                                                                  └─────────────────────┘
                                                                                                           │
                                                                                                           ▼
                                                                                                  ┌─────────────────────┐
                                                                                                  │ Telegram Notifier   │
                                                                                                  │ send alert + image  │
                                                                                                  │ → [JSON][IMG]       │
                                                                                                  └─────────────────────┘
                                                                                                           │
                                                                                                           ▼
                                                                                                  ┌─────────────────────┐
                                                                                                  │ Feedback Collector  │
                                                                                                  │ trader confirms     │
                                                                                                  │ → label [JSON]      │
                                                                                                  │ → ML Service REST   │
                                                                                                  └─────────────────────┘
                                                                                                           │
                                                                                                           ▼
                                                                                                  ┌─────────────────────┐
                                                                                                  │ ML Service API      │
                                                                                                  │ receive labels,     │
                                                                                                  │ train embeddings,   │
                                                                                                  │ update vector DB    │
                                                                                                  └─────────────────────┘
```

**Типы данных:**  
- `[JSON]` — обмен между Prefect задачами.  
- `[DF]` — рыночные данные.  
- `[IMG]` — скриншоты графиков.  
- `[YAML]` — трейдерские правила.  

**Основной поток:**  
Trader → Streamlit → FastAPI → Prefect → Market Tools → Vision → Decision → Telegram → Feedback → ML Service.

⚙️ Технические обозначения в схемах

| Обозначение | Значение                                |
| ----------- | --------------------------------------- |
| `[JSON]`    | стандарт обмена между тасками Prefect   |
| `[DF]`      | pandas DataFrame (OHLCV или результаты) |
| `[IMG]`     | визуализация Plotly/Dash (PNG)          |
| `[YAML]`    | трейдерские правила                     |
| `(task)`    | узел Prefect                            |
| `→`         | направление потока данных               |

