# 07_Visualization_Engine
Описание модуля и его назначения.
### **Visualisation Engine**

**2.7.1** **Dash Visualizer (Plotly-based)** — рендер графиков по входным данным MT5 + отмеченным зонам в TV-похожем стиле; генерирует PNG и интерактивную HTML-панель.
Plotly candlestick + overlaid zones (FVG, OB, session boxes, entry SL TP).

**2.7.2 TV-like Styling Module** — набор параметров стиля (цвета свечей, фон, шрифты, прозрачности зон) и тема стиля как в Трейдинг Вью, чтобы унифицировать визуализацию под «эталон» для обучения GPT Vision.

Configurable TV-like theme (stored in `style/theme.yaml`).

**2.7.3 Visual Formatter** - под модуль постобработки изображений после визуализации. Он обеспечивает стандартизацию и очистку финальных графиков перед подачей в GPT Vision:
приводит все скриншоты к единому виду, масштабу и цветовой схеме, добавляет подписи и вырезает лишние элементы.
Normalize PNG size, colors, crop, watermark, add labels (timeframe, symbol, run_id).

**2.7.4 Annotation Service** — сервис, принимающий команды (draw position/line/arrow/text) для имитации GPT Виженом действий трейдера и последующей записи этого анализа в журнал. Дает команду в **Dash Visualizer** отрисовать анализ на графике

Применяет команды аннотаций (из LLM) к PNG. Формат команд:

```jsx
[ {"op":"line","x1":..,"y1":..,"x2":..,"y2":..,"label":"liquidity"}, ... ]
```

Выполняет рендеринг на изображении и сохраняет в файл `exchange/annotated`.

output `png_annotated_path` и метаданные `annotation_json`

Acceptance: PNG-файлы должны быть согласованы между запусками; выходной скрин - аннотации LLM накладываются точно на входящий скриншот.

Гарантировать, что при каждом сэмпле бэктеста сохраняется `png_original` и возвращается путь.

**Vision Adapter** outputs - Schema Validation 
schemas (напр. `signal_schema`, `annotation_schema`) и валидатор (pydantic).

**Коротко — круговорот PNG в проекте:**

- **Dash** — создает PNG (оригинал).
- **LLM (Vision Adapter)** — анализирует PNG и возвращает аннотации.
- **Annotation Service** — создаёт annotated PNG.
- **Backtester Core** — **включает пути** к PNG(ориг/аннот) в отчёт; **Notion Uploader** — отправляет PNG в журнал.


## ⚙️ ASCII схема
## МОДУЛЬ 2.7 — Visualisation Engine

### Подмодуль 2.7.1 — Dash Visualizer (Plotly-based)

**submodule_name:** "2.7.1 Dash Visualizer (Plotly-based)"

**inputs:**
- **from_source:** Data Processor (candles DataFrame) + Market Tools (zones JSON: FVG, OB, sessions, liquidity) + Rule Executor (signals JSON с entry/sl/tp)
- **data_type:** DataFrame (candles) + JSON (zones) + JSON (signals)
- **params:** symbol, timeframe, zones[], signals[], style_config
- **format:** 
```
  candles_df: [time, ohlcv, ...]
  zones: [{type, start, end, price_low, price_high, ...}, ...]
  signals: [{entry_price, sl_price, tp_price, entry_timestamp, ...}, ...]
  style_config: {"theme": "tv_dark", "colors": {...}}
```
- **description:** Данные для визуализации графика со всеми зонами и сигналами

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│     DASH VISUALIZER (Plotly-based)             │
├────────────────────────────────────────────────┤
│  • Plotly candlestick chart                    │
│  • Overlay зон (FVG, OB, sessions как boxes)   │
│  • Entry/SL/TP маркеры на графике              │
│  • TradingView-подобный стиль                  │
│  • Генерация PNG и интерактивного HTML         │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** Visual Formatter (для постобработки) + ARCHIVE (to_vision/ папка) + GPT Vision Adapter (для анализа)
- **data_type:** PNG файл + HTML (интерактивный график)
- **params:** file_path, width, height, zones_count, signals_count
- **format:** 
````
  PNG: D:/ITA/ITA_1.0/exchange/to_vision/{symbol}_{tf}_{timestamp}.png
  HTML: D:/ITA/ITA_1.0/exchange/interactive/{symbol}_{tf}_{timestamp}.html
  Metadata JSON: {
    "file_path": "...",
    "symbol": "GER40",
    "timeframe": "M15",
    "time_range": ["2025-10-31T08:00", "2025-10-31T12:00"],
    "zones_rendered": 5,
    "signals_rendered": 2
  }`

- **description:** Визуализированный график в PNG и HTML форматах с метаданными

**logic_notes:**

- "Zones рендерятся как прозрачные прямоугольники с цветом по типу: FVG=blue, OB=orange, sessions=grey"
- "Entry/SL/TP как markers: entry=green circle, sl=red line, tp=green line"
- "TradingView стиль: тёмный фон, зелёные/красные свечи, чистая сетка"
- "PNG размер: стандартно 1920x1080 для GPT Vision (configurable)"
- "HTML для интерактивного просмотра: с zoom, pan, hover tooltips"
- "ДОБАВЛЕНО: watermark с run_id в углу PNG для трассируемости"

### Подмодуль 2.7.2 — TV-like Styling Module

**submodule_name:** "2.7.2 TV-like Styling Module"

**inputs:**

- **from_source:** Configuration файл (style/theme.yaml) или USER_REQUEST (кастомная тема через UI)
- **data_type:** YAML файл
- **params:** theme_name, colors, fonts, transparency_levels, candlestick_style
- **format:**

yaml

  `theme_name: "tv_dark"
  background_color: "#131722"
  grid_color: "#363c4e"
  candle_colors:
    up: "#26a69a"
    down: "#ef5350"
  zone_colors:
    fvg: "rgba(33, 150, 243, 0.3)"
    ob: "rgba(255, 152, 0, 0.3)"
    session: "rgba(158, 158, 158, 0.2)"
  fonts:
    main: "Arial, sans-serif"
    size: 12
````
- **description:** Параметры стиля для унификации визуализации под TradingView

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│      TV-LIKE STYLING MODULE                    │
├────────────────────────────────────────────────┤
│  • Централизованное хранение параметров стиля  │
│  • TradingView тема (dark/light)               │
│  • Цвета свечей, фон, сетка, зоны              │
│  • Шрифты, размеры, прозрачности               │
│  • Применение темы ко всем визуализациям       │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Dash Visualizer (применение стиля при рендере) + Visual Formatter (для постобработки)
- **data_type:** Python dict (parsed YAML)
- **params:** theme_name, style_config_dict
- **format:**

python

  `{
    "theme_name": "tv_dark",
    "background_color": "#131722",
    "candle_colors": {"up": "#26a69a", "down": "#ef5350"},
    "zone_colors": {...},
    "fonts": {...}
  }`

- **description:** Готовый конфиг стиля для применения к Plotly графикам

**logic_notes:**

- "Единая тема для ВСЕХ визуализаций - гарантирует консистентность для обучения GPT Vision"
- "TradingView dark - эталон стиля (большинство трейдеров привыкли к этому виду)"
- "Transparency levels: зоны полупрозрачные (0.2-0.3 alpha) чтобы не закрывать свечи"
- "Theme switching: возможность переключения dark/light через UI (но default всегда dark)"
- "ДОБАВЛЕНО: preset themes - несколько готовых тем (tv_dark, tv_light, custom_1) для выбора"

### Подмодуль 2.7.3 — Visual Formatter

**submodule_name:** "2.7.3 Visual Formatter"

**inputs:**

- **from_source:** Dash Visualizer (raw PNG файлы)
- **data_type:** PNG файл
- **params:** file_path, target_size, normalization_rules, crop_margins, watermark_config
- **format:**

json

  `{
    "input_png": "to_vision/raw_ger40_m15.png",
    "target_size": [1920, 1080],
    "normalization": {
      "color_space": "RGB",
      "contrast": "auto_adjust"
    },
    "crop": {"top": 50, "bottom": 50, "left": 0, "right": 0},
    "watermark": {"text": "run_id", "position": "bottom_right"}
  }
````
- **description:** Сырой PNG для постобработки и стандартизации

`**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         VISUAL FORMATTER                       │
├────────────────────────────────────────────────┤
│  • Нормализация размера PNG (resize to target) │
│  • Нормализация цветов (RGB, contrast)         │
│  • Crop лишних элементов (margins)             │
│  • Добавление watermark (run_id, timestamp)    │
│  • Добавление labels (symbol, timeframe)       │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** ARCHIVE (to_vision/ финальные PNG) + GPT Vision Adapter (для анализа)
- **data_type:** PNG файл (formatted)
- **params:** output_path, processing_applied[], file_size_kb
- **format:** 
````
  Output PNG: to_vision/formatted_ger40_m15_20251031.png
  Metadata: {
    "original_file": "raw_ger40_m15.png",
    "size": [1920, 1080],
    "processing": ["resize", "crop", "watermark", "contrast_adjust"],
    "file_size_kb": 245,
    "ready_for_llm": true
  }`

- **description:** Стандартизированный PNG готовый для подачи в GPT Vision

**logic_notes:**

- "Resize: все PNG приводятся к 1920x1080 (оптимально для GPT-4V, не слишком большой размер)"
- "Crop: удаление пустых margins сверху/снизу если есть (для фокуса на графике)"
- "Contrast auto_adjust: усиление контраста если изображение слишком тёмное/светлое"
- "Watermark: run_id в правом нижнем углу малозаметным шрифтом для трассировки"
- "Labels: добавление текста в верхний угол: 'GER40 M15' для идентификации без метаданных"
- "ДОБАВЛЕНО: детекция и удаление артефактов (например glitches от Plotly rendering)"

### Подмодуль 2.7.4 — Annotation Service

**submodule_name:** "2.7.4 Annotation Service"

**inputs:**

- **from_source:** GPT Vision Adapter (annotation commands JSON) + Dash Visualizer (original PNG)
- **data_type:** JSON (commands) + PNG (base image)
- **params:** png_path, annotation_commands[]
- **format:**

json

  `{
    "input_png": "to_vision/formatted_ger40_m15.png",
    "annotation_commands": [
      {
        "op": "line",
        "x1": "2025-10-31T10:00", "y1": 15840.0,
        "x2": "2025-10-31T11:00", "y2": 15840.0,
        "color": "red",
        "width": 2,
        "label": "Liquidity level"
      },
      {
        "op": "arrow",
        "x1": "2025-10-31T10:30", "y1": 15850.0,
        "x2": "2025-10-31T10:30", "y2": 15830.0,
        "color": "green",
        "label": "Entry direction"
      },
      {
        "op": "text",
        "x": "2025-10-31T10:15", "y": 15860.0,
        "text": "OB zone confirmed",
        "color": "yellow"
      }
    ]
  }
```
- **description:** Команды от LLM для отрисовки анализа на графике

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       ANNOTATION SERVICE                       │
├────────────────────────────────────────────────┤
│  • Приём команд аннотаций от GPT Vision        │
│  • Рендеринг: line, arrow, rectangle, text     │
│  • Overlay на исходный PNG                     │
│  • Координаты: time+price → pixel conversion   │
│  • Сохранение annotated PNG                    │
└────────────────────────────────────────────────┘
````

**outputs:**
- **destination:** ARCHIVE (annotated/ папка) + Notion Uploader (для журнала) + Backtester Core (для включения в отчёт)
- **data_type:** PNG (annotated) + JSON (metadata)
- **params:** output_png_path, annotations_applied[], annotation_json_path
- **format:** 
```
  PNG: exchange/annotated/ger40_m15_20251031_annotated.png
  `Metadata JSON: {
    "original_png": "to_vision/formatted_ger40_m15.png",
    "annotated_png": "annotated/ger40_m15_annotated.png",
    "annotations_count": 3,
    "annotations": [{op, x1, y1, ...}, ...],
    "created_by": "GPT_Vision_Adapter",
    "timestamp": "2025-10-31T10:20:00Z"
  }
````
- **description:** Аннотированный PNG с анализом LLM визуализированным на графике

**logic_notes:**
- "Coordinate conversion: time+price (из annotation commands) → x,y pixels с учётом масштаба графика"
- "Supported ops: line, arrow, rectangle, circle, text - основные примитивы для разметки"
- "Colors: используются контрастные цвета (red, green, yellow) для видимости поверх графика"
- "Overlay: аннотации рисуются ПОВЕРХ исходного PNG без изменения оригинала"
- "Validation: проверка что coordinates в пределах графика (не за границами time/price range)"
- "ДОБАВЛЕНО: opacity control для аннотаций - полупрозрачные элементы не закрывают свечи"

---