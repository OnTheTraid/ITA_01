from persistent_store import save_json, load_json

data = {"run_id": "test_001", "result": 42, "status": "ok"}

ref = save_json(data, kind="test_json", filename="demo_result.json")
print("ArtifactRef:", ref)

loaded = load_json(ref)
print("Loaded data:", loaded)
