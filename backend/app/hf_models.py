from __future__ import annotations

import json
from contextlib import nullcontext
from functools import lru_cache
from pathlib import Path
from typing import Optional

from .config import Settings
from .debug import log_event


class OptionalModelUnavailable(RuntimeError):
    pass


class HuggingFaceVisionAnalyzer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_id = settings.manual_vision_model
        self._processor = None
        self._model = None
        self._device = "cpu"
        self._dtype = None

    def describe_image(self, image_path: Path, prompt: Optional[str] = None) -> str:
        self._ensure_loaded()
        try:
            from PIL import Image
            import torch
        except ImportError as exc:
            raise OptionalModelUnavailable(
                "Pillow, torch y transformers son requeridos para analisis visual Hugging Face."
            ) from exc

        image = Image.open(image_path).convert("RGB")
        message_prompt = prompt or (
            "Describe en una frase breve que informacion util aporta esta captura "
            "para un manual operativo. Si no aporta informacion, responde: SIN_APORTE."
        )
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": message_prompt},
                ],
            }
        ]
        try:
            inputs = self._processor.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
            ).to(self._device)
        except Exception:
            fallback_messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image"},
                        {"type": "text", "text": message_prompt},
                    ],
                }
            ]
            template = self._processor.apply_chat_template(
                fallback_messages,
                add_generation_prompt=True,
            )
            inputs = self._processor(text=template, images=[image], return_tensors="pt").to(self._device)
        inference_context = (
            torch.backends.cudnn.flags(enabled=False)
            if self._device == "cuda"
            else nullcontext()
        )
        with torch.inference_mode(), inference_context:
            generated = self._model.generate(**inputs, do_sample=False, max_new_tokens=80)
        input_token_count = inputs["input_ids"].shape[-1]
        text = self._processor.decode(
            generated[0][input_token_count:],
            skip_special_tokens=True,
        )
        return text.strip()

    def _ensure_loaded(self) -> None:
        if self._model is not None and self._processor is not None:
            return
        try:
            import torch
            import transformers
            from transformers import AutoProcessor
            from huggingface_hub import snapshot_download
        except ImportError as exc:
            raise OptionalModelUnavailable(
                "Pillow, torch, transformers y huggingface_hub son requeridos para analisis visual Hugging Face."
            ) from exc

        model_loader = getattr(transformers, "AutoModelForImageTextToText", None)
        if model_loader is None:
            model_loader = getattr(transformers, "AutoModelForMultimodalLM", None)
        if model_loader is None:
            model_loader = getattr(transformers, "AutoModelForVision2Seq", None)
        if model_loader is None:
            raise OptionalModelUnavailable(
                "La version instalada de transformers no soporta modelos image-text. "
                "Actualiza transformers dentro del entorno que ejecuta uvicorn."
            )

        self._device = resolve_vision_device(torch, self.settings)
        self._dtype = torch.float16 if self._device == "cuda" else torch.float32

        model_source = self._resolve_model_source(snapshot_download)
        repair_smolvlm_processor_config(model_source)

        log_event(
            "Cargando modelo visual Hugging Face "
            f"device={self._device} dtype={self._dtype} model={model_source}"
        )
        self._processor = load_smolvlm_processor(AutoProcessor, transformers, model_source)
        try:
            self._model = model_loader.from_pretrained(
                model_source,
                dtype=self._dtype,
                _attn_implementation="eager",
            ).to(self._device)
        except TypeError:
            self._model = model_loader.from_pretrained(
                model_source,
                torch_dtype=self._dtype,
                _attn_implementation="eager",
            ).to(self._device)
        self._model.eval()

    def _resolve_model_source(self, snapshot_download) -> str:
        configured_path = Path(self.model_id).expanduser()
        if configured_path.exists():
            return str(configured_path.resolve())
        try:
            return snapshot_download(repo_id=self.model_id, local_files_only=True)
        except Exception:
            try:
                return snapshot_download(repo_id=self.model_id)
            except Exception as exc:
                raise OptionalModelUnavailable(
                    f"No se pudo resolver el modelo visual {self.model_id}. "
                    "Ejecuta backend/download_models.py en el entorno que corre el backend."
                ) from exc


@lru_cache(maxsize=1)
def get_vision_analyzer(settings: Settings) -> HuggingFaceVisionAnalyzer:
    return HuggingFaceVisionAnalyzer(settings)


def resolve_vision_device(torch_module, settings: Settings) -> str:
    requested = (settings.inference_device or "cpu").strip().lower()
    if requested == "cuda":
        if not torch_module.cuda.is_available():
            raise OptionalModelUnavailable(
                "INFERENCE_DEVICE=cuda pero torch no detecta CUDA disponible para el modelo visual."
            )
        return "cuda"
    return "cpu"


def load_smolvlm_processor(auto_processor, transformers, model_source: str):
    try:
        return auto_processor.from_pretrained(model_source)
    except ValueError:
        try:
            image_processor_cls = getattr(transformers, "Idefics3ImageProcessor")
            processor_cls = getattr(transformers, "Idefics3Processor")
            tokenizer_cls = getattr(transformers, "AutoTokenizer")
            image_processor = image_processor_cls.from_pretrained(model_source)
            tokenizer = tokenizer_cls.from_pretrained(model_source)
            return processor_cls(image_processor=image_processor, tokenizer=tokenizer)
        except ImportError as exc:
            raise OptionalModelUnavailable(
                "El modelo visual SmolVLM requiere torchvision. "
                "Instala las dependencias actualizadas en el entorno que ejecuta uvicorn."
            ) from exc
        except ValueError as exc:
            raise OptionalModelUnavailable(
                "El tokenizer de SmolVLM requiere sentencepiece o tiktoken. "
                "Instala las dependencias actualizadas en el entorno que ejecuta uvicorn."
            ) from exc


def repair_smolvlm_processor_config(model_path: str) -> None:
    path = Path(model_path)
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
