"""
ITA Project — Test Environment
Module: CoreData / MT5Connector Emulator
Purpose: SetupManager and Prefect test emulation (Offline Mode)
Version: 1.3 (Fully Standalone)
Author: Dreyk / GPT-5 Engineering
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from loguru import logger

# ============================================================
#  Prefect — офлайн режим (без клиента и API)
# ============================================================
from prefect import flow, task
from prefect.context import get_run_context

# ============================================================
#  Автоматическая настройка путей
# ============================================================
ROOT = Path(__file__).resolve().parents[2]

# Добавляем корень проекта в sys.path, чтобы не требовался пакет src
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

# Импортируем боевой модуль напрямую
from src.M02_CoreData.mt5_connector import run_mt5_ingest

# ============================================================
#  Пути (только проверка, ничего не создаём)
# ============================================================
TEST_DIR = ROOT / "tests"
LOG_DIR = ROOT / "logs"

print("\n🔍 Проверка путей:")
for p in [ROOT, TEST_DIR, LOG_DIR]:
    print(f"  {p}  {'✅' if p.exists() else '❌'}")

# Логирование
if LOG_DIR.exists():
    logger.add(LOG_DIR / "test_mt5connector.log", rotation="2 MB", level="INFO")
else:
    logger.add(sys.stderr, level="INFO")

# ============================================================
#  SetupContext — создаём только в памяти
# ============================================================
def get_setup_context():
    """Создаёт тестовый SetupManager контекст (без записи в файл)."""
    return {
        "symbol": "DE40",
        "timeframe": "M15",
        "date_start": "2025-04-01",
        "date_end": "2025-05-31",
        "mode": "BACKTEST",
        "prefect_context_id": f"local-{datetime.now():%Y%m%d%H%M%S}"
    }

# ============================================================
#  Prefect Flow Эмулятор (локальный)
# ============================================================
@flow(name="TestFlow_MT5Connector", validate_parameters=False)
def test_flow_run():
    """Имитация Prefect потока (без API)."""
    ctx = get_setup_context()
    logger.info("[FLOW] Starting MT5Connector local test run")
    print("\n🚀 Запуск MT5Connector с параметрами:")
    print(json.dumps(ctx, indent=2))

    try:
        result = run_mt5_ingest(ctx)
        logger.success(f"[FLOW] Finished run with status: {result['status']}")
        print("\n✅ Результат выполнения:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        logger.exception(f"[ERROR] Flow crashed: {e}")
        print(f"\n❌ Ошибка выполнения: {e}")

# ============================================================
#  Точка входа
# ============================================================
if __name__ == "__main__":
    os.environ.setdefault("MT5_LOGIN", "12345678")
    os.environ.setdefault("MT5_PASSWORD", "your_password")
    os.environ.setdefault("MT5_SERVER", "MetaQuotes-Demo")

    logger.info("[ENV] Environment variables set for MT5 test")
    test_flow_run()
