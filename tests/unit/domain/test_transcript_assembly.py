"""TranscriptAssemblyService 的单元测试：验证 ASR 片段与说话人片段按重叠度对齐。"""
from __future__ import annotations

from memoflow.domain.transcript.services import (
    RawSpeakerSegment,
    RawUtteranceSegment,
    TranscriptAssemblyService,
)


def test_assemble_assigns_best_overlapping_speaker():
    asr_segments = [
        RawUtteranceSegment(start=0.0, end=2.0, text="大家好"),
        RawUtteranceSegment(start=2.5, end=5.0, text="我们开始今天的会议"),
    ]
    speaker_segments = [
        RawSpeakerSegment(start=0.0, end=2.2, speaker_label="SPEAKER_00"),
        RawSpeakerSegment(start=2.2, end=6.0, speaker_label="SPEAKER_01"),
    ]

    transcript = TranscriptAssemblyService.assemble(
        meeting_id="m-1", language="zh", asr_segments=asr_segments, speaker_segments=speaker_segments
    )

    assert len(transcript.utterances) == 2
    assert len(transcript.speakers) == 2

    first, second = transcript.utterances
    assert transcript.speakers[first.speaker_id].label == "SPEAKER_00"
    assert transcript.speakers[second.speaker_id].label == "SPEAKER_01"


def test_assemble_without_speaker_segments_leaves_speaker_unset():
    asr_segments = [RawUtteranceSegment(start=0.0, end=1.0, text="你好")]
    transcript = TranscriptAssemblyService.assemble(
        meeting_id="m-1", language="zh", asr_segments=asr_segments, speaker_segments=[]
    )

    assert transcript.utterances[0].speaker_id is None
    assert transcript.speakers == {}
