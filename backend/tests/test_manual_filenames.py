from app.models import VideoMetadata, VideoStatus
from app.service import manual_filename_stem, thumbnail_timestamp


def test_manual_filename_uses_video_name_and_datetime_without_id():
    video = VideoMetadata(
        id="b3fb19b690f946faa140bf24c25361ad",
        original_filename="Capacitacion Weblogic - Grupo 1 - BestResource.mp4",
        stored_filename="source.mp4",
        status=VideoStatus.ready,
        created_at="2026-06-23T10:00:00+00:00",
        updated_at="2026-06-23T10:00:00+00:00",
    )

    filename = manual_filename_stem(video, "2026-06-23T17:49:52+00:00")

    assert filename == "manual-capacitacion-weblogic-grupo-1-bestresource-20260623-134952"
    assert video.id not in filename


def test_thumbnail_timestamp_stays_inside_short_videos():
    assert thumbnail_timestamp(2.0) == 0.5
    assert thumbnail_timestamp(120.0) == 3.0
