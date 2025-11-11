# 13_QA_Testing
Описание модуля и его назначения.
### QA / Testing

Контроль качества / Тестирование

- Модульные тесты для каждого детектора (используйте pytest).
- Backtest acceptance: визуальное утверждение трейдером базового правила 20/20..
- Integration tests: сквозное тестирование небольшого набора данных. small dataset end-to-end.
- **Acceptance test dataset** (control set) - контрольная папка 20–50 скринов + expected outputs for detectors — обязательна для acceptance.

## ⚙️ ASCII схема
## МОДУЛЬ 2.14 — QA / Testing

### Подмодуль 2.14.1 — Unit Tests

**submodule_name:** "2.14.1 Unit Tests"

**inputs:**

- **from_source:** Python test files (tests/ папка) + pytest framework
- **data_type:** Python code (test functions)
- **params:** test_file, test_function, fixtures
- **format:**

python

`*# tests/test_market_tools.py*
import pytest
from modules.market_tools import Detect_FVG

def test_detect_fvg_bullish():
    """Test FVG detection для bullish паттерна"""
    *# Arrange*
    candles = load_test_data("fvg_bullish_sample.csv")
    detector = Detect_FVG(min_gap_pct=0.2)
    
    *# Act*
    result = detector.detect(candles)
    
    *# Assert*
    assert len(result) == 1
    assert result[0]["type"] == "fvg"
    assert result[0]["fvg_direction"] == "bullish"
    assert result[0]["confidence"] > 0.7
    assert "gap_size_pct" in result[0]["meta"]

def test_detect_fvg_no_gap():
    """Test что детектор не находит FVG когда gap отсутствует"""
    candles = load_test_data("no_gap_sample.csv")
    detector = Detect_FVG(min_gap_pct=0.2)
    
    result = detector.detect(candles)
    
    assert len(result) == 0
```
- **description:** Unit tests для индивидуальных компонентов (детекторы, парсеры, и тд)

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│         UNIT TESTS (pytest)                    │
├────────────────────────────────────────────────┤
│  • Tests для каждого детектора Market Tools    │
│  • Tests для Data Processor функций            │
│  • Tests для Rule Parser (YAML → executable)   │
│  • Mock external APIs (MT5, OpenAI, Notion)    │
│  • Coverage target: >80% для core modules      │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Test reports (console + HTML) + Coverage report
- **data_type:** Test results JSON + coverage metrics
- **params:** tests_run, passed, failed, skipped, coverage_percent
- **format:**

json

`{
  "test_session": "2025-10-31T14:00:00Z",
  "tests_run": 87,
  "passed": 85,
  "failed": 2,
  "skipped": 0,
  "duration_sec": 12.5,
  "failed_tests": [
    "test_market_tools.py::test_detect_ob_edge_case",
    "test_visualizer.py::test_png_generation_large_dataset"
  ],
  "coverage": {
    "total_percent": 82.5,
    "by_module": {
      "market_tools": 89.2,
      "data_processor": 91.5,
      "backtester": 78.3,
      "llm_integration": 65.1
    }
  }
}`

- **description:** Результаты прогона unit tests с coverage метриками

**logic_notes:**

- "pytest framework: стандарт для Python testing"
- "Test data: папка tests/data/ с CSV samples для детерминированных тестов"
- "Mocking: использовать unittest.mock для MT5, OpenAI, Notion API calls (не делать real calls в tests)"
- "Coverage target: минимум 80% для core modules (Market Tools, Backtester, Data Processor)"
- "CI integration: тесты запускаются автоматически при каждом commit (GitHub Actions или local git hook)"
- "ДОБАВЛЕНО: parametrized tests - для проверки multiple scenarios с разными параметрами"

### Подмодуль 2.14.2 — Integration Tests

**submodule_name:** "2.14.2 Integration Tests"

**inputs:**

- **from_source:** Test scenarios (end-to-end workflows) + small test dataset
- **data_type:** Test scenarios JSON + CSV (test candles)
- **params:** scenario_name, test_data_path, expected_output
- **format:**

json

`{
  "scenario": "backtest_frank_raid_small_dataset",
  "description": "End-to-end backtest на маленьком датасете",
  "test_data": "tests/data/ger40_m15_1month.csv",
  "setup_config": {
    "setup_id": "Frank_raid_v1",
    "rule_version": "v1.2"
  },
  "expected_output": {
    "trades_count_range": [5, 15],
    "winrate_range": [0.5, 0.7],
    "execution_time_max_sec": 60
  }
}
```
- **description:** Сценарий integration test для проверки end-to-end workflow

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│       INTEGRATION TESTS                        │
├────────────────────────────────────────────────┤
│  • End-to-end backtest flow test               │
│  • Live scan flow test (mocked MT5 data)       │
│  • Data pipeline: Ingest → Process → Detect    │
│  • LLM integration test (с mock или real API)  │
│  • Notion upload test (test database)          │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Test reports + Logs
- **data_type:** Test results JSON
- **params:** scenario_name, status, duration, issues_found[]
- **format:**

json

`{
  "scenario": "backtest_frank_raid_small_dataset",
  "status": "passed",
  "start_time": "2025-10-31T14:05:00Z",
  "end_time": "2025-10-31T14:05:45Z",
  "duration_sec": 45,
  "results": {
    "trades_count": 8,
    "winrate": 0.625,
    "backtest_json_created": true,
    "trades_csv_created": true,
    "sample_pngs_count": 2
  },
  "checks": [
    {"check": "trades_count_in_range", "result": "pass"},
    {"check": "winrate_in_range", "result": "pass"},
    {"check": "execution_time_ok", "result": "pass"},
    {"check": "outputs_exist", "result": "pass"}
  ],
  "issues_found": []
}
```
- **description:** Результаты integration test с детализацией проверок

**logic_notes:**
- "Small dataset: 1 месяц данных M15 (~3000 свечей) для быстрого прогона"
- "End-to-end: тест проходит через ВСЕ этапы: Data Ingest → Process → Detect → Backtest → Visualize → Upload"
- "Assertions: проверка что outputs (JSON, CSV, PNG) созданы и содержат ожидаемые данные"
- "Mock vs Real: для LLM можно использовать mock ответы (быстрее) или real API с test account (дороже но реалистичнее)"
- "ДОБАВЛЕНО: smoke tests - быстрые integration tests для базовой проверки что система работает (запускаются перед full test suite)"

---

### Подмодуль 2.14.3 — Acceptance Test Dataset

**submodule_name:** "2.14.3 Acceptance Test Dataset (Control Set)"

**inputs:**
- **from_source:** Manually labeled data + Ground truth annotations
- **data_type:** PNG files + JSON (labels)
- **params:** screenshot_path, ground_truth_zones[], expected_signals[]
- **format:** 
```
# Control dataset structure:
tests/acceptance_dataset/
  ├── case_001_frank_raid_perfect/
  │   ├── screenshot.png
  │   ├── ground_truth.json
  │   └── expected_output.json
  ├── case_002_false_fvg/
  │   ├── screenshot.png
  │   ├── ground_truth.json
  │   └── expected_output.json
  ...

# ground_truth.json example:
{
  "case_id": "case_001",
  "description": "Perfect Frank raid setup",
  "zones": [
    {"type": "session", "session_name": "Frankfurt", "price_low": 15820, "price_high": 15850},
    {"type": "fvg", "price_low": 15835, "price_high": 15840},
    {"type": "ob", "price_low": 15830, "price_high": 15835}
  ],
  "expected_signal": {
    "should_trigger": true,
    "entry_range": [15838, 15842],
    "confidence_min": 0.7
  }
}
```
- **description:** Контрольный датасет с ground truth для валидации детекторов

**ascii_diagram:**
```
┌────────────────────────────────────────────────┐
│   ACCEPTANCE TEST DATASET (Control Set)        │
├────────────────────────────────────────────────┤
│  • 20-50 размеченных скриншотов (ground truth) │
│  • Позитивные cases (должен детектировать)     │
│  • Негативные cases (НЕ должен детектировать)  │
│  • Edge cases (граничные условия)              │
│  • Manual validation трейдером (acceptance)    │
└────────────────────────────────────────────────┘`

**outputs:**

- **destination:** Test reports + Precision/Recall metrics
- **data_type:** JSON (test results with metrics)
- **params:** cases_tested, precision, recall, f1_score, failed_cases[]
- **format:**

json

`{
  "dataset": "acceptance_test_v1",
  "cases_tested": 25,
  "results": {
    "true_positives": 18,
    "false_positives": 2,
    "true_negatives": 4,
    "false_negatives": 1,
    "precision": 0.90,
    "recall": 0.95,
    "f1_score": 0.92
  },
  "failed_cases": [
    {
      "case_id": "case_012",
      "issue": "Missed FVG (false negative)",
      "reason": "Gap size 0.18% < threshold 0.2%"
    }
  ],
  "acceptance_status": "pass"
}`

- **description:** Метрики качества детекторов на контрольном датасете

**logic_notes:**

- "Ground truth: размечен вручную трейдером - 'золотой стандарт' для сравнения"
- "Positive cases: где сетап действительно есть и должен быть найден"
- "Negative cases: где визуально похоже, но сетап НЕ валидный (детектор НЕ должен срабатывать)"
- "Acceptance criteria: precision >0.85, recall >0.80 для базовых детекторов"
- "Manual review: трейдер проверяет failed cases и решает - это bug детектора или проблема ground truth"
- "ДОБАВЛЕНО: version tracking - датасет версионируется, при улучшении детекторов добавляются новые cases"