# 15_Feedback_Learning
Описание модуля и его назначения.
### Модуль 16 — Feedback Loop & Continuous Learning

Цикл обратной связи и непрерывное обучение

- SignalFeedbackCollector: Трейдер отмечает ✅/❌ в Streamlit; запускает `train_model_flow` or `store_label`.
- Policy Update Manager: предлагает корректировки правил  (сохранить как черновик, требуется ручная публикация).).
- Continuous Improvement Tracker - сравнение и улучшение метрик - все backtest results, feedback, rule versions за всю историю, качественная оценка системы

## ⚙️ ASCII схема
 ## МОДУЛЬ 2.16 — Feedback Loop & Continuous Learning

### Подмодуль 2.16.1 — Signal Feedback Collector

**submodule_name:** "2.16.1 Signal Feedback Collector"

**inputs:**

- **from_source:** USER_REQUEST (✅/❌ feedback через Streamlit или Telegram) + DATABASE (signal records)
- **data_type:** JSON (feedback event)
- **params:** signal_id, user_feedback, comment (optional)
- **format:**

json

`{
  "signal_id": "sig_live_001",
  "symbol": "GER40",
  "timestamp": "2025-10-31T10:15:00Z",
  "signal_data": {
    "entry": 15840, "sl": 15800, "tp": 15900,
    "confidence": 0.75, "ml_score": 0.68
  },
  "user_feedback": "approved",
  "feedback_type": "taken_trade",
  "user_comment": "Excellent setup, clean entry",
  "trade_result": null,  # will be updated later
  "feedback_by": "trader_1",
  "feedback_timestamp": "2025-10-31T10:20:00Z"
}
```
- **description:** Feedback от трейдера на live signal

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│     SIGNAL FEEDBACK COLLECTOR                  │
├────────────────────────────────────────────────┤
│  • Streamlit UI: ✅ Took Trade / ❌ Skipped    │
│  • Telegram inline buttons для feedback        │
│  • Optional comment field                      │
│  • Сохранение feedback в labels/ + DB          │
│  • Связь signal → feedback → trade_result      │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** DATABASE (feedback table) + ChromaDB (metadata update) + Learning Module (training data)
- **data_type:** JSON (feedback record)
- **params:** signal_id, feedback, comment, linked_to_training_set
- **format:**

json

`{
  "feedback_id": "fb_001",
  "signal_id": "sig_live_001",
  "feedback": "approved",
  "comment": "Excellent setup",
  "trade_taken": true,
  "trade_result": {
    "outcome": "win",
    "pnl": +60.0,
    "exit_time": "2025-10-31T12:30:00Z",
    "exit_reason": "TP_hit"
  },
  "feedback_by": "trader_1",
  "timestamp": "2025-10-31T10:20:00Z",
  "added_to_training": true
}`

- **description:** Полный feedback record с результатом сделки

**logic_notes:**

- "Two-stage feedback: 1) immediate (took/skipped), 2) later (trade result после закрытия)"
- "Telegram inline buttons: быстрый способ дать feedback прямо из уведомления"
- "Comment optional: но рекомендуется для качественных insights"
- "Training data: approved signals с trade_result автоматически добавляются в training dataset"
- "Feedback stats: используются для Rule Profiler (winrate по rule versions)"
- "ДОБАВЛЕНО: disagreement tracking - если user skipped но ML score high → пометить для review"

### Подмодуль 2.16.2 — Policy Update Manager

**submodule_name:** "2.16.2 Policy Update Manager"

**inputs:**

- **from_source:** Learning Module (анализ feedback + backtest results) + Rule Profiler (param sensitivity)
- **data_type:** JSON (suggested changes)
- **params:** setup_id, current_version, suggested_changes[], confidence_in_change
- **format:**

json

`{
  "setup_id": "Frank_raid_v1",
  "current_version": "v1.2",
  "analysis_period": ["2025-08-01", "2025-10-31"],
  "analysis_summary": {
    "total_signals": 156,
    "user_taken": 89,
    "wins": 58,
    "losses": 31,
    "winrate": 0.65,
    "avg_rr": 1.85
  },
  "suggested_changes": [
    {
      "parameter": "components.Detect_FVG.min_gap_pct",
      "current_value": 0.2,
      "suggested_value": 0.25,
      "rationale": "Signals with gap >0.25% have 72% winrate vs 58% for 0.2-0.25%",
      "expected_improvement": "+7% winrate, -15% signal count",
      "confidence": 0.82
    }
  ],
  "recommendation": "create_draft_version",
  "requires_manual_approval": true
}
```
- **description:** Автоматически сгенерированные предложения по улучшению правил

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│     POLICY UPDATE MANAGER                      │
├────────────────────────────────────────────────┤
│  • Анализ feedback + backtest stats            │
│  • Генерация suggested parameter tweaks        │
│  • Сохранение как draft (НЕ auto-deploy)       │
│  • Manual approval required от трейдера        │
│  • A/B testing option (старая vs новая версия) │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Rule & Version Registry (draft version) + Streamlit UI (review panel) + DATABASE (suggestions log)
- **data_type:** YAML (draft rule) + JSON (suggestion metadata)
- **params:** suggestion_id, setup_id, draft_version, approval_status
- **format:**

json

`{
  "suggestion_id": "sugg_001",
  "setup_id": "Frank_raid_v1",
  "draft_version": "v1.3_draft",
  "draft_file": "rules/Frank_raid_v1/v1.3_draft.yaml",
  "suggested_changes": [...],
  "status": "pending_review",
  "created_at": "2025-10-31T16:00:00Z",
  "review_deadline": "2025-11-07T00:00:00Z",
  "approval_required_by": "trader_1",
  "approval_status": null,
  "notes": "System suggests increasing FVG gap threshold based on recent performance"
}`

- **description:** Draft версия правила ожидающая review трейдером

**logic_notes:**

- "НИКОГДА не auto-deploy: все изменения правил требуют manual approval трейдера"
- "Draft versions: сохраняются с суффиксом _draft, не используются в live/backtest до approval"
- "Rationale обязателен: каждое предложение должно иметь статистическое обоснование"
- "Confidence threshold: предложения с confidence <0.7 помечаются как 'low confidence' - требуют особого внимания"
- "A/B testing mode: возможность запуска backtest на одних и тех же данных со старой и новой версией для сравнения"
- "Review deadline: если через 7 дней не было review - reminder в Telegram"
- "ДОБАВЛЕНО: rollback plan - если после deployment новой версии performance падает - автоматический rollback к предыдущей"

### Подмодуль 2.16.3 — Continuous Improvement Tracker

**submodule_name:** "2.16.3 Continuous Improvement Tracker"

**inputs:**

- **from_source:** DATABASE (все backtest results, feedback, rule versions за всю историю)
- **data_type:** SQL aggregation queries + time-series data
- **params:** metric_name, time_period, grouping (by_setup|by_month|by_version)
- **format:**

json

`{
  "tracking_period": ["2025-01-01", "2025-10-31"],
  "metrics_tracked": [
    "avg_winrate_by_month",
    "total_signals_generated",
    "user_approval_rate",
    "ml_model_accuracy_trend",
    "rule_versions_created",
    "feedback_volume"
  ],
  "grouping": "by_month"
}
```
- **description:** Конфигурация для трекинга метрик улучшения системы

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│   CONTINUOUS IMPROVEMENT TRACKER               │
├────────────────────────────────────────────────┤
│  • Трекинг winrate trends (по месяцам)         │
│  • ML model performance evolution              │
│  • Rule versions effectiveness comparison      │
│  • User feedback volume & quality              │
│  • System learning curve visualization         │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Analytics Dashboard (Streamlit) + Monthly Reports (PDF/Notion) + DATABASE (metrics history)
- **data_type:** JSON (metrics snapshot) + Charts (Plotly)
- **params:** period, metrics{}, improvement_indicators[], charts[]
- **format:**

json

`{
  "report_period": "2025-10-01 to 2025-10-31",
  "metrics": {
    "avg_winrate": {
      "current_month": 0.63,
      "previous_month": 0.59,
      "change": +0.04,
      "trend": "improving"
    },
    "ml_model_auc": {
      "current": 0.74,
      "baseline_3months_ago": 0.72,
      "improvement": +0.02
    },
    "feedback_volume": {
      "signals_with_feedback": 89,
      "total_signals": 156,
      "feedback_rate": 0.57
    },
    "rule_iterations": {
      "Frank_raid": 3,
      "Asia_fvg_break": 2,
      "total_versions_created": 5
    }
  },
  "improvement_indicators": [
    {
      "indicator": "Learning velocity",
      "value": "High",
      "explanation": "5 rule versions in 1 month with clear performance improvement"
    },
    {
      "indicator": "Data quality",
      "value": "Good",
      "explanation": "57% feedback rate, sufficient for training"
    }
  ],
  "charts": [
    {
      "type": "line",
      "title": "Winrate Trend (6 months)",
      "data": [[0.55], [0.57], [0.59], [0.61], [0.59], [0.63]]
    }
  ]
}
```
- **description:** Отчёт о непрерывном улучшении системы

**logic_notes:**
- "Monthly snapshots: каждый месяц сохраняется snapshot метрик для long-term trend analysis"
- "Baseline comparison: текущие метрики сравниваются с baseline (первый месяц или 3 месяца назад)"
- "Improvement indicators: качественная оценка (High/Medium/Low) learning velocity системы"
- "Trend detection: автоматическое определение improving/stable/declining trends"
- "Alerts: если winrate падает 2 месяца подряд - alert в Telegram для investigation"
- "ДОБАВЛЕНО: knowledge base growth - трекинг размера ChromaDB (embeddings count) как индикатор накопления знаний"` 