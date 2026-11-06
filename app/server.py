"""HTTP API and the speech-bench pages."""

from __future__ import annotations

import csv
import io
import json
import time
from pathlib import Path

from config.settings import Settings, load_settings
from itsdangerous import BadSignature, URLSafeSerializer
from src.datasets.catalog import cards_as_dicts
from src.evaluation.aggregate import pack_results
from src.experiments.config import ExperimentConfig
from src.experiments.launch import launch, reconcile, stop_process
from src.experiments.validate import validate_config
from src.languages import DISPLAY_NAMES, SCRIPTS
from src.logging_config import configure_logging
from src.models.registry import MODEL_SPECS
from src.redact import scrub
from src.storage.db import Store, utcnow
from src.system.gpu import gpu_status
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

WEB = Path(__file__).resolve().parents[1] / "web"
_GPU_CACHE = {"at": 0.0, "value": None}


def _store(settings: Settings) -> Store:
    settings.ensure_dirs()
    store = Store(settings.db_path)
    store.init()
    reconcile(store)
    return store


def _serializer(settings: Settings) -> URLSafeSerializer:
    secret = settings.dashboard_token or "vaku-local-only"
    return URLSafeSerializer(secret, salt="vaku-session")


def _authorized(request: Request, settings: Settings) -> bool:
    if settings.dashboard_auth_disabled:
        return True
    if not settings.dashboard_token:
        return False
    cookie = request.cookies.get("vaku_session")
    if not cookie:
        return False
    try:
        payload = _serializer(settings).loads(cookie)
    except BadSignature:
        return False
    return payload.get("ok") is True


class Guard(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and path not in {"/api/session", "/api/login"}:
            settings = load_settings()
            if not _authorized(request, settings):
                return JSONResponse({"error": "Sign in required."}, status_code=401)
        return await call_next(request)


def _cached_gpu() -> dict:
    now = time.time()
    if _GPU_CACHE["value"] is None or now - _GPU_CACHE["at"] > 5:
        _GPU_CACHE["value"] = gpu_status()
        _GPU_CACHE["at"] = now
    return _GPU_CACHE["value"]


def _models() -> list[dict]:
    rows = []
    for spec in MODEL_SPECS.values():
        rows.append(
            {
                "model_id": spec.model_id,
                "display_name": spec.display_name,
                "hf_id": spec.hf_id,
                "languages": sorted(spec.languages),
                "license_name": spec.license_name,
                "note": spec.note,
                "min_free_mb": spec.min_free_mb,
            }
        )
    return rows


def _status(counts: dict, datasets: list[dict]) -> str:
    if counts["running"]:
        return "Running"
    if not any(item["selectable"] for item in datasets):
        return "Blocked"
    if counts["failed"] and counts["completed"] == 0:
        return "Attention"
    return "Ready"


async def session(request: Request) -> JSONResponse:
    settings = load_settings()
    required = not settings.dashboard_auth_disabled
    configured = bool(settings.dashboard_token) or settings.dashboard_auth_disabled
    return JSONResponse(
        {
            "authenticated": _authorized(request, settings),
            "auth_required": required,
            "configured": configured,
        }
    )


async def login(request: Request) -> JSONResponse:
    settings = load_settings()
    if settings.dashboard_auth_disabled:
        response = JSONResponse({"ok": True})
        return response
    if not settings.dashboard_token:
        return JSONResponse(
            {"error": "Set DASHBOARD_TOKEN before opening the bench."},
            status_code=403,
        )
    body = await request.json()
    provided = str(body.get("token") or "")
    import hmac

    if not hmac.compare_digest(provided, settings.dashboard_token):
        return JSONResponse({"error": "That token does not match."}, status_code=403)
    response = JSONResponse({"ok": True})
    response.set_cookie(
        "vaku_session",
        _serializer(settings).dumps({"ok": True}),
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


async def overview(request: Request) -> JSONResponse:
    settings = load_settings()
    store = _store(settings)
    datasets = cards_as_dicts(settings)
    counts = store.counts()
    experiments = store.list_experiments()
    return JSONResponse(
        {
            "status": _status(counts, datasets),
            "counts": counts,
            "datasets": datasets,
            "models": _models(),
            "experiments": experiments,
            "latest": experiments[0] if experiments else None,
            "gpu": _cached_gpu(),
            "languages": [
                {"code": code, "name": DISPLAY_NAMES[code], "script": SCRIPTS[code]}
                for code in ("te", "ta", "hi", "kn", "ml")
            ],
        }
    )


async def create_run(request: Request) -> JSONResponse:
    settings = load_settings()
    try:
        config = ExperimentConfig.from_dict(await request.json())
    except (TypeError, ValueError) as exc:
        return JSONResponse({"errors": [str(exc)]}, status_code=400)
    errors = validate_config(config, settings)
    if errors:
        return JSONResponse({"errors": errors}, status_code=400)
    store = _store(settings)
    experiment_id = store.create(config)
    launch(store, settings, experiment_id)
    return JSONResponse({"id": experiment_id}, status_code=201)


async def experiment_detail(request: Request) -> JSONResponse:
    settings = load_settings()
    store = _store(settings)
    experiment = store.get(request.path_params["experiment_id"])
    if experiment is None:
        return JSONResponse({"error": "Run not found."}, status_code=404)
    rows = store.list_predictions(experiment["id"])
    packed = pack_results(rows)
    return JSONResponse({"experiment": experiment, **packed})


async def cancel_run(request: Request) -> JSONResponse:
    settings = load_settings()
    store = _store(settings)
    experiment = store.get(request.path_params["experiment_id"])
    if experiment is None:
        return JSONResponse({"error": "Run not found."}, status_code=404)
    if experiment["status"] not in {"queued", "running"}:
        return JSONResponse({"error": "That run is already finished."}, status_code=409)
    stop_process(experiment.get("pid"))
    store.set_runtime(
        experiment["id"],
        status="failed",
        finished_at=utcnow(),
        error="Stopped from the bench.",
        current_model=None,
        current_sample=None,
    )
    return JSONResponse({"ok": True})


async def experiment_log(request: Request) -> JSONResponse:
    settings = load_settings()
    store = _store(settings)
    experiment = store.get(request.path_params["experiment_id"])
    if experiment is None:
        return JSONResponse({"error": "Run not found."}, status_code=404)
    log_path = experiment.get("log_path")
    if not log_path or not Path(log_path).is_file():
        return JSONResponse({"log": ""})
    text = Path(log_path).read_text(encoding="utf-8", errors="replace")
    tail = "\n".join(text.splitlines()[-80:])
    return JSONResponse({"log": scrub(tail)})


async def audio(request: Request) -> Response:
    settings = load_settings()
    store = _store(settings)
    try:
        prediction_id = int(request.path_params["prediction_id"])
    except ValueError:
        return JSONResponse({"error": "Unknown clip."}, status_code=404)
    row = store.get_prediction(prediction_id)
    if row is None or not row.get("audio_path"):
        return JSONResponse({"error": "Clip not found."}, status_code=404)
    path = Path(row["audio_path"]).resolve()
    roots = [
        settings.data_dir.resolve(),
        settings.output_dir.resolve(),
        (settings.root / "data").resolve(),
    ]
    if not any(path == root or root in path.parents for root in roots):
        return JSONResponse({"error": "Clip is outside the data directories."}, status_code=403)
    if not path.is_file():
        return JSONResponse({"error": "Audio file is not on this machine."}, status_code=404)
    return FileResponse(path, media_type="audio/wav")


def _export_rows(experiment_id: str) -> tuple[dict, list[dict]] | None:
    settings = load_settings()
    store = _store(settings)
    experiment = store.get(experiment_id)
    if experiment is None:
        return None
    return experiment, store.list_predictions(experiment_id)


async def export_json(request: Request) -> Response:
    found = _export_rows(request.path_params["experiment_id"])
    if found is None:
        return JSONResponse({"error": "Run not found."}, status_code=404)
    experiment, rows = found
    payload = {"experiment": experiment, "results": pack_results(rows)}
    body = json.dumps(payload, indent=2).encode()
    return Response(
        body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{experiment["id"]}.json"'},
    )


async def export_csv(request: Request) -> Response:
    found = _export_rows(request.path_params["experiment_id"])
    if found is None:
        return JSONResponse({"error": "Run not found."}, status_code=404)
    experiment, rows = found
    buffer = io.StringIO()
    fields = [
        "sample_id",
        "language",
        "dataset",
        "model_id",
        "audio_condition",
        "reference",
        "prediction",
        "wer",
        "cer",
        "wer_raw",
        "cer_raw",
        "ser",
        "substitutions",
        "deletions",
        "insertions",
        "inference_time_s",
        "rtf",
        "peak_gpu_mb",
        "error",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{experiment["id"]}.csv"'},
    )


async def export_summary(request: Request) -> Response:
    found = _export_rows(request.path_params["experiment_id"])
    if found is None:
        return JSONResponse({"error": "Run not found."}, status_code=404)
    experiment, rows = found
    packed = pack_results(rows)
    lines = [
        f"Run {experiment['id']} · {experiment['name']}",
        f"Status {experiment['status']}",
        "",
        "Model scores (micro WER, lower is better)",
    ]
    for item in packed["by_model"]:
        wer = "n/a" if item["wer"] is None else f"{item['wer'] * 100:.1f}%"
        cer = "n/a" if item["cer"] is None else f"{item['cer'] * 100:.1f}%"
        lines.append(f"- {item['model_id']}: WER {wer}, CER {cer}, n={item['samples']}")
    if experiment.get("error"):
        lines.extend(["", "Notice", experiment["error"]])
    return Response(
        "\n".join(lines) + "\n",
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{experiment["id"]}-summary.txt"'},
    )


configure_logging()
app = Starlette(
    routes=[
        Route("/api/session", session),
        Route("/api/login", login, methods=["POST"]),
        Route("/api/overview", overview),
        Route("/api/experiments", create_run, methods=["POST"]),
        Route("/api/experiments/{experiment_id}", experiment_detail),
        Route("/api/experiments/{experiment_id}/cancel", cancel_run, methods=["POST"]),
        Route("/api/experiments/{experiment_id}/log", experiment_log),
        Route("/api/experiments/{experiment_id}/export.json", export_json),
        Route("/api/experiments/{experiment_id}/export.csv", export_csv),
        Route("/api/experiments/{experiment_id}/summary.txt", export_summary),
        Route("/api/audio/{prediction_id}", audio),
        Mount("/", StaticFiles(directory=WEB, html=True), name="web"),
    ],
)
app.add_middleware(Guard)
