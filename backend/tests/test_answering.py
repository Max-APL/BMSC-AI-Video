from app.answering import build_llm_answer
from app.config import Settings
from app.models import AnswerMode, AnswerRequest, SearchMatch


class FakeLlmClient:
    def __init__(self):
        self.system_prompt = ""
        self.user_prompt = ""

    def chat(self, *, system_prompt: str, user_prompt: str, on_delta=None) -> str:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return "Debe descargar la aplicacion desde la tienda de aplicaciones, segun 00:00:29.870."


def make_match() -> SearchMatch:
    return SearchMatch(
        id=1,
        segment_ids=[5],
        start_seconds=29.87,
        end_seconds=38.35,
        start_timecode="00:00:29.870",
        end_timecode="00:00:38.350",
        text="Primero, descarga o actualiza gratuitamente la aplicacion movil desde la tienda de aplicaciones.",
        score=0.82,
    )


def test_answer_request_defaults_to_extractive_mode():
    request = AnswerRequest(question="Donde descargo la app?")

    assert request.mode == AnswerMode.extractive


def test_build_llm_answer_uses_retrieved_sources():
    client = FakeLlmClient()

    response = build_llm_answer(
        video_id="video-1",
        question="Donde descargo la app?",
        matches=[make_match()],
        settings=Settings(),
        provider="llama_cpp",
        model="local-model",
        client=client,
    )

    assert response.mode == AnswerMode.llm
    assert response.provider == "llama_cpp"
    assert response.model == "local-model"
    assert response.confidence == 0.82
    assert response.sources[0].id == 1
    assert "tienda de aplicaciones" in client.user_prompt
    assert "Donde descargo la app?" in client.user_prompt


def test_build_llm_answer_without_sources_falls_back_to_extractive():
    response = build_llm_answer(
        video_id="video-1",
        question="Pregunta no cubierta",
        matches=[],
        settings=Settings(),
        provider="llama_cpp",
        model="llama3.1:8b",
        client=FakeLlmClient(),
    )

    assert response.mode == AnswerMode.extractive
    assert response.confidence == 0.0
    assert response.sources == []
    assert response.fallback_reason
