# utils/logging_stub.py
from loguru import logger
import os

# Создаём базовую директорию для логов, если её нет
os.makedirs("logs/coredata", exist_ok=True)

# Настраиваем логгер
logger.add(
    "logs/coredata/mt5_connector.log",
    rotation="5 MB",
    retention="10 days",
    level="INFO",
    encoding="utf-8",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)
