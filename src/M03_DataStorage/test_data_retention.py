"""
test_data_retention.py
Тесты для 2.3.4 Data Retention / Purge Policy.

Сценарий:
- создаём несколько временных файлов в data/temp;
- искусственно старим часть файлов (mtime);
- запускаем purge('temp', dry_run=False);
- выводим отчёт в консоль.
"""

import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.M03_DataStorage.data_retention import DataRetentionService  # noqa: E402


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("test", encoding="utf-8")


def _set_mtime_days_ago(path: Path, days: int) -> None:
    """
    Устанавливает mtime файла на N дней назад.
    """
    ts = datetime.now(timezone.utc) - timedelta(days=days)
    epoch = ts.timestamp()
    os.utime(path, (epoch, epoch))


def main():
    print("=== TEST: DataRetention (purge temp) ===")

    service = DataRetentionService(dry_run_default=False)
    temp_root = ROOT / "data" / "temp"

    print(f"- Temp dir: {temp_root}")

    # создаём тестовые файлы
    old_file = temp_root / "old_temp_file.txt"
    very_old_file = temp_root / "very_old_temp_file.txt"
    fresh_file = temp_root / "fresh_temp_file.txt"

    _touch(old_file)
    _touch(very_old_file)
    _touch(fresh_file)

    # Делаем два файла старыми:
    # допустим retention.policies.temp.ttl_days = 3
    # ставим 5 и 10 дней назад
    _set_mtime_days_ago(old_file, days=5)
    _set_mtime_days_ago(very_old_file, days=10)
    # свежий оставляем как сейчас

    print(f"- Created files:")
    print(f"  {old_file}")
    print(f"  {very_old_file}")
    print(f"  {fresh_file}")

    # Небольшая пауза, чтобы ОС точно зафиксировала mtime
    time.sleep(0.5)

    print("- Running purge('temp', dry_run=False)...")
    report = service.purge("temp", dry_run=False)

    print("=== REPORT ===")
    print(report)

    print("=== TEST FINISHED ===")


if __name__ == "__main__":
    main()
