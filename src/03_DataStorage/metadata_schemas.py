from typing import Dict
from pydantic import BaseModel


class ArtifactRef(BaseModel):
    id: str
    kind: str
    path: str
    format: str
    meta: Dict[str, str] = {}
