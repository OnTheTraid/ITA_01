Изменения в процессе разработки

# Изменения в процессе разработки

| №  | Направление              | Что сделать                                                                                         | Выполнение  |
|----|--------------------------|-----------------------------------------------------------------------------------------------------|-------------|
| 1  | **Docs**                 | Добавить схему связей между модулями (PlantUML или Mermaid).                                        |             |
| 2  | **Config Management**    | Все пути, ключи, env-переменные — централизовать в `config.yaml`.                                   |             |
| 3  | **Tests / QA**           | Создать контрольный набор тестовых данных (OHLC 100 свечей) и golden JSON для acceptance.           |             |
| 4  | **Data Flows Prefect**   | Настроить два deployment’а: `backtest_flow` и `live_flow`, добавить логирование в Persistent Store. |             |
| 5  | **Versioning Rules**     | Добавить Git-интеграцию в Rule Registry — фиксация `commit_hash` в каждом run.                      |             |
| 6  | **Logging / Monitoring** | Добавить loguru + Prefect monitoring дашборд в Streamlit.                                           |             |
| 7  | **Notion Integration**   | Создать модуль `notion_formatter.py` для форматирования отчётов.                                    |             |
| 8  | **API Layer**            | Ввести `api_adapter.py` для связи Streamlit ↔ Prefect.                                              |             |
| 9  | **Safety Layer**         | Реализовать безопасное управление LLM токенами и ограничение вызовов (`LLM rate limit + retry`).    |             |
| 10 | **UX**                   | Добавить визуальный индикатор состояния Flow (выполняется, завершён, ошибка) в Streamlit.           |             |
