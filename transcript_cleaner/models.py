from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class TranscriptFormat(str, Enum):
    PLAIN_TXT = "plain"
    ZOOM = "zoom"
    REV_JSON = "rev"
    OTTER = "otter"
    AUTO = "auto"


@dataclass
class Turn:
    speaker: Optional[str]
    text: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    index: int = 0

    def is_unlabelled(self) -> bool:
        return self.speaker is None or self.speaker.strip() == ""

    def is_short(self, min_words: int = 3) -> bool:
        return len(self.text.split()) < min_words

    def __str__(self) -> str:
        ts = f"[{self.start_time}] " if self.start_time else ""
        speaker = f"{self.speaker}: " if self.speaker else "[Unknown]: "
        return f"{ts}{speaker}{self.text}"


@dataclass
class Transcript:
    turns: list[Turn] = field(default_factory=list)
    source_format: TranscriptFormat = TranscriptFormat.AUTO
    metadata: dict = field(default_factory=dict)

    def to_text(self) -> str:
        return "\n".join(str(t) for t in self.turns)

    def speaker_set(self) -> set[str]:
        return {t.speaker for t in self.turns if t.speaker}

    def __len__(self) -> int:
        return len(self.turns)


@dataclass
class CleaningReport:
    original_turns: int = 0
    final_turns: int = 0
    speaker_fixes: int = 0
    unlabelled_filled: int = 0
    fillers_removed: int = 0
    turns_merged: int = 0
    timestamps_normalised: int = 0
    llm_calls: int = 0

    def summary(self) -> str:
        lines = [
            f"  Turns:              {self.original_turns} → {self.final_turns}",
            f"  Speaker fixes:      {self.speaker_fixes}",
            f"  Unlabelled filled:  {self.unlabelled_filled}",
            f"  Fillers removed:    {self.fillers_removed}",
            f"  Turns merged:       {self.turns_merged}",
            f"  Timestamps fixed:   {self.timestamps_normalised}",
            f"  LLM calls made:     {self.llm_calls}",
        ]
        return "\n".join(lines)
