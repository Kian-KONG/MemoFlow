from memoflow.infrastructure.ai.moss_transcript import moss_speaker_label, parse_moss_transcript


def test_parse_moss_transcript_compact_format():
    text = "[0.06][S01] Hello world.[3.12][12.26][S02]Second speaker here.[15.00]"
    segments = parse_moss_transcript(text)
    assert len(segments) == 2
    assert segments[0].speaker == "S01"
    assert segments[0].text == "Hello world."
    assert segments[1].speaker == "S02"


def test_moss_speaker_label_maps_to_speaker_xx():
    assert moss_speaker_label("S01") == "SPEAKER_01"
    assert moss_speaker_label("SPEAKER_02") == "SPEAKER_02"
