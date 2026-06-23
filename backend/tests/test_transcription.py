from app.transcription import build_audio_chunk_ranges


def test_build_audio_chunk_ranges_keeps_final_partial_chunk():
    assert build_audio_chunk_ranges(725.5, 300) == [
        (0, 0.0, 300.0),
        (1, 300.0, 300.0),
        (2, 600.0, 125.5),
    ]


def test_build_audio_chunk_ranges_can_be_disabled():
    assert build_audio_chunk_ranges(725.5, 0) == []
