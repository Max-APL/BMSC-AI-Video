from __future__ import annotations

import json
from typing import List

from sqlalchemy import text
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
from .screenshots import ScreenshotError
from .service import VideoService
from .storage import VideoStorage
from .transcription import FasterWhisperTranscriber
from .database import Base, SessionLocal, engine
from .database import Base, engine, ensure_sqlite_schema_columns

from .auth import get_current_user, require_permission
from .db_models import DBRole, DBSubArea, DBUser, DBVideoMetadata
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


def _migrate_user_columns() -> None:
    columns = {
        "name": "VARCHAR",
        "updated_at": "VARCHAR",
        "is_disabled": "BOOLEAN NOT NULL DEFAULT 0",
        "disabled_at": "VARCHAR",
        "disabled_reason": "VARCHAR",
        "failed_login_attempts": "INTEGER NOT NULL DEFAULT 0",
    }
    with engine.begin() as connection:
        existing = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(users)")).fetchall()
        }
        for column_name, column_type in columns.items():
            if column_name not in existing:
                connection.execute(
                    text(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")
                )


def _user_allowed_areas(db, current_user: DBUser) -> list[str]:
    role = db.query(DBRole).filter(DBRole.id == current_user.role_id).first()
    if not role or not role.allowed_areas:
        return []
    return json.loads(role.allowed_areas)


def _ensure_video_access(video_id: str, current_user: DBUser) -> None:
    db = SessionLocal()
    try:
        video = db.query(DBVideoMetadata).filter(DBVideoMetadata.id == video_id).first()
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video no encontrado",
            )

        allowed_areas = _user_allowed_areas(db, current_user)
        if "*" in allowed_areas:
            return

        if not video.subarea_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a este video",
            )

        subarea = db.query(DBSubArea).filter(DBSubArea.id == video.subarea_id).first()
        if not subarea or subarea.area_id not in allowed_areas:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a este video",
            )
    finally:
        db.close()


def _ensure_subarea_access(subarea_id: str | None, current_user: DBUser) -> None:
    if not subarea_id:
        return

    db = SessionLocal()
    try:
        subarea = db.query(DBSubArea).filter(DBSubArea.id == subarea_id).first()
        if not subarea:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subárea no encontrada",
            )

        allowed_areas = _user_allowed_areas(db, current_user)
        if "*" in allowed_areas or subarea.area_id in allowed_areas:
            return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para asignar videos a esta área",
        )
    finally:
        db.close()


@app.on_event("startup")
def recover_interrupted_processing() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_user_columns()
    ensure_sqlite_schema_columns()
    
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
        super_admin_permissions = [
            "view_dashboard", "view_videos", "view_library",
            "view_organization", "view_users", "view_roles",
            "upload_video", "generate_manual", "manage_organization",
            "manage_users", "manage_roles", "edit_video",
            "reprocess_video", "reindex_video", "delete_video",
        ]
        # Check and create Super Admin role
        super_admin_role = db.query(DBRole).filter(DBRole.name == "Super Admin").first()
        if not super_admin_role:
            super_admin_role = DBRole(
                id=str(uuid.uuid4()),
                name="Super Admin",
                permissions=json.dumps(super_admin_permissions),
                allowed_areas=json.dumps(["*"]),
                created_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
            )
            db.add(super_admin_role)
            db.commit()
            db.refresh(super_admin_role)
        else:
            super_admin_role.permissions = json.dumps(super_admin_permissions)
            super_admin_role.allowed_areas = json.dumps(["*"])
            db.commit()
            db.refresh(super_admin_role)

        admin_exists = db.query(DBUser).filter(DBUser.email == "admin@bmsc.com.bo").first()
        if not admin_exists:
            hashed_pw = get_password_hash("admin123")
            db.add(DBUser(
                id=str(uuid.uuid4()),
                name="Administrador del sistema",
                email="admin@bmsc.com.bo",
                hashed_password=hashed_pw,
                role_id=super_admin_role.id,
                created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                is_disabled=False,
                failed_login_attempts=0,
                locked_until=None,
                force_password_change=False,
                password_changed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                token_version=0,
            ))
            db.commit()
        else:
            # Migration for existing admin
            if not hasattr(admin_exists, 'role_id') or not admin_exists.role_id:
                 admin_exists.role_id = super_admin_role.id
            if not admin_exists.name:
                 admin_exists.name = "Administrador del sistema"
            admin_exists.is_disabled = False
            admin_exists.failed_login_attempts = 0
            admin_exists.disabled_at = None
            admin_exists.disabled_reason = None
            admin_exists.locked_until = None
            admin_exists.force_password_change = False
            if admin_exists.password_changed_at is None:
                 admin_exists.password_changed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            if admin_exists.token_version is None:
                 admin_exists.token_version = 0
            admin_exists.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            db.commit()
    finally:
        db.close()

    log_event(
        "Backend startup "
        f"storage_dir={settings.storage_dir} "
        f"inference_device={settings.inference_device} "
        f"whisper_model={settings.whisper_model} "
        f"device={settings.whisper_device} "
        f"compute_type={settings.whisper_compute_type} "
        f"audio_chunk_seconds={settings.whisper_audio_chunk_seconds} "
        f"beam_size={settings.whisper_beam_size} "
        f"best_of={settings.whisper_best_of} "
        f"whisper_cpu_threads={settings.whisper_cpu_threads} "
        f"whisper_num_workers={settings.whisper_num_workers} "
        f"whisper_chunk_workers={settings.whisper_chunk_workers} "
        f"llm_ctx={settings.llm_num_ctx} "
        f"llm_gpu_layers={settings.llm_n_gpu_layers} "
        f"llm_threads={settings.llm_n_threads or 'auto'} "
        f"llm_batch={settings.llm_n_batch}"
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
    _ensure_video_access(video_id, current_user)
    try:
        return service.get_video(video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc


@app.put("/videos/{video_id}", response_model=VideoMetadata)
def update_video(
    video_id: str,
    request: VideoUpdate,
    current_user: DBUser = Depends(require_permission("edit_video")),
) -> VideoMetadata:
    _ensure_video_access(video_id, current_user)
    _ensure_subarea_access(request.subarea_id, current_user)
    from sqlalchemy.orm import Session
    from .database import SessionLocal
    from .db_models import DBVideoMetadata, DBSubArea
    
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
                subarea = db.query(DBSubArea).filter(DBSubArea.id == request.subarea_id).first()
                if not subarea:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subárea no encontrada")
                db_video.subarea_id = request.subarea_id
                
        db.commit()
        return service.get_video(video_id)
    finally:
        db.close()


@app.post("/videos/{video_id}/process", response_model=VideoMetadata)
def reprocess_video(
    video_id: str,
    background_tasks: BackgroundTasks,
    current_user: DBUser = Depends(require_permission("reprocess_video")),
) -> VideoMetadata:
    _ensure_video_access(video_id, current_user)
    try:
        metadata = service.get_video(video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc

    background_tasks.add_task(service.process_video, video_id)
    return metadata


@app.post("/videos/{video_id}/index", response_model=VideoMetadata)
def reindex_video(
    video_id: str,
    current_user: DBUser = Depends(require_permission("reindex_video")),
) -> VideoMetadata:
    _ensure_video_access(video_id, current_user)
    try:
        return service.reindex_video(video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.get("/videos/{video_id}/transcript", response_model=TranscriptResponse)
def get_transcript(video_id: str, current_user: DBUser = Depends(get_current_user)) -> TranscriptResponse:
    _ensure_video_access(video_id, current_user)
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


@app.get("/videos/{video_id}/thumbnail", response_class=FileResponse)
def get_video_thumbnail(video_id: str) -> FileResponse:
    try:
        thumbnail_path, media_type, filename = service.get_video_thumbnail(video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc
    except ScreenshotError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return FileResponse(
        path=thumbnail_path,
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
    _ensure_video_access(video_id, current_user)
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
    _ensure_video_access(video_id, current_user)
    try:
        return service.list_manuals(video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc


@app.get("/videos/{video_id}/manuals/{manual_id}", response_model=ManualResponse)
def get_manual(video_id: str, manual_id: str, include_content: bool = False, current_user: DBUser = Depends(get_current_user)) -> ManualResponse:
    _ensure_video_access(video_id, current_user)
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
def delete_manual(
    video_id: str,
    manual_id: str,
    current_user: DBUser = Depends(require_permission("generate_manual")),
) -> Response:
    _ensure_video_access(video_id, current_user)
    try:
        service.delete_manual(video_id, manual_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manual no encontrado") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/videos/{video_id}/query", response_model=QueryResponse)
def query_video(video_id: str, request: QueryRequest, current_user: DBUser = Depends(get_current_user)) -> QueryResponse:
    _ensure_video_access(video_id, current_user)
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
    _ensure_video_access(video_id, current_user)
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
def delete_video(
    video_id: str,
    current_user: DBUser = Depends(require_permission("delete_video")),
) -> Response:
    _ensure_video_access(video_id, current_user)
    try:
        service.delete_video(video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
