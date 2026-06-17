from __future__ import annotations

from typing import List

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .debug import log_event
from .models import (
    AnswerRequest,
    AnswerResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    SystemDependenciesResponse,
    TranscriptResponse,
    VideoMetadata,
)
from .search import TfidfSearchEngine
from .service import VideoService
from .storage import VideoStorage
from .transcription import FasterWhisperTranscriber


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backend local para transcribir videos y consultarlos con TF-IDF.",
)

allow_origins = list(settings.cors_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage = VideoStorage(settings)
transcriber = FasterWhisperTranscriber(settings)
search_engine = TfidfSearchEngine()
service = VideoService(settings, storage, transcriber, search_engine)


@app.on_event("startup")
def recover_interrupted_processing() -> None:
    log_event(
        "Backend startup "
        f"storage_dir={settings.storage_dir} "
        f"whisper_model={settings.whisper_model} "
        f"device={settings.whisper_device} "
        f"compute_type={settings.whisper_compute_type}"
    )
    recovered = service.recover_interrupted_processing()
    log_event(f"Interrupted processing recovery complete recovered={recovered}")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/system/dependencies", response_model=SystemDependenciesResponse)
def system_dependencies() -> SystemDependenciesResponse:
    return service.get_system_dependencies()


@app.post("/videos", response_model=VideoMetadata, status_code=status.HTTP_202_ACCEPTED)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> VideoMetadata:
    try:
        metadata = await service.create_video(file)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    background_tasks.add_task(service.process_video, metadata.id)
    return metadata


@app.get("/videos", response_model=List[VideoMetadata])
def list_videos() -> List[VideoMetadata]:
    return service.list_videos()


@app.get("/videos/{video_id}", response_model=VideoMetadata)
def get_video(video_id: str) -> VideoMetadata:
    try:
        return service.get_video(video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc


@app.post("/videos/{video_id}/process", response_model=VideoMetadata)
def reprocess_video(video_id: str, background_tasks: BackgroundTasks) -> VideoMetadata:
    try:
        metadata = service.get_video(video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc

    background_tasks.add_task(service.process_video, video_id)
    return metadata


@app.post("/videos/{video_id}/index", response_model=VideoMetadata)
def reindex_video(video_id: str) -> VideoMetadata:
    try:
        return service.reindex_video(video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.get("/videos/{video_id}/transcript", response_model=TranscriptResponse)
def get_transcript(video_id: str) -> TranscriptResponse:
    try:
        return service.get_transcript(video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.post("/videos/{video_id}/query", response_model=QueryResponse)
def query_video(video_id: str, request: QueryRequest) -> QueryResponse:
    try:
        return service.query_video(
            video_id=video_id,
            query=request.query,
            top_k=request.top_k,
            min_score=request.min_score,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.post("/videos/{video_id}/ask", response_model=AnswerResponse)
def ask_video(video_id: str, request: AnswerRequest) -> AnswerResponse:
    try:
        return service.answer_video(
            video_id=video_id,
            question=request.question,
            top_k=request.top_k,
            min_score=request.min_score,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.delete(
    "/videos/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_video(video_id: str) -> Response:
    try:
        service.delete_video(video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
