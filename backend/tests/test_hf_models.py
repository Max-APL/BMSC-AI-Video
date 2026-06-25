import json
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.hf_models import OptionalModelUnavailable, repair_smolvlm_processor_config, resolve_vision_device


def test_repair_smolvlm_processor_config_adds_missing_image_processor(tmp_path):
    config_path = tmp_path / "preprocessor_config.json"
    config_path.write_text(json.dumps({"do_resize": True}), encoding="utf-8")

    repair_smolvlm_processor_config(str(tmp_path))

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["image_processor_type"] == "Idefics3ImageProcessor"
    assert payload["processor_class"] == "Idefics3Processor"
    assert payload["do_resize"] is True


def test_resolve_vision_device_uses_cuda_when_requested_and_available():
    torch_stub = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True))
    settings = SimpleNamespace(inference_device="cuda")

    assert resolve_vision_device(torch_stub, settings) == "cuda"


def test_resolve_vision_device_uses_cpu_by_default():
    torch_stub = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True))
    settings = SimpleNamespace(inference_device="cpu")

    assert resolve_vision_device(torch_stub, settings) == "cpu"


def test_resolve_vision_device_fails_when_cuda_requested_but_unavailable():
    torch_stub = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    settings = SimpleNamespace(inference_device="cuda")

    with pytest.raises(OptionalModelUnavailable):
        resolve_vision_device(torch_stub, settings)


def test_cuda_generation_disables_cudnn(tmp_path):
    from PIL import Image

    from app.hf_models import HuggingFaceVisionAnalyzer

    image_path = tmp_path / "frame.jpg"
    Image.new("RGB", (16, 16), "white").save(image_path)

    class FakeInputs(dict):
        def to(self, _device):
            return self

    class FakeProcessor:
        def apply_chat_template(self, *_args, **_kwargs):
            return FakeInputs({"input_ids": SimpleNamespace(shape=[1, 2])})

        def decode(self, *_args, **_kwargs):
            return "Pantalla de prueba."

    class FakeModel:
        def generate(self, **_kwargs):
            return [[0, 1, 2]]

    class FakeCudnn:
        def flags(self, *, enabled):
            assert enabled is False
            return nullcontext()

    fake_torch = SimpleNamespace(
        inference_mode=lambda: nullcontext(),
        backends=SimpleNamespace(cudnn=FakeCudnn()),
    )

    analyzer = HuggingFaceVisionAnalyzer(SimpleNamespace(manual_vision_model="unused"))
    analyzer._processor = FakeProcessor()
    analyzer._model = FakeModel()
    analyzer._device = "cuda"

    with patch("app.hf_models.HuggingFaceVisionAnalyzer._ensure_loaded"), patch.dict(
        "sys.modules", {"torch": fake_torch}
    ):
        assert analyzer.describe_image(image_path) == "Pantalla de prueba."
