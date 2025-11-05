# 05_SetupManager_RuleLogic
Описание модуля и его назначения.
### Setup Manager / Rule Logic

Цель: Создать централизованный модуль управления торговыми сетапами, их конфигурациями, версиями и логикой взаимодействия инструментов (FVG, Liquidity, OB, BOS, Sessions и т.д.), связывает эти **Market Tools** SMC-инструменты и анализ.

Модуль служит “мозгом стратегий” — хранит правила, обеспечивает их воспроизводимость, адаптирует параметры по результатам торговли и бэктестов, обновляется на основе статистики. Модуль позволяет изменять правила без изменения кода.

**Назначение:** связывает Market Tools в правила (DSL/YAML).

**Setup Manager - главный оркестратор** — ключ для гибкости и traceability. Он определяет вызов нужных Market Tools для запроса пользователя по нужному сетапу, хранит всю логику.

### Важные пояснения по последовательности и очередности (START, Scheduler, Setup Manager и Dispatcher)

1. **Кто регулирует очередь?**
    
    — **Setup Manager**. Scheduler или кнопка START запускает Setup Manager. Setup Manager отвечает: делать мт5 Data Ingest или брать из Cache; ждать Data Processor; затем запускать Market Tools. Это единая точка контроля порядка выполнения.
    
2. **Двухсторонняя связь Market Tools <-> Setup Manager:**
    
    — Market Tools вызываются по списку из Setup Manager. Результаты возвращаются обратно. Если Market Tools нуждается в дополнительном пред-вычислении (например, более длительный расчёт некоторых индикаторов), он может вернуть job_id, и Setup Manager будет ждать (polling) или подписываться на callback. Но по умолчанию — синхронный вызов (Setup Manager ждёт ответы).
    
3. **Кэширование:**
    
    — При повторных запросах Setup Manager прежде чем вызывать Data Ingest проверит Persistent Store / MT5 Data Cache. Это уменьшит нагрузку.
    
4. **Асинхронность vs Синхронность:**
    
    — Для простоты MVP: синхронные вызовы. Для масштабирования: Task Queue / Prefect for batch execution; Job IDs for long-running detectors.
    
5. **Как START / Scheduler взаимодействуют:**
    
    — Scheduler пишет в START payload и START → Setup Manager. Scheduler **не** вызывает Market Tools напрямую.

### Подмодули:

**2.5.1 Parser YAML → executable rule**: превращает `.yaml` правила в Python-checks. безопасный интермедиат (JSON spec) для исполнения.

**2.5.2 Rule Executor**: применяет ruleset к tools_json[] и формирует decision + explain chain. На вход получает `tools_json[]` + DataFrame → возвращает `signals[]` (entry, sl, tp, confidence, meta). Уточнить, это делает ГПТ Вижен, возможно Вижен может советоваться и запросить уровни стоп лосса и тейка

**2.5.3 Versioning**: при каждом изменении создаётся `rule_version`. хранит audit diff (draft -> publish workflow).

**2.5.4 Rule Profiler**: собирает статистику исполнения правил в бэктестах: winrate, avg_profit, avg_loss, PF, precision/recall, latency per rule. Выход: CSV/JSON профайлы, визуализации.

**Пример YAML:**

```yaml
setup_id: Frank_raid_v1
components:
  - Detect_Sessions(Frankfurt)
  - Detect_FVG(TF_m1, min_gap_pct:0.2)
  - Detect_BOS
rules:
  - condition: "Frankfurt raid, reverse, inversion fvg m1"
  - timeframe: m1
targets:
  tp: 2.0
  sl: 1.0

```

**Acceptance:** при заданном dataset `run_rules(rule_id, data)` возвращает сигналы и ссылку на `rule_version`.

Подмодуль: DSL / YAML Rule Template (логика описания и хранения сетапов)

Реализация: Notion + YAML + парсер в Prefect 2.19.

- Описание Работы модуля
    
    ### Задачи модуля:
    
    1. **Хранение сетапов и их параметров**
        - Где хранить: таблица в Notion или YAML/JSON файл.
        - Формат:
            
            ```yaml
            setup_id: asia_fvg_break
            name: "Asia Range Break + FVG"
            description: "Пробой Азии + FVG в сторону импульса"
            version: 1.3
            components:
              - Detect_Sessions(Asia)
              - Detect_FVG
              - Detect_BOS
            rules:
              - condition: "Asia_High_Broken and FVG_bullish_above"
              - timeframe: "M15"
              - confirmation: "BOS_up"
            targets:
              tp: 2.0
              sl: 1.0
            
            ```
            
    2. **Использование правил**
        - При вызове этого модуля Setup Manager выдает:
        
        ```json
        {
          "setup_id": "Frank_raid",
          "ruleset": [...],
          "parameters": {...}
        }
        
        ```
        
    3. **Связь с Backtester**
        - При каждом бэктесте указывается `setup_id`, `rule_version`.
        - Результаты записываются в Notion как:
            - WinRate, RR, Accuracy.
            - Ссылка на `setup_id` и версию.
    4. **Связь с Learning Module**
        - После накопления статистики модуль предлагает изменения параметров:
            
            > "Увеличить порог FVG_gap от 0.2% до 0.3% — повышает winrate +5%."
            > 
    5. **Обратная связь**
        - Трейдер может вручную отметить ✅/❌ в Notion — всё привязывается к `setup_id`.



 

## ⚙️ ASCII схема
МОДУЛЬ: Setup Manager / Rule Logic (Центральный дирижёр)

module_name: Setup Manager / Rule Logic

inputs:

source: START (User Trigger) / Scheduler

data_type: JSON

description: {setup_id, symbol, timeframe, start, end, mode, run_id, options}

ascii_diagram:

┌──────────────────────────────          ─┐
│         SETUP MANAGER / RULE LOGIC      │
├────────────────────────────────         ┤
│  • Загружает YAML rule для setup_id     │
│  • Парсит required Market Tools         │
│  • Формирует pipeline spec              │
│  • Вызывает Data Ingest → Processor     │
│  • Вызывает Market Tools Dispatcher     │
│  • Оценивает правило → signals          │
│  • Отправляет в Backtester/LiveHandler  │
└────────────────────────────            ─┘


outputs:

destination: Data Ingest (or read from cache), Market Tools Dispatcher, Backtester Manager, Live Handler

data_type: JSON (pipeline spec, signals, trace logs)

description: pipeline_spec {tools: [...], params}, processed_context, or signals list

logic_notes:

Ключ: Setup Manager управляет очередностью. Он сначала проверяет кэш/ingest registry: если данные за период уже доступны — он может пропустить Data Ingest и сразу передать processed_path в Data Processor или Market Tools.

Если нет кэша — он вызывает Data Ingest и ждёт завершения Data Processor прежде чем вызывать Market Tools. Это важный порядок: Market Tools ожидают уже нормализованные/обогащённые данные.

Setup Manager формирует список required_tools на основе YAML (например required_tools: [Detect_Sessions, Detect_FVG, Detect_Liquidity]) и передаёт их Market Tools Dispatcher.

Setup Manager логирует все шаги (tool calls, durations, run_id) и сохраняет в Persistent Store.

---

### Подмодуль 2.5.1 — Parser YAML → Executable Rule

**submodule_name:** "2.5.1 Parser YAML → Executable Rule"

**inputs:**

- **from_source:** Rule & Version Registry (2.3.2) - YAML файлы правил
- **data_type:** YAML файл
- **params:** setup_id, version
- **format:**

yaml

  `setup_id: Frank_raid_v1
  version: 1.2
  components: [Detect_Sessions(Frankfurt), Detect_FVG(TF_m1, min_gap_pct:0.2)]
  rules:
    - condition: "Frankfurt raid AND reverse AND inversion fvg m1"
  targets: {tp: 2.0, sl: 1.0}
````
- **description:** YAML файл с определением сетапа

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│   PARSER YAML → EXECUTABLE RULE                │
├────────────────────────────────────────────────┤
│  • Парсинг YAML в Python dict                  │
│  • Извлечение components (какие детекторы)     │
│  • Парсинг rules (условия для сигнала)         │
│  • Компиляция в executable Python функцию      │
│  • Validation: все components доступны         │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Rule Executor (2.5.2)
- **data_type:** Python dict + executable function object
- **params:** setup_id, version, components_list[], rule_function, targets
- **format:**

python

  `{
    "setup_id": "Frank_raid_v1",
    "version": "1.2",
    "components": ["Detect_Sessions", "Detect_FVG"],
    "rule_function": <compiled_function>,
    "targets": {"tp": 2.0, "sl": 1.0},
    "meta": {"author": "trader_1", "created": "2025-10-15"}
  }`

- **description:** Исполняемое представление правила для Rule Executor

**logic_notes:**

- "Парсинг components: извлекает список детекторов и их параметры (например Detect_FVG с min_gap_pct:0.2)"
- "Rule compilation: превращает текстовое условие ('Frankfurt raid AND fvg') в Python логику (AST transformation)"
- "Validation: проверка что все указанные детекторы существуют в Market Tools модуле"
- "Если парсинг fails - возврат ошибки БЕЗ запуска backtest/live flow"
- "ДОБАВЛЕНО: caching скомпилированных правил (rule_id + version) для избежания повторного парсинга"

### Подмодуль 2.5.2 — Rule Executor

**submodule_name:** "2.5.2 Rule Executor"

**inputs:**

- **from_source:** Parser (2.5.1) - executable rule + Market Tools (детекторы outputs JSON) + Data Processor (DataFrame)
- **data_type:** Python dict (rule) + JSON array (tools outputs) + DataFrame
- **params:** setup_id, version, tools_json[], candles_df
- **format:**

python

  `rule = {rule_function, targets, ...}
  tools_json = [{type:"fvg", ...}, {type:"session_zone", ...}, ...]
  candles_df = DataFrame[time, ohlcv, ...]
```
- **description:** Данные для проверки условий правила и генерации сигналов

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         RULE EXECUTOR                          │
├────────────────────────────────────────────────┤
│  • Применение rule_function к tools_json       │
│  • Проверка условий (AND/OR логика)            │
│  • Расчёт entry, SL, TP на основе targets      │
│  • Генерация signals[] с confidence            │
│  • Добавление meta (rule_id, version, detectors│
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Backtester (если backtest mode) ИЛИ ML Scoring Module + Decision Logic (если live mode)
- **data_type:** JSON массив сигналов
- **params:** signal_id, symbol, tf, entry_price, sl_price, tp_price, confidence, rule_id, rule_version, meta
- **format:**

json

  `[
    {
      "signal_id": "sig_20251031_001",
      "symbol": "GER40",
      "tf": "M15",
      "entry_price": 15840.0,
      "sl_price": 15800.0,
      "tp_price": 15900.0,
      "confidence": 0.78,
      "rule_id": "Frank_raid_v1",
      "rule_version": "v1.2",
      "meta": {
        "detectors": ["Detect_Sessions", "Detect_FVG"],
        "candles_analyzed": 3,
        "entry_timestamp": "2025-10-31T10:15:00Z"
      }
    }
  ]`

- **description:** Сигналы для торговли с полной трассируемостью к правилу

**logic_notes:**

- "Rule function получает tools_json и возвращает bool (условие выполнено?) + entry/sl/tp координаты"
- "Entry/SL/TP расчёт: обычно на основе зон от детекторов (например entry = OB low, SL = OB high + buffer)"
- "Confidence наследуется от детекторов: берётся минимальный confidence среди использованных зон"
- "Meta всегда включает rule_id + version для трассировки результата к конкретной версии правила"
- "ДОБАВЛЕНО: поле meta.context_snapshot - краткий JSON с рыночным контекстом (trend, volatility) для анализа"

### Подмодуль 2.5.3 — Versioning (Setup Manager)

**submodule_name:** "2.5.3 Versioning (Setup Manager)"

**inputs:**

- **from_source:** USER_REQUEST (изменение правила через Streamlit UI или ручное редактирование YAML) или Learning Module (автоматические предложения)
- **data_type:** YAML (modified rule) + JSON (change description)
- **params:** setup_id, old_version, new_version, changes_description, author
- **format:**

json

  `{
    "setup_id": "Frank_raid_v1",
    "old_version": "v1.1",
    "new_version": "v1.2",
    "changes": [
      {"field": "components.Detect_FVG.min_gap_pct", "old": 0.2, "new": 0.3},
      {"field": "targets.tp", "old": 1.8, "new": 2.0}
    ],
    "author": "trader_1",
    "reason": "Increased TP based on backtest analysis"
  }
````
- **description:** Запрос на создание новой версии правила с описанием изменений

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      VERSIONING (Setup Manager)                │
├────────────────────────────────────────────────┤
│  • Создание новой версии при изменении правила │
│  • Автоинкремент версии (v1.1 → v1.2)          │
│  • Сохранение changelog (что изменилось)       │
│  • Архивация старой версии (не удаляется)      │
│  • Связывание с Rule & Version Registry        │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** Rule & Version Registry (2.3.2) - сохранение новой версии + DATABASE (версионная запись)
- **data_type:** YAML файл (новая версия) + JSON (metadata record)
- **params:** setup_id, version, file_path, created_at, changes_log
- **format:** 
````
  File: rules/Frank_raid_v1/v1.2.yaml
  DB record: {
    id, setup_id, version: "v1.2", 
    file_path, author, created_at,
    changes_log: [{field, old, new}, ...],
    parent_version: "v1.1"
  }`

- **description:** Новая версия правила с полной историей изменений

**logic_notes:**

- "КАЖДОЕ изменение создаёт новую версию - даже изменение одного параметра"
- "Semantic versioning: major.minor.patch (например v2.0.0 для радикальных изменений стратегии)"
- "Старые версии НИКОГДА не удаляются - архивируются для воспроизводимости прошлых бэктестов"
- "Changelog автоматически генерируется через diff между old и new YAML"
- "ДОБАВЛЕНО: поле 'reason' - обязательное текстовое описание ПОЧЕМУ было изменено (для future reference)"

### Подмодуль 2.5.4 — Rule Profiler

**submodule_name:** "2.5.4 Rule Profiler"

**inputs:**

- **from_source:** Backtester (результаты бэктестов) + Rule & Version Registry (параметры правил)
- **data_type:** JSON (backtest results) + YAML (rule params)
- **params:** setup_id, version, backtest_results[], param_variations[]
- **format:**

json

  `{
    "setup_id": "Frank_raid_v1",
    "versions_tested": ["v1.0", "v1.1", "v1.2"],
    "backtest_results": [
      {"version": "v1.0", "winrate": 0.58, "avg_rr": 1.6, "params": {...}},
      {"version": "v1.2", "winrate": 0.61, "avg_rr": 1.8, "params": {...}}
    ]
  }
````
- **description:** Результаты множественных бэктестов для анализа влияния параметров

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         RULE PROFILER                          │
├────────────────────────────────────────────────┤
│  • Сбор статистики по всем версиям правила     │
│  • Анализ winrate vs params (какой параметр ↑) │
│  • Корреляция между параметрами и метриками    │
│  • Генерация рекомендаций по оптимизации       │
│  • Визуализация param sensitivity              │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Learning Module (для автоматических предложений) + Streamlit Dashboard (визуализация) + DATABASE (сохранение статистики)
- **data_type:** JSON (profiling report)
- **params:** setup_id, best_version, param_sensitivity, recommendations[]
- **format:**

json

  `{
    "setup_id": "Frank_raid_v1",
    "best_version": "v1.2",
    "best_metrics": {"winrate": 0.61, "avg_rr": 1.8, "expectancy": 0.58},
    "param_sensitivity": {
      "min_gap_pct": {"impact": "high", "correlation_with_winrate": 0.72},
      "tp": {"impact": "medium", "correlation_with_avg_rr": 0.45}
    },
    "recommendations": [
      "Increase min_gap_pct from 0.2 to 0.3 (projected winrate +3%)",
      "Keep tp at 2.0 (optimal risk/reward balance)"
    ]
  }
````
- **description:** Аналитический отчёт о влиянии параметров на эффективность правила

**logic_notes:**
- "Собирает данные ВСЕХ бэктестов для конкретного setup_id (все версии)"
- "Param sensitivity: вычисляет корреляцию между изменением параметра и изменением winrate/RR"
- "Recommendations основаны на statistical significance (>50 trades для надёжности)"
- "Визуализация в Streamlit: heatmap param vs winrate, линейные графики версий"
- "ДОБАВЛЕНО: детекция overfitting - если новая версия +10% winrate но только на одном периоде - warning"

---

``
