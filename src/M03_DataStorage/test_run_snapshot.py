"""
Тест подмодуля Run Snapshot / Provenance.
"""

from src.M03_DataStorage.run_snapshot import RunProvenance

if __name__ == "__main__":
    prov = RunProvenance()

    # Создаём тестовый снапшот
    ref = prov.create_snapshot(
        run_id="demo_run_001",
        setup_id="setup_test",
        rule_version="v1.0.0",
        data_path=None,  # можно указать путь к csv, если хочешь проверить hash
        data_range=["2025-01-01", "2025-01-10"],
        meta={"author": "Max", "mode": "test"},
    )
    print("✅ Snapshot saved:", ref)

    # Загружаем обратно
    data = prov.load_snapshot("demo_run_001")
    print("📦 Loaded snapshot:", data)

    # Проверяем целостность данных (файл не указан — просто пример)
    ok = prov.verify_data_hash("demo_run_001", "nonexistent_file.csv")
    print("🧩 Data hash check:", ok)
