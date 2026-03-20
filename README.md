# transcript-cleaner

> Fix messy interview transcripts in seconds — speaker labels, filler words, fragmented turns, and broken timestamps. Rule-based by default. LLM-powered when you need it.

[![CI](https://github.com/kgkazakos/transcript-cleaner/actions/workflows/ci.yml/badge.svg)](https://github.com/kgkazakos/transcript-cleaner/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## The problem

Every UX researcher knows this pain. You finish a one-hour interview, export the transcript from Zoom, Otter, or Rev — and the file is a mess:

- `Kostas K`, `K Kazakos`, and `interviewer` are all the same person
- Half the turns start with *"um, like, you know, sort of..."*
- Three consecutive `"Yeah."` turns that should be one
- Timestamps in five different formats across the same file
- Turns with no speaker label at all

Fixing this manually takes 1–2 hours per transcript. This tool does it in seconds.

---

## Features

| Operation | Approach |
|---|---|
| Fix speaker label inconsistencies | Rule-based normalisation + fuzzy matching + optional LLM |
| Fill unlabelled / silent turns | Heuristic continuation + optional LLM context inference |
| Remove filler words | Regex pipeline (um, uh, like, you know, sort of, basically...) |
| Merge fragmented short turns | Same-speaker merge with configurable word threshold |
| Normalise timestamps | Handles HH:MM:SS.mmm, M:SS, float seconds, plain integers |

**Model-agnostic** — works with OpenAI, Anthropic (Claude), or Google Gemini. No LLM required for most operations.

**Supports all major transcript formats:**
- Plain `.txt` (manual formatting)
- Zoom / Microsoft Teams auto-transcripts
- Rev / Trint `.json`
- Otter.ai `.txt` and `.docx`

---

## Installation

```bash
# Minimal (rule-based only, no LLM)
pip install transcript-cleaner[cli]

# With a specific LLM backend
pip install "transcript-cleaner[cli,anthropic]"
pip install "transcript-cleaner[cli,openai]"
pip install "transcript-cleaner[cli,gemini]"

# Everything
pip install "transcript-cleaner[all]"
```

---

## Quick start

### CLI

```bash
# Rule-based only — no API key needed
transcript-cleaner clean my_interview.txt

# With LLM (Claude) for speaker resolution and unlabelled turns
transcript-cleaner clean my_interview.txt --llm anthropic --model claude-sonnet-4-5

# Batch clean a whole folder
transcript-cleaner batch interviews/*.txt --output-dir cleaned/ --llm openai

# Dry run — see the report without writing output
transcript-cleaner clean my_interview.txt --dry-run
```

**Example output:**

```
📄  Parsing  session_04.txt ...
    Format detected: zoom  (47 turns)
🔧  Running cleaning pipeline ...

✅  Cleaning report:
  Turns:              47 → 39
  Speaker fixes:      12
  Unlabelled filled:  3
  Fillers removed:    28
  Turns merged:       8
  Timestamps fixed:   47
  LLM calls made:     0

💾  Saved → session_04_cleaned.txt
```

### Python API

```python
from transcript_cleaner import parse, run_pipeline, TranscriptFormat

# Parse
transcript = parse("session_04.txt")
print(f"Format: {transcript.source_format.value}, Turns: {len(transcript)}")

# Clean (rule-based)
cleaned, report = run_pipeline(transcript)
print(report.summary())

# Clean with LLM
from transcript_cleaner.llm import get_backend
llm = get_backend("anthropic")  # reads ANTHROPIC_API_KEY from env
cleaned, report = run_pipeline(transcript, llm=llm)

# Export
print(cleaned.to_text())
```

---

## Format support details

### Plain `.txt`
Expects `Speaker Name: turn text` format, with optional `[HH:MM:SS]` prefix.

### Zoom / Teams
Standard auto-transcript export: timestamp on one line, speaker name on the next, then text block.

### Rev / Trint `.json`
Supports Rev's `monologues` format and the generic AWS Transcribe / Trint segment format.

### Otter.ai
Both `.txt` export (speaker name → timestamp → text blocks) and `.docx` export (requires `pip install "transcript-cleaner[docx]"`).

---

## Configuration

All flags can be combined:

```bash
transcript-cleaner clean interview.txt \
  --llm anthropic \
  --model claude-haiku-4-5 \
  --no-fillers \          # keep filler words
  --no-merge \            # keep short turns separate
  --json-report           # machine-readable report
```

---

## Contributing

Bug reports, format support requests, and PRs welcome. If you use a transcript format not listed above, open an issue with a sample (anonymised) — I'll add a parser.

---

## Part of the CPR Ecosystem

`transcript-cleaner` is a satellite tool in the **Computational Product Research (CPR)** ecosystem — a discipline building AI-augmented infrastructure for rigorous, human-centred product research.

**Related projects:**
- [CausalTrack](https://github.com/kgkazakos/causaltrack) — detect the Say-Do Gap in user research sessions
- [synthetic-user-council](https://github.com/kgkazakos/synthetic-user-council) — generate richly profiled synthetic research participants


Learn more about CPR at [github.com/kgkazakos](https://github.com/kgkazakos).

---

## Citation

If you use this tool in research, please cite:

```bibtex
@software{kazakos2026transcriptcleaner,
  author  = {Kazakos, Kostas},
  title   = {transcript-cleaner: Rule-based and LLM-powered transcript cleaning for UX research},
  year    = {2026},
  url     = {https://github.com/kgkazakos/transcript-cleaner}
}
```
