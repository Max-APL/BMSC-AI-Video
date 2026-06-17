from app.timecodes import format_timecode


def test_format_timecode():
    assert format_timecode(0) == "00:00:00.000"
    assert format_timecode(65.4321) == "00:01:05.432"
    assert format_timecode(3661.5) == "01:01:01.500"
