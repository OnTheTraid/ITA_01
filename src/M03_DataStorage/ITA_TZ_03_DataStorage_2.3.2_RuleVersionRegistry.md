# ITA_TZ_03_DataStorage_2.3.2_RuleVersionRegistry

## 1. Назначение
Подмодуль **Rule & Version Registry** отвечает за **учёт, хранение и версионирование торговых правил и сетапов** (`setup_id`, `rule_version`, `params`).
Основная цель — обеспечить воспроизводимость стратегий и трассировку изменений между версиями правил.

## 2. Функциональные задачи

| № | Задача | Описание |
|---|---------|-----------|
| 1 | Регистрация версии правила | Сохранение YAML с конфигурацией сетапа в структуре `rules/{setup_id}/v{N}.yaml` |
| 2 | Получение текущей версии | Возврат последней активной версии (`active_flag=True`) |
| 3 | Сравнение версий | Вычисление diff между версиями (по полям `params`, `components`) |
| 4 | Архивация старых версий | Перемещение неактивных YAML в `rules/{setup_id}/archive/` |
| 5 | Интеграция | Обеспечить выдачу `ArtifactRef` через `persistent_store` |

## 3. Контракт
```yaml
setup_id: asia_fvg_break
version: 1.3
author: "maxim.malysh"
date_created: "2025-11-10T18:20:00Z"
active_flag: true
components:
  - Detect_Sessions(Asia)
  - Detect_FVG
rules:
  - condition: "Asia_High_Broken and FVG_bullish_above"
  - timeframe: "M15"
targets:
  tp: 2.0
  sl: 1.0
params:
  min_gap_pct: 0.3
meta:
  comment: "После обучения повысили gap"
```

## 4. Архитектура и связи
- 🔄 **Использует:** `persistent_store.save_yaml()`
- 🧩 **Вызывается из:** `Setup Manager` (2.5)
- 💾 **Пишет в:** `data/rules/{setup_id}/v{N}.yaml`
- 🔐 **Взаимодействует:**
  - с `Run Snapshot` — выдаёт `rule_version` для снапшота;
  - с `Backtester Manager` — метаданные `rule_version` в отчётах.

## 5. Пример интерфейса класса
```python
class RuleVersionRegistry:
    def register_rule(self, setup_id: str, params: dict, author: str) -> ArtifactRef: ...
    def get_active_version(self, setup_id: str) -> dict: ...
    def list_versions(self, setup_id: str) -> list[str]: ...
    def diff_versions(self, setup_id: str, v1: float, v2: float) -> dict: ...
```

## 6. Acceptance
- Каждый сетап имеет уникальный `setup_id`.
- YAML валиден, проходит pydantic-валидацию схемы.
- В логах — запись о регистрации новой версии.
- Diff содержит минимум поля (`params`, `components`).

## 7. Структура файлов проекта
```
src/03_DataStorage/
  ├── persistent_store.py
  ├── version_registry.py
  ├── schemas/
  │     └── rule_schema.yaml
data/
  └── rules/
      └── <setup_id>/
          ├── v1.yaml
          ├── v2.yaml
          └── archive/
```