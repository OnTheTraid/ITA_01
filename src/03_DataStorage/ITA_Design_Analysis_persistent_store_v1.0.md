# ITA_Design_Analysis_persistent_store_v1.0.md

## 1. Роль persistent_store.py в ITA

С учётом:

ITA_description.md — нужна воспроизводимая, прозрачная, документированная система для анализа и бэктестов.

ITA_modules_v1.1 — блок 2.3.1 Persistent Store: база исходных свечей, PNG, JSON, моделей, метаданных.

architecture_v1.1.md — local-first структура (data/, exchange/, logs/ и т.д.).

ITA_TZ_03_DataStorage_v1.0.md — DataStorage как слой хранения + versioning, без бизнес-логики.

ITA_TZ_02_CoreData.md — CoreData генерирует нормализованные данные и summary.

manifest.md + ITA Development Guidelines — модульная дисциплина, строгая трассируемость.

Вывод:
persistent_store.py — это низкоуровневый сервис-хранилище внутри модуля 03_DataStorage, который:

Даёт единый способ надёжно сохранять и читать артефакты (parquet, json, любые файлы).

Работает через конфиг, не хардкодит пути.

Возвращает стандартизированный ArtifactRef (из metadata_schemas.py).

Не решает, какие артефакты к какому run_id относятся — это задача run_registry.py.

Не содержит бизнес-логики, только I/O и минимальную валидацию.

Это кирпич, на котором строится:

run_registry (provenance),

rule_registry,

Backtester, Outputs, ML, Vision, и т.д.

2. Границы ответственности (очень чётко)
persistent_store.py ДЕЛАЕТ:

Читает глобальные пути из config.yaml.

Создаёт при необходимости директории.

Сохраняет:

табличные данные → parquet/csv,

структуры → json,

бинарные файлы (png, html, zip, др.) → как есть.

Возвращает ArtifactRef с:

id (строка),

kind (что это за артефакт),

path (относительный или абсолютный путь),

format,

meta (небольшой словарь).

Загружает данные по ArtifactRef.

Делает это максимально безопасно (atomic write, базовая проверка существования).

persistent_store.py НЕ ДЕЛАЕТ:

Не придумывает run_id, setup_id, rule_version.

Не регистрирует run’ы — это run_registry.py.

Не определяет политик очистки — это retention_policy.py.

Не строит бизнес-структуры (schema сигналов, бэктестов) — только сохраняет то, что ему передали.

Не дергает Prefect, Streamlit, Notion, Telegram.

Это важно: мы не смешиваем слои.

3. Структурные зависимости (по ITA Docs)

persistent_store.py должен опираться на:

configs/config.yaml
Использует секцию (с учётом уже внесённого обновления):

paths:
  data_root: "data/"
  archive_root: "data/archive/"
  cache_root: "data/cache/"
  results_root: "data/results/"
  exchange_root: "exchange/"
  logs_root: "logs/"


metadata_schemas.py
Для ArtifactRef.

path_resolver.py
Логику построения путей лучше вынести туда; persistent_store либо:

вызывает path_resolver,

либо использует внутренний минимальный helper, но не ломает общую концепцию.

Логгер DataStorage
Логи в logs/runtime/data_storage.log или logs/datastorage/persistent_store.log (как решите в ТЗ).

persistent_store не должен знать, кто его зовёт (CoreData, Backtester, ML) — он получает уже всё необходимое в параметрах.

4. Концепция артефакта: ArtifactRef

В соответствии с ТЗ DataStorage:

Видимое извне правило:

Всё, что сохранено через persistent_store, возвращается как ArtifactRef.

Всё, что загружается, делается по ArtifactRef.

Минимальная модель (псевдо, уже есть в metadata_schemas.py):

class ArtifactRef(BaseModel):
    id: str          # уникальный ID, например "{run_id}__{kind}__{suffix}"
    kind: str        # semantic: "raw_candles", "processed_candles", "signals", "backtest_results", "png_original" etc.
    path: str        # относительный путь от корня проекта или data_root
    format: str      # "parquet", "json", "png", "csv", ...
    meta: Dict[str, str] = {}


Важно:

run_id, setup_id, rule_version НЕ обязаны храниться в самом ArtifactRef — их хранит RunMeta в run_registry. Но:

при желании можно продублировать их в meta как удобство.

5. Минимально необходимый интерфейс persistent_store.py

Только то, что точно нужно. Не плодим 30 функций.

5.1. Базовые принципы

Все операции должны быть:

предсказуемы,

просты,

покрываемы тестами.

Запись делаем атомарно:

пишем во временный файл,

fsync,

rename.

Всегда логируем:

успешные записи,

ошибки.

5.2. Предлагаемый интерфейс (без реализации, но жёстко зафиксированный)
# persistent_store.py (целевой интерфейс)

from typing import Any, Dict, Union
import pandas as pd
from .metadata_schemas import ArtifactRef
from .path_resolver import resolve_artifact_path  # предполагаем такой интерфейс

# --- Публичные функции ---

def save_dataframe(
    df: pd.DataFrame,
    kind: str,
    filename: str,
    subdir: str = ""
) -> ArtifactRef:
    """
    Сохраняет DataFrame в parquet (по умолчанию) в results/archive/cache (в зависимости от kind/subdir).
    Не решает, к какому run_id относится — имя файла и subdir приходят извне.
    """

def load_dataframe(ref: ArtifactRef) -> pd.DataFrame:
    """
    Читает parquet/csv из пути ref.path.
    """

def save_json(
    data: Union[Dict[str, Any], list],
    kind: str,
    filename: str,
    subdir: str = ""
) -> ArtifactRef:
    """
    Сохраняет JSON-структуру.
    """

def load_json(ref: ArtifactRef) -> Union[Dict[str, Any], list]:
    """
    Читает JSON по ArtifactRef.
    """

def save_binary(
    content: bytes,
    kind: str,
    filename: str,
    subdir: str = ""
) -> ArtifactRef:
    """
    Сохраняет бинарный файл (PNG, HTML, ZIP и т.п.).
    """

def file_exists(ref: ArtifactRef) -> bool:
    """
    Проверяет существование файла.
    """

Почему так:

kind и subdir позволяют на стороне вызывающего (run_registry, backtester) решать:

куда логически отнести файл (results, screenshots и т.п.).

filename формируется там же из контекста:

например: f"{run_id}__candles.parquet", "{run_id}__signals.json".

persistent_store только:

строит путь через path_resolver,

создаёт директорию,

пишет файл,

возвращает ArtifactRef.

Никаких “мудрых” auto-решений, которые потом сложно отлаживать.

6. Взаимодействие с run_registry.py

Чтобы соблюсти ITA_TZ_03 и манифест:

Шаг выполнения флоу (Prefect / Backtest / Live):

run_registry.register_run(RunMeta(...)) создаёт запись и знает run_id.

Когда нужно сохранить артефакт:

вызывающий модуль (Backtester, CoreData wrapper и т.д.):

собирает имя файла, например:

f"{run_id}__backtest_results.json"

f"{run_id}__candles.parquet".

вызывает persistent_store.save_*.

получает ArtifactRef.

Привязка:

run_registry.attach_artifact(run_id, artifact_ref).

Таким образом:

persistent_store не знает о run_id как обязательном поле,

но интерфейс легко позволяет выстраивать связку согласно ITA_TZ_03.

7. Ошибки, надёжность, логирование

Минимум, который нужен и достаточен:

Любая ошибка записи/чтения:

логируется в data_storage-логгер с уровнем ERROR,

поднимает осмысленное исключение (PersistentStoreError), чтобы Upstream (Prefect task) видел причину.

При записи:

если директория не существует → создать.

если файл уже есть:

либо перезаписать (по умолчанию),

либо опционально overwrite=False и тогда кидать ошибку — это можно добавить аргументом, без усложнения.

Это всё. Без собственного кэша, без сложных локов, без избыточной магии.

8. Проверка на согласованность с ITA Docs

Пробегаемся по ключевым требованиям:

ITA_modules_v1.1 (2.3.1 Persistent Store) — наш дизайн:

хранит все типы артефактов;

поддерживает метаданные через ArtifactRef;

легко расширяется до БД/облака, не ломая интерфейсы.

ITA_TZ_03_DataStorage_v1.0:

persistent_store не влезает в run_snapshot, rule_registry, retention — они сверху.

соответствует обновлению: всё завязано на единые пути и метаданные.

ITA_TZ_02_CoreData:

CoreData может писать архивы/кэши через save_dataframe, имя файла формируется с учётом run_id/периода.

Нет циклической зависимости 02 ↔ 03.

Prefect Flows / Data Flows:

backtest_flow / live_flow могут централизованно регистрировать run’ы и сохранять всё через persistent_store.

Всё трассируемо.

Manifest & Development Guidelines:

Модуль изолирован,

функции прозрачны,

нет смешения ролей.

Конфликтов или логических дыр в связках persistent_store ←→ остальная архитектура нет, при таком дизайне.