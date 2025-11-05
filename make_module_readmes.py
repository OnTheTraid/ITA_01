# make_module_readmes.py
import os

base_path = r"D:\ITA\ITA_1.0\ITA_Project\src"

template = """# {module_name}
Описание модуля и его назначения.

## 📥 Входные данные (Inputs)
- источник данных
- формат
- частота обновления

## 📤 Выходные данные (Outputs)
- назначение
- формат

## ⚙️ ASCII схема
[Твоя ASCII-схема]

scss
Копировать код
"""

# пройти по всем папкам верхнего уровня в src
for folder in os.listdir(base_path):
    full_path = os.path.join(base_path, folder)
    if os.path.isdir(full_path):
        readme_path = os.path.join(full_path, "README.md")

        # если README ещё нет — создаём
        if not os.path.exists(readme_path):
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(template.format(module_name=folder))
            print(f"✅ Создан README.md для {folder}")
        else:
            print(f"⚠️ Уже существует: {folder}")

print("\nГотово! Все README.md файлы созданы.")