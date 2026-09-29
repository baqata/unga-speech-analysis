"""Recover speech that Whisper skipped in the 2026 transcripts.

Whisper sometimes ends a 30-second window early and jumps to the next one, leaving a
gap although the interpreter kept speaking (Paraguay lost 25 s at 852-877 s, from "The
United Nations remains indispensable" to the Manuel Gondra quote). This pass
re-transcribes every stretch of MIN_GAP seconds or more between two segments, one stretch
at a time with a few seconds of the speech before it (for punctuation and casing), and
splices in what it finds; a stretch that was really silence or applause comes back empty
or with a stray "Thank you.", which tidying treats as noise. Whisper also stretches a short
segment over the rest of its window and drops the speech inside it ("Thank you." from 30 to
60 s, where Switzerland's opening was lost), so a segment counts as ending where its words
can have ended (SECONDS_PER_WORD). Such a stretch is decoded without pre-roll: hearing the
"Thank you." again makes Whisper stop again. Recovered segments carry "recovered": true,
and the QC file records the pass ("regap", with its VERSION), so a transcript is processed
once per version. The text file gains the recovered words at the same places. Started in
applause or silence, Whisper may hear only a "Thank you." stretched over the whole stretch
although speech follows (Bolivia's opening, 33-59 s), so a long stretch that gives nothing
else is decoded again from later starts (RETRY_STEP); a transcript marked by an earlier
version gets only its long stretches looked at again. In the silence before a speech
Whisper can also fall into a loop ("I go, I go, I go, ..." for 147 words, Hungary 21-30 s);
a recovered segment whose text compresses beyond Whisper's own loop threshold (LOOP_RATIO)
is rejected like filler.

    uv run python -m pipeline.regap --session 81 --year 2026 [--lang ES] [--only PRY_81_2026,...]
"""
import argparse
import difflib
import json
import os
import re
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import mlx_whisper
import pycountry
from mlx_whisper.audio import SAMPLE_RATE, load_audio
from mlx_whisper.decoding import compression_ratio

from pipeline.config import AUDIO, INTERIM, PROVISIONAL
from pipeline.transcribe import WHISPER_LANG, WHISPER_REPO

MIN_GAP = 4.0  # seconds without a segment worth a second look
PREROLL = 4.0  # seconds of the preceding speech decoded with each stretch, then trimmed
PASSES = 3  # a recovered stretch can itself stop early; look again at what is left
SECONDS_PER_WORD = 1.0  # generous: speech runs at 0.3-0.5 s a word
RETRY_MIN = 8.0  # a stretch this long that gives nothing is decoded again from later starts
RETRY_STEP = 3.0  # seconds between those starts
FILLER_WORDS = 4  # up to this many words stretched over the clip is Whisper's filler, not speech
LOOP_RATIO = 2.4  # Whisper's compression_ratio_threshold; no first-pass 2026 segment exceeds 1.95
VERSION = 5  # 1: gaps between segments; 2: also the silent tail of a stretched segment; 3: that tail without pre-roll; 4: long stretches retried from later starts; 5: repetition loops rejected


def spoken_end(s: dict) -> float:
    """Where a segment's words can have ended, however far Whisper stretched it."""
    return min(s["end"], s["start"] + len(s["text"].split()) * SECONDS_PER_WORD + 1.0)


def find_gaps(segs: list[dict], min_gap: float = MIN_GAP) -> list[tuple[float, float]]:
    """Stretches of at least min_gap seconds after a segment's words and before the next segment."""
    out = []
    for a, b in zip(segs, segs[1:]):
        end = spoken_end(a)
        if b["start"] - end >= min_gap:
            out.append((round(end, 2), b["start"]))
    return out


def filler(s: dict) -> bool:
    """A few words stretched far beyond their length: Whisper's "Thank you." for applause or silence."""
    n = len(s["text"].split())
    return n <= FILLER_WORDS and s["end"] - s["start"] > 2 * (n * SECONDS_PER_WORD + 1.0)


def looping(text: str) -> bool:
    """Whisper repeating itself: a text that compresses as no speech does."""
    return compression_ratio(text) > LOOP_RATIO


def words(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", text.lower())


def trim(text: str, prev: str, nxt: str) -> str:
    """Drop leading words that repeat the end of prev and trailing words that repeat the start of nxt."""
    toks, pw, nw = text.split(), words(prev), words(nxt)
    for k in range(len(toks), 0, -1):
        head = words(" ".join(toks[:k]))
        if head and head == pw[-len(head):]:
            toks = toks[k:]
            break
    for k in range(len(toks), 0, -1):
        tail = words(" ".join(toks[-k:]))
        if tail and tail == nw[:len(tail)]:
            toks = toks[:-k]
            break
    return " ".join(toks)


def repeats(w: list[str], ref: list[str]) -> bool:
    """The pre-roll heard again, perhaps spelt differently ('repartory' / 'a partry')."""
    return difflib.SequenceMatcher(None, w, ref, autojunk=False).ratio() >= 0.7


def merge(segs: list[dict], found: list[dict]) -> tuple[list[dict], list[dict]]:
    """Insert recovered segments in time order, without words their neighbours already hold."""
    out, added = list(segs), []
    for f in sorted(found, key=lambda s: s["start"]):
        i = sum(1 for s in out if s["start"] <= f["start"])
        prev = out[i - 1]["text"] if i > 0 else ""
        nxt = out[i]["text"] if i < len(out) else ""
        text = trim(f["text"], prev, nxt)
        w = words(text)
        if not w or repeats(w, words(prev)[-len(w):]) or repeats(w, words(nxt)[:len(w)]):
            continue
        f = {**f, "text": text}
        if i > 0 and out[i - 1]["end"] > f["start"]:  # a stretched segment ends where the recovered one starts
            out[i - 1]["end"] = f["start"]  # in place: splice_text knows an earlier pass's segments by identity
        out.insert(i, f)
        added.append(f)
    return out, added


def splice_text(text: str, segs: list[dict], added: list[dict]) -> str:
    """Put the words of this pass's recovered segments into the text at the matching places.

    Every other segment, including one recovered by an earlier pass, already has its words
    in the text, in order and word for word (a re-timing may respell a word, never add one)."""
    tokens, new = text.split(), {id(s) for s in added}
    if len(tokens) != sum(len(s["text"].split()) for s in segs if id(s) not in new):
        raise ValueError("text and segments differ in word count")
    out, k = [], 0
    for s in segs:
        n = len(s["text"].split())
        if id(s) in new:
            out += s["text"].split()
        else:
            out += tokens[k:k + n]
            k += n
    return " ".join(out)


def decode(audio, t0: float, a: float, b: float, language: str) -> list[dict]:
    """The segments heard from t0 to b that lie mostly past a (t0 < a is pre-roll)."""
    result = mlx_whisper.transcribe(audio[int(t0 * SAMPLE_RATE):int(b * SAMPLE_RATE)],
                                    path_or_hf_repo=WHISPER_REPO, language=language,
                                    condition_on_previous_text=False)
    out = []
    for s in result["segments"]:
        start, end = round(s["start"] + t0, 2), round(min(s["end"] + t0, b), 2)
        if s["text"].strip() and end > a and end - max(start, a) >= (end - start) / 2 and not looping(s["text"]):
            out.append({"start": max(start, a), "end": end, "text": s["text"].strip(), "recovered": True})
    return out


def recover(audio, segs: list[dict], language: str,
            min_gap: float = MIN_GAP) -> tuple[list[dict], list[dict], int]:
    tried, added = set(), []
    for _ in range(PASSES):
        gaps = [g for g in find_gaps(segs, min_gap) if g not in tried]
        if not gaps:
            break
        tried.update(gaps)
        found = []
        for a, b in gaps:
            stretched = any(s["start"] < a < s["end"] for s in segs)
            starts = [a if stretched else max(0.0, a - PREROLL)]
            if b - a >= RETRY_MIN:
                starts += [a + k * RETRY_STEP for k in range(1, int((b - a - MIN_GAP) / RETRY_STEP) + 1)]
            first = None
            for t0 in starts:
                got = decode(audio, t0, a, b, language)
                first = got if first is None else first
                if not all(filler(s) for s in got):
                    break
            else:
                got = first  # only filler from every start: keep what the first decode heard
            found += got
        segs, new = merge(segs, found)
        if not new:
            break
        added += new
    return segs, added, len(tried)


def iso2_of(iso3: str) -> str:
    return "EU" if iso3 == "EU" else pycountry.countries.get(alpha_3=iso3).alpha_2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", type=int, required=True)
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--lang", default="EN", choices=sorted(WHISPER_LANG))
    ap.add_argument("--only", help="comma-separated speech ids (ISO3_session_year)")
    args = ap.parse_args(argv)

    if args.lang == "EN":
        seg_dir, txt_dir = INTERIM / "transcripts" / str(args.year), PROVISIONAL / f"Session {args.session} - {args.year}"
    else:
        seg_dir = txt_dir = INTERIM / "transcripts" / f"{args.year}_{args.lang.lower()}"
    only = set(args.only.split(",")) if args.only else None
    for seg_path in sorted(seg_dir.glob(f"*_{args.session}_{args.year}.segments.json")):
        sid = seg_path.name.removesuffix(".segments.json")
        qc_path, txt_path = seg_dir / f"{sid}.json", txt_dir / f"{sid}.txt"
        if (only and sid not in only) or not qc_path.exists() or not txt_path.exists():
            continue
        qc = json.loads(qc_path.read_text(encoding="utf-8"))
        before = qc.get("regap", {})
        if before.get("version", 1 if before else 0) >= VERSION:
            continue
        segs = json.loads(seg_path.read_text(encoding="utf-8"))
        mp3 = AUDIO / str(args.year) / f"{args.session}_{iso2_of(sid.split('_')[0])}_{args.lang}.mp3"
        new, added, n_gaps = recover(load_audio(str(mp3)), segs, WHISPER_LANG[args.lang],
                                     min_gap=RETRY_MIN if before else MIN_GAP)
        if added:
            text = splice_text(txt_path.read_text(encoding="utf-8").strip(), new, added)
            tmp = txt_path.with_suffix(".tmp")
            tmp.write_text(text + "\n", encoding="utf-8")
            tmp.replace(txt_path)
            seg_path.write_text(json.dumps(new, ensure_ascii=False, indent=0), encoding="utf-8")
            qc.update(segments=len(new), words=len(text.split()))
        qc["regap"] = {"version": VERSION, "min_gap": MIN_GAP, "gaps": before.get("gaps", 0) + n_gaps,
                       "recovered_segments": before.get("recovered_segments", 0) + len(added),
                       "recovered_words": before.get("recovered_words", 0)
                       + sum(len(s["text"].split()) for s in added)}
        qc_path.write_text(json.dumps(qc, indent=1), encoding="utf-8")
        print(json.dumps({"id": sid, "channel": args.lang, **qc["regap"]}), flush=True)
        for s in added:
            print(f"  + {s['start']:7.1f}-{s['end']:7.1f} {s['text']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
