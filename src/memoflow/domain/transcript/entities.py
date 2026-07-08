"""转写（Transcript）聚合根：Transcript / Utterance / Speaker。"""
from __future__ import annotations

from datetime import datetime

from memoflow.domain.shared.entity import AggregateRoot, Entity, utcnow
from memoflow.domain.shared.exceptions import EntityNotFoundError, InvariantViolationError
from memoflow.domain.shared.value_objects import TimeRange
from memoflow.domain.transcript.value_objects import SpeakerId, TranscriptId, UtteranceId


class Speaker(Entity[SpeakerId]):
    """说话人：pyannote 输出的是匿名标签（如 SPEAKER_00），用户可在 UI 中重命名为真实姓名。"""

    def __init__(self, speaker_id: SpeakerId, label: str, display_name: str | None = None) -> None:
        super().__init__(speaker_id)
        self.label = label
        self.display_name = display_name

    @property
    def name(self) -> str:
        return self.display_name or self.label

    def rename(self, display_name: str) -> None:
        if not display_name.strip():
            raise InvariantViolationError("说话人姓名不能为空")
        self.display_name = display_name


class Utterance(Entity[UtteranceId]):
    """一句话语：ASR 输出的文本片段，可能已关联说话人。"""

    def __init__(
        self,
        utterance_id: UtteranceId,
        time_range: TimeRange,
        text: str,
        speaker_id: SpeakerId | None = None,
        confidence: float | None = None,
    ) -> None:
        super().__init__(utterance_id)
        self.time_range = time_range
        self.text = text
        self.speaker_id = speaker_id
        self.confidence = confidence

    def assign_speaker(self, speaker_id: SpeakerId) -> None:
        self.speaker_id = speaker_id


class Transcript(AggregateRoot[TranscriptId]):
    """转写聚合根：一次会议的完整转写结果，包含所有话语与说话人。"""

    def __init__(
        self,
        transcript_id: TranscriptId,
        meeting_id: str,
        language: str,
        utterances: list[Utterance],
        speakers: dict[SpeakerId, Speaker],
        created_at: datetime,
    ) -> None:
        super().__init__(transcript_id)
        self.meeting_id = meeting_id
        self.language = language
        self.utterances = utterances
        self.speakers = speakers
        self.created_at = created_at

    @classmethod
    def create(cls, meeting_id: str, language: str, utterances: list[Utterance]) -> "Transcript":
        return cls(
            transcript_id=TranscriptId.new(),
            meeting_id=meeting_id,
            language=language,
            utterances=sorted(utterances, key=lambda u: u.time_range.start),
            speakers={},
            created_at=utcnow(),
        )

    # ---- 说话人管理 ----
    def register_speaker(self, label: str) -> Speaker:
        """注册一个新说话人（若同 label 已存在则直接返回）。"""
        for speaker in self.speakers.values():
            if speaker.label == label:
                return speaker
        speaker = Speaker(SpeakerId.new(), label=label)
        self.speakers[speaker.id] = speaker
        return speaker

    def rename_speaker(self, speaker_id: SpeakerId, display_name: str) -> None:
        speaker = self.speakers.get(speaker_id)
        if speaker is None:
            raise EntityNotFoundError("Speaker", str(speaker_id))
        speaker.rename(display_name)

    def assign_speaker_to_utterance(self, utterance_id: UtteranceId, speaker_id: SpeakerId) -> None:
        if speaker_id not in self.speakers:
            raise EntityNotFoundError("Speaker", str(speaker_id))
        utterance = self._find_utterance(utterance_id)
        utterance.assign_speaker(speaker_id)

    def _find_utterance(self, utterance_id: UtteranceId) -> Utterance:
        for utterance in self.utterances:
            if utterance.id == utterance_id:
                return utterance
        raise EntityNotFoundError("Utterance", str(utterance_id))

    # ---- 查询辅助 ----
    @property
    def full_text(self) -> str:
        lines = []
        for u in self.utterances:
            speaker_name = self.speakers[u.speaker_id].name if u.speaker_id else "未知说话人"
            lines.append(f"[{speaker_name}] {u.text}")
        return "\n".join(lines)

    def utterances_by_speaker(self, speaker_id: SpeakerId) -> list[Utterance]:
        return [u for u in self.utterances if u.speaker_id == speaker_id]
