"""
run_snapshot.py
Подмодуль 2.3.3 Run Snapshot / Provenance (боевой).

Задачи:
- Зафиксировать контекст каждого запуска (backtest/live).
- Обеспечить воспроизводимость через сохранённый снапшот.
- Использовать централизованное хранилище (persistent_store + ArtifactRef).
- Не содержать бизнес-логики стратегий и сигналов.

Основано на:
- ITA_TZ_03_DataStorage_2.3.3_RunSnapshot.md
- ITA_TZ_03_DataStorage_2.3.2_RuleVersionRegistry.md
- ITA_TZ_03_DataStorage_v1.0.md
- ITA_Design_Analysis_persistent_store_v1.0.md
- ITA Development Guidelines
- ITA_modules_v1.1 (M03_DataStorage)
- ITA_Dependency_Manifest

Принципы:
- Все записи снапшотов идут через persistent_store.
- Структура снапшота стабильна, валидируется.
- Минимум зависимостей, максимум предсказуемости.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import yaml  # PyYAML
from pydantic import BaseModel, ValidationError

# ---- Импорт persistent_store и ArtifactRef (устойчиво к способу запуска) ----

try:
    # Пакетный импорт, если M03_DataStorage оформлен как пакет
    from . import persistent_store as ps  # type: ignore
    from .metadata_schemas import ArtifactRef  # type: ignore
except Exception:  # noqa: BLE001
    # Фоллбек, если модуль запускается напрямую
    import importlib.util

    here = Path(__file__).resolve().parent
    ps_path = here / "persistent_store.py"
    ms_path = here / "metadata_schemas.py"

    if not ps_path.exists():
        raise ImportError("persistent_store.py not found for run_snapshot")

    spec_ps = importlib.util.spec_from_file_location("persistent_store", ps_path)
    ps = importlib.util.module_from_spec(spec_ps)  # type: ignore[assignment]
    assert spec_ps.loader is not None
    spec_ps.loader.exec_module(ps)  # type: ignore[arg-type]

    if not ms_path.exists():
        raise ImportError("metadata_schemas.py not found for run_snapshot")

    spec_ms = importlib.util.spec_from_file_location("metadata_schemas", ms_path)
    ms = importlib.util.module_from_spec(spec_ms)  # type: ignore[assignment]
    assert spec_ms.loader is not None
    spec_ms.loader.exec_module(ms)  # type: ignore[arg-type]

    if not hasattr(ms, "ArtifactRef"):
        raise ImportError("ArtifactRef not found in metadata_schemas")

    ArtifactRef = ms.ArtifactRef  # type: ignore[assignment]


logger = logging.getLogger("ita.M03_DataStorage.run_snapshot")
logger.addHandler(logging.NullHandler())


# ==== Конфигурация и пути ====


def _get_project_root() -> Path:
    """
    Определяет корень проекта ITA_01.
    Ожидаем:
    .../ITA_01/
        configs/config.yaml
        src/M03_DataStorage/run_snapshot.py
    """
    return Path(__file__).resolve().parents[2]


def _load_config() -> Dict[str, Any]:
    root = _get_project_root()
    cfg_path = root / "configs" / "config.yaml"
    if not cfg_path.exists():
        logger.warning("config.yaml not found for RunSnapshot, using defaults")
        return {
            "paths": {
                "data_root": "data/",
                "results_root": "data/results/",
            },
            "results": {
                "provenance_path": "data/results/provenance",
            },
        }

    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    paths = cfg.setdefault("paths", {})
    paths.setdefault("data_root", "data/")
    paths.setdefault("results_root", "data/results/")

    results = cfg.setdefault("results", {})
    results.setdefault("provenance_path", "data/results/provenance")

    return cfg


_CONFIG: Dict[str, Any] = _load_config()


def _get_provenance_dir() -> Path:
    """
    Возвращает абсолютный путь к директории для снапшотов.
    Основано на config.results.provenance_path или дефолте.
    """
    root = _get_project_root()
    prov_cfg = (
        _CONFIG.get("results", {})
        .get("provenance_path", "data/results/provenance")
    )
    prov_path = Path(prov_cfg)

    if not prov_path.is_absolute():
        prov_path = root / prov_path

    prov_path.mkdir(parents=True, exist_ok=True)
    return prov_path


_PROVENANCE_DIR: Path = _get_provenance_dir()


# ==== Модели данных снапшота ====


@dataclass
class EnvInfo:
    python: str
    os: str
    machine: str


@dataclass
class RunSnapshotData:
    run_id: str
    setup_id: str
    rule_version: str
    data_hash: str
    data_range: Optional[list[str]]
    git_commit_hash: str
    env: EnvInfo
    timestamp: str
    meta: Dict[str, Any]


class RunSnapshotModel(BaseModel):
    """
    Pydantic-валидация снапшота.
    Соответствует ITA_TZ_03_DataStorage_2.3.3_RunSnapshot.
    """

    run_id: str
    setup_id: str
    rule_version: str
    data_hash: str
    data_range: Optional[list[str]] = None
    git_commit_hash: str
    env: Dict[str, Any]
    timestamp: str
    meta: Dict[str, Any] = {}


# ==== Утилиты ====


def _hash_file(path: Path) -> str:
    """
    SHA256 для файла. Если файла нет — возвращаем 'none'.
    """
    if not path.exists() or not path.is_file():
        logger.warning("Data file for hash not found: %s", path)
        return "none"

    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_git_commit_hash(project_root: Path) -> str:
    """
    Пытаемся получить git commit hash. Если нет git/репозитория — 'none'.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            check=False,
        )
        commit = (result.stdout or "").strip()
        return commit if commit else "none"
    except Exception:  # noqa: BLE001
        return "none"


def _collect_env_info() -> EnvInfo:
    return EnvInfo(
        python=sys.version.split()[0],
        os=f"{platform.system()} {platform.release()}",
        machine=platform.machine(),
    )


def _build_snapshot_filename(run_id: str) -> str:
    return f"{run_id}.json"


def _build_snapshot_path(run_id: str) -> Path:
    return _PROVENANCE_DIR / _build_snapshot_filename(run_id)


def _validate_snapshot(snapshot: Dict[str, Any]) -> None:
    """
    Минимальная строгая валидация структуры снапшота.
    Если не проходит — выбрасываем исключение.
    """
    try:
        RunSnapshotModel(**snapshot)
    except ValidationError as exc:  # noqa: BLE001
        logger.error("Run snapshot validation failed: %s", exc)
        raise ValueError(f"Invalid run snapshot structure: {exc}") from exc


# ==== Публичный интерфейс подмодуля ====


class RunProvenance:
    """
    Боевой сервис для работы со снапшотами запусков.

    Обязанности:
    - Создать снапшот запуска (create_snapshot).
    - Загрузить снапшот по run_id (load_snapshot).
    - Проверить целостность данных по сохранённому хешу (verify_data_hash).

    Не делает:
    - не генерирует run_id;
    - не запускает бэктесты;
    - не меняет правила (использует RuleVersionRegistry извне).
    """

    def __init__(self) -> None:
        # Проверь, что директория существует (создаётся при инициализации модуля)
        _PROVENANCE_DIR.mkdir(parents=True, exist_ok=True)

    # --- Основной метод ---

    def create_snapshot(
        self,
        run_id: str,
        setup_id: str,
        rule_version: str,
        data_path: Optional[str] = None,
        data_range: Optional[list[str]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> ArtifactRef:
        """
        Создаёт и сохраняет снапшот запуска.

        Параметры:
        - run_id: уникальный ID запуска (генерируется оркестратором/Backtester).
        - setup_id: ID сетапа из Rule & Version Registry.
        - rule_version: конкретная версия правил.
        - data_path: путь к файлу с входными данными (csv/parquet/etc) для hash.
        - data_range: опциональный диапазон дат, если есть.
        - meta: любой дополнительный контекст (author, mode, tags и т.п.).

        Возвращает:
        - ArtifactRef на сохранённый JSON.
        """
        project_root = _get_project_root()
        env = _collect_env_info()
        git_hash = _get_git_commit_hash(project_root)

        data_file = Path(data_path) if data_path else None
        data_hash = _hash_file(data_file) if data_file else "none"

        ts = datetime.now(timezone.utc).isoformat()

        snapshot = RunSnapshotData(
            run_id=run_id,
            setup_id=setup_id,
            rule_version=rule_version,
            data_hash=data_hash,
            data_range=data_range,
            git_commit_hash=git_hash,
            env=env,
            timestamp=ts,
            meta=meta or {},
        )

        snapshot_dict = asdict(snapshot)
        # env в dataclass → dict
        snapshot_dict["env"] = asdict(env)

        _validate_snapshot(snapshot_dict)

        filename = _build_snapshot_filename(run_id)

        # Используем persistent_store для записи.
        # subdir берём как относительный к data_root: "results/provenance"
        # Это согласовано с config.results.provenance_path.
        try:
            ref: ArtifactRef = ps.save_json(
                snapshot_dict,
                kind="run_snapshot",
                filename=filename,
                subdir="results/provenance",
            )
            logger.info(
                "Run snapshot created: run_id=%s setup_id=%s rule_version=%s path=%s",
                run_id,
                setup_id,
                rule_version,
                ref.path,
            )
            return ref
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to save run snapshot for %s: %s", run_id, exc)
            raise

    # --- Загрузка снапшота ---

    def load_snapshot(self, run_id: str) -> Dict[str, Any]:
        """
        Загружает снапшот по run_id.

        Если файла нет или структура невалидна — выбрасывает исключение.
        """
        path = _build_snapshot_path(run_id)
        if not path.exists():
            raise FileNotFoundError(f"Run snapshot not found for run_id={run_id}: {path}")

        # Строим ArtifactRef вручную и читаем через persistent_store.load_json
        ref = ArtifactRef(
            id=path.name,
            kind="run_snapshot",
            path=str(path),
            format="json",
            meta={},
        )

        data = ps.load_json(ref)
        _validate_snapshot(data)
        return data

    # --- Проверка целостности данных ---

    def verify_data_hash(self, run_id: str, file_path: str) -> bool:
        """
        Сравнивает сохранённый в снапшоте хеш данных с текущим хешем файла.

        Возвращает:
        - True, если хеши совпадают;
        - False, если нет или файл отсутствует.
        """
        snapshot = self.load_snapshot(run_id)
        expected_hash = snapshot.get("data_hash", "none")

        current_hash = _hash_file(Path(file_path))
        if expected_hash == "none":
            logger.warning(
                "Snapshot for run_id=%s has no data_hash (expected_hash=none)", run_id
            )
            return False

        match = (expected_hash == current_hash)
        if not match:
            logger.warning(
                "Data hash mismatch for run_id=%s: expected=%s got=%s",
                run_id,
                expected_hash,
                current_hash,
            )
        else:
            logger.info(
                "Data hash verified for run_id=%s", run_id
            )
        return match
