from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv is in requirements.
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
DEFAULT_HF_HOME = BASE_DIR / "models_cache" / "huggingface"
DEFAULT_LLM_REPO_ID = "bartowski/Llama-3.2-3B-Instruct-GGUF"
DEFAULT_LLM_FILENAME = "Llama-3.2-3B-Instruct-Q4_K_M.gguf"


WHISPER_REPO_ALIASES = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "large-v1": "Systran/faster-whisper-large-v1",
    "large-v2": "Systran/faster-whisper-large-v2",
    "large-v3": "Systran/faster-whisper-large-v3",
    "distil-large-v2": "Systran/faster-distil-whisper-large-v2",
    "distil-large-v3": "Systran/faster-distil-whisper-large-v3",
}


def main() -> None:
    if load_dotenv:
        load_dotenv(ENV_PATH)

    configure_hf_home()
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

    parser = argparse.ArgumentParser(
        description=(
            "Descarga los modelos locales usados por BMSC AI Video sin instalar "
            "binarios del sistema operativo."
        )
    )
    parser.add_argument("--skip-whisper", action="store_true", help="No descargar el modelo faster-whisper.")
    parser.add_argument("--skip-llm", action="store_true", help="No descargar el GGUF del LLM local.")
    parser.add_argument("--skip-vision", action="store_true", help="No descargar el modelo visual de capturas.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar que se descargaria sin llamar a Hugging Face.",
    )
    args = parser.parse_args()

    print(f"HF_HOME={os.environ['HF_HOME']}")
    ensure_dirs()

    if not args.skip_whisper:
        download_whisper_model(dry_run=args.dry_run)
    if not args.skip_llm:
        download_llm_model(dry_run=args.dry_run)
    if not args.skip_vision:
        vision_path = download_snapshot(
            env_value("MANUAL_VISION_MODEL", "HuggingFaceTB/SmolVLM-500M-Instruct"),
            "modelo visual",
            args.dry_run,
        )
        if vision_path:
            repair_smolvlm_processor_config(Path(vision_path))

    print("Descarga de modelos finalizada.")


def ensure_dirs() -> None:
    for path in (
        Path(os.environ["HF_HOME"]),
        BASE_DIR / "models_cache" / "llm",
    ):
        path.mkdir(parents=True, exist_ok=True)


def configure_hf_home() -> None:
    configured = os.getenv("HF_HOME")
    if configured and configured.strip():
        path = Path(configured.strip()).expanduser()
        if not path.is_absolute():
            path = BASE_DIR / path
        os.environ["HF_HOME"] = str(path.resolve())
        return
    os.environ["HF_HOME"] = str(DEFAULT_HF_HOME)


def env_value(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def download_whisper_model(*, dry_run: bool) -> None:
    model = env_value("WHISPER_MODEL", "base")
    repo_id = WHISPER_REPO_ALIASES.get(model, model if "/" in model else f"Systran/faster-whisper-{model}")
    print(f"[whisper] {repo_id}")
    if dry_run:
        return

    # Snapshot download is enough to prime the Hugging Face cache used by faster-whisper.
    download_snapshot(repo_id, "modelo faster-whisper", dry_run=False)


def download_llm_model(*, dry_run: bool) -> None:
    repo_id = env_value("LLM_MODEL_REPO_ID", DEFAULT_LLM_REPO_ID)
    configured_filename = optional_env_value("LLM_MODEL_FILENAME")
    filename = configured_filename or DEFAULT_LLM_FILENAME
    target = resolve_llm_target(filename)

    print(f"[llm] repo={repo_id} file={filename} -> {target}")
    if target.name != filename:
        print(
            f"[llm] nota: se descargara {filename} y se guardara como {target.name} "
            "porque LLM_MODEL_PATH define ese destino."
        )
    if dry_run:
        return

    from huggingface_hub import hf_hub_download

    target.parent.mkdir(parents=True, exist_ok=True)
    downloaded = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=str(target.parent),
        local_dir_use_symlinks=False,
    )
    downloaded_path = Path(downloaded)
    if downloaded_path.resolve() != target.resolve() and downloaded_path.exists():
        shutil.copy2(downloaded_path, target)
    print(f"[llm] listo: {target}")


def resolve_llm_target(filename: str) -> Path:
    configured = os.getenv("LLM_MODEL_PATH")
    if configured and configured.strip():
        path = Path(configured.strip()).expanduser()
        if not path.is_absolute():
            path = BASE_DIR / path
        return path.resolve()
    return BASE_DIR / "models_cache" / "llm" / (filename or DEFAULT_LLM_FILENAME)


def optional_env_value(name: str) -> str | None:
    value = os.getenv(name)
    if value and value.strip():
        return value.strip()
    return None


def download_snapshot(repo_id: str, label: str, dry_run: bool) -> str | None:
    if not repo_id:
        print(f"[{label}] omitido: repo vacio")
        return None
    print(f"[{label}] {repo_id}")
    if dry_run:
        return None
    from huggingface_hub import snapshot_download

    path = snapshot_download(repo_id=repo_id)
    print(f"[{label}] listo: {path}")
    return path


def repair_smolvlm_processor_config(path: Path) -> None:
    if not path.exists() or not path.is_dir():
        return
    config_path = path / "preprocessor_config.json"
    defaults = {
        "do_convert_rgb": True,
        "do_image_splitting": True,
        "do_normalize": True,
        "do_pad": True,
        "do_rescale": True,
        "do_resize": True,
        "image_mean": [0.5, 0.5, 0.5],
        "image_processor_type": "Idefics3ImageProcessor",
        "image_std": [0.5, 0.5, 0.5],
        "max_image_size": {"longest_edge": 512},
        "processor_class": "Idefics3Processor",
        "resample": 1,
        "rescale_factor": 0.00392156862745098,
        "size": {"longest_edge": 2048},
    }
    payload = {}
    if config_path.exists():
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
    changed = False
    for key, value in defaults.items():
        if key not in payload:
            payload[key] = value
            changed = True
    if changed or not config_path.exists():
        config_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[modelo visual] preprocessor_config.json reparado: {config_path}")


if __name__ == "__main__":
    main()
