# ITA 

## 3. Потоки данных — подробный сценарий (Live Trading)

1. Пользовательский запрос (через Streamlit UI или API):
→ передаёт `setup_id` и параметры (symbol, timeframe, period, mode)
2. **Poll MT5 (1 min)** → `get_ohlcv(symbol,t)` → cache and process.
3. **Setup Manager**: check rules for active setups.
- загружает YAML этого `setup_id` (из Data Storage)
- парсит, какие Market Tools нужны
- формирует задание (pipeline spec)
1. **Market Tools**: detect session break, FVG, liquidity.
вызываются динамически **только те**, что прописаны в YAML
- возвращают JSON с фичами, нужными этому сетапу
1. **Setup Manager**:
- получает результаты Market Tools
- применяет Rule Logic и принимает решение (signal / no signal)
1. **If candidate signal**:
    - package `snapshot`: create 2–4 PNGs (H1,M15,M5,M1) → save to `exchange/to_vision`.
    - compute ML score (`p_success`) using classifier.
2. **Decision**:
    - if `p_success > threshold` and rule passes hard checks → create `alert`.
3. **Alert**:
    - Prefect triggers `llm_analysis(task)` providing PNG paths + JSON meta.
    - LangChain chain (Vision Adapter) analyzes → returns annotated PNG + text.
    - Prefect uploads annotated PNG + analysis to Notion, sends Telegram message with short comment and link.
4. **Feedback**:
    - Trader marks in Streamlit; label saved; eventually used for retraining.

---

## 4. Interfaces & JSON schemas — примеры

### Detector output schema (already shown)

### Signal schema

```json
{
  "signal_id":"sig_20251031_001",
  "symbol":"GER40",
  "tf":"M15",
  "entry_price": 15840,
  "sl_price": 15800,
  "tp_price": 15900,
  "confidence": 0.78,
  "rule_id":"IB_raid_v1",
  "rule_version":"v1.2",
  "meta": {"detectors":["FVG","SessionBreak"], "candles": 3 }
}

```

### Backtest result schema

```json
{
  "run_id":"bt_2025_10_31_001",
  "setup_id":"IB_raid_v1",
  "symbol":"GER40",
  "period":["2025-05-01","2025-10-31"],
  "trades_count": 234,
  "winrate": 0.61,
  "avg_rr": 1.8,
  "max_drawdown": 0.12,
  "trades_csv":"path/to/trades.csv",
  "png_sample":"path/to/sample.png"
}

```
## Пример Потоки данных — подробный сценарий - Бектест:

1. **START (User Trigger)**
    - Какой тип: ручной (кнопка) или API (HTTP POST).
    - Payload — пример JSON, который START будет отправлять в Setup Manager:
        
        ```json
        {
          "setup_id": "asia_fvg_break",
          "symbol": "EURUSD",
          "timeframe": "M15",
          "start": "2025-01-01",
          "end": "2025-10-01",
          "mode": "backtest",
          "extra": {"rr": "1:2", "max_trades": 100}
        }
        
        ```
        
    - Соединяешь кнопку Start → Setup Manager node.
2. **Setup Manager node**
    - **Вход:** JSON от START.
    - **Действие:** загрузить правило YAML (из Data Storage) по `setup_id`. Парсить список `required_tools`.
    - **Выход:** формирует контекст для Data Ingest: `{symbol, timeframe, start, end, required_tools, rule_params}` и вызывает следующую ноду.
    - **В визуальном редакторе**: подключи Setup Manager к Data Ingest ноде (стрелка).
3. **Data Ingest node (MT5 Connector)**
    - **Вход:** контекст от Setup Manager.
    - **Действие:** получить свечи (или загрузить CSV), вернуть raw DataFrame (или путь к parquet).
    - **Выход:** path/to/parquet или serialized DataFrame (формат JSON/CSV в Flow).
    - **Соединение:** Data Ingest → Data Processor.
4. **Data Processor node**
    - **Вход:** raw DataFrame / parquet path.
    - **Действие:** унификация таймстампов, заполнение NaN, расчёт ATR/фич.
    - **Выход:** processed DataFrame (или path).
    - **Соединение:** Data Processor → Market Tools Dispatcher.
5. **Market Tools Dispatcher (динамический вызов)**
    - **Вход:** processed DataFrame + `required_tools` из Setup Manager.
    - **Действие:** вызывает **только** перечисленные детекторы (Detect_FVG, Detect_Liquidity и т.д.), собирает их JSON outputs.
    - **Выход:** `market_features JSON` — всё пакетировано.
    - **Соединение:** возвращает результат в **Setup Manager** (стрелка назад).
6. **Setup Manager (сбор результатов и rule evaluation)**
    - **Вход:** market_features JSON.
    - **Действие:** проверить условия правила (YAML) — вернуть signals или null.
    - **Если mode=backtest:** передать signals (или rule + data) в Backtester Manager.
    - **Если mode=live:** передать live signal в Live Handler (Alert pipeline).
    - **Соединение:** Setup Manager → Backtester Manager OR Setup Manager → Live Handler.
7. **Backtester Manager**
    - **Вход:** signals OR rule + historical data.
    - **Действие:** симуляция, создание trades.csv, aggregated metrics.
    - **Выход:** backtest JSON + list PNG samples (через Visualizer).
    - **Соединение:** Backtester → Visualizer → Annotation → Outputs.
8. **Live Handler**
    - **Вход:** live signal object.
    - **Действие:** формирует alert, создает snapshot (через Visualizer), запускает GPT Vision/Annotation и шлёт уведомление (Telegram/Notion).
    - **Соединение:** Live Handler → Visualizer → GPT Vision → Outputs.