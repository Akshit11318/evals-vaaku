"""GPU status. Importing this module does not import torch until a call."""

from __future__ import annotations


def gpu_status() -> dict:
    try:
        import torch
    except Exception as exc:  # pragma: no cover - torch is installed in the project venv
        return {
            "available": False,
            "name": None,
            "free_mb": 0.0,
            "total_mb": 0.0,
            "device": "cpu",
            "error": f"PyTorch is not importable ({exc}).",
        }
    if not torch.cuda.is_available():
        return {
            "available": False,
            "name": None,
            "free_mb": 0.0,
            "total_mb": 0.0,
            "device": "cpu",
            "error": "CUDA is not available to PyTorch.",
        }
    free, total = torch.cuda.mem_get_info()
    props = torch.cuda.get_device_properties(0)
    return {
        "available": True,
        "name": props.name,
        "free_mb": free / (1024 * 1024),
        "total_mb": total / (1024 * 1024),
        "device": "cuda",
        "error": None,
    }
