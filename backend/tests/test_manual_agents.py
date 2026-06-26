from app.manual_agents import (
    run_agentic_manual_review,
    run_editor_agent,
    run_fidelity_agent,
    run_visual_agent,
)
from app.manual_review import review_manual_content
from app.models import TranscriptSegment, VideoMetadata, VideoStatus


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
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
            end_seconds=10,
            start_timecode="00:00:00",
            end_timecode="00:00:10",
            text="Ingrese a BMSC Movil y seleccione registrar dispositivo.",
        ),
        TranscriptSegment(
            id=2,
            start_seconds=10,
            end_seconds=20,
            start_timecode="00:00:10",
            end_timecode="00:00:20",
            text="Introduzca el codigo enviado al correo registrado.",
        ),
    ]


def test_fidelity_agent_parses_structured_unsupported_claim_report():
    client = FakeClient([
        """
        {
          "score": 0.62,
          "passed": false,
          "issues": [
            {
              "code": "unsupported_claim",
              "severity": "high",
              "message": "El manual inventa instalacion.",
              "section": "Instalacion",
              "evidence": null,
              "recommendation": "Eliminar la seccion."
            }
          ],
          "recommended_actions": ["remove_unsupported_section"]
        }
        """
    ])

    report = run_fidelity_agent(
        "### Instalacion\n1. Descargue el instalador.",
        metadata=make_metadata(),
        segments=make_segments(),
        client=client,
        max_tokens=500,
    )

    assert not report.passed
    assert report.score == 0.62
    assert report.issues[0].code == "unsupported_claim"
    assert report.issues[0].severity == "high"


def test_visual_agent_adds_deterministic_caption_issue():
    client = FakeClient([
        '{"score": 1.0, "passed": true, "issues": [], "recommended_actions": []}'
    ])

    report = run_visual_agent(
        "![Figura mala](screenshots/bad.jpg)",
        screenshots_by_block={
            1: [
                (
                    "screenshots/bad.jpg",
                    "Figura - No se puede utilizar esta captura para un manual operativo.",
                )
            ]
        },
        segments=make_segments(),
        client=client,
        max_tokens=500,
    )

    assert not report.passed
    assert any(issue.code == "bad_visual_caption" for issue in report.issues)


def test_editor_agent_keeps_previous_content_when_llm_fails():
    content = "### Registro\n1. Ingrese a BMSC Movil."
    review = review_manual_content(content, section_count=1, word_count=40, screenshot_count=0)
    client = FakeClient([RuntimeError("llm unavailable")])

    repaired, report = run_editor_agent(
        content,
        metadata=make_metadata(),
        segments=make_segments(),
        heuristic_review=review,
        agent_reports=[],
        client=client,
        max_tokens=500,
    )

    assert repaired == content
    assert not report.passed
    assert report.issues[0].code == "editor_failed"


def test_agentic_review_repairs_when_agents_report_actionable_issues():
    content = """
# Manual

## Procedimiento detallado

### Instalacion inventada
1. Descargue el instalador externo.
""".strip()
    heuristic = review_manual_content(content, section_count=1, word_count=80, screenshot_count=0)
    client = FakeClient([
        '{"score": 0.5, "passed": false, "issues": [{"code": "unsupported_claim", "severity": "high", "message": "Instalacion no soportada"}], "recommended_actions": ["remove"]}',
        '{"score": 1.0, "passed": true, "issues": [], "recommended_actions": []}',
        "### Registro de dispositivo\n\n#### Procedimiento\n1. Ingrese a BMSC Movil.\n2. Introduzca el codigo enviado al correo registrado.",
    ])

    result = run_agentic_manual_review(
        content,
        metadata=make_metadata(),
        segments=make_segments(),
        screenshots_by_block={},
        heuristic_review=heuristic,
        client=client,
        max_tokens=500,
    )

    assert result.repaired
    assert "Descargue el instalador externo" not in result.content
    assert result.fidelity_report.issues[0].code == "unsupported_claim"
    assert result.editor_report.passed
