from app.server import app
from src.inference.upload import compare_uploaded_audio
from starlette.testclient import TestClient


def test_overview_and_invalid_run():
    client = TestClient(app)
    overview = client.get("/api/overview")
    assert overview.status_code == 200
    body = overview.json()
    assert body["status"] in {"Ready", "Attention", "Blocked", "Running"}
    assert any(item["dataset_id"] == "fleurs" and item["selectable"] for item in body["datasets"])
    assert any(
        item["dataset_id"] == "kathbath" and not item["selectable"] for item in body["datasets"]
    )
    rejected = client.post("/api/experiments", json={"name": ""})
    assert rejected.status_code == 400


def test_cancel_missing_run():
    client = TestClient(app)
    missing = client.post("/api/experiments/missing/cancel")
    assert missing.status_code == 404
    client = TestClient(app)
    page = client.get("/")
    assert page.status_code == 200
    assert "Vaaku" in page.text
    assert "Streamlit" not in page.text


def test_upload_is_not_implemented():
    try:
        compare_uploaded_audio("clip.wav")
    except NotImplementedError as exc:
        assert "not implemented" in str(exc)
    else:
        raise AssertionError("upload path should not run")
