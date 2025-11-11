# ===============================================================
# ITA Project | Module: CoreData (2.2.1)
# File: mt5_connector.py
# Version: v1.4
# Author: Dreyk & GPT-5 Architect
# ===============================================================
# Description:
# Универсальный коннектор к MetaTrader 5 для загрузки котировок.
# Поддерживает два режима работы:
# 1️⃣ BACKTEST (архив исторических данных, MetaQuotes-Demo)
# 2️⃣ LIVE (текущие котировки, EquityEdge / проп-сервер)
# ===============================================================

import MetaTrader5 as MT5
import pandas as pd
import os
import time
import threading
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger
import yaml

# ===============================================================
# INITIALIZATION
# ===============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

CONFIG_PATH = BASE_DIR / "config.yaml"
LOG_PATH = BASE_DIR / "logs" / "coredata"
CACHE_DIR = BASE_DIR / "data" / "cache"
ARCHIVE_DIR = BASE_DIR / "data" / "archive" / "raw"

# Ensure directories exist
for d in [LOG_PATH, CACHE_DIR, ARCHIVE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

logger.add(LOG_PATH / "mt5_connector.log", rotation="5 MB", level="INFO", encoding="utf-8")

# ===============================================================
# CONFIGURATION
# ===============================================================

try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
except Exception as e:
    logger.error(f"[CONFIG] Ошибка чтения config.yaml: {e}")
    config = {}

ITA_MODE = os.getenv("ITA_MODE", "BACKTEST").upper()  # LIVE / BACKTEST
symbol = config.get("symbol", "EURUSD")
timeframe = config.get("timeframe", "M15")
date_from = config.get("date_from", "2025-01-01")
date_to = config.get("date_to", "2025-11-01")

# ===============================================================
# MT5 CONNECTION
# ===============================================================

def connect_mt5(mode="BACKTEST"):
    """
    Подключение к MT5: LIVE → EquityEdge, BACKTEST → MetaQuotes.
    Без fallback. При ошибке — raise ConnectionError.
    """
    if mode.upper() == "LIVE":
        login = os.getenv("MT5_LOGIN")
        password = os.getenv("MT5_PASSWORD")
        server = os.getenv("MT5_SERVER")
        broker_name = "EquityEdge"
        logger.info(f"[MODE] LIVE | Подключение к {server} (EquityEdge)")
    else:
        login = os.getenv("MT5_DEMO_LOGIN")
        password = os.getenv("MT5_DEMO_PASSWORD")
        server = os.getenv("MT5_DEMO_SERVER")
        broker_name = "MetaQuotes"
        logger.info(f"[MODE] BACKTEST | Подключение к {server} (MetaQuotes Demo)")

    if not mt5.initialize(login=int(login), password=password, server=server):
        err = mt5.last_error()
        logger.error(f"[MT5] Не удалось подключиться: {err}")
        mt5.shutdown()
        raise ConnectionError(f"[MT5] Ошибка подключения: {err}")

    logger.info(f"[MT5] Соединение успешно установлено: {broker_name}")
    return mt5, broker_name


def disconnect_mt5():
    """Отключение от терминала."""
    mt5.shutdown()
    logger.info("[MT5] Соединение закрыто.")

# ===============================================================
# CACHE CLEANUP
# ===============================================================

def clear_cache():
    """Очистка временных файлов cache/"""
    removed = 0
    for f in CACHE_DIR.glob("*.parquet"):
        try:
            f.unlink()
            removed += 1
        except Exception as e:
            logger.warning(f"[CACHE] Ошибка удаления {f.name}: {e}")
    logger.info(f"[CACHE] Очистка завершена, удалено файлов: {removed}")

def schedule_cache_cleanup(interval_hours=1):
    """Плановая очистка кэша каждые interval_hours часов."""
    def loop():
        while True:
            time.sleep(interval_hours * 3600)
            clear_cache()
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()

# ===============================================================
# DATA INTEGRITY CHECK
# ===============================================================

def data_integrity_check(df: pd.DataFrame) -> bool:
    """
    Проверка целостности данных перед сохранением.
    Возвращает True, если всё корректно.
    """
    try:
        if df.empty:
            logger.error("[CHECK] DataFrame пустой!")
            return False

        # --- Исправление: нормализация колонок ---
        columns_map = {c: c.lower() for c in df.columns}
        df.rename(columns=columns_map, inplace=True)

        if "time" in df.columns and "datetime" not in df.columns:
            df.rename(columns={"time": "datetime"}, inplace=True)

        # Проверка дубликатов
        if df.duplicated(subset=["datetime"]).any():
            dup_count = df.duplicated(subset=["datetime"]).sum()
            logger.warning(f"[CHECK] Найдены дубликаты по времени: {dup_count}")
            df.drop_duplicates(subset=["datetime"], inplace=True)

        # Проверка пропусков
        diffs = df["datetime"].diff().dropna().dt.total_seconds()
        gap_threshold = diffs.median() * 3
        if (diffs > gap_threshold).any():
            logger.warning("[CHECK] Обнаружены пропуски во временных рядах!")

        # Проверка сортировки
        if not df["datetime"].is_monotonic_increasing:
            logger.warning("[CHECK] Данные не отсортированы, выполняется сортировка...")
            df.sort_values("datetime", inplace=True)

        logger.info("[CHECK] Проверка данных завершена успешно.")
        return True

    except Exception as e:
        logger.error(f"[CHECK] Ошибка проверки данных: {e}")
        return False

# ===============================================================
# DATA DOWNLOAD
# ===============================================================

def download_data(mt5, mode):
    """Загрузка котировок в зависимости от режима работы."""
    from_date = datetime.strptime(date_from, "%Y-%m-%d")
    to_date = datetime.strptime(date_to, "%Y-%m-%d")

    tf_map = {
        "M1": MT5.TIMEFRAME_M1,
        "M5": MT5.TIMEFRAME_M5,
        "M15": MT5.TIMEFRAME_M15,
        "M30": MT5.TIMEFRAME_M30,
        "H1": MT5.TIMEFRAME_H1
    }

    logger.info(f"[MT5] Загрузка данных {symbol} {timeframe} ({from_date} - {to_date})")

    rates = MT5.copy_rates_range(symbol, tf_map[timeframe], from_date, to_date)
    if rates is None:
        logger.error(f"[MT5] Ошибка загрузки данных: {MT5.last_error()}")
        return

    df = pd.DataFrame(rates)

    # --- Исправление: безопасная конвертация времени ---
    if "time" in df.columns:
        df["datetime"] = pd.to_datetime(df["time"], unit="s")
        df.drop(columns=["time"], inplace=True)

    if not data_integrity_check(df):
        logger.error("[MT5] Проверка целостности не пройдена, сохранение отменено.")
        return

    # ARCHIVE MODE
    if mode == "BACKTEST":
        archive_path = ARCHIVE_DIR / symbol / timeframe
        archive_path.mkdir(parents=True, exist_ok=True)
        file_name = f"{date_from}_{date_to}.parquet"
        df.to_parquet(archive_path / file_name, index=False)
        logger.info(f"[ARCHIVE] Исторические данные сохранены: {file_name}")

    # LIVE MODE
    else:
        cache_file = CACHE_DIR / f"{symbol}_{timeframe}_live.parquet"
        df.to_parquet(cache_file, index=False)
        logger.info(f"[LIVE] Текущие котировки обновлены: {cache_file}")

# ===============================================================
# MAIN EXECUTION
# ===============================================================

def main(mode: str = None):
    """
    Главная функция коннектора ITA.
    mode: 'LIVE' или 'BACKTEST'
    Если не указано — берется из .env (ITA_MODE).
    """
    mode = mode or os.getenv("ITA_MODE", "BACKTEST").upper()
    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logger.info(f"[START] MT5 Connector launched at {start_time} ({mode} mode)")

    # Проверка терминала
    term_path = os.getenv("MT5_PATH_LIVE") if mode == "LIVE" else os.getenv("MT5_PATH_BACKTEST")
    if not Path(term_path).exists():
        logger.error(f"[MT5] Указанный путь к терминалу не найден: {term_path}")
        return

    logger.info(f"[MT5] Используется терминал: {term_path}")

    # Подключение
    mt5, broker = connect_mt5(mode)
    if mt5 is None:
        logger.error("[MT5] Подключение невозможно.")
        return

    # Очистка кэша для LIVE
    if mode == "LIVE":
        clear_cache()
        schedule_cache_cleanup(1)

    # Загрузка данных
    download_data(mt5, mode)

    # Завершение
    try:
        MT5.shutdown()
        logger.info("[MT5] Соединение закрыто.")
    except Exception as e:
        logger.warning(f"[MT5] Ошибка при закрытии соединения: {e}")

    logger.info(">>> ITA MT5 Connector finished")

# ===============================================================
# ENTRY POINT
# ===============================================================

if __name__ == "__main__":
    main()
