"""transcript-cleaner: Fix messy interview transcripts with rule-based heuristics and optional LLM assistance."""

__version__ = "0.1.0"

from .models import Transcript, Turn, CleaningReport, TranscriptFormat
from .parsers import parse, detect_format
from .cleaners import run_pipeline

__all__ = [
    "Transcript", "Turn", "CleaningReport", "TranscriptFormat",
    "parse", "detect_format", "run_pipeline",
    "__version__",
]
