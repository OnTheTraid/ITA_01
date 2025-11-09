# utils/config_loader.py
import os
import yaml
from dotenv import load_dotenv

def load_config():
    """Загрузка конфигураций из .env и config.yaml"""
    load_dotenv()  # Загружаем переменные окружения из .env

    # Читаем YAML-файл
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Добавляем чувствительные данные из .env
    config["mt5"] = {
        "login": os.getenv("MT5_LOGIN"),
        "password": os.getenv("MT5_PASSWORD"),
        "server": os.getenv("MT5_SERVER"),
    }

    return config
