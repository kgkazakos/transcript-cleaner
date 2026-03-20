"""
Five cleaning operations, each operating on a Transcript in place.
All LLM-powered operations are lazy — only called when rule-based
heuristics are insufficient.
"""

import re
from difflib import SequenceMatcher
from typing import Optional
from ..models import Transcript, Turn, CleaningReport
from ..llm import LLMBackend


# ── 1. Fix speaker label inconsistencies ─────────────────────────────────────

_NORMALISATION_MAP = {
    # Common auto-transcript artifacts
    r"\binterviewer\b": "Interviewer",
    r"\bparticipant\b": "Participant",
    r"\bmod(erator)?\b": "Moderator",
    r"\bfacilitator\b": "Facilitator",
    r"\bhost\b": "Host",
    r"\bguest\b": "Guest",
    r"\bspeaker\s*0*1\b": "Speaker 1",
    r"\bspeaker\s*0*2\b": "Speaker 2",
}


def fix_speaker_labels(
    transcript: Transcript,
    report: CleaningReport,
    llm: Optional[LLMBackend] = None,
) -> Transcript:
    """
    1. Rule-based: normalise obvious variants (case, whitespace, abbreviations).
    2. Fuzzy-match: cluster near-duplicate names (e.g. 'Kostas K' vs 'K Kazakos').
    3. LLM fallback: only if fuzzy clustering leaves ambiguous singletons.
    """
    raw_speakers = list(transcript.speaker_set())

    # Step 1 — rule-based normalisation
    mapping: dict[str, str] = {}
    for raw in raw_speakers:
        normalised = raw.strip()
        for pattern, replacement in _NORMALISATION_MAP.items():
            normalised = re.sub(pattern, replacement, normalised, flags=re.IGNORECASE)
        normalised = re.sub(r"\s+", " ", normalised)
        if normalised != raw:
            mapping[raw] = normalised

    # Step 2 — fuzzy deduplication
    candidates = [mapping.get(s, s) for s in raw_speakers]
    fuzzy_map = _fuzzy_cluster(candidates)

    # Merge both maps
    final_map = {}
    for raw in raw_speakers:
        mid = mapping.get(raw, raw)
        final_map[raw] = fuzzy_map.get(mid, mid)

    # Step 3 — LLM for remaining singletons with short/ambiguous labels
    if llm:
        ambiguous = [s for s in final_map.values()
                     if re.match(r"^[A-Z]\d?$|^Speaker\s*\d+$|^Unknown", s, re.I)]
        if ambiguous:
            resolved = _llm_resolve_speakers(transcript, ambiguous, llm, report)
            for raw, mapped in final_map.items():
                if mapped in resolved:
                    final_map[raw] = resolved[mapped]

    # Apply mapping
    fixes = 0
    for turn in transcript.turns:
        if turn.speaker and turn.speaker in final_map:
            new_label = final_map[turn.speaker]
            if new_label != turn.speaker:
                turn.speaker = new_label
                fixes += 1

    report.speaker_fixes += fixes
    return transcript


def _fuzzy_cluster(speakers: list[str], threshold: float = 0.82) -> dict[str, str]:
    """Group near-duplicate speaker labels, mapping each to the longest variant."""
    groups: list[list[str]] = []
    for s in speakers:
        placed = False
        for group in groups:
            if any(SequenceMatcher(None, s.lower(), g.lower()).ratio() >= threshold
                   for g in group):
                group.append(s)
                placed = True
                break
        if not placed:
            groups.append([s])
    result = {}
    for group in groups:
        canonical = max(group, key=len)
        for member in group:
            result[member] = canonical
    return result


def _llm_resolve_speakers(
    transcript: Transcript,
    ambiguous: list[str],
    llm: LLMBackend,
    report: CleaningReport,
) -> dict[str, str]:
    sample = "\n".join(
        f"{t.speaker}: {t.text[:120]}"
        for t in transcript.turns[:40]
        if t.speaker in ambiguous
    )
    prompt = (
        f"These speaker labels appear in a research interview transcript:\n"
        f"{ambiguous}\n\n"
        f"Sample turns:\n{sample}\n\n"
        "Based on context, suggest a cleaner name for each label. "
        "Reply ONLY as JSON: {\"original\": \"better_name\", ...}"
    )
    report.llm_calls += 1
    raw = llm.complete(prompt)
    import json
    try:
        return json.loads(re.search(r"\{.+\}", raw, re.DOTALL).group())
    except Exception:
        return {}


# ── 2. Fill unlabelled / silent turns ────────────────────────────────────────

def fill_unlabelled_turns(
    transcript: Transcript,
    report: CleaningReport,
    llm: Optional[LLMBackend] = None,
) -> Transcript:
    """
    Heuristic: inherit speaker from previous turn if text is a short
    continuation. LLM for longer ambiguous unlabelled turns.
    """
    filled = 0
    unlabelled_indices = [i for i, t in enumerate(transcript.turns) if t.is_unlabelled()]

    for i in unlabelled_indices:
        turn = transcript.turns[i]
        prev = transcript.turns[i - 1] if i > 0 else None
        
        # Heuristic: short continuation → same speaker as previous
        if prev and prev.speaker and len(turn.text.split()) <= 8:
            turn.speaker = prev.speaker
            filled += 1
        elif llm and len(turn.text.split()) > 4:
            context = "\n".join(
                f"{t.speaker}: {t.text}" for t in transcript.turns[max(0, i-3):i+1]
            )
            prompt = (
                f"Transcript context:\n{context}\n\n"
                f"The last turn has no speaker label. "
                f"Who most likely said it? Reply with ONLY the speaker name."
            )
            report.llm_calls += 1
            guessed = llm.complete(prompt).strip().strip('"')
            if guessed:
                turn.speaker = guessed
                filled += 1

    report.unlabelled_filled += filled
    return transcript


# ── 3. Remove filler words ────────────────────────────────────────────────────

_FILLERS = re.compile(
    r"\b(um+|uh+|er+|ah+|like|you know|i mean|sort of|kind of|basically|"
    r"literally|actually|honestly|right\?|okay\?|so+)\b[,.]?",
    re.IGNORECASE,
)
_MULTI_SPACE = re.compile(r"\s{2,}")
_SENTENCE_START = re.compile(r"(?<=[.!?]\s)([a-z])")


def remove_filler_words(transcript: Transcript, report: CleaningReport) -> Transcript:
    removed = 0
    for turn in transcript.turns:
        original = turn.text
        cleaned = _FILLERS.sub(" ", turn.text)
        cleaned = _MULTI_SPACE.sub(" ", cleaned).strip()
        cleaned = _SENTENCE_START.sub(lambda m: m.group(1).upper(), cleaned)
        # Capitalise first letter if it got eaten
        if cleaned and original[0].isupper() and cleaned[0].islower():
            cleaned = cleaned[0].upper() + cleaned[1:]
        if cleaned != turn.text:
            removed += len(re.findall(_FILLERS, turn.text))
            turn.text = cleaned
    report.fillers_removed += removed
    return transcript


# ── 4. Merge fragmented short turns ──────────────────────────────────────────

def merge_short_turns(
    transcript: Transcript,
    report: CleaningReport,
    min_words: int = 3,
) -> Transcript:
    """Merge consecutive turns from the same speaker when a turn is too short."""
    if not transcript.turns:
        return transcript

    merged_turns: list[Turn] = []
    merged_count = 0

    i = 0
    while i < len(transcript.turns):
        current = transcript.turns[i]

        # Look ahead: merge if same speaker and current turn is short
        if (current.is_short(min_words) and
                i + 1 < len(transcript.turns) and
                transcript.turns[i + 1].speaker == current.speaker):
            nxt = transcript.turns[i + 1]
            current.text = f"{current.text} {nxt.text}"
            current.end_time = nxt.end_time
            merged_count += 1
            i += 2
        else:
            merged_turns.append(current)
            i += 1

    # Re-index
    for idx, turn in enumerate(merged_turns):
        turn.index = idx

    report.turns_merged += merged_count
    transcript.turns = merged_turns
    return transcript


# ── 5. Normalise timestamps ───────────────────────────────────────────────────

_TS_PATTERNS = [
    # HH:MM:SS.mmm → HH:MM:SS
    (re.compile(r"(\d{2}:\d{2}:\d{2})\.\d+"), r"\1"),
    # H:MM:SS → HH:MM:SS
    (re.compile(r"^(\d):(\d{2}:\d{2})$"), r"0\1:\2"),
    # M:SS → 00:0M:SS
    (re.compile(r"^(\d{1,2}):(\d{2})$"), lambda m: f"00:{int(m.group(1)):02d}:{m.group(2)}"),
    # Seconds float → HH:MM:SS
    (re.compile(r"^(\d+\.\d+)$"), lambda m: _seconds_to_hms(float(m.group(1)))),
    # Plain integer seconds
    (re.compile(r"^(\d+)$"), lambda m: _seconds_to_hms(float(m.group(1)))),
]


def _seconds_to_hms(secs: float) -> str:
    s = int(secs)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def normalise_timestamps(transcript: Transcript, report: CleaningReport) -> Transcript:
    fixed = 0
    for turn in transcript.turns:
        for ts_attr in ("start_time", "end_time"):
            raw = getattr(turn, ts_attr)
            if raw is None:
                continue
            normalised = raw
            for pattern, replacement in _TS_PATTERNS:
                if callable(replacement):
                    normalised = pattern.sub(replacement, normalised)
                else:
                    normalised = pattern.sub(replacement, normalised)
            if normalised != raw:
                setattr(turn, ts_attr, normalised)
                fixed += 1
    report.timestamps_normalised += fixed
    return transcript


# ── Pipeline runner ───────────────────────────────────────────────────────────

def run_pipeline(
    transcript: Transcript,
    fix_speakers: bool = True,
    fill_unlabelled: bool = True,
    remove_fillers: bool = True,
    merge_turns: bool = True,
    norm_timestamps: bool = True,
    llm: Optional[LLMBackend] = None,
) -> tuple[Transcript, CleaningReport]:
    report = CleaningReport(original_turns=len(transcript))

    if fix_speakers:
        transcript = fix_speaker_labels(transcript, report, llm)
    if fill_unlabelled:
        transcript = fill_unlabelled_turns(transcript, report, llm)
    if remove_fillers:
        transcript = remove_filler_words(transcript, report)
    if merge_turns:
        transcript = merge_short_turns(transcript, report)
    if norm_timestamps:
        transcript = normalise_timestamps(transcript, report)

    report.final_turns = len(transcript)
    return transcript, report
