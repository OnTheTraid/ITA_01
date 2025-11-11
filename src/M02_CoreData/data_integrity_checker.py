# ===============================================================
# ITA Project | Module: CoreData (2.2.1.1)
# File: data_integrity_checker.py
# Version: v1.0
# Author: Dreyk & GPT-5 Architect
# ===============================================================
# Description:
# Проверка целостности данных MT5 перед сохранением в архив или кэш.
# ===============================================================

import pandas as pd
from datetime import datetime
from loguru import logger

# ===============================================================
# MAIN CHECK FUNCTION
# ===============================================================

def data_integrity_check(df: pd.DataFrame, symbol: str = "EURUSD", timeframe: str = "M15") -> bool:
    """
    Проверяет целостность и корректность данных в DataFrame.
    Возвращает True, если всё в порядке.
    """

    try:
        if df is None or df.empty:
            logger.error(f"[CHECK] DataFrame пустой для {symbol} {timeframe}")
            return False

        logger.info(f"[CHECK] Начало проверки данных {symbol} {timeframe}, {len(df)} записей")

        # --- Проверка обязательных колонок ---
        required_columns = ["datetime", "open", "high", "low", "close", "tick_volume"]
        for col in required_columns:
            if col not in df.columns:
                logger.error(f"[CHECK] Отсутствует колонка: {col}")
                return False

        # --- Проверка типов данных ---
        numeric_cols = ["open", "high", "low", "close", "tick_volume"]
        for col in numeric_cols:
            if not pd.api.types.is_numeric_dtype(df[col]):
                logger.warning(f"[CHECK] Некорректный тип данных в колонке {col}, выполняется преобразование...")
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # --- Проверка сортировки по времени ---
        if not df["datetime"].is_monotonic_increasing:
            logger.warning("[CHECK] Данные не отсортированы, выполняется сортировка...")
            df.sort_values("datetime", inplace=True)

        # --- Проверка дубликатов ---
        dup_count = df.duplicated(subset=["datetime"]).sum()
        if dup_count > 0:
            logger.warning(f"[CHECK] Найдено дубликатов: {dup_count}, удаляются...")
            df.drop_duplicates(subset=["datetime"], inplace=True)

        # --- Проверка пропусков во временной последовательности ---
        df["delta"] = df["datetime"].diff().dt.total_seconds()
        median_step = df["delta"].median()
        gap_limit = median_step * 3 if median_step else 0
        gaps = df[df["delta"] > gap_limit]
        if not gaps.empty:
            logger.warning(f"[CHECK] Обнаружены возможные пропуски ({len(gaps)} баров)")

        df.drop(columns=["delta"], inplace=True, errors="ignore")

        # --- Проверка диапазона ---
        min_time, max_time = df["datetime"].min(), df["datetime"].max()
        logger.info(f"[CHECK] Диапазон данных: {min_time} → {max_time}")

        # --- Финальный вывод ---
        logger.info(f"[CHECK] Проверка данных завершена успешно для {symbol} {timeframe}")
        return True

    except Exception as e:
        logger.error(f"[CHECK] Ошибка при проверке данных: {e}")
        return False

# ===============================================================
# TEST MODE (manual run)
# ===============================================================

if __name__ == "__main__":
    logger.info("[CHECK] Тестовый запуск Data Integrity Checker")
    # Пример теста (если нужно отладить локально)
    # df = pd.read_parquet("data/archive/raw/EURUSD/M15/2025_01_01_2025_11_01.parquet")
    # data_integrity_check(df, "EURUSD", "M15")
