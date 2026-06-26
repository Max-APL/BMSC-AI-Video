from app.manual_review import review_manual_content
from app.manual_generation import ManualBuildResult
from app.manual_pipeline import build_fast_llm_manual, build_quality_llm_manual
from app.models import ManualQualityMode, ManualRequest
from app.config import Settings
from app.models import TranscriptSegment, VideoMetadata, VideoStatus


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)

    def chat(self, **kwargs):
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def make_metadata():
    return VideoMetadata(
        id="video-1",
        original_filename="registro-celular.mp4",
        stored_filename="registro-celular.mp4",
        status=VideoStatus.ready,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


def make_segments():
    return [
        TranscriptSegment(
            id=1,
            start_seconds=0,
            end_seconds=15,
            start_timecode="00:00:00",
            end_timecode="00:00:15",
            text="Ingrese a BMSC Movil y registre el dispositivo con el codigo enviado al correo.",
        )
    ]


def test_manual_request_defaults_to_fast_quality_mode():
    request = ManualRequest()

    assert request.quality_mode == ManualQualityMode.fast


def test_manual_request_accepts_quality_mode():
    request = ManualRequest(quality_mode="quality")

    assert request.quality_mode == ManualQualityMode.quality


def test_review_manual_content_flags_generic_short_manual():
    content = """
# Manual operativo: capacitacion

## Objeto
Documentar de forma ordenada el procedimiento explicado en el video sobre capacitacion.

## Alcance
El contenido cubre unicamente los pasos del material base.
""".strip()

    report = review_manual_content(
        content,
        section_count=0,
        word_count=24,
        screenshot_count=0,
    )

    assert not report.passed
    assert report.score < 0.78
    assert {issue.code for issue in report.issues} >= {
        "too_short",
        "missing_sections",
        "few_steps",
        "generic_language",
    }


def test_review_manual_content_passes_specific_manual():
    content = """
# Manual operativo: Registro de celular

## Objeto
Registrar un dispositivo movil desde la aplicacion utilizando el codigo enviado al correo registrado.

## Alcance
Incluye la descarga de la aplicacion, el ingreso con credenciales, el envio del codigo y la confirmacion del equipo.

## Procedimiento detallado

### Registro inicial

#### Procedimiento
1. Descargue o actualice la aplicacion BMSC Movil desde la tienda correspondiente.
2. Ingrese con el usuario y la contrasena de banca por internet.
3. Presione el boton para enviar el codigo al correo electronico registrado.
4. Introduzca el codigo recibido en el campo de validacion.
5. Confirme el registro del dispositivo cuando aparezca el mensaje de finalizacion.
""".strip()

    report = review_manual_content(
        content,
        section_count=1,
        word_count=220,
        screenshot_count=0,
    )

    assert report.passed
    assert report.score >= 0.78


def test_quality_llm_manual_writes_agentic_artifacts(monkeypatch):
    import app.manual_pipeline as pipeline

    base_content = """
# Manual operativo: Registro

## Procedimiento detallado

### Instalacion inventada

#### Procedimiento
1. Descargue el instalador externo.
""".strip()
    repaired_content = """
# Manual operativo: Registro

## Procedimiento detallado

### Registro de dispositivo

#### Procedimiento
1. Ingrese a BMSC Movil.
2. Registre el dispositivo con el codigo enviado al correo.
""".strip()
    artifacts = {}

    monkeypatch.setattr(
        pipeline,
        "build_llm_manual",
        lambda *args, **kwargs: ManualBuildResult(
            content=base_content,
            section_count=1,
            word_count=220,
        ),
    )
    monkeypatch.setattr(
        pipeline,
        "get_llm_client",
        lambda **kwargs: FakeClient(
            [
                '{"score": 0.5, "passed": false, "issues": [{"code": "unsupported_claim", "severity": "high", "message": "Instalacion no soportada"}], "recommended_actions": ["remove"]}',
                repaired_content,
            ]
        ),
    )

    result = build_quality_llm_manual(
        make_metadata(),
        make_segments(),
        settings=Settings(manual_quality_max_loops=0),
        provider="llama_cpp",
        model="test-model.gguf",
        include_timestamps=True,
        generated_at="2026-01-01T00:00:00Z",
        screenshots_by_block={},
        on_progress=None,
        write_artifact=lambda filename, payload: artifacts.setdefault(filename, payload),
    )

    assert "Descargue el instalador externo" not in result.content
    assert "Registre el dispositivo" in result.content
    assert artifacts["agent_fidelity_report.json"]["issues"][0]["code"] == "unsupported_claim"
    assert artifacts["agent_visual_report.json"]["passed"] is True
    assert artifacts["agent_editor_report.json"]["passed"] is True
    assert artifacts["agentic_review_summary.json"]["repaired"] is True
    assert "review_report_agentic.json" in artifacts


def test_fast_llm_manual_does_not_write_agentic_artifacts(monkeypatch):
    import app.manual_pipeline as pipeline

    artifacts = {}
    monkeypatch.setattr(
        pipeline,
        "build_llm_manual",
        lambda *args, **kwargs: ManualBuildResult(
            content="# Manual\n\n### Registro\n1. Ingrese a BMSC Movil.\n2. Confirme el codigo.",
            section_count=1,
            word_count=220,
        ),
    )

    build_fast_llm_manual(
        make_metadata(),
        make_segments(),
        settings=Settings(),
        provider="llama_cpp",
        model="test-model.gguf",
        include_timestamps=True,
        generated_at="2026-01-01T00:00:00Z",
        screenshots_by_block={},
        on_progress=None,
        write_artifact=lambda filename, payload: artifacts.setdefault(filename, payload),
    )

    assert "evidence.json" in artifacts
    assert not any(filename.startswith("agent_") for filename in artifacts)
