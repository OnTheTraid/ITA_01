# 08_GPT_VisionFlow
Описание модуля и его назначения.
 **2.8.1 GPT Prompt Manager** — централизованное хранилище и генератор подсказок (prompts) с шаблонами для анализа сигнала, интерпретаций бэктестов и генерирования комментариев; поддерживает версии подсказок.

**2.8.2 Vision Adapter** — компонент, который подаёт в GPT Vision оба источника: (a) PNG/HTML кастомного графика и (b) JSON-данные (что посчитал Python), и формирует запрос вида: “Сравни визуально и по данным — подтвердить/опровергнуть сетап”.

- Два входных файла: PNG (изображение) и JSON (данные инструментов).
- Подготавливает multimodal prompt: `"Image: <embedding or base64 link>, Tools summary: {...}".`
- Вызывает OpenAI или GPT-4V через цепочку LangChain, которая может использовать анализ изображений и текст LLM.
- Возвращает: `{analysis_text, annotation_commands, certain_score, proposed_rule_tweak}`.
- Гарантировать, что LLM возвращает `annotation_commands` + optional `annotated_png_path` (если LLM сервис сам возвращает image).

**Decision Reconciler (уточнить надо ли)** — логика, которая агрегирует выводы Python-анализа и GPT-оценки (визуал/качество), даёт финальный вердикт и confidence score.

**2.8.3 LLM Chains & Agents**

- Chains: `image -> vision tool -> summarizer -> classifier`.
- Agents: Tool-using agents that can call `notion_uploader`, `chroma.query` etc. (careful with security).

**2.8.4 Prompt Version Registry** — лог/версионирование промптов (каждый промпт с id, hash, версия) → **модуль:** добавить в **GPT Integration & Vision Flow → Prompt Manager**.

**2.8.5 Prompt Testing Harness** — unit tests для промптов (проверка на контрольных данных) → **модуль:** новый подмодуль `Prompt Tester` внутри Prompt Manager.

**2.8.6 Rate-limit / Retry / Backoff** (API adapter) — обработка ошибок OpenAI/LLM, timeouts → **модуль:** `API Adapter` в GPT Integration.

** 2.8.7 Decision Reconciler ** - агрегация трёх источников (Python, LLM, ML) в единое решение
 
**2.8.8 Safety / Sanity Checks** — проверять корректность `annotation_commands` JSON schema перед применением → `Vision Adapter` + `Annotation Service`.

**2.8.9** Costs / Token accounting (для LLM) 

- **LLM Call Logger -**  логировать токены/стоимость, лимиты usage per day.

**Acceptance:** Для тестового набора из 20 аннотированных PNG-файлов ожидаемый структурированный вывод соответствует золотому стандарту ≥ X (первоначально ручная оценка).).

**Logging & Observability** для LLM (prompts, responses, tokens used) — для анализа стоимости/качества → добавить логирование в GPT Integration.
## ⚙️ ASCII схема

## МОДУЛЬ 2.8 — GPT Integration & Vision Flow

### Подмодуль 2.8.1 — GPT Prompt Manager

**submodule_name:** "2.8.1 GPT Prompt Manager"

**inputs:**
- **from_source:** Configuration (prompts/ папка с шаблонами) или USER_REQUEST (кастомные промпты)
- **data_type:** Text файлы (prompts templates) + JSON (variables)
- **params:** prompt_type (signal_analysis, backtest_interpretation, image_annotation), variables{}
- **format:** 
```
  Template file: prompts/signal_analysis_v1.txt
  Content:
  "Analyze the trading chart for {symbol} on {timeframe}.
  Detected zones: {zones_summary}.
  Signal: entry={entry}, sl={sl}, tp={tp}.
  Provide: 1) confirmation/rejection, 2) risk factors, 3) annotation commands."
  
  `Variables JSON: {
    "symbol": "GER40",
    "timeframe": "M15",
    "zones_summary": "FVG at 15835, OB at 15830, PDH at 15860",
    "entry": 15840, "sl": 15800, "tp": 15900
  }
````
- **description:** Шаблоны промптов и переменные для подстановки

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       GPT PROMPT MANAGER                       │
├────────────────────────────────────────────────┤
│  • Централизованное хранилище промптов         │
│  • Шаблоны с переменными {var}                 │
│  • Версионирование промптов (v1, v2...)        │
│  • Генерация финального промпта с подстановкой │
│  • Поддержка multimodal (text + image)         │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Vision Adapter (финальный промпт для LLM) + DATABASE (prompt usage log)
- **data_type:** String (final prompt) + JSON (metadata)
- **params:** prompt_id, prompt_version, final_text, variables_used
- **format:**

json

  `{
    "prompt_id": "signal_analysis",
    "version": "v1.2",
    "template": "prompts/signal_analysis_v1.txt",
    "final_prompt": "Analyze the trading chart for GER40 on M15...",
    "variables": {"symbol": "GER40", ...},
    "character_count": 487,
    "timestamp": "2025-10-31T10:15:00Z"
  }`

- **description:** Готовый промпт с подставленными переменными для отправки в LLM

**logic_notes:**

- "Template engine: простая подстановка {variable} через Python string.format() или Jinja2"
- "Версионирование: каждый промпт имеет версию (v1.0, v1.1...) для A/B тестирования"
- "Prompt types: signal_analysis, backtest_interpretation, annotation_generation, theory_query"
- "Usage logging: каждый вызов логируется для анализа эффективности промптов"
- "ДОБАВЛЕНО: поле 'expected_output_schema' - описание какой формат ответа ожидается от LLM"

### Подмодуль 2.8.2 — Vision Adapter

**submodule_name:** "2.8.2 Vision Adapter"

**inputs:**

- **from_source:** Prompt Manager (final prompt) + Visual Formatter (formatted PNG) + Market Tools (zones JSON для контекста)
- **data_type:** String (prompt) + PNG (image) + JSON (tools data)
- **params:** prompt, image_path, tools_summary_json, model (gpt-4-vision/gpt-4o)
- **format:**

`json`

  `{
    "prompt": "Analyze the trading chart for GER40...",
    "image": "to_vision/formatted_ger40_m15.png",
    "tools_summary": {
      "fvg": [{price_low: 15835, price_high: 15840, ...}],
      "ob": [{price_low: 15830, ...}],
      "sessions": [...]
    },
    "model": "gpt-4-vision-preview",
    "max_tokens": 1000
  }
````
- **description:** Multimodal входные данные для GPT Vision анализа

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         VISION ADAPTER                         │
├────────────────────────────────────────────────┤
│  • Multimodal prompt: image + text + JSON data │
│  • Base64 encoding PNG для OpenAI API          │
│  • Вызов GPT-4V через LangChain/OpenAI SDK     │
│  • Парсинг ответа: text + annotation_commands  │
│  • Возврат analysis + confidence + annotations │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Decision Reconciler (для финального вердикта) + Annotation Service (для визуализации) + Persistent Store (для хранения)
- **data_type:** JSON (LLM response parsed)
- **params:** analysis_text, annotation_commands[], confidence_score, proposed_tweaks
- **format:**

`json`

  `{
    "run_id": "run_2025_10_31_001",
    "signal_id": "sig_001",
    "llm_model": "gpt-4-vision-preview",
    "analysis_text": "Setup confirmed. Frankfurt session high swept, clean OB retest at 15830. FVG aligns with entry. Risk: low liquidity period ahead.",
    "confidence_score": 0.82,
    "recommendation": "entry_approved",
    "risk_factors": ["Low liquidity 12:00-13:00 GMT", "News event at 14:00"],
    "annotation_commands": [
      {"op": "line", "x1": ..., "label": "Liquidity sweep"},
      {"op": "arrow", "x1": ..., "label": "Entry direction"}
    ],
    "proposed_rule_tweak": null,
    "tokens_used": 876,
    "response_time_sec": 3.2
  }`

- **description:** Структурированный анализ от LLM с рекомендациями и командами аннотаций

**logic_notes:**

- "Image encoding: PNG → base64 для OpenAI API (или URL если hosted)"
- "Tools summary включается в prompt как контекст: 'Python detected FVG at 15835, OB at 15830...'"
- "LLM должен возвращать JSON с полями: analysis_text, confidence, recommendation, annotation_commands"
- "Parsing response: regex или JSON mode (OpenAI function calling) для извлечения structured data"
- "Rate limiting: max 10 requests/min (configurable), exponential backoff при 429 errors"
- "ДОБАВЛЕНО: retry logic с 3 попытками при API errors, fallback на simplified prompt если timeout"

### Подмодуль 2.8.3 — LLM Chains & Agents (LangChain)

**submodule_name:** "2.8.3 LLM Chains & Agents"

**inputs:**

- **from_source:** Vision Adapter (для vision chain) или User Query (для theory search) + ChromaDB (для retrieval)
- **data_type:** String (query) + PNG (optional) + JSON (context from retrieval)
- **params:** chain_type (vision|summarizer|classifier|retrieval), input_data, tools[]
- **format:**

json

  `{
    "chain_type": "retrieval_qa",
    "query": "Что такое Order Block в SMC методологии?",
    "retrieval_source": "chroma_theory_docs",
    "tools": ["chroma.query", "summarizer"],
    "max_results": 5
  }
````
- **description:** Конфигурация LangChain chain для различных задач

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      LLM CHAINS & AGENTS (LangChain)           │
├────────────────────────────────────────────────┤
│  • Vision chain: image → analyzer → output     │
│  • Summarizer chain: long text → concise       │
│  • Classifier chain: signal → category/quality │
│  • Retrieval QA: query → Chroma → answer       │
│  • Agent: tool-using (notion_upload, chroma.q) │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** зависит от chain type: Vision Adapter, User Interface, Notion, Database
- **data_type:** JSON или String (chain output)
- **params:** chain_type, output, intermediate_steps[], tokens_used
- **format:**

`json`

  `{
    "chain_type": "retrieval_qa",
    "query": "Что такое Order Block?",
    "answer": "Order Block - это последняя противоположная свеча перед сильным импульсом. В SMC методологии используется как зона интереса для входа...",
    "sources": [
      {"doc_id": "theory_smc_v1", "chunk": 3, "score": 0.89},
      {"doc_id": "ict_concepts", "chunk": 12, "score": 0.76}
    ],
    "intermediate_steps": [
      "Retrieved 5 documents from Chroma",
      "Summarized top 2 most relevant",
      "Generated answer based on context"
    ],
    "tokens_used": 645
  }`

- **description:** Результат выполнения LangChain chain с трассировкой шагов

**logic_notes:**

- "Vision chain: используется в Vision Adapter для image→text→structured_output pipeline"
- "Retrieval QA: для ответов на вопросы пользователя с приоритетом на theory_docs из Chroma"
- "Classifier chain: определяет качество сигнала (A/B/C grade) на основе features"
- "Agent mode: LangChain agent с tools=[chroma.query, notion_upload, web_search] для сложных задач"
- "ДОБАВЛЕНО: chain versioning - каждая chain имеет версию для A/B тестирования различных конфигураций"

### Подмодуль 2.8.4 — Prompt Version Registry

**submodule_name:** "2.8.4 Prompt Version Registry"

**inputs:**

- **from_source:** Prompt Manager (при создании/обновлении промпта)
- **data_type:** Text (prompt template) + JSON (metadata)
- **params:** prompt_id, version, template_text, variables[], created_by
- **format:**

json

  `{
    "prompt_id": "signal_analysis",
    "version": "v1.2",
    "template_file": "prompts/signal_analysis_v1_2.txt",
    "template_text": "Analyze the trading chart...",
    "variables": ["symbol", "timeframe", "zones_summary", "entry", "sl", "tp"],
    "created_by": "user_admin",
    "created_at": "2025-10-15T14:00:00Z",
    "hash": "sha256:abc123...",
    "parent_version": "v1.1",
    "changes": "Added risk_factors section to output"
  }
````
- **description:** Новая версия промпта с метаданными и историей изменений

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      PROMPT VERSION REGISTRY                   │
├────────────────────────────────────────────────┤
│  • Хранение всех версий промптов               │
│  • Hash для идентификации изменений            │
│  • Связь parent_version → child_version        │
│  • Usage tracking (сколько раз использовался)  │
│  • Performance metrics по версиям              │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** DATABASE (prompt versions table) + ARCHIVE (prompts/ папка)
- **data_type:** Database record + Text file
- **params:** prompt_id, version, file_path, hash, usage_count, avg_performance
- **format:** 
````
  DB record: {
    id, prompt_id, version, file_path, hash,
    created_at, created_by, parent_version, changes,
    usage_count: 0, avg_response_time: null, avg_quality_score: null
  }
  File: prompts/signal_analysis_v1_2.txt`

- **description:** Версионированный промпт с трассируемостью и метриками использования

**logic_notes:**

- "Hash рассчитывается от template_text для детекта изменений (если hash совпадает - та же версия)"
- "Parent version: v1.2 ссылается на v1.1 - можно восстановить историю эволюции промпта"
- "Usage tracking: инкрементируется каждый раз при использовании промпта"
- "Performance metrics: avg_quality_score обновляется на основе feedback (✅/❌ от трейдера)"
- "ДОБАВЛЕНО: A/B testing support - возможность сравнения двух версий промпта side-by-side"

### Подмодуль 2.8.5 — Prompt Testing Harness

**submodule_name:** "2.8.5 Prompt Testing Harness"

**inputs:**

- **from_source:** Prompt Version Registry (промпты для тестирования) + Test Dataset (контрольные данные)
- **data_type:** List of prompts + JSON (test cases)
- **params:** prompts_to_test[], test_dataset[], expected_outputs[]
- **format:**

json

  `{
    "test_id": "prompt_test_001",
    "prompts": ["signal_analysis_v1.1", "signal_analysis_v1.2"],
    "test_dataset": [
      {
        "case_id": "test_case_1",
        "symbol": "GER40",
        "image": "test_data/ger40_frank_raid.png",
        "zones": {...},
        "expected_output": {
          "recommendation": "approve",
          "confidence": ">0.7",
          "annotation_commands_count": ">2"
        }
      },
      ...
    ]
  }
````
- **description:** Набор промптов и тестовых кейсов для сравнительного тестирования

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      PROMPT TESTING HARNESS                    │
├────────────────────────────────────────────────┤
│  • Unit tests для промптов на control dataset  │
│  • Сравнение output разных версий промпта      │
│  • Метрики: accuracy, precision, response_time │
│  • Automated regression testing при изменениях │
│  • Визуализация результатов (pass/fail report) │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** DATABASE (test results) + Streamlit Dashboard (визуализация) + Logs
- **data_type:** JSON (test report)
- **params:** test_id, prompts_tested, pass_rate, metrics_by_prompt
- **format:**

json

  `{
    "test_id": "prompt_test_001",
    "test_date": "2025-10-31",
    "prompts_tested": ["v1.1", "v1.2"],
    "test_cases_count": 20,
    "results": {
      "v1.1": {
        "pass_rate": 0.75,
        "avg_confidence": 0.72,
        "avg_response_time": 3.5,
        "failed_cases": ["test_case_5", "test_case_12"]
      },
      "v1.2": {
        "pass_rate": 0.85,
        "avg_confidence": 0.78,
        "avg_response_time": 3.2,
        "failed_cases": ["test_case_12"]
      }
    },
    "winner": "v1.2",
    "recommendation": "Deploy v1.2 as default"
  }`

- **description:** Сравнительный отчёт эффективности промптов

**logic_notes:**

- "Control dataset: 20-50 размеченных кейсов с known good/bad signals для consistent testing"
- "Pass criteria: output должен совпадать с expected (например confidence >0.7, recommendation=approve)"
- "Automated testing: запускается при каждом изменении промпта (CI/CD style)"
- "Regression detection: если новая версия промпта хуже предыдущей - alert"
- "ДОБАВЛЕНО: cost tracking - расчёт стоимости каждого промпта (tokens used × price)"

### Подмодуль 2.8.6 — API Adapter (Rate-limit / Retry / Backoff)

**submodule_name:** "2.8.6 API Adapter"

**inputs:**

- **from_source:** Vision Adapter или LLM Chains (API запросы к OpenAI/LLM)
- **data_type:** JSON (API request)
- **params:** endpoint, payload, headers, retry_config
- **format:**

json

  `{
    "endpoint": "https://api.openai.com/v1/chat/completions",
    "method": "POST",
    "payload": {...},
    "headers": {"Authorization": "Bearer sk-..."},
    "retry_config": {
      "max_retries": 3,
      "backoff_factor": 2,
      "retry_on": [429, 500, 502, 503]
    }
  }
````
- **description:** API запрос с конфигурацией retry логики

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      API ADAPTER (Rate-limit/Retry/Backoff)    │
├────────────────────────────────────────────────┤
│  • Обработка rate limits (429 errors)          │
│  • Exponential backoff при ошибках API         │
│  • Retry logic (max 3 attempts)                │
│  • Timeout handling (30 sec default)           │
│  • Circuit breaker pattern при длительных сбоях│
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Вызывающий модуль (Vision Adapter/Chains) + Logs (error tracking)
- **data_type:** JSON (API response) или Error object
- **params:** success (bool), response_data, attempts_made, error_details
- **format:**

json

  `{
    "success": true,
    "response": {...LLM output...},
    "attempts_made": 1,
    "response_time_sec": 3.2,
    "tokens_used": 876,
    "cost_usd": 0.0263
  }
  OR (при ошибке):
  {
    "success": false,
    "error_type": "RateLimitError",
    "error_message": "Rate limit exceeded (429)",
    "attempts_made": 3,
    "retry_after_sec": 60,
    "circuit_breaker_triggered": false
  }`

- **description:** Успешный ответ API или детали ошибки с retry информацией

**logic_notes:**

- "Rate limit handling: при 429 ошибке - exponential backoff (1s, 2s, 4s, 8s...)"
- "Retryable errors: 429 (rate limit), 500/502/503 (server errors), timeout"
- "Non-retryable: 400 (bad request), 401 (auth), 403 (forbidden) - немедленный fail"
- "Circuit breaker: если 10 подряд requests failed - остановка на 5 минут (configurable)"
- "Timeout: default 30 sec для API calls, configurable per endpoint"
- "ДОБАВЛЕНО: request queuing - при rate limit добавление запроса в очередь вместо immediate fail"

### Подмодуль 2.8.7 — **Decision Reconciler**

**submodule_name:** "2.8.7 **Decision Reconciler**"

**inputs:**

- **from_source:** Rule Executor (Python-based signal) + Vision Adapter (LLM analysis) + ML Scoring Module (probability score)
- **data_type:** JSON (signal from Python) + JSON (LLM analysis) + float (ML score)
- **params:** python_signal, llm_analysis, ml_probability, reconciliation_rules
- **format:**

json

  `{
    "python_signal": {
      "signal_id": "sig_001",
      "entry": 15840, "sl": 15800, "tp": 15900,
      "confidence": 0.75,
      "detectors_used": ["Detect_FVG", "Detect_OB"]
    },
    "llm_analysis": {
      "recommendation": "entry_approved",
      "confidence": 0.82,
      "risk_factors": [...]
    },
    "ml_probability": 0.68,
    "reconciliation_rules": {
      "min_agreement": 0.7,
      "require_llm_approval": true
    }
  }
````
- **description:** Три источника оценки сигнала для агрегации финального решения

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       DECISION RECONCILER                      │
├────────────────────────────────────────────────┤
│  • Агрегация: Python signal + LLM + ML score   │
│  • Проверка согласованности (agreement check)  │
│  • Расчёт финального confidence (weighted avg) │
│  • Вердикт: approve/reject/review_required     │
│  • Логирование разногласий для анализа         │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Live Handler (если live mode) или Backtester (если backtest) + DATABASE (decision log)
- **data_type:** JSON (final decision)
- **params:** decision, final_confidence, reasons[], disagreements[]
- **format:**

json

  `{
    "signal_id": "sig_001",
    "decision": "approve",
    "final_confidence": 0.75,
    "confidence_breakdown": {
      "python_detector": 0.75,
      "llm_analysis": 0.82,
      "ml_model": 0.68,
      "weighted_avg": 0.75
    },
    "reasons": [
      "All three sources agree on entry direction",
      "LLM confirmed setup with high confidence",
      "ML probability above threshold (>0.6)"
    ],
    "disagreements": [],
    "timestamp": "2025-10-31T10:20:00Z"
  }`

- **description:** Финальное решение с обоснованием и уровнем уверенности

**logic_notes:**

- "Agreement check: если Python и LLM не согласны (противоположные recommendation) → decision='review_required'"
- "Weighted average: Python confidence 40%, LLM 40%, ML 20% (configurable weights)"
- "Threshold: final_confidence > 0.7 для approve, <0.5 для reject, между = review_required"
- "Disagreements логируются для последующего анализа (почему источники расходятся)"
- "ДОБАВЛЕНО: поле 'dominant_source' - какой источник имел решающий вес в финальном решении"

### Подмодуль 2.8.8 — Safety / Sanity Checks

**submodule_name:** "2.8.8 Safety / Sanity Checks"

**inputs:**

- **from_source:** Vision Adapter (LLM output JSON) перед использованием
- **data_type:** JSON (LLM response)
- **params:** response_json, expected_schema, sanity_rules
- **format:**

json

  `{
    "response": {
      "analysis_text": "...",
      "confidence": 0.82,
      "annotation_commands": [...]
    },
    "expected_schema": {
      "required_fields": ["analysis_text", "confidence", "annotation_commands"],
      "types": {"confidence": "float", "annotation_commands": "array"}
    },
    "sanity_rules": {
      "confidence_range": [0.0, 1.0],
      "max_annotation_commands": 10,
      "forbidden_ops": ["delete", "execute"]
    }
  }
````
- **description:** LLM output для валидации перед применением

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      SAFETY / SANITY CHECKS                    │
├────────────────────────────────────────────────┤
│  • Валидация JSON schema LLM output            │
│  • Проверка annotation_commands безопасности   │
│  • Sanity checks: confidence в [0,1], coords   │
│  • Forbidden operations filter                 │
│  • Блокировка dangerous commands               │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Annotation Service (validated commands) ИЛИ Error Handler (если validation failed)
- **data_type:** JSON (validated) или Error object
- **params:** is_valid (bool), validated_data, errors[], warnings[]
- **format:**

json

  `{
    "is_valid": true,
    "validated_data": {...},
    "errors": [],
    "warnings": ["Confidence close to upper limit (0.99), verify manually"],
    "timestamp": "2025-10-31T10:20:00Z"
  }
  OR:
  {
    "is_valid": false,
    "errors": [
      "Missing required field: annotation_commands",
      "Invalid confidence value: 1.5 (must be 0.0-1.0)",
      "Forbidden op detected: 'execute' in annotation_commands"
    ],
    "raw_response": {...}
  }`

- **description:** Результат валидации с детализацией ошибок

**logic_notes:**

- "Schema validation через pydantic models - строгая проверка типов и required fields"
- "Annotation commands safety: проверка что операции только draw-related (line, arrow, text), НЕ execute/delete/modify"
- "Sanity checks: confidence в [0, 1], coordinates в пределах графика, max 10 annotation commands"
- "Warnings vs Errors: warnings не блокируют использование, errors - блокируют"
- "ДОБАВЛЕНО: injection protection - детекция попыток code injection в annotation text/labels"

### Подмодуль 2.8.9 — LLM Call Logger

**submodule_name:** "2.8.9 LLM Call Logger"

**inputs:**

- **from_source:** Vision Adapter, LLM Chains (каждый вызов LLM)
- **data_type:** JSON (call metadata)
- **params:** call_id, model, prompt_id, tokens_used, cost, response_time, success
- **format:**

json

  `{
    "call_id": "llm_call_2025_10_31_001",
    "timestamp": "2025-10-31T10:15:30Z",
    "model": "gpt-4-vision-preview",
    "prompt_id": "signal_analysis_v1.2",
    "prompt_hash": "sha256:abc...",
    "input_tokens": 450,
    "output_tokens": 426,
    "total_tokens": 876,
    "cost_usd": 0.0263,
    "response_time_sec": 3.2,
    "success": true,
    "error": null,
    "run_id": "run_2025_10_31_001"
  }
````
- **description:** Метаданные каждого вызова LLM для анализа стоимости и качества

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       LLM CALL LOGGER                          │
├────────────────────────────────────────────────┤
│  • Логирование каждого LLM API вызова          │
│  • Трекинг tokens used и cost (USD)            │
│  • Response time monitoring                    │
│  • Связь с prompt_id и run_id (трассировка)    │
│  • Агрегация статистики (daily cost, usage)    │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** DATABASE (llm_calls table) + Monitoring Dashboard + Cost Analytics
- **data_type:** Database record per call + aggregated metrics JSON
- **params:** call_id, timestamp, model, tokens, cost, связь с run_id/prompt_id
- **format:** 
````
  DB record per call: {call_id, timestamp, model, prompt_id, tokens, cost, response_time, success, run_id}
  
  Aggregated daily: {
    "date": "2025-10-31",
    "total_calls": 234,
    "total_tokens": 205340,
    "total_cost_usd": 6.16,
    "avg_response_time": 3.1,
    "success_rate": 0.97,
    "by_model": {
      "gpt-4-vision": {"calls": 120, "cost": 4.50},
      "gpt-4": {"calls": 114, "cost": 1.66}
    }
  }`

- **description:** Детальный лог вызовов + агрегированная статистика по периодам

**logic_notes:**

- "Cost calculation: tokens × pricing (например gpt-4-vision: $0.03/1K tokens input, $0.06/1K output)"
- "Связь с run_id: возможность посчитать стоимость конкретного backtest run"
- "Связь с prompt_id: анализ какие промпты самые дорогие/медленные"
- "Daily limits: alert если daily_cost > threshold (например $50/day)"
- "ДОБАВЛЕНО: quality metrics - связь с feedback (✅/❌) для анализа cost vs quality"
 