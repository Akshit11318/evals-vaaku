import os

import pytest


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DASHBOARD_AUTH_DISABLED", "1")
    monkeypatch.setenv("DASHBOARD_TOKEN", "")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "outputs" / "bench.db"))
    monkeypatch.setenv("ALLOW_CPU_FALLBACK", "1")
    monkeypatch.setenv("PREFER_GPU", "1")
    os.environ.pop("HF_TOKEN", None)
