ITA_TZ_03_DataStorage_2.3.3_RunSnapshot.md
1. Назначение

Подмодуль Run Snapshot / Provenance сохраняет контекст выполнения каждого backtest/live run — включая правило, версию, данные и окружение.
Цель — полная воспроизводимость и аудит экспериментов.

2. Функциональные задачи
№	Задача	Описание
1	Создание снапшота	Формирование JSON с метаданными запуска
2	Хеш данных	Расчёт sha256 по исходному CSV или DataFrame
3	Git commit tracking	Встраивание текущего git_commit_hash
4	Хранение окружения	Python version, OS, GPU
5	Сохранение через Persistent Store	JSON в data/results/provenance/
6	Ссылка на Rule Version	Сохранение setup_id и rule_version из Rule Registry
3. Контракт
run_id: bt_2025_11_10_001
setup_id: asia_fvg_break
rule_version: v1.3
data_hash: "e2f89b2d7c..."
data_range: ["2025-05-01", "2025-10-31"]
git_commit_hash: "f1b2c3d"
env:
  python: "3.11.9"
  os: "Windows 10"
  cpu: "AMD Ryzen"
timestamp: "2025-11-10T18:23:00Z"
meta:
  author: "maxim.malysh"
  run_mode: "backtest"

4. Архитектура и связи

🔄 Использует: persistent_store.save_json()

📦 Читает: RuleVersionRegistry.get_active_version()

🧩 Вызывается из: BacktestManager и SetupManager

💾 Хранит: data/results/provenance/{run_id}.json

5. Пример интерфейса класса
class RunProvenance:
    def create_snapshot(self, run_id: str, setup_id: str, rule_version: str, data_path: str, meta: dict) -> ArtifactRef: ...
    def load_snapshot(self, run_id: str) -> dict: ...
    def verify_data_hash(self, run_id: str, file_path: str) -> bool: ...

6. Acceptance

Для каждого run_id существует соответствующий snapshot JSON.

Хеш данных совпадает при повторной проверке.

rule_version и setup_id совпадают с Rule Registry.

В Prefect logs — запись: “Run snapshot saved”.

7. Структура файлов проекта
src/03_DataStorage/
  ├── run_snapshot.py
  ├── version_registry.py
  ├── persistent_store.py
data/
  └── results/
      └── provenance/
          ├── bt_2025_11_10_001.json

8. Интеграция с другими модулями
Модуль	Взаимодействие
02_CoreData	предоставляет диапазон данных и путь
03_DataStorage (PersistentStore)	сохраняет JSON
05_SetupManager	получает rule_version
06_Backtester	создаёт снапшот перед выполнением
10_Outputs	может выгружать снапшот в Notion
9. Манифест связей
modules:
  03_DataStorage.RuleVersionRegistry:
    provides: [rule_versioning, rule_metadata]
    used_by: [SetupManager, Backtester, RunSnapshot]
    config: [rules_path: data/rules/]
    status: stable_mvp

  03_DataStorage.RunSnapshot:
    provides: [run_provenance, run_audit]
    used_by: [SetupManager, Backtester, Outputs]
    depends_on: [RuleVersionRegistry, PersistentStore]
    config: [provenance_path: data/results/provenance/]
    status: stable_mvp