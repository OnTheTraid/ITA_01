from pathlib import Path
from typing import Optional


def resolve_artifact_path(kind: str, filename: str, subdir: Optional[str] = "") -> Path:
    """
    Простая реализация для раннего этапа.
    Можно усложнить позже по архитектуре.
    """
    base = Path("data")
    if subdir:
        base = base / subdir
    return base / filename
