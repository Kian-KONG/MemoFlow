"""转写（Transcript）上下文 —— 领域服务。

`TranscriptAssemblyService` 是本上下文的核心业务规则：
将 ASR（语音识别）输出的文本片段与说话人识别（diarization）输出的说话人片段
按时间重叠度对齐，组装成带说话人标注的 `Transcript` 聚合。

这是纯粹的领域逻辑（无 I/O），输入输出均为领域内定义的简单数据结构，
应用层负责把 AI 适配器（SenseVoice / pyannote）的原始输出转换为这里的
`RawUtteranceSegment` / `RawSpeakerSegment` 后再调用。
"""
from __future__ import annotations

from dataclasses import dataclass

from memoflow.domain.shared.value_objects import TimeRange
from memoflow.domain.transcript.entities import Transcript, Utterance
from memoflow.domain.transcript.value_objects import UtteranceId


@dataclass(frozen=True)
class RawUtteranceSegment:
    """ASR 输出的一段原始文本片段。"""

    start: float
    end: float
    text: str
    confidence: float | None = None


@dataclass(frozen=True)
class RawSpeakerSegment:
    """说话人识别输出的一段原始说话人片段。"""

    start: float
    end: float
    speaker_label: str


class TranscriptAssemblyService:
    """把 ASR 片段与说话人片段对齐、组装为 Transcript 聚合。"""

    @staticmethod
    def assemble(
        meeting_id: str,
        language: str,
        asr_segments: list[RawUtteranceSegment],
        speaker_segments: list[RawSpeakerSegment],
    ) -> Transcript:
        utterances: list[Utterance] = []
        for seg in asr_segments:
            time_range = TimeRange(seg.start, seg.end)
            utterances.append(
                Utterance(
                    utterance_id=UtteranceId.new(),
                    time_range=time_range,
                    text=seg.text,
                    confidence=seg.confidence,
                )
            )

        transcript = Transcript.create(meeting_id=meeting_id, language=language, utterances=utterances)
        TranscriptAssemblyService.assign_speakers(transcript, speaker_segments)
        return transcript

    @staticmethod
    def assign_speakers(transcript: Transcript, speaker_segments: list[RawSpeakerSegment]) -> None:
        """为已存在的 Transcript 就地回填说话人标注。

        用于分阶段处理场景：ASR 完成后先保存无说话人标注的转写（让用户尽快看到文本），
        说话人识别完成后再调用本方法为已有话语补充说话人信息。
        """
        if not speaker_segments:
            return
        for utterance in transcript.utterances:
            best_label = TranscriptAssemblyService._best_matching_speaker(
                utterance.time_range, speaker_segments
            )
            if best_label is None:
                continue
            speaker = transcript.register_speaker(best_label)
            utterance.assign_speaker(speaker.id)

    @staticmethod
    def _best_matching_speaker(
        time_range: TimeRange, speaker_segments: list[RawSpeakerSegment]
    ) -> str | None:
        best_label: str | None = None
        best_overlap = 0.0
        for seg in speaker_segments:
            seg_range = TimeRange(seg.start, seg.end)
            overlap = time_range.overlap_seconds(seg_range)
            if overlap > best_overlap:
                best_overlap = overlap
                best_label = seg.speaker_label
        return best_label
