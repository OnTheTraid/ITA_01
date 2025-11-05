# 09_Learning_Module
Описание модуля и его назначения.
### Learning Module. Training & Memory Subsystem

Этот модуль — критически важен для обучения.

**2.9.1 Labeling & Annotation Manager**

Менеджер маркировки и аннотаций

Простой интерфейс для быстрой маркировки: пользователь видит исходные PNG-файлы, предложения LLM, может отмечать ✅/❌ и добавлять комментарии.

Сохраняет метки в labels/, а также отправляет в Chroma в качестве метаданных.

**2.9.2 Vector DB / Semantic Memory (Chroma)**

Collections:

`theory_docs` — руководства, PDF/текстовые вставки.

`trade_cases` — вставки аннотированных сделок и сводок бэктестинга.

`prompts_history` — шаблоны подсказок и их векторы производительности.

- **Хранить скрины (embeddings) + JSON схемы**:
    - **Image embeddings** — генерировать CLIP-like эмбеддинг (dim e.g. 512) для **каждого PNG** (оригинал и аннот) и сохранять в Chroma.
    - **Textual embeddings** — для всех JSON (trade meta, rules, backtest summaries, annotation_text) — в той же базе/коллекции или соседней.
- **Метаданные для каждого вектора** (обязательно):
    - `id` (unique),
    - `file_path` (локальный путь к PNG/JSON),
    - `run_id` / `trade_id` / `setup_id` / `rule_version`,
    - `timestamp`,
    - `type` (`image`/`text`),
    - `author`/`source`.
    
    **2.9.2.1 Image Embedding Pipeline** (batch + online): при создании PNG вызывать embedder -> upsert to Chroma with metadata.
    
    **2.9.2.2 JSON Schema Embedding**: конвертировать ключевые поля JSON → текст → embed → store.
    
    **2.9.2.3** связь: **Data Storage & Versioning** должен хранить `vector_id` ↔ `file_path` link.
    
    - retention/backup policy (удерживать raw images + embeddings, или архивировать старые).
    - **Operational notes:**
        - Для быстрых запросов LLM use-retrieval: query Chroma by text/image => get top-k candidates + pass to LangChain prompt as context.
        - Для изображений: можно хранить both embeddings and thumbnails in DB metadata.
    - **Acceptance:** каждый saved PNG должен иметь corresponding embedding record with correct metadata and retrievable by `run_id`.

**2.9.3 Model Training Pipeline (phase-ready)**

- Pipelines:
    - Feature extraction (from trades) → набор данных для классификатора sklearn/lightgbm для вероятностного анализа.
    - Few-shot / fine-tune scripts (for LLM fine-tuning if provider allows).
- Tooling: `scikit-learn`, `lightgbm`, `huggingface transformers` (if local fine-tune).

**2.9.4 ML Scoring Module**

 Модуль оценки машинного обучения

- Обучает классификатор **`score_model`**, который, учитывая текущие факторы, выводит `p_success` для сигнала.
- Интегрируется в поток данных для порогового определения решений.

Acceptance:

Для классификатора: ROC-AUC > базового уровня (0,5), целевая AUC зависит от данных (≥0,65 начального).

Модель воспроизводима и подлежит повторному обучению.
 

## ⚙️ ASCII схема
## МОДУЛЬ 2.9 — Learning Module / Training & Memory Subsystem

### Подмодуль 2.9.1 — Labeling & Annotation Manager

**submodule_name:** "2.9.1 Labeling & Annotation Manager"

**inputs:**

- **from_source:** USER_REQUEST (через Streamlit UI для маркировки) + Backtester (сделки для labeling) + Vision Adapter (LLM предложения)
- **data_type:** PNG (trades screenshots) + JSON (trade metadata + LLM suggestions)
- **params:** trade_id, screenshot_path, llm_suggestion, user_feedback_ui

**format:**

json

`{
  "trade_id": "trade_001",
  "screenshot": "archive/results/trade_001.png",
  "trade_data": {
    "entry": 15840, "sl": 15800, "tp": 15900,
    "result": "win", "pnl": +60
  },
  "llm_suggestion": {
    "quality": "A",
    "confidence": 0.82,
    "comment": "Clean setup, all criteria met"
  },
  "user_feedback_ui": {
    "buttons": ["✅ Approve", "❌ Reject", "⚠️ Review", "✏️ Add Comment"]
  }
}
````
- **description:** Сделка с LLM предложением для быстрой маркировки трейдером

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│   LABELING & ANNOTATION MANAGER                │
├────────────────────────────────────────────────┤
│  • Streamlit UI для быстрой маркировки         │
│  • Просмотр PNG + LLM suggestions              │
│  • Кнопки: ✅/❌/⚠️ + текстовый комментарий    │
│  • Сохранение labels в labels/ + Chroma meta   │
│  • Bulk labeling (массовая маркировка)         │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** ARCHIVE (labels/ папка) + ChromaDB (metadata update) + DATABASE (labels table) + ML Training Pipeline
- **data_type:** JSON (label record)
- **params:** trade_id, label, user_feedback, comment, timestamp, labeler_id
- **format:**

json

`{
  "trade_id": "trade_001",
  "screenshot": "archive/results/trade_001.png",
  "label": "approved",
  "quality_grade": "A",
  "user_comment": "Perfect Frank raid setup, exactly as expected",
  "llm_agreed": true,
  "labeler_id": "trader_1",
  "timestamp": "2025-10-31T15:30:00Z",
  "chroma_vector_id": "vec_001"
}`

- **description:** Сохранённая метка с комментарием для обучения

**logic_notes:**

- "Streamlit UI: grid view с PNG preview, LLM suggestion справа, кнопки снизу"
- "Quick labeling: keyboard shortcuts (Y/N/R) для быстрой маркировки без мыши"
- "Bulk mode: возможность отметить 10-20 похожих сделок одним действием"
- "Labels сохраняются как JSON файлы в labels/{trade_id}_label.json + запись в DB"
- "Chroma metadata update: добавление user_label и quality_grade к embedding записи"
- "ДОБАВЛЕНО: disagreement tracking - если user_label != llm_suggestion, пометить для review"

### Подмодуль 2.9.2 — Vector DB / Semantic Memory (Chroma)

**submodule_name:** "2.9.2 Vector DB / Semantic Memory (ChromaDB)"

**inputs:**

- **from_source:** Multiple sources: Theory Docs (PDF/text), Trade Cases (PNG + JSON), Prompts History, Backtest Results
- **data_type:** Множественный: Text, PNG (embeddings), JSON (metadata)
- **params:** collection_name, document/image, metadata, embedding_model
- **format:**

`json`

`{
  "collection": "theory_docs",
  "document": {
    "type": "text",
    "content": "Order Block definition: последняя противоположная свеча...",
    "source_file": "theory/smc_concepts.pdf",
    "page": 15
  },
  "metadata": {
    "doc_id": "smc_concepts_p15",
    "topic": "order_block",
    "author": "ICT",
    "date_added": "2025-10-15"
  },
  "embedding_model": "openai/text-embedding-ada-002"
}
```
- **description:** Документы/изображения для векторизации и хранения

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│   VECTOR DB / SEMANTIC MEMORY (ChromaDB)       │
├────────────────────────────────────────────────┤
│  • Collections: theory_docs, trade_cases,      │
│    prompts_history                             │
│  • Text embeddings (theory, backtest summaries)│
│  • Image embeddings (CLIP-like для PNG)        │
│  • Metadata rich (run_id, rule_version, labels)│
│  • Semantic search & retrieval                 │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** ChromaDB storage (локальная папка) + Retrieval queries (для LLM context)
- **data_type:** Vector embeddings + metadata records
- **params:** vector_id, collection, embedding[], metadata, similarity_score (при query)
- **format:** 
````
Storage: data/chroma/{collection_name}/
Record structure: {
  "id": "vec_theory_001",
  "embedding": [0.123, -0.456, ...] (dim 1536 for text-embedding-ada-002),
  "metadata": {
    "type": "text|image",
    "source_file": "...",
    "run_id": "...",
    "rule_version": "...",
    "timestamp": "...",
    "user_label": "approved"
  },
  "document": "original text or image path"
}

Query result: {
  "results": [
    {"id": "vec_001", "distance": 0.23, "metadata": {...}, "document": "..."},
    ...
  ],
  "query_embedding": [...],
  "top_k": 5
}`

- **description:** Векторное хранилище с rich metadata для semantic retrieval

**logic_notes:**

- "Collections разделены по типам: theory_docs (теория), trade_cases (сделки с PNG), prompts_history"
- "Text embeddings: OpenAI text-embedding-ada-002 (1536 dim) для теории и JSON summaries"
- "Image embeddings: CLIP model (512 dim) для PNG screenshots - возможность visual similarity search"
- "Metadata ОБЯЗАТЕЛЬНО включает: source, timestamp, type, и связь с run_id/rule_version для трассировки"
- "Retrieval: semantic search по query → top-k наиболее похожих векторов"
- "ДОБАВЛЕНО: hybrid search - комбинация semantic (vector) + keyword (metadata filters) для точности"

### Подмодуль 2.9.2.1 — Image Embedding Pipeline

**submodule_name:** "2.9.2.1 Image Embedding Pipeline"

**inputs:**

- **from_source:** Dash Visualizer (PNG files) + Annotation Service (annotated PNG)
- **data_type:** PNG files
- **params:** image_path, embedding_model (CLIP), batch_mode (bool)
- **format:**

json

`{
  "images": [
    "to_vision/ger40_m15_001.png",
    "annotated/ger40_m15_001_annotated.png"
  ],
  "embedding_model": "openai/clip-vit-base-patch32",
  "batch_size": 10,
  "metadata": {
    "run_id": "run_001",
    "symbol": "GER40",
    "timeframe": "M15"
  }
}
````
- **description:** PNG файлы для генерации embeddings

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│     IMAGE EMBEDDING PIPELINE                   │
├────────────────────────────────────────────────┤
│  • Batch processing PNG → embeddings           │
│  • CLIP model (512 dim vectors)                │
│  • Online mode: immediate embed при создании   │
│  • Batch mode: periodic processing накопленных │
│  • Upsert to ChromaDB с metadata               │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** ChromaDB (trade_cases collection) + DATABASE (vector_id ↔ file_path mapping)
- **data_type:** Vector embeddings + metadata records
- **params:** vector_ids[], embeddings[][], file_paths[], processing_time
- **format:**

json

`{
  "processed_images": 10,
  "embeddings_generated": 10,
  "chroma_records": [
    {
      "vector_id": "img_vec_001",
      "embedding": [0.23, -0.45, ...],
      "metadata": {
        "file_path": "to_vision/ger40_m15_001.png",
        "run_id": "run_001",
        "type": "image",
        "image_type": "original",
        "timestamp": "2025-10-31T10:15:00Z"
      }
    },
    ...
  ],
  "processing_time_sec": 2.3
}`

- **description:** Сгенерированные embeddings с метаданными в ChromaDB

**logic_notes:**

- "Online mode: при создании PNG сразу генерируется embedding и добавляется в Chroma (для live режима)"
- "Batch mode: для backtest - накопление PNG, затем batch processing (быстрее)"
- "CLIP model: используется для visual similarity - поиск похожих паттернов на графике"
- "Два типа embeddings: original PNG и annotated PNG - разные векторы для разных целей"
- "ДОБАВЛЕНО: thumbnail storage в Chroma metadata - маленькое preview изображения (base64) для быстрого просмотра"

### Подмодуль 2.9.2.2 — JSON Schema Embedding

**submodule_name:** "2.9.2.2 JSON Schema Embedding"

**inputs:**

- **from_source:** Market Tools (zones JSON), Backtester (backtest results JSON), Rule Executor (signals JSON)
- **data_type:** JSON objects
- **params:** json_object, schema_type (zone|signal|backtest_result), key_fields[]
- **format:**

`json`

`{
  "json_object": {
    "type": "fvg",
    "price_low": 15835.0,
    "price_high": 15840.0,
    "confidence": 0.82,
    "meta": {"gap_size_pct": 0.35}
  },
  "schema_type": "zone",
  "key_fields": ["type", "price_low", "price_high", "confidence"],
  "embedding_strategy": "key_fields_to_text"
}
```
- **description:** JSON данные для конвертации в text embeddings

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│     JSON SCHEMA EMBEDDING                      │
├────────────────────────────────────────────────┤
│  • Конвертация JSON key fields → text         │
│  • Text embedding (ada-002)                    │
│  • Сохранение в ChromaDB с original JSON      │
│  • Retrieval по семантике (zone type, params)  │
│  • Связь JSON ↔ image embedding (same run_id)  │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** ChromaDB (соответствующая collection) + DATABASE (mapping record)
- **data_type:** Text embedding + JSON metadata
- **params:** vector_id, embedding[], original_json, schema_type
- **format:**

json

`{
  "vector_id": "json_vec_001",
  "embedding": [0.123, -0.456, ...],
  "text_representation": "FVG zone at 15835.0-15840.0, confidence 0.82, gap size 0.35%",
  "original_json": {...},
  "metadata": {
    "schema_type": "zone",
    "zone_type": "fvg",
    "run_id": "run_001",
    "timestamp": "2025-10-31T10:15:00Z"
  }
}`

- **description:** Text embedding JSON данных для semantic search

**logic_notes:**

- "Key fields extraction: берутся только важные поля (type, prices, confidence), игнорируется meta для краткости"
- "Text representation: 'FVG zone at 15835-15840, confidence 0.82' - human-readable для embedding"
- "Связь с image: run_id позволяет найти соответствующий PNG для визуализации"
- "Use case: retrieval похожих сетапов по семантике ('find all FVG zones with high confidence')"
- "ДОБАВЛЕНО: normalized fields - prices нормализуются для сравнения (relative positions, не absolute values)"

### Подмодуль 2.9.3 — Model Training Pipeline

**submodule_name:** "2.9.3 Model Training Pipeline"

**inputs:**

- **from_source:** DATABASE (labeled trades) + ChromaDB (embeddings) + Backtester (historical results)
- **data_type:** CSV (training dataset) + JSON (config)
- **params:** training_data_path, model_type (classifier|regressor), features[], target_variable
- **format:**

csv

`# training_data.csv
trade_id,fvg_confidence,ob_confidence,liquidity_proximity,session,ml_score,winrate,result
trade_001,0.82,0.75,0.3,London,0.68,0.61,win
trade_002,0.65,0.80,0.5,NY,0.55,0.61,loss
...

# config.json
{
  "model_type": "classifier",
  "algorithm": "lightgbm",
  "features": ["fvg_confidence", "ob_confidence", "liquidity_proximity", "session_encoded"],
  "target": "result",
  "train_test_split": 0.8,
  "hyperparams": {"n_estimators": 100, "max_depth": 5}
}
````
- **description:** Подготовленный датасет и конфигурация для обучения ML модели

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│     MODEL TRAINING PIPELINE                    │
├────────────────────────────────────────────────┤
│  • Feature extraction (from trades JSON)       │
│  • Train/test split (80/20)                    │
│  • Model training (LightGBM/sklearn)           │
│  • Evaluation: ROC-AUC, precision, recall      │
│  • Model versioning & persistence (pickle)     │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** ARCHIVE (models/ папка) + DATABASE (model registry) + ML Scoring Module
- **data_type:** Pickle file (trained model) + JSON (metrics report)
- **params:** model_id, version, metrics, feature_importance, file_path
- **format:** 
````
Model file: models/signal_classifier_v1.pkl

Metrics JSON: {
  "model_id": "signal_classifier",
  "version": "v1.0",
  "algorithm": "lightgbm",
  "training_date": "2025-10-31",
  "dataset_size": 1500,
  "train_test_split": [1200, 300],
  "metrics": {
    "roc_auc": 0.72,
    "accuracy": 0.68,
    "precision": 0.71,
    "recall": 0.65,
    "f1_score": 0.68
  },
  "feature_importance": {
    "fvg_confidence": 0.35,
    "ob_confidence": 0.28,
    "liquidity_proximity": 0.22,
    "session_encoded": 0.15
  },
  "model_path": "models/signal_classifier_v1.pkl"
}`

- **description:** Обученная модель с метриками и feature importance

**logic_notes:**

- "Feature engineering: извлечение признаков из JSON (confidence scores, proximity metrics, session encoding)"
- "Algorithm: LightGBM для табличных данных (быстро, хорошая точность), sklearn для baseline"
- "Train/test split: 80/20 с stratification по target для balanced classes"
- "Baseline threshold: ROC-AUC > 0.65 для acceptance (лучше случайного 0.5)"
- "Model versioning: каждое переобучение создаёт новую версию с timestamp"
- "ДОБАВЛЕНО: cross-validation (5-fold) для robust оценки, не только single train/test split"

### Подмодуль 2.9.4 — ML Scoring Module

**submodule_name:** "2.9.4 ML Scoring Module"

**inputs:**

- **from_source:** Rule Executor (signal features) + Model Training Pipeline (trained model)
- **data_type:** JSON (signal features) + Pickle (model)
- **params:** signal_id, features{}, model_path
- **format:**

json

`{
  "signal_id": "sig_001",
  "features": {
    "fvg_confidence": 0.82,
    "ob_confidence": 0.75,
    "liquidity_proximity": 0.3,
    "session": "London",
    "atr_normalized": 0.65
  },
  "model_path": "models/signal_classifier_v1.pkl"
}
````
- **description:** Признаки сигнала для предсказания вероятности успеха

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       ML SCORING MODULE                        │
├────────────────────────────────────────────────┤
│  • Загрузка trained model (pickle)             │
│  • Feature preprocessing (encoding, scaling)   │
│  • Prediction: p_success (вероятность win)     │
│  • Explainability: feature contributions       │
│  • Integration в Decision Reconciler           │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Decision Reconciler (для финального решения) + DATABASE (prediction log)
- **data_type:** JSON (prediction result)
- **params:** signal_id, p_success, feature_contributions, model_version
- **format:**

json

`{
  "signal_id": "sig_001",
  "ml_prediction": {
    "p_success": 0.68,
    "p_failure": 0.32,
    "confidence_interval": [0.63, 0.73]
  },
  "feature_contributions": {
    "fvg_confidence": +0.12,
    "ob_confidence": +0.08,
    "liquidity_proximity": -0.03,
    "session": +0.05
  },
  "model_version": "v1.0",
  "prediction_time_ms": 15,
  "timestamp": "2025-10-31T10:20:00Z"
}`

- **description:** Вероятность успеха сигнала с объяснением вклада признаков

**logic_notes:**

- "Feature preprocessing: session encoding (London=1, NY=2...), scaling numeric features если требуется"
- "p_success = вероятность класса 'win' из classifier (0.0-1.0)"
- "Feature contributions: SHAP values или feature importance × feature value для explainability"
- "Confidence interval: bootstrap estimation для uncertainty quantification"
- "Integration: p_success передаётся в Decision Reconciler как один из трёх источников (Python, LLM, ML)"
- "ДОБАВЛЕНО: model warm-up - загрузка модели при старте приложения, не при каждом prediction (performance)"
 