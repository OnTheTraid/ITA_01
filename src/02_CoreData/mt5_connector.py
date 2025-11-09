# ===============================================================
# ITA Project | Module: CoreData (2.2.1)
# File: mt5_connector.py
# Version: v1.4
# Author: Dreyk & GPT-5 Architect
# ===============================================================
# Description:
# Универсальный коннектор к MetaTrader 5 для загрузки котировок.
# Поддерживает два режима работы:
# 1️⃣ BACKTEST — архив исторических данных (MetaQuotes-Demo)
# 2️⃣ LIVE — текущие котировки (EquityEdge / проп-сервер)
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

for d in [LOG_PATH, CACHE_DIR, ARCHIVE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

logger.add(LOG_PATH / "mt5_connector.log", rotation="5 MB", level="INFO", encoding="utf-8")

# ===============================================================
# CONFIG FALLBACK
# ===============================================================

def load_config_fallback():
    """Загрузка config.yaml (только fallback, не production)."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"[CONFIG] Файл config.yaml не найден или поврежден: {e}")
        return {}

# ===============================================================
# MT5 CONNECTION
# ===============================================================

def connect_mt5(mode="BACKTEST"):
    """Подключение к MT5: выбирает терминал и учетные данные по режиму."""
    if mode == "LIVE":
        term_path = os.getenv("MT5_PATH_LIVE")
        login = os.getenv("MT5_LOGIN")
        password = os.getenv("MT5_PASSWORD")
        server = os.getenv("MT5_SERVER")
        broker_name = "EquityEdge"
    else:
        term_path = os.getenv("MT5_PATH_BACKTEST")
        login = os.getenv("MT5_DEMO_LOGIN")
        password = os.getenv("MT5_DEMO_PASSWORD")
        server = os.getenv("MT5_DEMO_SERVER")
        broker_name = "MetaQuotes"

    logger.info(f"[MODE] {mode} | Подключение к {server} ({broker_name})")
    logger.info(f"[MT5] Terminal path: {term_path}")

    if not MT5.initialize(path=term_path, login=int(login), password=password, server=server):
        logger.error(f"[MT5] Не удалось подключиться: {MT5.last_error()}")
        MT5.shutdown()
        if mode == "LIVE":
            logger.warning("[MT5] Переключение на MetaQuotes-Demo...")
            return connect_mt5("BACKTEST")
        return None, None

    logger.info(f"[MT5] Соединение успешно установлено: {broker_name}")
    return MT5, broker_name

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
    """Проверка целостности данных перед сохранением."""
    try:
        if df.empty:
            logger.error("[CHECK] DataFrame пустой!")
            return False

        if "time" not in df.columns:
            logger.error(f"[CHECK] В DataFrame отсутствует колонка 'time': {df.columns}")
            return False

        if df.duplicated(subset=["time"]).any():
            dup_count = df.duplicated(subset=["time"]).sum()
            logger.warning(f"[CHECK] Найдены дубликаты по времени: {dup_count}")
            df.drop_duplicates(subset=["time"], inplace=True)

        diffs = df["time"].diff().dropna().dt.total_seconds()
        gap_threshold = diffs.median() * 3
        if (diffs > gap_threshold).any():
            logger.warning("[CHECK] Обнаружены пропуски во временных рядах!")

        if not df["time"].is_monotonic_increasing:
            logger.warning("[CHECK] Данные не отсортированы, выполняется сортировка...")
            df.sort_values("time", inplace=True)

        logger.info("[CHECK] Проверка данных завершена успешно.")
        return True

    except Exception as e:
        logger.error(f"[CHECK] Ошибка проверки данных: {e}")
        return False

# ===============================================================
# DATA DOWNLOAD
# ===============================================================

def download_data(mt5, mode, symbol, timeframe, date_from, date_to):
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
    df["time"] = pd.to_datetime(df["time"], unit="s")

    if not data_integrity_check(df):
        logger.error("[MT5] Проверка целостности не пройдена, сохранение отменено.")
        return

    if mode == "BACKTEST":
        archive_path = ARCHIVE_DIR / symbol / timeframe
        archive_path.mkdir(parents=True, exist_ok=True)
        file_name = f"{date_from}_{date_to}.parquet"
        df.to_parquet(archive_path / file_name, index=False)
        logger.info(f"[ARCHIVE] Исторические данные сохранены: {file_name}")
    else:
        cache_file = CACHE_DIR / f"{symbol}_{timeframe}_live.parquet"
        df.to_parquet(cache_file, index=False)
        logger.info(f"[LIVE] Текущие котировки обновлены: {cache_file}")

# ===============================================================
# MAIN EXECUTION
# ===============================================================

def main(mode: str = None, symbol=None, timeframe=None, date_from=None, date_to=None):
    """
    Главная функция коннектора ITA.
    Все параметры передаются от SetupManager или DataEngine.
    Если не указаны — используется fallback (config.yaml).
    """
    config = load_config_fallback()

    mode = mode or os.getenv("ITA_MODE", "BACKTEST").upper()
    symbol = symbol or config.get("symbol", "EURUSD")
    timeframe = timeframe or config.get("timeframe", "M15")
    date_from = date_from or config.get("date_from", "2025-01-01")
    date_to = date_to or config.get("date_to", "2025-11-01")

    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logger.info(f"[START] MT5 Connector launched at {start_time} ({mode} mode)")

    mt5, broker = connect_mt5(mode)
    if mt5 is None:
        logger.error("[MT5] Подключение невозможно.")
        return

    if mode == "LIVE":
        clear_cache()
        schedule_cache_cleanup(1)

    download_data(mt5, mode, symbol, timeframe, date_from, date_to)

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
