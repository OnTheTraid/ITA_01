"""
version_registry.py
Подмодуль 2.3.2 Rule & Version Registry — БОЕВАЯ ВЕРСИЯ

Задачи:
- хранить версии сетапов и правил
- регистрировать новые версии
- загружать любую версию
- помечать версии deprecated
- сохранять документы JSON через persistent_store

Совместимо с:
- persistent_store
- ArtifactRef
- ITA Development Guidelines
"""

from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, ValidationError

# === Persistent Store Import (универсальный) ===
try:
    from . import persistent_store as ps
    from .metadata_schemas import ArtifactRef
except Exception:
    import importlib.util

    here = Path(__file__).resolve().parent

    # persistent_store
    spec_ps = importlib.util.spec_from_file_location(
        "persistent_store", here / "persistent_store.py"
    )
    ps = importlib.util.module_from_spec(spec_ps)
    spec_ps.loader.exec_module(ps)

    # metadata_schemas
    spec_ms = importlib.util.spec_from_file_location(
        "metadata_schemas", here / "metadata_schemas.py"
    )
    ms = importlib.util.module_from_spec(spec_ms)
    spec_ms.loader.exec_module(ms)

    ArtifactRef = ms.ArtifactRef


logger = logging.getLogger("ita.M03_DataStorage.version_registry")
logger.addHandler(logging.NullHandler())


# ================================================================
# CONFIG LOAD
# ================================================================

def _get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_config() -> Dict[str, Any]:
    root = _get_project_root()
    cfg_path = root / "configs" / "config.yaml"

    if not cfg_path.exists():
        return {
            "results": {
                "rules_path": "data/rules",
            }
        }

    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    results = cfg.setdefault("results", {})
    results.setdefault("rules_path", "data/rules")

    return cfg


_CONFIG = _load_config()


def _get_rules_root() -> Path:
    """
    Корневая папка с версиями правил.
    """
    root = _get_project_root()
    rel = _CONFIG["results"]["rules_path"]

    p = Path(rel)
    if not p.is_absolute():
        p = root / p

    p.mkdir(parents=True, exist_ok=True)
    return p


_RULES_ROOT = _get_rules_root()


# ================================================================
# Pydantic MODEL
# ================================================================

class RuleVersionDocument(BaseModel):
    """
    Структура документа версии правил (строго JSON-friendly).
    """

    setup_id: str
    version: str
    rules: Dict[str, Any]
    description: Optional[str] = None
    created_at: str  # ISO string, не datetime !!!
    tags: List[str] = []
    status: str  # active / deprecated

    class Config:
        extra = "forbid"


# ================================================================
# MAIN CLASS
# ================================================================

class RuleVersionRegistry:
    """
    Боевой реестр версий сетапов/правил.

    Все сохранения — через persistent_store.
    """

    def __init__(self) -> None:
        _RULES_ROOT.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------
    # INTERNAL HELPERS
    # ------------------------------------------------------------

    def _build_path(self, setup_id: str, version: str) -> Path:
        """
        Возвращает полный путь: data/rules/<setup_id>/<version>.json
        """
        return _RULES_ROOT / setup_id / f"{version}.json"

    # ------------------------------------------------------------
    # REGISTER VERSION
    # ------------------------------------------------------------

    def register_rule_version(
        self,
        setup_id: str,
        version: str,
        rules: Dict[str, Any],
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> ArtifactRef:
        """
        Регистрирует версию правил.

        Всегда перезаписывает старую версию (если структура совпадает).
        """

        created = datetime.now(timezone.utc).isoformat()

        # создаём документ
        doc = RuleVersionDocument(
            setup_id=setup_id,
            version=version,
            rules=rules,
            description=description,
            created_at=created,
            tags=tags or [],
            status="active",
        )

        doc_dict = doc.model_dump()

        # путь для файла
        rel_subdir = f"rules/{setup_id}"
        filename = f"{version}.json"

        # сохраняем через persistent_store
        ref: ArtifactRef = ps.save_json(
            doc_dict,
            kind="rule_version",
            filename=filename,
            subdir=rel_subdir,
        )

        logger.info("Registered rule version %s/%s", setup_id, version)
        return ref

    # ------------------------------------------------------------
    # LOAD VERSION
    # ------------------------------------------------------------

    def load_rule_version(self, setup_id: str, version: str) -> Dict[str, Any]:
        """
        Загружает файл версии правил.
        """
        path = self._build_path(setup_id, version)
        if not path.exists():
            raise FileNotFoundError(f"Rule version not found: {path}")

        ref = ArtifactRef(
            id=path.name,
            kind="rule_version",
            path=str(path),
            format="json",
            meta={},
        )

        doc = ps.load_json(ref)

        try:
            RuleVersionDocument(**doc)
        except ValidationError as exc:
            raise ValueError(f"Invalid rule version structure: {exc}") from exc

        return doc

    # ------------------------------------------------------------
    # DEPRECATE VERSION
    # ------------------------------------------------------------

    def deprecate_version(self, setup_id: str, version: str) -> ArtifactRef:
        """
        Помечает версию как deprecated
        """

        doc = self.load_rule_version(setup_id, version)
        doc["status"] = "deprecated"

        rel_subdir = f"rules/{setup_id}"
        filename = f"{version}.json"

        # сохраняем обратно
        return ps.save_json(
            doc,
            kind="rule_version",
            filename=filename,
            subdir=rel_subdir,
        )

