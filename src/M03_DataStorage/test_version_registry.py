"""
test_version_registry.py — боевой тест для RuleVersionRegistry
"""

# === ДОБАВЛЯЕМ ПУТЬ К ПРОЕКТУ (ВАЖНО!) ===
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

# Теперь можно грузить как пакет
from src.M03_DataStorage.version_registry import RuleVersionRegistry
from src.M03_DataStorage.persistent_store import load_json
from src.M03_DataStorage.metadata_schemas import ArtifactRef


def test_rule_version_registry():
    print("=== TEST: RuleVersionRegistry ===")

    registry = RuleVersionRegistry()

    setup_id = "TEST_SETUP_RULES"
    version = "v1"

    rules = {
        "entry": {"type": "breakout", "threshold": 1.5},
        "exit": {"type": "stop", "value": 0.8},
        "risk": {"rr": 2.0},
    }

    print(f"- Registering version: {setup_id}/{version}")
    ref = registry.register_rule_version(
        setup_id=setup_id,
        version=version,
        rules=rules,
        description="Test rule version",
        tags=["unit_test", "example"]
    )
    print(f"✓ Saved: {ref.path}")

    # Load back
    loaded = registry.load_rule_version(setup_id, version)
    print("✓ Loaded OK")

    assert loaded["setup_id"] == setup_id
    assert loaded["version"] == version
    assert loaded["status"] == "active"

    print("✓ Structure validated")

    # Deprecate
    print("- Deprecating version...")
    ref2 = registry.deprecate_version(setup_id, version)

    loaded2 = registry.load_rule_version(setup_id, version)
    assert loaded2["status"] == "deprecated"

    print("✓ Deprecation OK")
    print("=== TEST FINISHED ===")


if __name__ == "__main__":
    test_rule_version_registry()
