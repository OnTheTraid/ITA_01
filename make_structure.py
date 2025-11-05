import os

# === Базовая директория проекта ===
BASE_DIR = r"D:\ITA\ITA_1.0\ITA_Project"

# === Основные папки проекта ===
FOLDERS = [
    # корень
    "docs/design_notes",
    "scripts",
    "data/archive",
    "data/cache",
    "data/examples",
    "exchange/to_vision",
    "exchange/annotated",
    "exchange/archive",
    "logs/prefect",
    "logs/training",
    "logs/runtime",
    "flows",
    "configs",
    "assets/icons",
    "assets/screenshots",
    "assets/styles",
    "assets/prompts",
    "notebooks",
    "tests/unit",
    "tests/integration",

    # исходный код
    "src/01_UserRequest_API",
    "src/02_CoreData_IO",
    "src/03_DataStorage_Versioning",
    "src/04_MarketTools",
    "src/05_SetupManager_RuleLogic",
    "src/06_Backtester_Manager",
    "src/07_Visualization_Engine",
    "src/08_GPT_VisionFlow",
    "src/09_Learning_Module",
    "src/10_Outputs_Integrations",
    "src/11_Orchestration_Workflows",
    "src/12_Config_Security",
    "src/13_QA_Testing",
    "src/14_UX_Interface",
    "src/15_Feedback_Learning",
    "src/utils",
]

# === Файлы-заглушки (создаём пустыми) ===
FILES = {
    "README.md": "# ITA_Project\n\nTrading Intelligence Agent (Prefect + Streamlit + LangChain)\n",
    "LICENSE": "MIT License\n\nCopyright (c) 2025 ITA",
    "setup.cfg": "[metadata]\nname = ita_project\nversion = 0.1.0\n",
    "config.yaml": "# Основной конфигурационный файл проекта\n",
    "config.example.env": "# Пример .env файла\nOPENAI_API_KEY=\nTELEGRAM_TOKEN=\nNOTION_TOKEN=\n",
    "requirements.txt": "# Установите зависимости из этого файла\n# pip install -r requirements.txt\n",
    ".gitignore": "# Добавьте сюда шаблоны исключений\n",
}

# === Пустые служебные файлы, которые должны быть во всех папках ===
def create_init_files(base_dir):
    for root, dirs, files in os.walk(base_dir):
        if "__init__.py" not in files and root.endswith("src"):
            continue
        init_path = os.path.join(root, "__init__.py")
        if not os.path.exists(init_path):
            with open(init_path, "w", encoding="utf-8") as f:
                f.write("# init\n")

def create_structure():
    print(f"Создание структуры проекта в: {BASE_DIR}\n")

    for folder in FOLDERS:
        path = os.path.join(BASE_DIR, folder)
        os.makedirs(path, exist_ok=True)
        # создаем __init__.py в src и его подпапках
        if path.startswith(os.path.join(BASE_DIR, "src")):
            init_file = os.path.join(path, "__init__.py")
            with open(init_file, "w", encoding="utf-8") as f:
                f.write("# init\n")

    # создаём корневые файлы
    for filename, content in FILES.items():
        file_path = os.path.join(BASE_DIR, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    # создаём шаблонные файлы в configs/
    config_files = {
        "default.yaml": "# Default project configuration\n",
        "secrets_template.yaml": "# Template for secrets (API keys)\n",
        "logging.yaml": "# Logging configuration\n"
    }
    for fname, content in config_files.items():
        path = os.path.join(BASE_DIR, "configs", fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    # создаём шаблонные flows
    flow_files = ["backtest_flow.py", "live_flow.py", "data_refresh_flow.py"]
    for fname in flow_files:
        with open(os.path.join(BASE_DIR, "flows", fname), "w", encoding="utf-8") as f:
            f.write(f"# {fname}\n# Prefect flow placeholder\n")

    print("✅ Структура проекта успешно создана.")

if __name__ == "__main__":
    create_structure()
