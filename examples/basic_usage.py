"""
Basic usage example — run without any LLM backend (pure rule-based).
"""

from pathlib import Path
from transcript_cleaner import parse, run_pipeline, TranscriptFormat

# Parse a Zoom transcript
transcript = parse(Path("my_interview.txt"), fmt=TranscriptFormat.AUTO)
print(f"Parsed {len(transcript)} turns")
print(f"Speakers: {transcript.speaker_set()}")

# Run the full cleaning pipeline (no LLM)
cleaned, report = run_pipeline(transcript)
print(report.summary())

# Write output
Path("my_interview_cleaned.txt").write_text(cleaned.to_text())

# ── With LLM backend ──────────────────────────────────────────────────────────
# Uncomment to enable LLM-powered speaker resolution and unlabelled turn filling

# from transcript_cleaner.llm import get_backend
# llm = get_backend("anthropic", model="claude-sonnet-4-5")  # or "openai", "gemini"
# cleaned, report = run_pipeline(transcript, llm=llm)
