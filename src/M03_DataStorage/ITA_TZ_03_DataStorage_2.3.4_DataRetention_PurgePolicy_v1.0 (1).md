# ITA – Technical Specification  
## Module M03_DataStorage  
### Submodule 2.3.4 — **Data Retention & Purge Policy**  
**Version:** 1.0  
**Status:** Production-ready  
**Author:** ITA System Architect (ChatGPT)  
**Based on:**  
- ITA Development Guidelines  
- ITA Modules v1.1  
- ITA Dependency Manifest  
- ITA_Design_Analysis_persistent_store_v1.0  
- ITA_TZ_03_DataStorage_2.3.2_RuleVersionRegistry  
- ITA_TZ_03_DataStorage_2.3.3_RunSnapshot  
- Existing M03_DataStorage codebase  

---

# 1. Назначение подмодуля  
Подмодуль **Data Retention & Purge Policy** обеспечивает:  
- контроль длительности хранения Артефактов;  
- автоматизированное удаление устаревших данных;  
- очистку временных и отладочных файлов;  
- защиту от переполнения стора;  
- работу как в автономном режиме, так и внутри ITA-Agent.  

Подмодуль является **боевым**, должен работать в реальном продакшене без доработок.

---

# 2. Область ответственности  
Подмодуль отвечает за следующие зоны:

### 2.1. Purge Policy  
Гарантирует поддержание стабильного объёма данных:

- Очистка старых результатов бэктестов.  
- Очистка старых снапшотов (превышение возраста или количества).  
- Удаление устаревших правил и их версий.  
- Удаление временных файлов (temp, cache).  
- Возможность полного purge для аварийных ситуаций.

### 2.2. Retention Policy  
Позволяет гибко настраивать хранение:

- Срок хранения артефактов по типу:  
  - run_snapshot  
  - rule_version  
  - backtest_result  
  - live_result  
  - logs  
- Ограничение количества объектов.  
- Защита последних N файлов.  
- Защита «закреплённых» (pinned) версий.

---

# 3. Требования к интеграции  
### 3.1. Совместимость  
- Полная совместимость с persistent_store.  
- Полная совместимость с ArtifactRef.  
- Не нарушает работу RunSnapshot, VersionRegistry.

### 3.2. Безопасность  
- Никогда не удаляет активные файлы агента.  
- Всегда логирует операции.

### 3.3. Конфигурация  
Все параметры задаются в:

```
/configs/data_retention.yaml
```

или в:

```
config.yaml:
  retention:
    enabled: true
    rules:
      run_snapshot:
        max_age_days: 30
        max_count: 200
        keep_last: 5
      rule_version:
        max_age_days: 180
        max_count: 50
        keep_last: 2
```

---

# 4. Директории, с которыми работает модуль

```
data/
 ├── results/
 │    ├── provenance/           # snapshots
 │    ├── backtests/            # backtest artifacts
 │    └── live/                 # live artifacts
 ├── rules/                     # RuleVersionRegistry files  
 └── temp/                      # temp files
logs/
 └── storage/                   # storage purge logs
```

---

# 5. Логика работы подмодуля

Подмодуль содержит сервис:

```
DataRetentionManager
```

Сервис предоставляет:

---

## 5.1. Метод purge()

Удаляет устаревшие объекты по правилам.

Логика:

1. Загружает конфиг из data_retention.yaml.  
2. Сканирует директории persistent_store.  
3. Для каждого типа артефактов:
   - определяет список файлов;  
   - сортирует по времени изменения;  
   - применяет фильтры:  
       - старше max_age_days  
       - количество > max_count  
   - защищает последние keep_last  
   - удаляет остальные  

4. Обновляет логи.  

---

## 5.2. Метод purge_all()

Используется в аварийных ситуациях.

Удаляет:

- все run_snapshot  
- все временные файлы  
- все результаты бэктестов  
- все ошибки и логи  

**Но не удаляет:**  
- pinned rules  
- critical metadata  

---

## 5.3. Метод get_storage_stats()

Возвращает:

- общий размер данных  
- размер по категориям  
- количество объектов  
- что подлежит удалению  

---

## 5.4. Метод simulate_purge()

«Сухой запуск» — показывает что будет удалено, но **не удаляет**.

---

# 6. Требования к коду

### 6.1. Качество

- Полное следование ITA Development Guidelines.  
- Исключения завернуты в DataRetentionError.  
- Логи пишутся в:
  ```
  logs/storage/purge.log
  ```

### 6.2. Тесты

Файл:

```
src/M03_DataStorage/test_data_retention.py
```

Тесты проверяют:

- purge  
- simulate_purge  
- max_count с keep_last  
- max_age_days  
- безопасность pinned-файлов  

---

# 7. Структура подмодуля

```
src/M03_DataStorage/
 ├── data_retention.py
 ├── test_data_retention.py
 ├── persistent_store.py
 ├── version_registry.py
 ├── run_snapshot.py
 └── schemas/
```

---

# 8. JSON-структуры

Формат файла purge_report.json:

```json
{
  "timestamp": "2025-11-14T20:12:55Z",
  "deleted": [
    {"path": "data/results/backtests/BTC_2024_01.json", "reason": "older_than_max_age"},
    {"path": "data/results/provenance/run_07.json", "reason": "exceeds_max_count"}
  ],
  "kept": [
    {"path": "data/results/provenance/run_31.json", "reason": "keep_last"}
  ],
  "stats": {
    "total_files": 129,
    "deleted_count": 38,
    "kept_count": 91
  }
}
```

---

# 9. Возможные ошибки

- DataRetentionError  
- MissingRetentionConfig  
- StoragePathNotFound  
- PurgePermissionError  

---

# 10. Производительность

- Обход директорий → до 10000 файлов.  
- Все операции должны выполняться ≤ 200 ms.  
- Работа происходит асинхронно (по желанию).

---

# 11. Совместимость с ITA-Agent

Подмодуль:

- используется оркестратором;  
- вызывается автоматически раз в N запусков;  
- может быть вызван вручную;  
- не мешает работе бэктестов/лайва.  

---

# 12. Планы расширения (на будущее)

- Хранение purge-журнала в clickhouse.  
- Retention для графиков / изображений.  
- Полная интеграция с Prefect pipeline.

---

# 13. Гарантии качества

Подмодуль считается готовым, когда:

✔ Все тесты пройдены  
✔ Код соответствует Guidelines  
✔ Тестируется в реальном окружении  
✔ Полностью совместим с существующими подмодулями  

---

# 14. Конец документа

Файл готов к сохранению в ITA Docs.
