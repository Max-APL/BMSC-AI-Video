from app.service import SUPPORTED_MEDIA_EXTENSIONS


def test_supported_video_formats_include_mp4_mkv_and_mvk_alias():
    assert ".mp4" in SUPPORTED_MEDIA_EXTENSIONS
    assert ".mkv" in SUPPORTED_MEDIA_EXTENSIONS
    assert ".mvk" in SUPPORTED_MEDIA_EXTENSIONS
