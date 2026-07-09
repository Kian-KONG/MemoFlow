"""Parse MOSS compact transcript: [start][Sxx]text[end]."""
from __future__ import annotations

import re
from dataclasses import dataclass

_SEGMENT_RE = re.compile(
    r"\[(?P<start>\d+(?:\.\d+)?)\]\[(?P<speaker>S\d+)\](?P<text>.*?)\[(?P<end>\d+(?:\.\d+)?)\]",
    re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class MossTranscriptSegment:
    start: float
    end: float
    speaker: str
    text: str


def parse_moss_transcript(text: str) -> list[MossTranscriptSegment]:
    try:
        from moss_transcribe_diarize.transcript_parser import parse_transcript

        return [
            MossTranscriptSegment(
                start=segment.start,
                end=segment.end,
                speaker=segment.speaker,
                text=segment.text,
            )
            for segment in parse_transcript(text)
        ]
    except ImportError:
        pass

    segments: list[MossTranscriptSegment] = []
    for match in _SEGMENT_RE.finditer(text):
        body = match.group("text").strip()
        if not body:
            continue
        segments.append(
            MossTranscriptSegment(
                start=float(match.group("start")),
                end=float(match.group("end")),
                speaker=match.group("speaker"),
                text=body,
            )
        )
    return segments


def moss_speaker_label(speaker: str) -> str:
    if speaker.startswith("SPEAKER_"):
        return speaker
    if speaker.startswith("S") and speaker[1:].isdigit():
        return f"SPEAKER_{int(speaker[1:]):02d}"
    return speaker
