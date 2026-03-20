"""
transcript-cleaner CLI
"""

import sys
import json
from pathlib import Path
from typing import Optional

try:
    import click
except ImportError:
    print("click not found. Install with: pip install transcript-cleaner[cli]")
    sys.exit(1)

from .parsers import parse, TranscriptFormat
from .cleaners import run_pipeline
from .llm import get_backend


FORMAT_CHOICES = ["auto", "plain", "zoom", "rev", "otter"]


@click.group()
@click.version_option()
def cli():
    """transcript-cleaner — fix messy interview transcripts with rule-based
    heuristics and optional LLM assistance."""
    pass


@cli.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path),
              help="Output file path (default: <input>_cleaned.<ext>)")
@click.option("--format", "fmt", type=click.Choice(FORMAT_CHOICES), default="auto",
              show_default=True, help="Force input format detection")
@click.option("--llm", "llm_provider", type=str, default=None,
              help="LLM provider: openai | anthropic | gemini")
@click.option("--model", type=str, default=None,
              help="Specific model (e.g. gpt-4o, claude-sonnet-4-5, gemini-2.0-flash)")
@click.option("--api-key", type=str, default=None, envvar="LLM_API_KEY",
              help="API key (or set <PROVIDER>_API_KEY env var)")
@click.option("--no-speakers", is_flag=True, help="Skip speaker label fixing")
@click.option("--no-fill", is_flag=True, help="Skip filling unlabelled turns")
@click.option("--no-fillers", is_flag=True, help="Skip filler word removal")
@click.option("--no-merge", is_flag=True, help="Skip merging short turns")
@click.option("--no-timestamps", is_flag=True, help="Skip timestamp normalisation")
@click.option("--json-report", is_flag=True, help="Print cleaning report as JSON")
@click.option("--dry-run", is_flag=True, help="Show report without writing output")
def clean(
    input_file: Path,
    output: Optional[Path],
    fmt: str,
    llm_provider: Optional[str],
    model: Optional[str],
    api_key: Optional[str],
    no_speakers: bool,
    no_fill: bool,
    no_fillers: bool,
    no_merge: bool,
    no_timestamps: bool,
    json_report: bool,
    dry_run: bool,
):
    """Clean a single transcript file."""

    click.echo(f"📄  Parsing  {input_file.name} ...", err=True)
    format_enum = TranscriptFormat(fmt)
    transcript = parse(input_file, fmt=format_enum)
    click.echo(f"    Format detected: {transcript.source_format.value}  "
               f"({len(transcript)} turns)", err=True)

    # Set up LLM backend if requested
    llm = None
    if llm_provider:
        click.echo(f"🤖  LLM backend: {llm_provider} / {model or 'default'}", err=True)
        llm = get_backend(llm_provider, model=model, api_key=api_key)

    click.echo("🔧  Running cleaning pipeline ...", err=True)
    cleaned, report = run_pipeline(
        transcript,
        fix_speakers=not no_speakers,
        fill_unlabelled=not no_fill,
        remove_fillers=not no_fillers,
        merge_turns=not no_merge,
        norm_timestamps=not no_timestamps,
        llm=llm,
    )

    # Report
    if json_report:
        click.echo(json.dumps(report.__dict__))
    else:
        click.echo("\n✅  Cleaning report:", err=True)
        click.echo(report.summary(), err=True)

    if dry_run:
        click.echo("\n-- DRY RUN: no file written --", err=True)
        return

    # Write output
    if output is None:
        output = input_file.with_stem(input_file.stem + "_cleaned")
        if output.suffix not in (".txt", ".json"):
            output = output.with_suffix(".txt")

    output.write_text(cleaned.to_text(), encoding="utf-8")
    click.echo(f"\n💾  Saved → {output}", err=True)


@cli.command()
@click.argument("input_files", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option("--output-dir", type=click.Path(path_type=Path), default=None,
              help="Directory for cleaned files (default: same as input)")
@click.option("--llm", "llm_provider", type=str, default=None)
@click.option("--model", type=str, default=None)
def batch(input_files, output_dir, llm_provider, model):
    """Clean multiple transcript files at once."""
    if not input_files:
        click.echo("No files provided.", err=True)
        sys.exit(1)

    llm = get_backend(llm_provider, model=model) if llm_provider else None

    total_fixes = 0
    for f in input_files:
        f = Path(f)
        transcript = parse(f)
        cleaned, report = run_pipeline(transcript, llm=llm)

        out_dir = output_dir or f.parent
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / (f.stem + "_cleaned.txt")
        out_path.write_text(cleaned.to_text(), encoding="utf-8")

        fixes = report.speaker_fixes + report.unlabelled_filled + report.turns_merged
        total_fixes += fixes
        click.echo(f"  ✓  {f.name} → {out_path.name}  ({fixes} fixes)", err=True)

    click.echo(f"\n✅  Done. {len(input_files)} files, {total_fixes} total fixes.", err=True)


def main():
    cli()


if __name__ == "__main__":
    main()
