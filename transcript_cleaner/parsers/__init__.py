"""
Parsers for all supported transcript formats.
Each parser returns a Transcript object.
"""

import re
import json
from pathlib import Path
from typing import Union
from ..models import Transcript, Turn, TranscriptFormat


# ── Format auto-detection ─────────────────────────────────────────────────────

def detect_format(path: Path) -> TranscriptFormat:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return TranscriptFormat.REV_JSON
    if suffix == ".docx":
        return TranscriptFormat.OTTER
    # Peek at content for .txt disambiguation
    text = path.read_text(encoding="utf-8", errors="replace")[:2000]
    if re.search(r"^\d{2}:\d{2}:\d{2}\s+\w", text, re.MULTILINE):
        return TranscriptFormat.ZOOM
    if re.search(r"^[A-Za-z].+\n\d{1,2}:\d{2}", text, re.MULTILINE):
        return TranscriptFormat.OTTER
    return TranscriptFormat.PLAIN_TXT


def parse(path: Union[str, Path], fmt: TranscriptFormat = TranscriptFormat.AUTO) -> Transcript:
    path = Path(path)
    if fmt == TranscriptFormat.AUTO:
        fmt = detect_format(path)
    parsers = {
        TranscriptFormat.PLAIN_TXT: parse_plain,
        TranscriptFormat.ZOOM:      parse_zoom,
        TranscriptFormat.REV_JSON:  parse_rev,
        TranscriptFormat.OTTER:     parse_otter,
    }
    transcript = parsers[fmt](path)
    transcript.source_format = fmt
    for i, turn in enumerate(transcript.turns):
        turn.index = i
    return transcript


# ── Plain .txt ────────────────────────────────────────────────────────────────

_PLAIN_PATTERN = re.compile(
    r"^(?P<ts>\[[\d:\.]+\]\s*)?(?P<speaker>[A-Za-z][^:\n]{0,40}):\s*(?P<text>.+)$",
    re.MULTILINE,
)


def parse_plain(path: Path) -> Transcript:
    text = path.read_text(encoding="utf-8", errors="replace")
    turns = []
    for m in _PLAIN_PATTERN.finditer(text):
        turns.append(Turn(
            speaker=m.group("speaker").strip(),
            text=m.group("text").strip(),
            start_time=m.group("ts").strip("[] \t") if m.group("ts") else None,
        ))
    if not turns:
        # Fallback: treat whole file as single unlabelled turn
        turns = [Turn(speaker=None, text=text.strip())]
    return Transcript(turns=turns)


# ── Zoom / Teams auto-transcript ──────────────────────────────────────────────

_ZOOM_BLOCK = re.compile(
    r"^(?P<ts>\d{2}:\d{2}:\d{2})\s+(?P<speaker>.+?)\n(?P<text>.+?)(?=\n\d{2}:\d{2}:\d{2}|\Z)",
    re.MULTILINE | re.DOTALL,
)


def parse_zoom(path: Path) -> Transcript:
    text = path.read_text(encoding="utf-8", errors="replace")
    turns = []
    for m in _ZOOM_BLOCK.finditer(text):
        turns.append(Turn(
            speaker=m.group("speaker").strip(),
            text=" ".join(m.group("text").split()),
            start_time=m.group("ts"),
        ))
    return Transcript(turns=turns)


# ── Rev / Trint .json ─────────────────────────────────────────────────────────

def parse_rev(path: Path) -> Transcript:
    data = json.loads(path.read_text(encoding="utf-8"))
    turns = []

    # Rev format: {"monologues": [{"speaker": 0, "elements": [...]}]}
    if "monologues" in data:
        speakers = {s["id"]: s.get("name", f"Speaker {s['id']}")
                    for s in data.get("speakers", [])}
        for mono in data["monologues"]:
            sid = mono.get("speaker", 0)
            words = [e["value"] for e in mono.get("elements", [])
                     if e.get("type") == "text"]
            ts_start = next(
                (str(e.get("ts", "")) for e in mono.get("elements", [])
                 if e.get("type") == "text"), None
            )
            turns.append(Turn(
                speaker=speakers.get(sid, f"Speaker {sid}"),
                text=" ".join(words).strip(),
                start_time=ts_start,
            ))

    # Trint / generic format: {"results": {"speaker_labels": {"segments": [...]}}}
    elif "results" in data:
        segs = (data["results"]
                .get("speaker_labels", {})
                .get("segments", []))
        for seg in segs:
            turns.append(Turn(
                speaker=seg.get("speaker_label", "Unknown"),
                text=seg.get("transcript", "").strip(),
                start_time=str(seg.get("start_time", "")),
                end_time=str(seg.get("end_time", "")),
            ))

    return Transcript(turns=turns)


# ── Otter.ai (.txt / .docx) ───────────────────────────────────────────────────

_OTTER_TXT = re.compile(
    r"^(?P<speaker>[A-Za-z][^\n]{0,60})\n(?P<ts>\d{1,2}:\d{2})\n(?P<text>.+?)(?=\n[A-Za-z]|\Z)",
    re.MULTILINE | re.DOTALL,
)


def parse_otter(path: Path) -> Transcript:
    if path.suffix.lower() == ".docx":
        return _parse_otter_docx(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    turns = []
    for m in _OTTER_TXT.finditer(text):
        turns.append(Turn(
            speaker=m.group("speaker").strip(),
            text=" ".join(m.group("text").split()),
            start_time=m.group("ts"),
        ))
    if not turns:
        return parse_plain(path)
    return Transcript(turns=turns)


def _parse_otter_docx(path: Path) -> Transcript:
    try:
        from docx import Document
    except ImportError:
        raise ImportError("python-docx required for .docx: pip install python-docx")
    doc = Document(str(path))
    turns = []
    current_speaker, current_ts, lines = None, None, []

    for para in doc.paragraphs:
        t = para.text.strip()
        if not t:
            continue
        if re.match(r"^\d{1,2}:\d{2}", t):
            current_ts = t
        elif re.match(r"^[A-Z][a-z]", t) and len(t) < 60 and not t.endswith("."):
            if current_speaker and lines:
                turns.append(Turn(speaker=current_speaker,
                                  text=" ".join(lines),
                                  start_time=current_ts))
                lines = []
            current_speaker = t
        else:
            lines.append(t)

    if current_speaker and lines:
        turns.append(Turn(speaker=current_speaker,
                          text=" ".join(lines),
                          start_time=current_ts))
    return Transcript(turns=turns)
