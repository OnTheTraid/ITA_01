"""
persistent_store.py
Универсальное и устойчивое хранилище артефактов для ITA.
Работает даже на ранней стадии проекта, с папкой 03_DataStorage.
"""

from __future__ import annotations

import json
import logging
import os
import importlib.util
from pathlib import Path
from typing import Any, Dict, Union

import pandas as pd
import yaml  # требуется PyYAML

logger = logging.getLogger("ita.datastorage.persistent_store")
logger.addHandler(logging.NullHandler())


class PersistentStoreError(Exception):
    """Базовое исключение для ошибок persistent_store."""


# ===== CONFIG =====

def _get_project_root() -> Path:
    """
    Корень проекта:
    .../ITA_01/
        configs/config.yaml
        src/03_DataStorage/persistent_store.py
    """
    here = Path(__file__).resolve()
    return here.parents[2]


def _load_config() -> Dict[str, Any]:
    root = _get_project_root()
    cfg_path = root / "configs" / "config.yaml"

    if not cfg_path.exists():
        logger.warning("config.yaml not found, using default paths")
        return {
            "paths": {
                "data_root": "data/",
                "archive_root": "data/archive/",
                "cache_root": "data/cache/",
                "results_root": "data/results/",
                "exchange_root": "data/exchange/",
                "logs_root": "logs/",
            }
        }

    with cfg_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    paths = data.setdefault("paths", {})
    paths.setdefault("data_root", "data/")
    paths.setdefault("archive_root", "data/archive/")
    paths.setdefault("cache_root", "data/cache/")
    paths.setdefault("results_root", "data/results/")
    paths.setdefault("exchange_root", "data/exchange/")
    paths.setdefault("logs_root", "logs/")

    return data


_CONFIG: Dict[str, Any] = _load_config()


# ===== ArtifactRef loader =====

def _load_artifactref_class():
    """
    Загружаем ArtifactRef из metadata_schemas.py,
    работает и в пакетном режиме, и как отдельный файл.
    """
    # 1. Пытаемся относительный импорт (если вдруг пакет работает)
    try:
        from .metadata_schemas import ArtifactRef as AR  # type: ignore
        return AR
    except Exception:
        pass

    # 2. Грузим файл по пути рядом
    here = Path(__file__).resolve().parent
    ms_path = here / "metadata_schemas.py"
    if not ms_path.exists():
        raise ImportError("metadata_schemas.py with ArtifactRef is required for persistent_store")

    spec = importlib.util.spec_from_file_location("metadata_schemas", ms_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore[arg-type]

    if not hasattr(module, "ArtifactRef"):
        raise ImportError("metadata_schemas.ArtifactRef not found in metadata_schemas.py")

    return module.ArtifactRef


ArtifactRef = _load_artifactref_class()


# ===== path_resolver loader =====

def _try_import_path_resolver():
    # 1. Пакетный импорт
    try:
        from .path_resolver import resolve_artifact_path  # type: ignore
        return resolve_artifact_path
    except Exception:
        pass

    # 2. Файл рядом
    here = Path(__file__).resolve().parent
    pr_path = here / "path_resolver.py"
    if pr_path.exists():
        spec = importlib.util.spec_from_file_location("path_resolver", pr_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)  # type: ignore[arg-type]
        if hasattr(module, "resolve_artifact_path"):
            return module.resolve_artifact_path  # type: ignore[attr-defined]

    # 3. Нет резолвера — будем использовать fallback
    return None


_RESOLVE_ARTIFACT_PATH = _try_import_path_resolver()


# ===== PATH LOGIC =====

def _fallback_resolve_artifact_path(kind: str, filename: str, subdir: str = "") -> Path:
    paths = _CONFIG.get("paths", {})
    data_root = Path(paths.get("data_root", "data/"))
    results_root = Path(paths.get("results_root", "data/results/"))
    exchange_root = Path(paths.get("exchange_root", "data/exchange/"))
    archive_root = Path(paths.get("archive_root", "data/archive/"))
    cache_root = Path(paths.get("cache_root", "data/cache/"))

    lk = kind.lower()

    if any(k in lk for k in ("backtest", "result", "report", "metric")):
        base = results_root
    elif any(k in lk for k in ("signal", "alert")):
        base = results_root
    elif any(k in lk for k in ("png", "snapshot", "annotated", "vision")):
        base = exchange_root
    elif "archive" in lk:
        base = archive_root
    elif "cache" in lk:
        base = cache_root
    else:
        base = data_root

    if subdir:
        base = base / subdir

    return base / filename


def _build_path(kind: str, filename: str, subdir: str = "") -> Path:
    if _RESOLVE_ARTIFACT_PATH is not None:
        try:
            p = _RESOLVE_ARTIFACT_PATH(kind=kind, filename=filename, subdir=subdir)  # type: ignore
            return Path(p)
        except TypeError:
            p = _RESOLVE_ARTIFACT_PATH(kind, filename, subdir)  # type: ignore
            return Path(p)
        except Exception as exc:  # noqa: BLE001
            logger.warning("path_resolver failed (%s), using fallback", exc)

    return _fallback_resolve_artifact_path(kind, filename, subdir)


# ===== ATOMIC WRITE =====

def _atomic_write_bytes(path: Path, data: bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with tmp_path.open("wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to write file %s: %s", path, exc)
        raise PersistentStoreError(f"Failed to write file: {path}") from exc


# ===== PUBLIC API =====

def save_dataframe(
    df: pd.DataFrame,
    kind: str,
    filename: str,
    subdir: str = "",
) -> ArtifactRef:
    path = _build_path(kind, filename, subdir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        df.to_parquet(tmp_path)
        with tmp_path.open("rb") as f:
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save DataFrame to %s: %s", path, exc)
        raise PersistentStoreError(f"Failed to save DataFrame: {path}") from exc

    logger.info("Saved DataFrame artifact: kind=%s path=%s", kind, path)
    return ArtifactRef(id=filename, kind=kind, path=str(path), format="parquet", meta={})


def load_dataframe(ref: ArtifactRef) -> pd.DataFrame:
    path = Path(ref.path)
    if not path.exists():
        logger.error("DataFrame file not found: %s", path)
        raise PersistentStoreError(f"DataFrame file not found: {path}")

    try:
        if ref.format == "csv":
            return pd.read_csv(path)
        return pd.read_parquet(path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load DataFrame from %s: %s", path, exc)
        raise PersistentStoreError(f"Failed to load DataFrame: {path}") from exc


def save_json(
    data: Union[Dict[str, Any], list],
    kind: str,
    filename: str,
    subdir: str = "",
) -> ArtifactRef:
    path = _build_path(kind, filename, subdir)
    try:
        txt = json.dumps(data, ensure_ascii=False, indent=2)
        _atomic_write_bytes(path, txt.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save JSON to %s: %s", path, exc)
        raise PersistentStoreError(f"Failed to save JSON: {path}") from exc

    logger.info("Saved JSON artifact: kind=%s path=%s", kind, path)
    return ArtifactRef(id=filename, kind=kind, path=str(path), format="json", meta={})


def load_json(ref: ArtifactRef):
    path = Path(ref.path)
    if not path.exists():
        logger.error("JSON file not found: %s", path)
        raise PersistentStoreError(f"JSON file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load JSON from %s: %s", path, exc)
        raise PersistentStoreError(f"Failed to load JSON: {path}") from exc


def save_binary(
    content: bytes,
    kind: str,
    filename: str,
    subdir: str = "",
) -> ArtifactRef:
    path = _build_path(kind, filename, subdir)
    try:
        _atomic_write_bytes(path, content)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save binary to %s: %s", path, exc)
        raise PersistentStoreError(f"Failed to save binary: {path}") from exc

    logger.info("Saved binary artifact: kind=%s path=%s", kind, path)
    fmt = path.suffix.lstrip(".").lower() if path.suffix else "bin"
    return ArtifactRef(id=filename, kind=kind, path=str(path), format=fmt, meta={})


def load_binary(ref: ArtifactRef) -> bytes:
    path = Path(ref.path)
    if not path.exists():
        logger.error("Binary file not found: %s", path)
        raise PersistentStoreError(f"Binary file not found: {path}")
    try:
        return path.read_bytes()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load binary from %s: %s", path, exc)
        raise PersistentStoreError(f"Failed to load binary: {path}") from exc


def file_exists(ref: ArtifactRef) -> bool:
    try:
        exists = Path(ref.path).exists()
        logger.debug("file_exists check: path=%s exists=%s", ref.path, exists)
        return exists
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to check file existence for %s: %s", ref.path, exc)
        raise PersistentStoreError(f"Failed to check file existence: {ref.path}") from exc
