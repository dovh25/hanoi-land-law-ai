"""Model policy helpers, importable without torch or Hugging Face installed."""
from backend.core.config import get_settings


def select_device(requested="cpu", *, cuda_available=None):
    if requested not in {"cpu", "cuda", "auto"}:
        raise ValueError("Device must be cpu, cuda, or auto")
    if requested == "cpu":
        return "cpu"
    if cuda_available is None:
        try:
            import torch
            cuda_available = torch.cuda.is_available()
        except ImportError:
            cuda_available = False
    if requested == "cuda" and not cuda_available:
        raise RuntimeError("CUDA was explicitly requested but is unavailable")
    return "cuda" if cuda_available else "cpu"


def model_location(name):
    """Resolve cached weights only unless download consent is explicit."""
    from pathlib import Path
    if Path(name).is_dir():
        return name
    settings = get_settings()
    from huggingface_hub import snapshot_download
    return snapshot_download(name, local_files_only=not settings.ALLOW_MODEL_DOWNLOADS)
