"""Transcribe General Debate audio with local Whisper (MLX).

Mirrors the UNGDC 2025 method: English interpretation track, Whisper large-v3-turbo,
one speech per file, single-line text named ISO3_<session>_<year>.txt. Presiding-officer
lines are kept, as in 2025; cleaning removes them downstream.

The Spanish channel (--lang ES) is transcribed only to check the English text. It is
written to data/interim/transcripts/<year>_es, never to the corpus. For Spanish-speaking
delegations it carries the speaker's own words; for the others, a second interpretation.
Every transcript also gets <stem>.segments.json, Whisper's timed segments, which line
up the two languages.
Whisper can skip speech after a pause; pipeline.regap re-transcribes those stretches.

    uv run python -m pipeline.transcribe --session 81 --year 2026 [--lang ES] [--only AR,CO] [--out DIR]
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import mlx_whisper
import pycountry

from pipeline.config import AUDIO, INTERIM, PROVISIONAL

WHISPER_REPO = "mlx-community/whisper-large-v3-turbo"
AUDIO_RE = re.compile(r"^(\d+)_([A-Z]{2})_(EN|ES)\.mp3$")
WHISPER_LANG = {"EN": "en", "ES": "es"}


def iso3(iso2: str) -> str:
    if iso2 == "EU":  # the corpus names European Union files EU_<session>_<year>
        return "EU"
    c = pycountry.countries.get(alpha_2=iso2)
    if c is None:
        raise ValueError(f"unknown ISO2 code {iso2}")
    return c.alpha_3


def drop_repeats(segments: list[dict]) -> tuple[list[dict], int]:
    """Collapse consecutive segments with identical text (Whisper decoding loops)."""
    kept, dropped = [], 0
    for s in segments:
        if kept and s["text"] == kept[-1]["text"]:
            dropped += 1
            continue
        kept.append(s)
    return kept, dropped


def transcribe(mp3: Path, language: str = "en") -> tuple[str, dict, list[dict]]:
    result = mlx_whisper.transcribe(
        str(mp3),
        path_or_hf_repo=WHISPER_REPO,
        language=language,
        condition_on_previous_text=False,  # avoids the runaway loops seen in 2025 (PAK)
    )
    segs = [{"start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"].strip()}
            for s in result["segments"] if s["text"].strip()]
    segs, dropped = drop_repeats(segs)
    text = re.sub(r"\s+", " ", " ".join(s["text"] for s in segs)).strip()
    duration = result["segments"][-1]["end"] if result["segments"] else 0.0
    qc = {"segments": len(segs), "dropped_repeats": dropped, "audio_seconds": round(duration, 1)}
    return text, qc, segs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", type=int, required=True)
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--lang", default="EN", choices=sorted(WHISPER_LANG), help="audio channel (default EN)")
    ap.add_argument("--only", help="comma-separated ISO2 codes")
    ap.add_argument("--out", type=Path, help="output folder for text and QC files "
                    "(default: provisional session folder for EN, interim transcripts folder for ES)")
    args = ap.parse_args(argv)

    audio_dir = AUDIO / str(args.year)
    if args.lang == "EN":
        out_dir = args.out or PROVISIONAL / f"Session {args.session} - {args.year}"
        qc_dir = args.out or INTERIM / "transcripts" / str(args.year)
    else:
        out_dir = qc_dir = args.out or INTERIM / "transcripts" / f"{args.year}_{args.lang.lower()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    qc_dir.mkdir(parents=True, exist_ok=True)
    only = {c.strip().upper() for c in args.only.split(",")} if args.only else None

    files = sorted(p for p in audio_dir.glob("*.mp3") if AUDIO_RE.match(p.name))
    for mp3 in files:
        session, iso2, lang = AUDIO_RE.match(mp3.name).groups()
        if lang != args.lang or int(session) != args.session or (only and iso2 not in only):
            continue
        target = out_dir / f"{iso3(iso2)}_{args.session}_{args.year}.txt"
        if target.exists():
            print(f"skip {target.name}")
            continue
        text, qc, segs = transcribe(mp3, WHISPER_LANG[lang])
        tmp = target.with_suffix(".tmp")
        tmp.write_text(text + "\n", encoding="utf-8")
        tmp.replace(target)
        qc.update(file=target.name, words=len(text.split()), channel=lang)
        (qc_dir / f"{target.stem}.json").write_text(json.dumps(qc, indent=1), encoding="utf-8")
        (qc_dir / f"{target.stem}.segments.json").write_text(
            json.dumps(segs, ensure_ascii=False, indent=0), encoding="utf-8")
        print(json.dumps(qc), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
