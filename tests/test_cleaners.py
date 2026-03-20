import pytest
from pathlib import Path
from transcript_cleaner.parsers import parse, detect_format, TranscriptFormat
from transcript_cleaner.cleaners import (
    run_pipeline,
    fix_speaker_labels,
    remove_filler_words,
    merge_short_turns,
    normalise_timestamps,
)
from transcript_cleaner.models import Transcript, Turn, CleaningReport

FIXTURES = Path(__file__).parent / "fixtures"


# ── Parser tests ──────────────────────────────────────────────────────────────

class TestZoomParser:
    def test_parses_turns(self):
        t = parse(FIXTURES / "sample_zoom.txt", fmt=TranscriptFormat.ZOOM)
        assert len(t.turns) >= 5

    def test_captures_speaker(self):
        t = parse(FIXTURES / "sample_zoom.txt", fmt=TranscriptFormat.ZOOM)
        speakers = t.speaker_set()
        assert any("Kostas" in s for s in speakers)

    def test_captures_timestamps(self):
        t = parse(FIXTURES / "sample_zoom.txt", fmt=TranscriptFormat.ZOOM)
        assert t.turns[0].start_time is not None


class TestFormatDetection:
    def test_detects_zoom(self):
        fmt = detect_format(FIXTURES / "sample_zoom.txt")
        assert fmt == TranscriptFormat.ZOOM


# ── Cleaner tests ─────────────────────────────────────────────────────────────

class TestSpeakerFixes:
    def setup_method(self):
        self.transcript = Transcript(turns=[
            Turn(speaker="kostas kazakos", text="Hello there."),
            Turn(speaker="K Kazakos", text="And another thing."),
            Turn(speaker="participant", text="Yes I agree."),
        ])

    def test_normalises_participant_label(self):
        report = CleaningReport()
        fix_speaker_labels(self.transcript, report)
        speakers = {t.speaker for t in self.transcript.turns}
        assert "Participant" in speakers

    def test_counts_fixes(self):
        report = CleaningReport()
        fix_speaker_labels(self.transcript, report)
        assert report.speaker_fixes > 0


class TestFillerRemoval:
    def test_removes_um(self):
        t = Transcript(turns=[Turn(speaker="P", text="So um like we basically just did it.")])
        report = CleaningReport()
        remove_filler_words(t, report)
        assert "um" not in t.turns[0].text.lower()
        assert report.fillers_removed > 0

    def test_preserves_meaning(self):
        t = Transcript(turns=[Turn(speaker="P", text="It was actually a great experience.")])
        report = CleaningReport()
        remove_filler_words(t, report)
        assert "great experience" in t.turns[0].text


class TestMergeShortTurns:
    def test_merges_same_speaker(self):
        t = Transcript(turns=[
            Turn(speaker="A", text="Yes.", index=0),
            Turn(speaker="A", text="That is correct.", index=1),
            Turn(speaker="B", text="Interesting, tell me more.", index=2),
        ])
        report = CleaningReport()
        merge_short_turns(t, report, min_words=3)
        assert report.turns_merged >= 1
        assert len(t.turns) < 3

    def test_does_not_merge_different_speakers(self):
        t = Transcript(turns=[
            Turn(speaker="A", text="Yes.", index=0),
            Turn(speaker="B", text="Okay.", index=1),
        ])
        report = CleaningReport()
        merge_short_turns(t, report)
        assert len(t.turns) == 2


class TestTimestampNormalisation:
    def test_normalises_fractional_seconds(self):
        t = Transcript(turns=[Turn(speaker="A", text="Hi", start_time="00:01:23.456")])
        report = CleaningReport()
        normalise_timestamps(t, report)
        assert t.turns[0].start_time == "00:01:23"
        assert report.timestamps_normalised == 1

    def test_normalises_plain_seconds(self):
        t = Transcript(turns=[Turn(speaker="A", text="Hi", start_time="83")])
        report = CleaningReport()
        normalise_timestamps(t, report)
        assert t.turns[0].start_time == "00:01:23"


# ── Pipeline integration ──────────────────────────────────────────────────────

class TestPipeline:
    def test_runs_end_to_end(self):
        t = parse(FIXTURES / "sample_zoom.txt", fmt=TranscriptFormat.ZOOM)
        cleaned, report = run_pipeline(t, llm=None)
        assert report.final_turns > 0
        assert report.fillers_removed > 0

    def test_report_final_turns_matches_transcript(self):
        t = parse(FIXTURES / "sample_zoom.txt", fmt=TranscriptFormat.ZOOM)
        cleaned, report = run_pipeline(t)
        assert report.final_turns == len(cleaned)
