import os
import time
import json
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
load_dotenv()


import pandas as pd
import MetaTrader5 as mt5
from loguru import logger
from prefect import task

# ============================================================
#  ПУТИ
# ============================================================
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
ARCHIVE_DIR = DATA_DIR / "archive"
CACHE_DIR = DATA_DIR / "cache"
LOG_DIR = ROOT / "logs" / "coredata"

LOG_DIR.mkdir(parents=True, exist_ok=True)
logger.add(LOG_DIR / "mt5_connector.log", rotation="5 MB", retention="7 days", level="INFO")


# ============================================================
#  ПОДДЕРЖКА РЕЖИМОВ
# ============================================================
def _resolve_server(mode: str) -> Dict[str, str]:
    """Выбор сервера и учетных данных по режиму (только из .env)."""
    if mode.upper() == "LIVE":
        return {
            "login": os.getenv("MT5_LIVE_LOGIN"),
            "password": os.getenv("MT5_LIVE_PASSWORD"),
            "server": os.getenv("MT5_SERVER_LIVE"),
        }
    elif mode.upper() == "BACKTEST":
        return {
            "login": os.getenv("MT5_DEMO_LOGIN"),
            "password": os.getenv("MT5_DEMO_PASSWORD"),
            "server": os.getenv("MT5_DEMO_SERVER"),
        }
    else:
        raise ValueError(f"[CONFIG] Unknown MT5 mode: {mode}")

def _cleanup_cache_periodically(interval_minutes: int = 60):
    """Фоновая очистка кеша каждые N минут (для LIVE режима)."""
    logger.info("[CACHE] Background cleaner started (interval: %d min).", interval_minutes)
    while True:
        try:
            if CACHE_DIR.exists():
                for f in CACHE_DIR.glob("*.parquet"):
                    f.unlink(missing_ok=True)
                logger.info("[CACHE] Cleared %d parquet files.", len(list(CACHE_DIR.glob('*.parquet'))))
        except Exception as e:
            logger.error(f"[CACHE] Cleanup error: {e}")
        time.sleep(interval_minutes * 60)


def _start_background_cache_cleaner():
    """Запускает фоновый поток очистки кэша в Live режиме."""
    thread = threading.Thread(target=_cleanup_cache_periodically, args=(60,), daemon=True)
    thread.start()
    logger.info("[CACHE] Background cache cleaner thread started.")


# ============================================================
#  MT5 API
# ============================================================
def connect_mt5(login: str, password: str, server: str):
    """Подключение к MetaTrader5 с диагностикой."""
    logger.info(f"[MT5] Connecting → {server}")
    try:
        # Приведение логина к int (требование MT5 API)
        login_int = int(login) if login and str(login).isdigit() else None

        # Попытка инициализации
        if not mt5.initialize(login=login_int, password=password, server=server):
            err = mt5.last_error()
            logger.error(f"[MT5] Initialize failed: {err}")
            raise ConnectionError(f"[MT5] Failed to connect ({err})")

        # Проверяем статус терминала
        info = mt5.terminal_info()
        if info is None:
            raise ConnectionError("[MT5] Terminal info unavailable after initialization")

        logger.info(f"[MT5] Connection established → {info.name} (build {info.build})")

    except Exception as e:
        logger.exception(f"[MT5] Critical connection failure: {e}")
        raise


def disconnect_mt5():
    """Завершение соединения с терминалом."""
    mt5.shutdown()
    logger.info("[MT5] Disconnected from terminal.")


def get_ohlcv(symbol: str, timeframe: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Получение OHLCV данных из MT5."""
    tf_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "H1": mt5.TIMEFRAME_H1,
        "D1": mt5.TIMEFRAME_D1,
    }
    tf = tf_map.get(timeframe.upper(), mt5.TIMEFRAME_M15)

    rates = mt5.copy_rates_range(symbol, tf, start.to_pydatetime(), end.to_pydatetime())
    if rates is None or len(rates) == 0:
        err = mt5.last_error()
        raise ValueError(f"[MT5] No data received for {symbol} {timeframe}. MT5 error: {err}")

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df[["time", "open", "high", "low", "close", "tick_volume"]]
    df.rename(columns={"tick_volume": "volume"}, inplace=True)
    return df
# ============================================================
#  АРХИВ И ПРОВЕРКА
# ============================================================
def save_parquet(df: pd.DataFrame, symbol: str, timeframe: str, mode: str) -> Path:
    """Сохранение результатов в архив."""
    target_dir = (CACHE_DIR if mode.upper() == "LIVE" else ARCHIVE_DIR) / symbol / timeframe
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"{symbol}_{timeframe}_{mode.lower()}_{datetime.now():%Y%m%d%H%M%S}.parquet"
    df.to_parquet(file_path)
    return file_path


def validate_data(df: pd.DataFrame, symbol: str):
    """Проверка целостности данных."""
    if df.isnull().values.any():
        raise ValueError(f"[INTEGRITY] NaN values detected for {symbol}")
    if not df["time"].is_monotonic_increasing:
        raise ValueError(f"[INTEGRITY] Timestamps not sorted for {symbol}")


def clear_live_cache_on_start():
    """Очистка кеша при старте LIVE режима."""
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("[CACHE] Live cache cleared at startup.")


# ============================================================
#  ГЛАВНАЯ ФУНКЦИЯ
# ============================================================
@task(name="MT5ConnectorTask")
def run_mt5_ingest(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Основная функция MT5Connector:
    - Работает в режимах BACKTEST / LIVE
    - Поддерживает Prefect
    """
    mode = ctx.get("mode", "BACKTEST").upper()
    symbol = ctx["symbol"]
    timeframe = ctx["timeframe"]
    start = pd.Timestamp(ctx["date_start"], tz="UTC")
    end = pd.Timestamp(ctx["date_end"], tz="UTC")
    run_id = ctx.get("prefect_context_id", f"run-{datetime.now():%Y%m%d%H%M%S}")

    logger.info(f"[START] {symbol} {timeframe} {mode} ({start}→{end}) [{run_id}]")

    try:
        creds = _resolve_server(mode)
        if mode == "LIVE":
            clear_live_cache_on_start()
            _start_background_cache_cleaner()

        connect_mt5(creds["login"], creds["password"], creds["server"])
        df = get_ohlcv(symbol, timeframe, start, end)
        validate_data(df, symbol)
        out_path = save_parquet(df, symbol, timeframe, mode)
        disconnect_mt5()

        result = {
            "context_id": run_id,
            "symbol": symbol,
            "mode": mode,
            "status": "SUCCESS",
            "rows": len(df),
            "path": str(out_path),
            "timestamp": datetime.utcnow().isoformat()
        }
        json.dump(result, open(LOG_DIR / f"{run_id}_result.json", "w"), indent=2)
        logger.success(f"[DONE] {symbol} {mode} OK → {out_path}")
        return result

    except Exception as e:
        logger.exception(f"[ERROR] {e}")
        result = {
            "context_id": run_id,
            "status": "FAILED",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
        json.dump(result, open(LOG_DIR / f"{run_id}_error.json", "w"), indent=2)
        return result
