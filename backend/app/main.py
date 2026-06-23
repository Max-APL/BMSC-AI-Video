from __future__ import annotations

from typing import List

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Response, UploadFile, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import settings
from .debug import log_event
from .manual_exports import ManualExportError
from .models import (
    AnswerRequest,
    AnswerResponse,
    HealthResponse,
    ManualMetadata,
    ManualRequest,
    ManualResponse,
    QueryRequest,
    QueryResponse,
    SystemDependenciesResponse,
    TranscriptResponse,
    VideoMetadata,
    VideoUpdate,
)
from .search import TfidfSearchEngine
from .service import VideoService
from .storage import VideoStorage
from .transcription import FasterWhisperTranscriber
from .database import Base, engine

from .auth import get_current_user, require_permission
from .db_models import DBUser
from .routers import auth, areas, users, roles

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backend local para transcribir videos y consultarlos con TF-IDF.",
)

allow_origins = list(settings.cors_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(areas.router)
app.include_router(users.router)
app.include_router(roles.router)

storage = VideoStorage(settings)
transcriber = FasterWhisperTranscriber(settings)
search_engine = TfidfSearchEngine()
service = VideoService(settings, storage, transcriber, search_engine)


@app.on_event("startup")
def recover_interrupted_processing() -> None:
    Base.metadata.create_all(bind=engine)
    
    # Create default roles and admin user if not exists
    from sqlalchemy.orm import Session
    from .database import SessionLocal
    from .db_models import DBUser, DBRole
    from .auth import get_password_hash
    import uuid
    import datetime
    import json
    
    db = SessionLocal()
    try:
        # Check and create Super Admin role
        super_admin_role = db.query(DBRole).filter(DBRole.name == "Super Admin").first()
        if not super_admin_role:
            super_admin_role = DBRole(
                id=str(uuid.uuid4()),
                name="Super Admin",
                permissions=json.dumps([
                    "view_dashboard", "view_videos", "view_library", 
                    "view_organization", "view_users", "view_roles",
                    "upload_video", "generate_manual", "manage_organization",
                    "manage_users", "manage_roles"
                ]),
                allowed_areas=json.dumps(["*"]),
                created_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
            )
            db.add(super_admin_role)
            db.commit()
            db.refresh(super_admin_role)

        admin_exists = db.query(DBUser).filter(DBUser.email == "admin@bmsc.com.bo").first()
        if not admin_exists:
            hashed_pw = get_password_hash("admin123")
            db.add(DBUser(
                id=str(uuid.uuid4()),
                email="admin@bmsc.com.bo",
                hashed_password=hashed_pw,
                role_id=super_admin_role.id,
                created_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
            ))
            db.commit()
        else:
            # Migration for existing admin
            if not hasattr(admin_exists, 'role_id') or not admin_exists.role_id:
                 admin_exists.role_id = super_admin_role.id
                 db.commit()
    finally:
        db.close()

    log_event(
        "Backend startup "
        f"storage_dir={settings.storage_dir} "
        f"whisper_model={settings.whisper_model} "
        f"device={settings.whisper_device} "
        f"compute_type={settings.whisper_compute_type} "
        f"audio_chunk_seconds={settings.whisper_audio_chunk_seconds} "
        f"beam_size={settings.whisper_beam_size}"
    )
    recovered = service.recover_interrupted_processing()
    log_event(f"Interrupted processing recovery complete recovered={recovered}")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/system/dependencies", response_model=SystemDependenciesResponse)
def system_dependencies(current_user: DBUser = Depends(get_current_user)) -> SystemDependenciesResponse:
    return service.get_system_dependencies()


@app.post("/videos", response_model=VideoMetadata, status_code=status.HTTP_202_ACCEPTED)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: DBUser = Depends(require_permission("upload_video"))
) -> VideoMetadata:
    try:
        metadata = await service.create_video(file)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    background_tasks.add_task(service.process_video, metadata.id)
    return metadata


@app.get("/videos", response_model=List[VideoMetadata])
def list_videos(current_user: DBUser = Depends(get_current_user)) -> List[VideoMetadata]:
    from .database import SessionLocal
    from .db_models import DBRole, DBSubArea
    import json
    
    videos = service.list_videos()
    
    db = SessionLocal()
    try:
        role = db.query(DBRole).filter(DBRole.id == current_user.role_id).first()
        allowed_areas = json.loads(role.allowed_areas) if role and role.allowed_areas else []
        if "*" in allowed_areas:
            return videos
            
        subareas = db.query(DBSubArea).all()
        subarea_to_area = {sa.id: sa.area_id for sa in subareas}
        
        filtered = []
        for v in videos:
            if not v.subarea_id:
                continue
            area_id = subarea_to_area.get(v.subarea_id)
            if area_id in allowed_areas:
                filtered.append(v)
        return filtered
    finally:
        db.close()


@app.get("/videos/{video_id}", response_model=VideoMetadata)
def get_video(video_id: str, current_user: DBUser = Depends(get_current_user)) -> VideoMetadata:
    try:
        return service.get_video(video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc


@app.put("/videos/{video_id}", response_model=VideoMetadata)
def update_video(video_id: str, request: VideoUpdate, current_user: DBUser = Depends(get_current_user)) -> VideoMetadata:
    from sqlalchemy.orm import Session
    from .database import SessionLocal
    from .db_models import DBVideoMetadata
    
    db = SessionLocal()
    try:
        db_video = db.query(DBVideoMetadata).filter(DBVideoMetadata.id == video_id).first()
        if not db_video:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado")
            
        if request.original_filename is not None:
            db_video.original_filename = request.original_filename
        if request.subarea_id is not None:
            # We allow empty string or null to unassign subarea
            if request.subarea_id == "":
                db_video.subarea_id = None
            else:
                db_video.subarea_id = request.subarea_id
                
        db.commit()
        return service.get_video(video_id)
    finally:
        db.close()


@app.post("/videos/{video_id}/process", response_model=VideoMetadata)
def reprocess_video(video_id: str, background_tasks: BackgroundTasks, current_user: DBUser = Depends(get_current_user)) -> VideoMetadata:
    try:
        metadata = service.get_video(video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc

    background_tasks.add_task(service.process_video, video_id)
    return metadata


@app.post("/videos/{video_id}/index", response_model=VideoMetadata)
def reindex_video(video_id: str, current_user: DBUser = Depends(get_current_user)) -> VideoMetadata:
    try:
        return service.reindex_video(video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.get("/videos/{video_id}/transcript", response_model=TranscriptResponse)
def get_transcript(video_id: str, current_user: DBUser = Depends(get_current_user)) -> TranscriptResponse:
    try:
        return service.get_transcript(video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.get("/videos/{video_id}/media", response_class=FileResponse)
def get_video_media(video_id: str) -> FileResponse:
    try:
        source_path, media_type, filename = service.get_video_media(video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc

    return FileResponse(
        path=source_path,
        media_type=media_type,
        filename=filename,
        content_disposition_type="inline",
    )


@app.post("/videos/{video_id}/manuals", response_model=ManualMetadata, status_code=status.HTTP_202_ACCEPTED)
def create_manual(
    video_id: str,
    request: ManualRequest,
    background_tasks: BackgroundTasks,
    current_user: DBUser = Depends(require_permission("generate_manual"))
) -> ManualMetadata:
    try:
        metadata = service.create_manual(video_id, request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    background_tasks.add_task(service.process_manual, video_id, metadata.id)
    return metadata


@app.get("/videos/{video_id}/manuals", response_model=List[ManualMetadata])
def list_manuals(video_id: str, current_user: DBUser = Depends(get_current_user)) -> List[ManualMetadata]:
    try:
        return service.list_manuals(video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc


@app.get("/videos/{video_id}/manuals/{manual_id}", response_model=ManualResponse)
def get_manual(video_id: str, manual_id: str, include_content: bool = False, current_user: DBUser = Depends(get_current_user)) -> ManualResponse:
    try:
        return service.get_manual(video_id, manual_id, include_content=include_content)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manual no encontrado") from exc


@app.get("/videos/{video_id}/manuals/{manual_id}/download", response_class=FileResponse)
def download_manual(video_id: str, manual_id: str, format: str = "markdown") -> FileResponse:
    try:
        path, filename, media_type = service.get_manual_file(video_id, manual_id, format)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manual no encontrado") from exc
    except ManualExportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return FileResponse(
        path=path,
        media_type=media_type,
        filename=filename,
        content_disposition_type="attachment",
    )


@app.get("/videos/{video_id}/manuals/{manual_id}/assets/{asset_path:path}", response_class=FileResponse)
def get_manual_asset(video_id: str, manual_id: str, asset_path: str) -> FileResponse:
    try:
        path, media_type, filename = service.get_manual_asset(video_id, manual_id, asset_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset no encontrado") from exc

    return FileResponse(
        path=path,
        media_type=media_type,
        filename=filename,
        content_disposition_type="inline",
    )


@app.delete(
    "/videos/{video_id}/manuals/{manual_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_manual(video_id: str, manual_id: str, current_user: DBUser = Depends(get_current_user)) -> Response:
    try:
        service.delete_manual(video_id, manual_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manual no encontrado") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/videos/{video_id}/query", response_model=QueryResponse)
def query_video(video_id: str, request: QueryRequest, current_user: DBUser = Depends(get_current_user)) -> QueryResponse:
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
def ask_video(video_id: str, request: AnswerRequest, current_user: DBUser = Depends(get_current_user)) -> AnswerResponse:
    try:
        return service.answer_video(
            video_id=video_id,
            question=request.question,
            top_k=request.top_k,
            min_score=request.min_score,
            mode=request.mode,
            provider=request.provider,
            model=request.model,
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
def delete_video(video_id: str, current_user: DBUser = Depends(get_current_user)) -> Response:
    try:
        service.delete_video(video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
