# 04_MarketTools
Описание модуля и его назначения.
### **Market Tools**

**Detect_sessions** — (взаимосвязано с Session Engine).
 — детектор сессий Азии, Франкфурта, Лондрна, НЮ; принимает свечные данные и возвращает список зон (цены, временные диапазоны, direction). Учитывает временную нормализацию, перевод времени часовых поясов.

**Detect_Opening_Levels** — daily/weekly open, NY midnight

**Detect_PDX_PWX -** находит ценовые границы предыдущего дня (двух) и предыдущей недели: PDH, PDL, PWH, PWL

**BOS_CHOCH_SHIFT Detector** — обнаруживает Break-of-Structure / Change-of-Character и ключевые свинги.

**Detect_Liquidity** — находит зоны ликвидности (ХТФ фракталы, равные уровни, и тд) и возвращает приоритетные уровни.

**Detect_FVG**, **Detect_OB** — по мере развития, список инструментов будет расширяться постоянно

(важно: каждый детектор возвращает стандартизированный JSON: `{type, start, end, price_low, price_high, confidence, meta}`)

2.4.8 — **Schema Validation** 

**Market Tools** outputs + **Vision Adapter** outputs.

- JSON schemas (напр. `signal_schema`, `annotation_schema`) и валидатор (pydantic).
- Валидированные данные или список ошибок
- При ошибке валидации: логирование + блокировка прохода в Setup Manager + alert в Telegram

- Планируемый пример работы
    
    ### Коротко: цепочка вызовов
    
    Prefect 2.19 (оркестратор) вызывает Python-tool (`Detect_sessions` / `Detect_PDX_PWX`), инструмент **вычисляет** зоны по ценам и **возвращает** структурированный JSON обратно в Prefect 2.19; Prefect 2.19 затем **перенаправляет** этот JSON в хранилище (базу/объектное хранилище), в визуализатор (Dash) и/или в GPT-модуль для интерпретации — и в итоге результат сохраняется в журнале (Notion) и/или шлётся в Telegram.
    
    ### Пошагово, кто — что — куда
    
    1. **Инициатор (Caller)**
        
        — обычно это Prefect **Orchestrator** (workflow «Backtest» или «Live Trading»).
        
        — он собирает входные данные (пары, период, сетап) и вызывает нужный Python-tool.
        
    2. **Выполнение (Tool)**
        
        — например `Detect_**sessions**` получает на вход: свечные данные (OHLCV) и параметры (таймфрейм, правила/порог).
        
        — Tool выполняет расчёт и формирует результат в **стандартизированном JSON** (см. пример ниже).
        
    3. **Возвращение результата**
        
        — Tool **возвращает этот JSON** обратно **в тот же вызвавший компонент** — т.е. вPrefect (или в вызывающий Python-процесс, если вызов локальный).
        
        — «Возвращает» означает: отдаёт структуру данных в память/контекст вызывающего процесса, а не печатает в консоль.
        
    4. **Дальнейшая маршрутизация (Prefect / Orchestrator)**
        
        После получения JSON Flowise делает один или несколько шагов:
        
        - **Пишет в Persistent Store** (базу / S3) с уникальным ID и метаданными (rule_id, версия, время запроса).
        - **Передаёт JSON визуализатору** (Dash) — визуализатор использует те же координаты/цены, чтобы отрисовать прямоугольник/линию точно там же.
        - **Подаёт JSON вместе с PNG/HTML в GPT Vision** (Vision Adapter) — GPT получает и картинку, и «истинные» координаты зон.
        - **Сохраняет запись в Notion** (через Notion Uploader) или отправляет уведомление в Telegram.
    5. **Хранение и трассируемость**
        
        — В Persistent Store хранится как сам JSON, так и исходные входные свечи + ссылка на rule_id и версию инструмента.
        
        — Это позволяет в любой момент восстановить «почему» и «кем» была посчитана конкретная зона.


## ⚙️ ASCII схема
## МОДУЛЬ 2.4 — Market Tools

### Подмодуль 2.4.1 — Detect_sessions

**submodule_name:** "2.4.1 Detect_sessions"

**inputs:**

- **from_source:** Data Processor (enriched DataFrame) + Session Engine (session boundaries JSON)
- **data_type:** DataFrame + JSON
- **params:** symbol, timeframe, session_names[] (Asia/Frankfurt/London/NY)
- **format:**

  `DataFrame: [time(UTC), open, high, low, close, volume, session, ...]
  Session JSON: [{session_name, start, end, timezone}, ...]
```
- **description:** Обогащённые данные со временными метками для детекции сессий

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         DETECT_SESSIONS                        │
├────────────────────────────────────────────────┤
│  • Детекция торговых сессий (Asia/Frank/Lon/NY)│
│  • Определение High/Low каждой сессии          │
│  • Выявление raid (пробоя границ сессии)       │
│  • Возврат зон в стандартизированном JSON      │
│  • Учёт временных зон и DST                    │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Setup Manager (для rule evaluation) + Persistent Store (сохранение результатов) + Dash Visualizer (для отрисовки)
- **data_type:** JSON массив зон
- **params:** type, session_name, start, end, price_low, price_high, confidence, meta
- **format:**

json

  `[
    {
      "type": "session_zone",
      "session_name": "Asia",
      "start": "2025-10-31T00:00:00Z",
      "end": "2025-10-31T08:00:00Z",
      "price_low": 15820.3,
      "price_high": 15850.5,
      "confidence": 1.0,
      "meta": {"raid_detected": false, "direction": null}
    }
  ]
```
- **description:** Стандартизированный список зон сессий с ценовыми границами

**logic_notes:**
- "Связан с Session Engine (2.2.4) - использует его JSON как базу, дополняет анализом raid/sweep"
- "Raid detection: если цена выходит за boundaries сессии и возвращается - meta.raid_detected = true"
- "Confidence = 1.0 для четких сессий с полными данными, <1.0 если есть пропуски в данных"
- "ДОБАВЛЕНО: поле meta.volume_profile - распределение объёма внутри сессии (high/low/mid)"

---

### Подмодуль 2.4.2 — Detect_Opening_Levels

**submodule_name:** "2.4.2 Detect_Opening_Levels"

**inputs:**
- **from_source:** Data Processor (enriched DataFrame с new_day флагами)
- **data_type:** DataFrame
- **params:** symbol, timeframe, level_types[] (daily_open, weekly_open, ny_midnight)
- **format:** DataFrame с колонками [time, open, new_day, new_week, ...]
- **description:** Данные для определения ключевых открытий (daily/weekly/NY midnight)

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      DETECT_OPENING_LEVELS                     │
├────────────────────────────────────────────────┤
│  • Daily Open (начало торгового дня)           │
│  • Weekly Open (понедельник)                   │
│  • NY Midnight (00:00 NY time)                 │
│  • Определение ценовых уровней открытий        │
│  • Трассировка уровней через время             │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Setup Manager + Dash Visualizer + Persistent Store
- **data_type:** JSON массив уровней
- **params:** type, level_name, timestamp, price, confidence, meta
- **format:**

json

  `[
    {
      "type": "opening_level",
      "level_name": "daily_open",
      "start": "2025-10-31T00:00:00Z",
      "end": null,
      "price_low": 15835.0,
      "price_high": 15835.0,
      "confidence": 1.0,
      "meta": {"day": "2025-10-31", "valid_until": "2025-11-01T00:00:00Z"}
    }
  ]
```
- **description:** Уровни открытий для использования в анализе и визуализации

**logic_notes:**
- "Daily Open = первая свеча дня (определяется по new_day флагу из Data Processor)"
- "Weekly Open = первая свеча понедельника (после выходных)"
- "NY Midnight = 00:00 по NY времени (критичный уровень в ICT методологии)"
- "end = null означает что уровень действителен до следующего открытия (next daily/weekly open)"
- "ДОБАВЛЕНО: детекция gap между close предыдущего дня и open текущего (meta.gap_pips)"

---

### Подмодуль 2.4.3 — Detect_PDX_PWX

**submodule_name:** "2.4.3 Detect_PDX_PWX"

**inputs:**
- **from_source:** Data Processor (enriched DataFrame с pdh, pdl, pwh, pwl колонками)
- **data_type:** DataFrame
- **params:** symbol, timeframe, lookback_days (по умолчанию 2 для PD, 1 неделя для PW)
- **format:** DataFrame с [time, high, low, pdh, pdl, pwh, pwl, ...]
- **description:** Данные для определения границ Previous Day/Week High/Low

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         DETECT_PDX_PWX                         │
├────────────────────────────────────────────────┤
│  • Previous Day High/Low (PDH, PDL)            │
│  • Previous Week High/Low (PWH, PWL)           │
│  • Lookback: 2 предыдущих дня для PD           │
│  • 1 предыдущая неделя для PW                  │
│  • Определение зон для liquidity analysis      │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Setup Manager + Dash Visualizer + Detect_Liquidity (для комбинированного анализа)
- **data_type:** JSON массив зон
- **params:** type, level_name, start, end, price_low, price_high, confidence, meta
- **format:**

json

  `[
    {
      "type": "pdx_pwx_zone",
      "level_name": "PDH",
      "start": "2025-10-30T00:00:00Z",
      "end": "2025-10-31T00:00:00Z",
      "price_low": 15860.0,
      "price_high": 15860.0,
      "confidence": 1.0,
      "meta": {"day": "2025-10-30", "touches": 0, "swept": false}
    }
  ]
```
- **description:** Уровни PDH/PDL/PWH/PWL для liquidity hunting анализа

**logic_notes:**
- "PDH/PDL рассчитываются от 2 предыдущих дней (configurable) - более надёжный уровень"
- "PWH/PWL = абсолютные high/low предыдущей недели (понедельник-пятница)"
- "meta.touches отслеживает количество касаний уровня (>3 touches = сильный уровень)"
- "meta.swept = true если цена пробила уровень и вернулась (liquidity sweep)"
- "ДОБАВЛЕНО: интеграция с Detect_Liquidity для определения confluence зон (PDH + liquidity pool)"

---

### Подмодуль 2.4.4 — BOS_CHOCH_SHIFT Detector

**submodule_name:** "2.4.4 BOS_CHOCH_SHIFT Detector"

**inputs:**
- **from_source:** Data Processor (enriched DataFrame)
- **data_type:** DataFrame
- **params:** symbol, timeframe, swing_detection_params (min_swing_size, lookback_period)
- **format:** DataFrame [time, high, low, close, atr, ...]
- **description:** Данные для детекции структурных сдвигов рынка (BOS/CHoCH)

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      BOS_CHOCH_SHIFT DETECTOR                  │
├────────────────────────────────────────────────┤
│  • Break of Structure (BOS) - пробой структуры │
│  • Change of Character (CHoCH) - смена характера│
│  • Определение ключевых свингов (highs/lows)   │
│  • Детекция смены тренда                       │
│  • Confidence на основе силы пробоя            │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Setup Manager + Dash Visualizer + Persistent Store
- **data_type:** JSON массив событий
- **params:** type, event_name, start, end, price_low, price_high, confidence, meta
- **format:**

json

  `[
    {
      "type": "structure_shift",
      "event_name": "BOS_bullish",
      "start": "2025-10-31T09:15:00Z",
      "end": "2025-10-31T09:30:00Z",
      "price_low": 15825.0,
      "price_high": 15855.0,
      "confidence": 0.85,
      "meta": {
        "swing_high": 15845.0,
        "swing_low": 15820.0,
        "break_strength": 1.2,
        "trend_before": "bearish",
        "trend_after": "bullish"
      }
    }
  ]
```
- **description:** События пробоя структуры с метаданными о смене тренда

**logic_notes:**
- "BOS = пробой предыдущего swing high/low в направлении тренда (confirmation)"
- "CHoCH = пробой counter-trend swing (возможная смена тренда, требует подтверждения)"
- "min_swing_size = минимальный размер свинга в ATR (обычно 1.5*ATR) для фильтрации шума"
- "confidence зависит от break_strength: >2*ATR = high conf (0.9), 1-2*ATR = medium (0.7)"
- "ДОБАВЛЕНО: поле meta.liquidity_sweep - был ли sweep ликвидности перед BOS (усиливает сигнал)"

---

### Подмодуль 2.4.5 — Detect_Liquidity

**submodule_name:** "2.4.5 Detect_Liquidity"

**inputs:**
- **from_source:** Data Processor + Detect_PDX_PWX (для confluence) + BOS_CHOCH Detector (для структурного контекста)
- **data_type:** DataFrame + JSON (PDX/PWX zones, structure shifts)
- **params:** symbol, timeframe, liquidity_types[] (htf_fractals, equal_highs_lows, stop_clusters)
- **format:** 
```
  DataFrame: [time, high, low, close, volume, ...]
  Zones JSON: PDX/PWX уровни для confluence
```
- **description:** Данные для определения зон накопления ликвидности

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         DETECT_LIQUIDITY                       │
├────────────────────────────────────────────────┤
│  • HTF фракталы (Higher Timeframe swing points)│
│  • Equal Highs/Lows (потенциальные stop pools) │
│  • Stop loss clusters (зоны накопления стопов) │
│  • Confluence с PDH/PDL/PWH/PWL                │
│  • Приоритизация по вероятности sweep          │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Setup Manager + Dash Visualizer + ML Scoring Module (feature для вероятности)
- **data_type:** JSON массив зон ликвидности
- **params:** type, liquidity_type, start, end, price_low, price_high, confidence, meta
- **format:**

json

  `[
    {
      "type": "liquidity_zone",
      "liquidity_type": "equal_highs",
      "start": "2025-10-31T08:00:00Z",
      "end": "2025-10-31T12:00:00Z",
      "price_low": 15858.0,
      "price_high": 15862.0,
      "confidence": 0.78,
      "meta": {
        "touches_count": 3,
        "confluence": ["PDH", "htf_fractal"],
        "priority": "high",
        "expected_sweep_direction": "upward"
      }
    }
  ]
```
- **description:** Приоритизированные зоны ликвидности для hunting стратегий

**logic_notes:**
- "Equal highs/lows = 3+ свечи с high/low в диапазоне <0.2% друг от друга (tight cluster)"
- "HTF fractals = swing points на старших таймфреймах (H4/D1) - сильные уровни"
- "Confluence увеличивает confidence: PDH+equal_highs = +0.2 к базовому confidence"
- "Priority (high/medium/low) определяется комбинацией: touches_count + confluence + proximity to structure"
- "ДОБАВЛЕНО: поле meta.swept_history - был ли этот уровень swept ранее (снижает приоритет)"

---

### Подмодуль 2.4.6 — Detect_FVG

**submodule_name:** "2.4.6 Detect_FVG (Fair Value Gap)"

**inputs:**
- **from_source:** Data Processor (enriched DataFrame)
- **data_type:** DataFrame
- **params:** symbol, timeframe, min_gap_pct (минимальный размер гэпа, обычно 0.2%), direction (bullish/bearish/both)
- **format:** DataFrame [time, open, high, low, close, body_pct, ...]
- **description:** Данные для детекции Fair Value Gap (imbalance)

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         DETECT_FVG                             │
├────────────────────────────────────────────────┤
│  • Детекция Fair Value Gap (3-свечной паттерн) │
│  • Bullish FVG: gap между свечой 1 high и 3 low│
│  • Bearish FVG: gap между свечой 1 low и 3 high│
│  • Фильтр по min_gap_pct (удаление шума)       │
│  • Трекинг заполнения FVG (mitigation)         │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Setup Manager + Dash Visualizer + Persistent Store
- **data_type:** JSON массив FVG зон
- **params:** type, fvg_direction, start, end, price_low, price_high, confidence, meta
- **format:**

json

  `[
    {
      "type": "fvg",
      "fvg_direction": "bullish",
      "start": "2025-10-31T10:00:00Z",
      "end": "2025-10-31T10:15:00Z",
      "price_low": 15830.0,
      "price_high": 15840.0,
      "confidence": 0.82,
      "meta": {
        "gap_size_pct": 0.35,
        "mitigation_status": "open",
        "candle_indices": [145, 146, 147],
        "created_by_impulse": true
      }
    }
  ]
```
- **description:** FVG зоны для использования в mean reversion или continuation стратегиях

**logic_notes:**
- "FVG = 3-свечной паттерн: gap между high свечи 1 и low свечи 3 (bullish) или наоборот (bearish)"
- "min_gap_pct фильтрует шум: если gap < 0.2% от цены - не считается FVG"
- "mitigation_status: 'open' (не заполнен), 'partial' (частично), 'filled' (полностью закрыт ценой)"
- "created_by_impulse = true если gap создан импульсной свечой (body > 70% range) - сильнее сигнал"
- "ДОБАВЛЕНО: поле meta.confluence_with_structure - совпадение FVG с BOS/CHoCH (повышает confidence)"

---`

### Подмодуль 2.4.8 — Schema Validator (Market Tools)

**submodule_name:** "2.4.8 Schema Validator (Market Tools)"

**inputs:**
- **from_source:** Все детекторы Market Tools (Detect_sessions, FVG, OB, BOS и тд)
- **data_type:** JSON (выходы детекторов)
- **params:** schema_type (signal_schema / zone_schema / event_schema)
- **format:** Любой JSON output от детектора
- **description:** Валидация структуры и полей выходных данных детекторов

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      SCHEMA VALIDATOR (Market Tools)           │
├────────────────────────────────────────────────┤
│  • Валидация JSON schema (pydantic models)     │
│  • Проверка обязательных полей                 │
│  • Типы: signal_schema, zone_schema, event     │
│  • Логирование ошибок валидации                │
│  • Блокировка невалидных данных до Setup Mgr   │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Setup Manager (только валидные данные) + Logs (ошибки валидации)
- **data_type:** JSON (validated) или Error object
- **params:** is_valid (bool), validated_data (JSON), errors[] (если есть)
- **format:**

json

  `{
    "is_valid": true,
    "validated_data": {...детектор output...},
    "schema_used": "zone_schema_v1",
    "timestamp": "2025-10-31T10:00:00Z"
  }
  OR
  {
    "is_valid": false,
    "errors": ["Missing field: confidence", "Invalid type: price_low must be float"],
    "raw_data": {...},
    "detector": "Detect_FVG"
  }`

- **description:** Валидированные данные или список ошибок

**logic_notes:**

- "Обязательные поля для всех детекторов: type, start, end, price_low, price_high, confidence, meta"
- "Pydantic models для каждого schema типа: ZoneSchema, SignalSchema, EventSchema"
- "При ошибке валидации: логирование + блокировка прохода в Setup Manager + alert в Telegram"
- "Confidence должен быть 0.0-1.0, цены должны быть float > 0, timestamps в ISO format"
- "ДОБАВЛЕНО: versioning schemas (zone_schema_v1, v2...) для обратной совместимости при изменении структуры"

