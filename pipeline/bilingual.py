"""Line up a 2026 English transcript with the Spanish channel of the same speech.

The Spanish channel checks the English where it looks doubtful (INSTRUCTIONS.md, `interp`).
Both channels are cut from the same meeting audio, so Whisper's segment times put them on
one clock. An interpretation runs a few seconds behind the words it renders; that lag is
estimated per speech from words written the same way in both languages (names, numbers),
and each English unit is shown with the Spanish spoken in its time window.

    uv run python -m pipeline.bilingual show ARG_81_2026 [--units 12-14]
    uv run python -m pipeline.bilingual view --year 2026 [--only ARG_81_2026,...] --out DIR
"""
import argparse
import difflib
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

from pipeline import tidy
from pipeline.config import INTERIM

PAD = 3.0  # seconds of Spanish shown before and after each English unit's window
DEFAULT_LAG = 3.0  # English behind Spanish, used when too few anchor words are found
ANCHOR = re.compile(r"^(?:[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü-]{3,}|\d[\d.,]*)$")


def timed_words(segments: list[dict]) -> list[tuple[str, float, float]]:
    """Each word with a start and end time, spread evenly across its segment."""
    out = []
    for s in segments:
        words = s["text"].split()
        step = (s["end"] - s["start"]) / max(len(words), 1)
        out += [(w, s["start"] + k * step, s["start"] + (k + 1) * step) for k, w in enumerate(words)]
    return out


def load_segments(sid: str, year: int, lang: str) -> list[dict]:
    folder = str(year) if lang == "EN" else f"{year}_{lang.lower()}"
    path = INTERIM / "transcripts" / folder / f"{sid}.segments.json"
    if not path.exists():
        raise FileNotFoundError(f"no {lang} segments for {sid}: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def unit_spans(units: list[dict], words: list[str]) -> list[tuple[int, int] | None]:
    """First and last transcript word of each unit (None when no word could be matched)."""
    tokens, owner = [], []
    for i, u in enumerate(units):
        for w in u["t"].split():
            tokens.append(w)
            owner.append(i)
    where = {}
    if tokens == words:
        where = dict(enumerate(range(len(words))))
    else:  # the unitizer changed some tokens (encoding, inline notes): match the rest
        sm = difflib.SequenceMatcher(None, tokens, words, autojunk=False)
        for a, b, n in sm.get_matching_blocks():
            where.update((a + k, b + k) for k in range(n))
    spans = [None] * len(units)
    for t, w in where.items():
        i = owner[t]
        spans[i] = (w, w) if spans[i] is None else (min(spans[i][0], w), max(spans[i][1], w))
    return spans


def anchor_key(w: str) -> str:
    return w.strip(".,;:!?¡¿\"'“”‘’()[]")


def estimate_lag(en: list[tuple], es: list[tuple]) -> tuple[float, int]:
    """Median delay of English behind Spanish over words written alike and said once in each."""
    def once(words):
        keys = Counter(anchor_key(w) for w, *_ in words)
        return {anchor_key(w): t for w, t, _ in words if keys[anchor_key(w)] == 1 and ANCHOR.match(anchor_key(w))}
    a, b = once(en), once(es)
    diffs = [a[k] - b[k] for k in a.keys() & b.keys() if abs(a[k] - b[k]) < 30]
    if len(diffs) < 3:
        return DEFAULT_LAG, len(diffs)
    return round(statistics.median(diffs), 1), len(diffs)


def clock(t: float) -> str:
    return f"{int(t // 60):02d}:{int(t % 60):02d}"


def align(sid: str) -> dict:
    meta = tidy.sources()[sid]
    data = tidy.load_units(sid, meta)
    en_words = (tidy.ROOT / meta["path"]).read_text(encoding="utf-8").split()
    en = timed_words(load_segments(sid, meta["year"], "EN"))
    if len(en) != len(en_words):  # a re-timing may respell a word (URY: "Head of State"), never add one
        raise ValueError(f"{sid}: English segments do not match the transcript text; re-time it first")
    es = timed_words(load_segments(sid, meta["year"], "ES"))
    lag, anchors = estimate_lag(en, es)
    rows = []
    for u, span in zip(data["units"], unit_spans(data["units"], en_words)):
        if span is None:
            rows.append({"en": u["t"], "start": None, "end": None, "es": ""})
            continue
        start, end = en[span[0]][1], en[span[1]][2]
        lo, hi = start - lag - PAD, end - lag + PAD
        rows.append({"en": u["t"], "start": start, "end": end,
                     "es": " ".join(w for w, t0, t1 in es if t1 > lo and t0 < hi)})
    return {"id": sid, "lag": lag, "anchors": anchors, "rows": rows}


def lines_for(sid: str, units: range | None = None) -> list[str]:
    al = align(sid)
    meta = tidy.sources()[sid]
    decision = tidy.canonical(sid, meta) or {}
    dropped = {u: r for a, b, r in decision.get("drop", []) for u in range(a, b + 1)}
    paras, cer = set(decision.get("para", [])), set(decision.get("cer", []))
    fixes = {}
    for u, old, new, reason in decision.get("fix", []):
        fixes.setdefault(u, []).append((old, new, reason))
    n, words = len(al["rows"]), sum(len(r["en"].split()) for r in al["rows"])
    out = [f"=== {sid} | {tidy.country_names().get(meta['iso3'], meta['iso3'])} | units 0-{n - 1} | {words:,} words | "
           f"English behind Spanish by {al['lag']} s ({al['anchors']} anchor words) | Spanish shown {PAD:.0f} s either side"]
    pno = 0
    for i, row in enumerate(al["rows"]):
        if i in paras and i not in dropped:
            pno += 1
        if units is not None and i not in units:
            continue
        text = row["en"]
        for old, new, reason in fixes.get(i, []):
            text = text.replace(old, f"{{{old}→{new} {reason}}}", 1)
        mark = f"[DROP {dropped[i]}] " if i in dropped else (
            f"¶P{pno}{' (cer)' if i in cer else ''} " if i in paras else "")
        when = f"{clock(row['start'])}" if row["start"] is not None else "--:--"
        out += wrap(f"{i} [{when}] EN {mark}{text}")
        out += wrap(f"{' ' * len(str(i))}         ES {row['es']}")
    out.append("")
    return out


def wrap(line: str) -> list[str]:
    out = []
    while len(line) > tidy.WRAP_CHARS:
        cut = line.rfind(" ", 0, tidy.WRAP_CHARS)
        cut = cut if cut > 0 else tidy.WRAP_CHARS
        out.append(line[:cut])
        line = "   ⋯ " + line[cut:].lstrip()
    return out + [line]


def parse_units(spec: str) -> range:
    a, _, b = spec.partition("-")
    return range(int(a), int(b or a) + 1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sh = sub.add_parser("show", help="print one speech, or some of its units, with the Spanish beneath")
    sh.add_argument("id")
    sh.add_argument("--units", type=parse_units, help="unit or range, e.g. 12-14")
    vw = sub.add_parser("view", help="write one bilingual file per speech")
    vw.add_argument("--year", type=int, required=True)
    vw.add_argument("--only", help="comma-separated speech ids")
    vw.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    if args.cmd == "show":
        print("\n".join(lines_for(args.id, args.units)))
        return 0
    only = set(args.only.split(",")) if args.only else None
    args.out.mkdir(parents=True, exist_ok=True)
    for sid, meta in sorted(tidy.sources().items()):
        if meta["year"] != args.year or (only and sid not in only):
            continue
        try:
            (args.out / f"{sid}.txt").write_text("\n".join(lines_for(sid)), encoding="utf-8")
            print(f"wrote {sid}")
        except (FileNotFoundError, ValueError) as e:
            print(f"skip {sid}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
