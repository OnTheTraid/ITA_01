# Архитектура проекта

**Архитектура проекта и структура репозитория**.

Мы работаем с системой из **Prefect + Streamlit + LangChain + MT5 API + GPT Vision**, и нам нужна чистая, масштабируемая структура.

**Готовая структура**, применимая для продакшн-агента, с пояснениями по каждой папке и файлами, которые должны быть внутри.

---

## 🧱 1. Общая структура репозитория

структура проекта ITA_01
ITA_01/
│
├── .gitignore                  # правила исключения (venv, data/, logs/ и т.д.)
├── README.md                   # описание проекта, инструкция запуска
├── LICENSE                     # MIT (или другая, по выбору)
├── requirements.txt             # зависимости
├── setup.cfg                    # конфигурация пакета / форматтера
├── config.example.env           # пример .env
│
├── docs/                        # документация и схемы
│   ├── architecture.md           # архитектура системы
│   ├── Decision_Log.md           # Журнал технических решений
│   ├── ascii_schemes.md          # ASCII-схемы всех модулей
│   ├── module_list.md            # краткое описание всех модулей
│   └── design_notes/
│       ├── LangChain_integration.md
│       └── Prefect_strategy.md
│
├── scripts/                     # скрипты для разработчиков
│   ├── init_env.bat              # создать venv и установить зависимости
│   ├── run_local.ps1             # запуск локального Prefect-агента
│   └── run_streamlit.ps1         # запуск Streamlit-панели
│
├── setup_rules/                 # хранение YAML правил сетапов, это не код, потому отдельно
│   └── Frank_raid/
│       └── v1.2.yaml
│
├── data/                        # данные (в .gitignore)
│   ├── archive/                  # исторические CSV, ZIP
│   ├── cache/                    # кэш живых данных MT5
│   ├── feedback_labels           # Feedback трейдера о работе ЛЛМ, данные для обучения
│   └── examples/                 # примеры для тестов и демонстраций
│
├── exchange/                    # обмен файлами между Prefect и Vision
│   ├── to_vision/                # PNG/JSON для анализа GPT-Vision
│   ├── annotated/                # файлы после аннотации Vision
│   └── archive/                  # архив старых анализов
│
├── logs/                         # логи (в .gitignore)
│   ├── prefect/                   # Prefect-логи
│   ├── training/                  # обучение моделей
│   └── runtime/                   # runtime / debug логи
│
├── flows/                        # пайплайны Prefect
│   ├── backtest_flow.py           # основной флоу для бэктестов
│   ├── live_flow.py               # флоу для лайв-анализа и сигналов
│   ├── data_refresh_flow.py       # обновление кэша/данных
│   └── __init__.py
│
├── configs/                      # настройки и шаблоны
│   ├── config.yaml                # глобальная конфигурация проекта
│   ├── default.yaml               # основные настройки проекта
│   ├── secrets_template.yaml      # пример API-ключей и токенов
│   ├── logging.yaml               # логирование
│   └── __init__.py
│
├── assets/                       # статические файлы
│   ├── icons/
│   ├── screenshots/
│   ├── styles/
│   └── prompts/                   # промпты LLM и шаблоны
│
├── notebooks/                    # эксперименты и анализ
│   ├── dev_analysis.ipynb
│   ├── feature_experiments.ipynb
│   └── model_testing.ipynb
│
├── tests/                        # тестирование
│   ├── unit/                      # модульные тесты
│   ├── integration/               # интеграционные тесты
│   └── __init__.py
│
└── src/                          # исходный код проекта
    ├── 01_UserRequest/
    ├── 02_CoreData/
    ├── 03_DataStorage/
    ├── 04_MarketTools/
    ├── 05_SetupManager/
    ├── 06_BacktestManager/
    ├── 07_Visualization/
    ├── 08_GPT_VisionFlow/
    ├── 09_Learning_Module/
    ├── 10_Outputs_Integrations/
    ├── 11_Orchestration/
    ├── 12_Config_Security/
    ├── 13_QA_Testing/
    ├── 14_UX_Interface/
    ├── 15_Feedback_Learning/
    └── utils/

📘 Пояснения по основным папкам
Папка	Назначение
src/	весь Python-код (модули и подмодули). Иерархия 01–15 соответствует номерам модулей проекта.
flows/	orchestration-файлы Prefect (каждый Flow собирает функции из src/).
configs/	YAML-конфиги и шаблоны токенов.
data/	хранение историй, кэша, временных данных.
exchange/	обмен PNG/JSON между Python-ядром и GPT-Vision.
assets/	иконки, шаблоны промптов, изображения.
docs/	архитектура, схемы, описания и другие записи по проекту.
scripts/	сервисные .bat/.ps1 для запуска окружения и UI.
logs/	логи всех систем.
tests/	pytest-тесты.
notebooks/	эксперименты Jupyter, обучение, анализ данных.
utils/	общие инструменты (декораторы, логирование и т.д.).

---

Полный перечень скриптов (разделён по приоритетам)
🧩 1. Core (ядро проекта)

Базовая инфраструктура, без неё ничего не запустится.

Папка: src/core/

config.py               ← глобальные пути, токены, env
scheduler.py            ← Prefect scheduler (cron/periodic запуск)
orchestrator.py         ← связывает все флоу (backtest_flow, live_flow)
__init__.py

utils/
├── logger.py           ← цветные логи через loguru/rich
├── time_utils.py       ← таймзоны, форматирование timestamp
├── file_io.py          ← чтение/запись JSON, CSV, YAML
├── decorators.py       ← @retry, @timed, @catch_errors
└── __init__.py


📌 Нужно написать: все файлы.
(они короткие, до 50–70 строк каждый)

📊 2. Data Layer (загрузка и подготовка данных)

Папка: src/data/

ingest/
├── mt5_connector.py       ← подключение к MetaTrader 5, загрузка котировок
├── csv_loader.py          ← импорт историй CSV/экспортов
├── data_cache.py          ← кэширование DataFrame локально (parquet)
└── __init__.py

processor/
├── cleaner.py             ← удаление NaN, выравнивание таймстампов
├── session_engine.py      ← сессии, DO/WO уровни
├── features.py            ← индикаторы, ATR, FVG_gap и пр.
└── __init__.py


📌 Нужно написать: все 6.
MT5-коннектор можно адаптировать из твоего уже существующего кода.

💾 3. Data Storage & Versioning

Папка: src/storage/

persistent_store.py      ← хранилище данных и моделей (локально/DB)
version_registry.py      ← версия правил/сетапов, rule_id tracking
cache_manager.py         ← кэш данных для live режима
__init__.py


📌 Нужно написать: все 3.
(это короткие классы, реализуют save/load в /data/)

📈 4. Market Tools (аналитика графика)

Папка: src/market_tools/

dispatcher.py             ← выбирает нужные детекторы под rule
detectors/
├── detect_sessions.py     ← сессии (Asia/London/NY)
├── detect_liquidity.py    ← high/low уровни
├── detect_opening_levels.py
├── detect_fvg.py          ← fair value gap
├── detect_ob.py           ← order blocks
├── detect_bos_choch.py    ← BOS/CHOCH
└── __init__.py


📌 Нужно написать: dispatcher + хотя бы 3 базовых детектора (остальные позже).
(по сути — функции, возвращающие JSON-структуры зон и уровней)

⚙️ 5. Setup Manager / Rule Logic

Папка: src/rules/

setup_manager.py         ← связывает правила с детекторами и данными
yaml_rules/
├── ib_raid_v1.yaml
├── fvg_reversal_v2.yaml
├── asia_sweep_v1.yaml
└── __init__.py
__init__.py


📌 Нужно написать: setup_manager.py и минимум 1 YAML-файл (правило).

🧪 6. Backtester Manager

Папка: src/backtester/

core.py           ← расчёт P/L, RR, winrate
runner.py         ← массовые прогоны правил
validator.py      ← проверка результатов, метрики QA
__init__.py


📌 Нужно написать: все 3.

🎨 7. Visualization Engine

Папка: src/visualizer/

dash_visualizer.py       ← графики Plotly (OHLC + зоны)
visual_formatter.py      ← постобработка (обрезка, стиль)
annotation_service.py    ← приём анотаций от GPT Vision и отрисовка
__init__.py


📌 Нужно написать: все 3.
(ты уже писал тест Dash-визуализацию, это готовая база)

🤖 8. LLM Integration (LangChain + GPT)

Папка: src/llm/

prompt_manager.py         ← шаблоны и формирование промптов
api_adapter.py            ← взаимодействие с OpenAI/Gemini API
vision_adapter.py         ← GPT-Vision обработка изображений
memory_manager.py         ← контекстная память LangChain Memory
embeddings.py             ← text+image эмбеддинги (CLIP/OpenAI)
__init__.py


📌 Нужно написать: все 5 (важно для обучения).
(эти файлы — сердце твоего “Learning Module”)

🧬 9. Learning / Memory Subsystem

Папка: src/learning/

labeling_manager.py       ← ручная разметка скринов, метки
vector_db.py              ← ChromaDB интеграция
trainer.py                ← обучение моделей (few-shot / fine-tune)
scorer.py                 ← runtime оценка вероятности успеха
__init__.py


📌 Нужно написать: минимум vector_db.py и scorer.py сразу,
trainer и labeling можно позже.

📤 10. Outputs & Integrations

Папка: src/outputs/

notion_uploader.py        ← API интеграция с Notion
telegram_notifier.py      ← уведомления с PNG и текстом
reporting_dashboard.py    ← статистика и отчёты
exporter.py               ← CSV/Excel выгрузки
__init__.py


📌 Нужно написать: notion_uploader и telegram_notifier сразу.
(другие — по мере надобности)

💻 11. Streamlit UI

Папка: src/ui/

streamlit_app.py          ← главный дашборд
components/
├── backtest_panel.py     ← панель запуска бэктеста
├── live_panel.py         ← панель лайв-анализа
├── results_panel.py      ← панель результатов
└── __init__.py
__init__.py


📌 Нужно написать: streamlit_app.py и хотя бы backtest_panel.

🔁 12. Feedback Loop

Папка: src/feedback/

feedback_loop.py          ← сбор фидбэка трейдера
policy_updater.py         ← обновление YAML правил по статистике
__init__.py


📌 Нужно написать: оба, чтобы реализовать обучаемость по результатам.

🧰 13. QA / Tests

Папка: src/qa/

tests/
├── test_detectors.py
├── test_backtester.py
├── test_ingest.py
├── test_llm_integration.py
└── __init__.py

ci_pipeline.yaml          ← пайплайн проверки (pytest + lint)
__init__.py


📌 Нужно написать: минимум 2 теста (ingest + backtester).

⚡ 14. Flows (Prefect DAGs)

Папка: flows/

backtest_flow.py         ← orchestration цепочки бэктеста
live_flow.py              ← лайв-анализ
data_refresh_flow.py      ← обновление данных
__init__.py


📌 Нужно написать: все три (они короткие — по 100–150 строк).

⚙️ 15. Configs

Папка: configs/

default.yaml              ← глобальные настройки проекта
secrets_template.yaml     ← пример структуры токенов
logging.yaml              ← логгинг формат
__init__.py


📌 Нужно создать: всё.
(default.yaml — критически важен для параметров Prefect/DB/Paths)



---

## ⚙️ 3. Дополнительные файлы

| Файл                    | Назначение                                   |
| ---                     | ---                                          |
| `.env`                  | ключи API и токены                           |
| `requirements.txt`      | зависимости                                  |
| `pyproject.toml`        | конфигурация сборки                          |
| `Makefile`              | автоматизация (`make backtest`, `make live`) |
| `README.md`             | документация                                 |
| `PREFECT_DEPLOYMENT.md` | описание развёртывания и Flow configs        |

---

## 🧩 4. Ключевые практики для архитектора

- **Каждый модуль независим** — можно тестировать отдельно.
- **Все модули общаются через JSON / DataFrame + meta**.
- **Prefect управляет только orchestration, не бизнес-логикой.**
- **Streamlit — только UI (не логика).**
- **Все пути и ключи централизованы в `core/config.py`.**
- **Все результаты (ingest_id, run_id, rule_version)** должны быть записаны в Persistent Store