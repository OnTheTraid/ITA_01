# ============================================================
#  TEST: Run Snapshot / Provenance
# ============================================================

import sys
from pathlib import Path

# === Добавляем корень проекта и src в PYTHONPATH ===
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

# Теперь всё доступно как пакеты: M03_DataStorage, M02_CoreData …
from M03_DataStorage.run_snapshot import RunProvenance

import json
import os


def test_run_snapshot():
    print("\n=== TEST: Run Snapshot ===")

    rp = RunProvenance()

    # --- Параметры тестового запуска ---
    run_id = "test_run_001"
    setup_id = "TEST_SETUP"
    rule_version = "1.0.0"
    meta = {"author": "test", "mode": "unittest"}

    # --- Создание снапшота ---
    ref = rp.create_snapshot(
        run_id=run_id,
        setup_id=setup_id,
        rule_version=rule_version,
        data_path=None,
        data_range=["2024-01-01", "2024-01-31"],
        meta=meta,
    )

    print("✓ Snapshot saved:", ref.path)

    # --- Загрузка снапшота ---
    loaded = rp.load_snapshot(run_id)
    print("✓ Snapshot loaded OK")

    # --- Проверка структуры ---
    assert loaded["run_id"] == run_id
    assert loaded["setup_id"] == setup_id
    assert loaded["rule_version"] == rule_version

    print("✓ Snapshot structure is valid")

    # --- Проверка хеша данных (нет файла → всегда False) ---
    ok = rp.verify_data_hash(run_id, "nonexistent.csv")
    print("✓ Data hash check executed:", ok)

    print("\n=== TEST FINISHED ===")


if __name__ == "__main__":
    test_run_snapshot()
