"""Corpus preparation: speech files -> speeches.parquet + fragments.parquet.

Run with `uv run python -m pipeline.prepare`. Reads the UNGDC v14 text files
(read-only), the sessions split from the UN verbatim records (data/official,
which replace the corpus files of those sessions) and any provisional texts.
A speech with a current tidy copy
(data/tidy/TXT, written by pipeline.tidy) is taken from that copy, whose
paragraphs and ceremonial labels were set by agents; any other speech is
cleaned from its source file and its paragraphs are rebuilt here. Then
fragments are built, ceremonial fragments flagged, speaker metadata joined,
Harrier tokens counted and a QC report written
(data/interim/qc/prepare_report.md).
"""
import csv
import hashlib
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline import clean, config, segment, tidy
from pipeline.speakers import POST_CATEGORIES, load_speakers

FILENAME_RE = re.compile(r"^([A-Z]{2,4})_(\d{2})_(\d{4})\.txt$")
SESSION_DIR_RE = re.compile(r"^Session (\d{2}) - (\d{4})$")
V14_SOURCE = "ungdc_v14"
PROVISIONAL_SOURCE = "provisional_2026"
OFFICIAL_SOURCE = "un_records"
PREPARE_REPORT = config.QC / "prepare_report.md"
TIDY_TXT = tidy.OUT_TXT  # decisions are read from the sibling "decisions" folder
SHORT_LINE = 60  # QC: kept lines up to this length that recur across files of a year

SPEECH_COLUMNS = ["speech_id", "iso3", "session", "year", "source", "text_clean", "n_words",
                  "n_tokens", "n_fragments", "layout", "speaker_name", "speaker_post",
                  "post_category"]
FRAGMENT_COLUMNS = ["frag_id", "speech_id", "iso3", "year", "seq", "text", "n_words",
                    "n_tokens", "para_method", "is_ceremonial"]


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def _scan(root: Path, source: str) -> list[dict]:
    rows = []
    if not root.exists():
        return rows
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        if not SESSION_DIR_RE.match(folder.name):
            continue
        for path in sorted(folder.iterdir()):
            m = FILENAME_RE.match(path.name)
            if not m or not path.is_file():
                continue  # .DS_Store, .Rhistory, ".DS_Store-to-UTF-8.txt", ...
            rows.append({"speech_id": path.stem, "iso3": config.CODE_RENAMES.get(m.group(1), m.group(1)),
                         "session": int(m.group(2)),
                         "year": int(m.group(3)), "source": source, "path": path})
    return rows


def list_sources(corpus_dir: Path = config.CORPUS_TXT,
                 provisional_dir: Path = config.PROVISIONAL,
                 official_dir: Path = config.OFFICIAL) -> list[dict]:
    """All speech files (Session NN - YYYY folders): UNGDC v14, the sessions split from the
    verbatim records, which replace the corpus files of those sessions, and provisional texts."""
    official = _scan(Path(official_dir), OFFICIAL_SOURCE)
    replaced = {s["session"] for s in official}
    corpus = [s for s in _scan(Path(corpus_dir), V14_SOURCE) if s["session"] not in replaced]
    return corpus + official + _scan(Path(provisional_dir), PROVISIONAL_SOURCE)


def is_transcript(year: int, source: str) -> bool:
    """Speech-to-text transcripts that carry the presiding officer's words."""
    return year >= 2025 or source == PROVISIONAL_SOURCE


def has_long_loops(year: int, source: str) -> bool:
    """Sources where a long passage can be duplicated by error (OCR records up to
    2014, speech-to-text transcripts). Born-digital texts (2015-2024) repeat on purpose."""
    return year < 2015 or is_transcript(year, source)


def country_names(countries: Path = config.COUNTRIES,
                  historical: Path = config.HISTORICAL_NAMES) -> dict[str, set]:
    """iso3 -> English country names (current and historical), when the files exist."""
    names = defaultdict(set)
    for path in (countries, historical):
        if Path(path).exists():
            with open(path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if row.get("name_en"):
                        names[row["iso3"]].add(row["name_en"])
    return names


def load_tidy(tidy_dir: Path | None, folder: str, speech_id: str, sha1: str):
    """(text, ceremonial labels per paragraph or None) from a current tidy copy, or None.

    A copy is current when its decision records the source file's `sha1` and
    the unitizer version of pipeline.tidy.
    """
    if tidy_dir is None:
        return None
    txt = Path(tidy_dir) / folder / f"{speech_id}.txt"
    dec = Path(tidy_dir).parent / "decisions" / folder / f"{speech_id}.json"
    if not (txt.exists() and dec.exists()):
        return None
    d = json.loads(dec.read_text(encoding="utf-8"))
    if d.get("sha1") != sha1 or d.get("unitizer_version") != tidy.UNITIZER_VERSION:
        return None
    text = txt.read_text(encoding="utf-8")
    blocks = [b for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    if not blocks:
        return None
    para, cer = d.get("para", []), set(d.get("cer", []))
    labels = [u in cer for u in para] if len(para) == len(blocks) else None
    return "\n\n".join(blocks), labels


# ---------------------------------------------------------------------------
# Per-speech processing
# ---------------------------------------------------------------------------

def _near_edge(i: int, n: int) -> bool:
    return i < 2 * segment.CEREMONIAL_HEAD or i >= n - 2 * segment.CEREMONIAL_TAIL


def _finish(paragraphs: list[str], marks: list[str], labels: list | None) -> dict:
    """Drop empty paragraphs, build fragments and ceremonial flags.

    With agent labels (tidy copy) a fragment is ceremonial when all its
    paragraphs are labelled so; otherwise segment.flag_ceremonial decides.
    """
    kept, kept_marks, kept_labels, carry = [], [], [], ""
    for k, p in enumerate(paragraphs):
        p = re.sub(r"\s+", " ", p).strip()
        if not re.search(r"\w", p):
            carry = carry or ("section" if marks[k] else "")
            continue
        kept.append(p)
        kept_marks.append(marks[k] or carry)
        kept_labels.append(labels[k] if labels else None)
        carry = ""
    n = len(kept)
    kinds = (kept_labels if labels else
             [_near_edge(i, n) and segment.is_courtesy(p) for i, p in enumerate(kept)])
    members = []
    fragments = segment.make_fragments(kept, kept_marks, kinds, members) if kept else []
    regex_flags = segment.flag_ceremonial(fragments)
    flags = [all(kinds[k] for k in m) for m in members] if labels else regex_flags
    return {"paragraphs": kept, "fragments": fragments, "ceremonial": flags,
            "regex_ceremonial": regex_flags}


def process_speech(text: str, speech_id: str, year: int, source: str,
                   vocab: clean.Vocab, counts: Counter, removed: list | None = None,
                   own_names=(), short_lines: set | None = None) -> dict:
    """Clean one normalised source text and segment it into paragraphs and fragments.

    `short_lines` (a set) receives the digit-masked short lines kept in the text,
    for the QC check on recurring page furniture.
    """
    text = clean.strip_editorial(text, counts)
    text = clean.strip_other_speakers(text, own_names, counts, removed)
    text = clean.strip_markdown(text, counts)
    text = clean.fix_ocr(text, speech_id, year, vocab, counts)
    if is_transcript(year, source):
        text = clean.strip_presiding(text, counts, removed)
    lines = clean.split_lines(text, year, counts)
    if short_lines is not None:
        short_lines.update(re.sub(r"\d", "N", ln.text) for ln in lines
                           if len(ln.text) <= SHORT_LINE and not ln.text.endswith(tuple(".,;:!?")))
    stats = segment.layout_stats(lines)
    layout = segment.detect_layout(lines, stats)
    if year >= 2015:
        segment.mark_titles(lines, layout, counts)
    marks = []
    paragraphs = segment.rebuild_paragraphs(lines, layout, stats, vocab, counts, marks)
    paragraphs = clean.collapse_loops_all(paragraphs, counts, removed,
                                          long_loops=has_long_loops(year, source))
    return {"layout": layout, **_finish(paragraphs, marks, None)}


def process_tidy(text: str, speech_id: str, year: int, vocab: clean.Vocab, counts: Counter,
                 labels: list | None = None) -> dict:
    """Segment a tidy copy: its blank-line paragraphs are kept, and each one only
    goes through the inline cleaning rules (the agents removed everything else)."""
    paragraphs = []
    for block in re.split(r"\n\s*\n", text):
        block = clean.strip_editorial(block, counts)
        block = clean.strip_markdown(block, counts)
        paragraphs.append(clean.fix_ocr(block, speech_id, year, vocab, counts))
    return {"layout": "tidy", **_finish(paragraphs, [""] * len(paragraphs), labels)}


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

def load_tokenizer():
    """Harrier tokenizer from the local Hugging Face cache (offline)."""
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    from huggingface_hub import constants
    from tokenizers import Tokenizer

    # The cache has no refs/main, so resolve the snapshot folder directly.
    repo = Path(constants.HF_HUB_CACHE) / ("models--" + config.MODEL_ID.replace("/", "--"))
    ref = repo / "refs" / "main"
    if ref.exists():
        snapshot = repo / "snapshots" / ref.read_text().strip()
    else:
        snapshots = sorted((repo / "snapshots").glob("*/tokenizer.json"),
                           key=lambda p: p.stat().st_mtime)
        if not snapshots:
            raise FileNotFoundError(f"No cached tokenizer for {config.MODEL_ID} in {repo}")
        snapshot = snapshots[-1].parent
    tok = Tokenizer.from_file(str(snapshot / "tokenizer.json"))
    tok.no_truncation()
    tok.no_padding()
    return tok


def count_tokens(tokenizer, texts: list[str], batch_size: int = 256) -> list[int]:
    """Content tokens per text (no special tokens; the embedder adds one EOS)."""
    lengths = []
    for i in range(0, len(texts), batch_size):
        encs = tokenizer.encode_batch(texts[i:i + batch_size], add_special_tokens=False)
        lengths.extend(len(e.ids) for e in encs)
    return lengths


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run(corpus_dir: Path = config.CORPUS_TXT, provisional_dir: Path = config.PROVISIONAL,
        speakers_path: Path = config.SPEAKERS_XLSX, out_dir: Path = config.INTERIM,
        report_path: Path | None = PREPARE_REPORT, tokenizer=None, log=print,
        tidy_dir: Path | None = TIDY_TXT, official_dir: Path = config.OFFICIAL) -> dict:
    """Prepare all speeches; `tidy_dir=None` ignores the tidy copies."""
    t0 = time.time()
    sources = list_sources(corpus_dir, provisional_dir, official_dir)
    log(f"[prepare] {len(sources)} speech files")

    # 1. Read and normalise; build the corpus vocabulary from the source files.
    vocab = clean.Vocab()
    texts, raw_words, speech_counts, sha1s = {}, {}, {}, {}
    for src in sources:
        counts = Counter()
        # Decode bytes ourselves: text mode would hide CR/CRLF and the BOM.
        raw = src["path"].read_bytes()
        text = clean.normalise(raw.decode("utf-8"), counts)
        texts[src["speech_id"]] = text
        raw_words[src["speech_id"]] = len(text.split())
        speech_counts[src["speech_id"]] = counts
        if src["speech_id"] not in clean.LIGATURE_FILES:
            vocab.add(text)
        sha1s[src["speech_id"]] = hashlib.sha1(raw).hexdigest()
    log(f"[prepare] read + vocabulary ({len(vocab.counts):,} types): {time.time() - t0:.0f}s")

    # 2. Clean and segment.
    names = country_names()
    speech_rows, frag_rows, removed = [], [], []
    short_lines = defaultdict(Counter)  # year -> digit-masked short line -> files
    for src in sources:
        sid, year = src["speech_id"], src["year"]
        counts = speech_counts[sid]
        text = texts.pop(sid)
        copy = load_tidy(tidy_dir, src["path"].parent.name, sid, sha1s[sid])
        if copy is not None:
            tidy_text, labels = copy
            out = process_tidy(clean.normalise(tidy_text, Counter()), sid, year, vocab, counts,
                               labels)
            out["labelled"] = labels is not None
        else:
            cut, lines = [], set()
            out = process_speech(text, sid, year, src["source"], vocab, counts, cut,
                                 names.get(src["iso3"], ()), lines)
            removed.extend((sid, kind, snippet) for kind, snippet in cut)
            short_lines[year].update(lines)
            out["labelled"] = False
        fragments = out["fragments"]
        method = segment.PARA_METHOD[out["layout"]]
        text_clean = "\n\n".join(out["paragraphs"])
        speech_rows.append({
            "speech_id": sid, "iso3": src["iso3"], "session": src["session"],
            "year": year, "source": src["source"], "text_clean": text_clean,
            "n_words": segment.n_words(text_clean), "n_fragments": len(fragments),
            "layout": out["layout"], "raw_words": raw_words[sid], "labelled": out["labelled"],
        })
        for seq, (frag, flag, rx) in enumerate(zip(fragments, out["ceremonial"],
                                                   out["regex_ceremonial"])):
            frag_rows.append({
                "speech_id": sid, "iso3": src["iso3"], "year": year, "seq": seq,
                "text": frag, "n_words": segment.n_words(frag), "para_method": method,
                "is_ceremonial": bool(flag), "regex_ceremonial": bool(rx),
            })
    log(f"[prepare] cleaned + segmented: {time.time() - t0:.0f}s")

    speeches = pd.DataFrame(speech_rows)
    fragments = pd.DataFrame(frag_rows)

    # 3. Speaker metadata.
    speakers = load_speakers(speakers_path, provisional_dir)
    speeches = speeches.merge(
        speakers[["iso3", "year", "speaker_name", "speaker_post", "post_category",
                  "speaker_rows"]], on=["iso3", "year"], how="left")
    speeches["post_category"] = speeches["post_category"].fillna("unknown")

    # 4. Tokens.
    tokenizer = tokenizer or load_tokenizer()
    speeches["n_tokens"] = count_tokens(tokenizer, speeches["text_clean"].tolist())
    fragments["n_tokens"] = count_tokens(tokenizer, fragments["text"].tolist())
    log(f"[prepare] tokens counted: {time.time() - t0:.0f}s")

    # 5. Order, ids, types.
    speeches = speeches.sort_values(["year", "iso3"], kind="stable").reset_index(drop=True)
    fragments = fragments.sort_values(["year", "iso3", "seq"], kind="stable").reset_index(drop=True)
    fragments.insert(0, "frag_id", np.arange(len(fragments), dtype=np.int64))
    for df, cols in ((speeches, ["session", "year", "n_words", "n_tokens", "n_fragments"]),
                     (fragments, ["year", "seq", "n_words", "n_tokens"])):
        for c in cols:
            df[c] = df[c].astype(np.int64)
    fragments["is_ceremonial"] = fragments["is_ceremonial"].astype(bool)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    speeches[SPEECH_COLUMNS].to_parquet(out_dir / config.SPEECHES.name, index=False)
    fragments[FRAGMENT_COLUMNS].to_parquet(out_dir / config.FRAGMENTS.name, index=False)
    log(f"[prepare] wrote {len(speeches):,} speeches and {len(fragments):,} fragments "
        f"to {out_dir}: {time.time() - t0:.0f}s")

    if report_path is not None:
        write_report(Path(report_path), speeches, fragments, speech_counts, removed, vocab,
                     runtime=time.time() - t0, short_lines=short_lines)
        log(f"[prepare] report: {report_path}")
    return {"speeches": speeches, "fragments": fragments, "speech_counts": speech_counts,
            "removed": removed, "vocab": vocab}


# ---------------------------------------------------------------------------
# QC report
# ---------------------------------------------------------------------------

ERAS = [  # (first year, last year, label); follows the layout eras of the corpus
    (1946, 1968, "1946-1968 (paragraph lines)"), (1969, 1969, "1969 (hard-wrapped)"),
    (1970, 1981, "1970-1981 (paragraph lines)"), (1982, 1982, "1982 (hard-wrapped)"),
    (1983, 1991, "1983-1991 (paragraph lines)"), (1992, 2014, "1992-2014 (hard-wrapped)"),
    (2015, 2023, "2015-2023 (paragraph lines)"), (2024, 2024, "2024 (mixed, notes)"),
    (2025, 2025, "2025 (transcripts)"), (2026, 2026, "2026 (provisional)"),
]
SAMPLE_ERAS = [(1950, 1959, "1950s"), (1970, 1979, "1970s"), (1990, 1999, "1990s"),
               (2000, 2009, "2000s"), (2015, 2015, "2015"), (2024, 2024, "2024"),
               (2025, 2025, "2025")]

RULE_DESCRIPTIONS = {
    "bom": "Byte-order mark at file start",
    "crlf": "CRLF line endings normalised to LF",
    "cr_only": "Bare CR line endings normalised to LF (CR-only files)",
    "unicode_space": "Non-breaking and other Unicode spaces replaced by a space",
    "invisible_char": "Zero-width characters and soft hyphens removed",
    "ligature_char": "Ligature characters (U+FB00-FB06) expanded",
    "mojibake": "UTF-8 mojibake repaired from an explicit map",
    "bracket_ref": "Editorial meeting and document references ([277th meeting], (144th meeting), "
                   "[resolution ...], damaged brackets)",
    "see_ref": "Cross-references such as (see A/73/PV.6)",
    "doc_ref": "Parenthetical document symbols, resolution numbers and (Official Records ...) "
               "citations",
    "footnote": "Footnote lines (2 See Official Records of ...)",
    "watermark": "Scanning watermark (Digitized by Dag Hammarskjold Library)",
    "other_speaker": "Other speakers' text cut (presiding officer, another delegation)",
    "speaker_label": "The speaker's own attribution label (Mr. X (Country):)",
    "record_note": "Verbatim-record boilerplate inside the text (This record contains ...)",
    "spoke_in": "Interpretation notes such as (spoke in French)",
    "applause": "Applause and laughter notes",
    "markdown": "Markdown emphasis and headers",
    "bullet": "List bullets at line start",
    "title_line": "Unmarked heading lines kept with the paragraph they introduce",
    "ligature_loss": "Lost PDF ligatures repaired, dictionary-checked (IRN/KNA 2024)",
    "modem": "OCR 'modem' corrected to 'modern' in adjective contexts",
    "not_sign": "'¬' used as a hyphen",
    "prefix_digit": "Space after a prefix hyphen removed before a digit (post- 2015)",
    "one_for_i": "OCR '1' for the pronoun 'I' before a verb (1946-1991)",
    "disfluency": "Speech-to-text disfluencies (uh, um)",
    "presiding_intro": "Presiding-officer introduction (and a repeated name and title) removed "
                       "(transcripts)",
    "transcript_caption": "All-caps caption text at the start of a transcript",
    "presiding_closing": "Presiding-officer closing sentences removed (transcripts)",
    "form_feed": "Form feeds (page breaks)",
    "page_number": "Bare page-number lines",
    "page_header": "Job-number, document-symbol and session running-head page headers",
    "separator": "Separator lines (---, ***, * * *)",
    "para_number": "Paragraph numbers at paragraph start",
    "stray_punct": "Stray punctuation at paragraph start",
    "hyphen_rejoined": "Line-break hyphenation rejoined to the closed form",
    "hyphen_kept": "Line-break hyphen kept (compound more frequent or capitalised)",
    "hyphen_suspended": "Suspended hyphen kept with its space (inter- and intra-State)",
    "ngram_loop": "Repeated n-gram loops collapsed to one copy",
    "ngram_loop_words": "Words removed by n-gram loop collapsing",
}

PRESIDING_PHRASES = re.compile(
    r"will (?:now )?hear (?:an|and) address|request (?:the )?protocol|"
    r"invite (?:him|her) to address the (?:General )?Assembly|"
    r"on behalf of the (?:General )?Assembly,? I (?:wish to )?thank|I now give the floor to|"
    r"I now invite (?:His|Her) (?:Excellency|Majesty|Highness)|"
    r"thank (?:you )?(?:very much )?on behalf of the (?:General )?Assembly|"
    r"I thank (?:on behalf of the (?:General )?Assembly )?(?:His|Her) (?:Excellency|Highness|Majesty),|"
    r"we have (?:thus )?heard the last speaker|order in the hall",
    re.I)
_MEETING_RESIDUE = r"\d{1,4}(?:st|nd|rd|th)\s+(?:plenary\s+)?meeting"
RESIDUE_PATTERNS = {
    "job number": r"\b\d{2}-\d{5}\b",
    "PV document symbol": r"\bA/\d{1,2}/PV\.",
    "(see ...)": r"\(\s*see\b",
    "bracket with digits (balanced or not)": r"\[[^\[\]\n]{0,200}\d|\d[^\[\]\n]{0,40}\]",
    "meeting reference in brackets or parentheses":
        rf"[\[({{]\s*{_MEETING_RESIDUE}|{_MEETING_RESIDUE}\s*[\])}}]",
    "(Official Records ...) or footnote": r"Official Records of the|(?:^|\n)\d{1,2}\s+See\s+[A-Z]",
    "scanning watermark": r"Digitized by",
    "session running head (1993-1996)":
        r"General Assembly\s*-\s*[A-Z][a-z]+(?:-[a-z]+)?(?:th|st|nd|rd) session"
        r"|[A-Z][a-z]+(?:-[a-z]+)?(?:th|st|nd|rd) session\s*-?\s*\d{1,2} [A-Z][a-z]+ [l1]9\d\d"
        r"|General Assembly \d{1,3}(?:st|nd|rd|th) plenary meeting",
    "other speaker's attribution":
        r"(?:^|\n)(?:\d{1,3}\.\s*)?The (?:Acting )?(?:PRESIDENT\b[^:\n]{0,40}"
        r"|President(?: \((?:interpretation|translated) from \w+\))?\s?)[:;]"
        r"|(?:^|\n)(?:Mr|Mrs|Ms)\.? [A-Z]{3,}[A-Z' -]* \([A-Z][^()\n]{2,60}\)\s*[:;(]",
    "(spoke in ...)": r"\(spoke in",
    "paragraph number at paragraph start": r"(?:^|\n)\d{1,3}\.(?:\s|$)",
    "letter-hyphen-space-digit (post- 2015)": r"\b[A-Za-z]{1,5}- \d",
    "mojibake": "â€|Ã[©¨ª´±¼¶¤§³¡º\u00ad]|[A-Za-z]â(?:s\\b|[A-Z])|\ufffd",
    "not sign": r"¬",
    "form feed": r"\x0c",
    "modem": r"\bmodem\b",
}


def _md_table(df: pd.DataFrame, floatfmt: str = "{:.1f}") -> str:
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for row in df.itertuples(index=False):
        cells = []
        for v in row:
            if isinstance(v, (float, np.floating)):
                cells.append(floatfmt.format(v))
            else:
                cells.append(str(v).replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _era(year: int, eras=ERAS) -> str | None:
    for first, last, label in eras:
        if first <= year <= last:
            return label
    return None


def _short(text: str, n: int = 200) -> str:
    text = text.replace("\n", " / ")
    return text if len(text) <= n else text[:n] + " ..."


def write_report(path: Path, speeches: pd.DataFrame, fragments: pd.DataFrame,
                 speech_counts: dict, removed: list, vocab: clean.Vocab, runtime: float,
                 short_lines: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260926)
    fr = fragments.copy()
    fr["era"] = fr["year"].map(_era)
    sp = speeches.copy()
    sp["era"] = sp["year"].map(_era)
    out = []
    w = out.append

    w("# Corpus preparation report\n")
    w(f"Generated {datetime.now():%Y-%m-%d %H:%M} by `uv run python -m pipeline.prepare` "
      f"in {runtime / 60:.1f} minutes.\n")
    by_source = sp.groupby("source").size().to_dict()
    w(f"- Speeches: {len(sp):,} ({', '.join(f'{k}: {v:,}' for k, v in by_source.items())})")
    w(f"- Fragments: {len(fr):,}; ceremonial: {int(fr.is_ceremonial.sum()):,} "
      f"({fr.is_ceremonial.mean():.1%})")
    w(f"- Words: {int(sp.n_words.sum()):,} in speeches (raw: {int(sp.raw_words.sum()):,}); "
      f"tokens (Harrier, no special tokens): {int(sp.n_tokens.sum()):,} in speeches, "
      f"{int(fr.n_tokens.sum()):,} in fragments")
    w(f"- Longest speech: {sp.loc[sp.n_tokens.idxmax(), 'speech_id']} "
      f"({int(sp.n_tokens.max()):,} tokens)")
    w(f"- Layouts: {', '.join(f'{k}: {v:,}' for k, v in sp.layout.value_counts().items())} "
      f"('tidy' = taken from the agents' tidy copy in data/tidy/TXT; all others are cleaned "
      f"from the source files here)")
    w(f"- Fragment words: median {fr.n_words.median():.0f}, "
      f"p10 {fr.n_words.quantile(.1):.0f}, p90 {fr.n_words.quantile(.9):.0f}; "
      f"fragment tokens: median {fr.n_tokens.median():.0f}, max {int(fr.n_tokens.max()):,}\n")

    # Counts per year.
    w("## Counts per year\n")
    per_year = sp.groupby("year").agg(speeches=("speech_id", "size"),
                                       fragments=("n_fragments", "sum"),
                                       words=("n_words", "sum"), tokens=("n_tokens", "sum"))
    per_year["fragments per speech"] = per_year.fragments / per_year.speeches
    per_year["tidy copies"] = sp.assign(t=sp.layout == "tidy").groupby("year").t.sum()
    cer = fr.groupby("year").is_ceremonial.mean() * 100
    per_year["ceremonial %"] = cer
    w(_md_table(per_year.reset_index()) + "\n")

    # Words per fragment by era.
    w("## Words per fragment by era\n")
    rows = []
    for _, _, label in ERAS:
        x = fr.loc[fr.era == label, "n_words"]
        if len(x) == 0:
            continue
        rows.append({"era": label, "fragments": len(x), "min": int(x.min()),
                     "p10": x.quantile(.1), "p25": x.quantile(.25), "median": x.median(),
                     "p75": x.quantile(.75), "p90": x.quantile(.9), "max": int(x.max()),
                     "% <60": (x < 60).mean() * 100, "% >260": (x > 260).mean() * 100})
    w(_md_table(pd.DataFrame(rows), "{:.0f}") + "\n")

    # Paragraph method per year.
    w("## Paragraph method per year (share of fragments, %)\n")
    pm = pd.crosstab(fr.year, fr.para_method, normalize="index") * 100
    pm = pm.reindex(columns=["line", "rebuilt", "notes", "sentence_pack", "tidy"], fill_value=0)
    w(_md_table(pm.reset_index(), "{:.0f}") + "\n")

    # Ceremonial share by era.
    w("## Ceremonial fragments by era\n")
    rows = []
    for _, _, label in ERAS:
        x = fr[fr.era == label]
        if len(x) == 0:
            continue
        per_speech = x.groupby("speech_id").is_ceremonial.any()
        rows.append({"era": label, "fragments": len(x), "ceremonial": int(x.is_ceremonial.sum()),
                     "% fragments": x.is_ceremonial.mean() * 100,
                     "% words": x.loc[x.is_ceremonial, "n_words"].sum() / x.n_words.sum() * 100,
                     "% speeches with one": per_speech.mean() * 100})
    w(_md_table(pd.DataFrame(rows)) + "\n")
    w(ceremonial_agreement(fr, sp) + "\n")

    # Cleaning rules.
    w("## Replacements per cleaning rule\n")
    total, files = Counter(), Counter()
    for counts in speech_counts.values():
        for rule, n in counts.items():
            total[rule] += n
            files[rule] += n > 0
    rows = [{"rule": r, "description": RULE_DESCRIPTIONS.get(r, ""), "replacements": total[r],
             "files": files[r]} for r in RULE_DESCRIPTIONS if r in total]
    rows += [{"rule": r, "description": "", "replacements": total[r], "files": files[r]}
             for r in sorted(total) if r not in RULE_DESCRIPTIONS]
    w(_md_table(pd.DataFrame(rows)) + "\n")

    decisions = vocab.decisions
    rejoined = [(k, n) for k, n in decisions.most_common() if k[0] != k[1]][:20]
    kept = [(k, n) for k, n in decisions.most_common() if k[0] == k[1]][:20]
    w("Most frequent line-break hyphenation decisions (rejoined / kept):\n")
    w("- Rejoined: " + ", ".join(f"{h} -> {c} ({n})" for (h, c), n in rejoined))
    w("- Kept: " + ", ".join(f"{h} ({n})" for (h, _), n in kept) + "\n")

    if short_lines:
        w(recurring_lines(short_lines, sp.groupby("year").size().to_dict()) + "\n")

    others = [r for r in removed if r[1] == "other_speaker"]
    w(f"Other speakers' text removed from source files ({len(others)} cuts):\n")
    for sid, _, snippet in others:
        w(f"- {sid}: \"{_short(snippet, 200)}\"")
    w("")

    loops = [r for r in removed if "gram" in r[1]]
    w(f"N-gram loops collapsed ({len(loops)}):\n")
    for sid, kind, snippet in loops[:40]:
        w(f"- {sid}: {kind}: \"{_short(snippet, 240)}\"")
    w("")

    # Speakers.
    w("## Speaker metadata\n")
    sp["matched"] = sp.speaker_rows.notna()
    rows = []
    for _, _, label in ERAS:
        x = sp[sp.era == label]
        if len(x):
            row = {"era": label, "speeches": len(x), "% matched": x.matched.mean() * 100}
            row.update({c: int((x.post_category == c).sum()) for c in
                        ["head_of_state", "head_of_government", "deputy", "foreign_minister",
                         "other_minister", "ambassador", "other", "unknown"]})
            rows.append(row)
    w(_md_table(pd.DataFrame(rows)) + "\n")
    w("Most frequent posts per category (so that a skewed category stands out):\n")
    for cat in POST_CATEGORIES:
        posts = sp.loc[sp.post_category == cat, "speaker_post"].value_counts().head(8)
        if len(posts):
            w(f"- {cat}: " + "; ".join(f"{p} ({n})" for p, n in posts.items()))
    w("")
    unmatched = sp.loc[~sp.matched, "speech_id"].tolist()
    w(f"Speeches without a speaker row ({len(unmatched)}): {', '.join(unmatched) or 'none'}\n")
    multi = sp.loc[sp.speaker_rows.fillna(1) > 1, ["speech_id", "speaker_name"]]
    w(f"Keys with two speaker rows ({len(multi)}; post_category set to unknown unless the "
      f"rows agree): " + "; ".join(f"{a} ({b})" for a, b in multi.itertuples(index=False)) + "\n")

    # Longest and shortest fragments.
    w("## 20 longest fragments\n")
    cols = ["frag_id", "speech_id", "seq", "n_words", "n_tokens", "para_method"]
    x = fr.nlargest(20, "n_words")[cols + ["text"]].copy()
    x["text"] = x["text"].map(_short)
    w(_md_table(x) + "\n")
    w("## 20 shortest fragments\n")
    x = fr.nsmallest(20, "n_words")[cols + ["text"]].copy()
    x["text"] = x["text"].map(_short)
    w(_md_table(x) + "\n")

    # Random samples.
    w("## Random fragments by era (full text)\n")
    for first, last, label in SAMPLE_ERAS:
        pool = fr.index[(fr.year >= first) & (fr.year <= last)].tolist()
        if not pool:
            continue
        w(f"### {label}\n")
        for i in sorted(rng.sample(pool, min(10, len(pool)))):
            r = fr.loc[i]
            flag = ", ceremonial" if r.is_ceremonial else ""
            w(f"**{r.speech_id} #{r.seq}** ({r.n_words} words, {r.para_method}{flag})\n")
            w("```text\n" + r.text + "\n```\n")

    # Ceremonial samples.
    w("### Sample of fragments flagged ceremonial\n")
    pool = fr.index[fr.is_ceremonial].tolist()
    for i in sorted(rng.sample(pool, min(10, len(pool)))):
        r = fr.loc[i]
        w(f"- **{r.speech_id} #{r.seq}**: {_short(r.text, 400)}")
    w("")

    # Anomalies.
    w("## Anomalies and checks\n")
    multi_frag = fr.groupby("speech_id").seq.transform("size") > 1
    short = fr[(fr.n_words < segment.MIN_WORDS) & multi_frag]
    w(f"- Fragments under {segment.MIN_WORDS} words in multi-fragment speeches: {len(short)}")
    longf = fr[fr.n_words > segment.MAX_WORDS]
    w(f"- Fragments over {segment.MAX_WORDS} words (no cut between sentences keeps every piece "
      f"within {segment.MIN_WORDS}-{segment.MAX_WORDS} words): "
      f"{len(longf)}" + (": " + ", ".join(f"{a} #{b} ({c})" for a, b, c in
                                           longf[["speech_id", "seq", "n_words"]].head(30)
                                           .itertuples(index=False)) if len(longf) else ""))
    tiny = sp[sp.n_words < segment.MIN_WORDS]
    w(f"- Speeches under {segment.MIN_WORDS} words: {len(tiny)}" +
      (": " + ", ".join(f"{a} ({b})" for a, b in tiny[["speech_id", "n_words"]]
                        .itertuples(index=False)) if len(tiny) else ""))
    w(f"- Speeches without fragments: {int((sp.n_fragments == 0).sum())}; empty fragments: "
      f"{int((fr.n_words == 0).sum())}")
    ratio = sp.n_words / sp.raw_words.clip(lower=1)
    low = sp.assign(ratio=ratio)[ratio < 0.9].sort_values("ratio")
    w(f"- Speeches keeping under 90% of their raw words: {len(low)}" +
      (": " + ", ".join(f"{a} ({b:.0%})" for a, b in low[["speech_id", "ratio"]].head(40)
                        .itertuples(index=False)) if len(low) else ""))
    single = sp[(sp.layout == "single") & (sp.year < 2025)]
    w(f"- Single-line (sentence-packed) speeches before 2025: {len(single)}" +
      (": " + ", ".join(single.speech_id) if len(single) else ""))
    caps = sp[sp.text_clean.map(lambda t: sum(c.isupper() for c in t) /
                                max(1, sum(c.isalpha() for c in t)) > 0.5)]
    w(f"- Speeches mostly in capital letters (kept as is): {len(caps)}" +
      (": " + ", ".join(caps.speech_id) if len(caps) else ""))
    for name, pat in RESIDUE_PATTERNS.items():
        hits = sp[sp.text_clean.str.contains(pat, regex=True)]
        w(f"- Residual '{name}': {len(hits)} speeches" +
          (": " + ", ".join(hits.speech_id.head(15)) + (" ..." if len(hits) > 15 else "")
           if len(hits) else ""))
    tr = sp[(sp.year >= 2025) & (sp.layout != "tidy")]  # tidy copies: the agents removed it
    no_intro = [s for s in tr.speech_id if speech_counts[s]["presiding_intro"] == 0]
    w(f"- Transcripts cleaned here (not from a tidy copy): {len(tr)}; without a detected "
      f"presiding-officer introduction: {len(no_intro)}" +
      (": " + ", ".join(no_intro) if no_intro else ""))
    left = fr[(fr.year >= 2025) & fr.text.str.contains(PRESIDING_PHRASES)]
    w(f"- Transcript fragments still containing presiding-officer phrases: {len(left)}" +
      (": " + ", ".join(f"{a} #{b}" for a, b in left[["speech_id", "seq"]].itertuples(index=False))
       if len(left) else ""))
    w("")
    intros = [r for r in removed if r[1] in ("intro", "name", "caption", "closing")]
    w(f"Examples of removed presiding-officer text ({len(intros)} removals; first 25):\n")
    for sid, kind, snippet in intros[:25]:
        w(f"- {sid} ({kind}): \"{_short(snippet, 300)}\"")
    w("")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def ceremonial_agreement(fr: pd.DataFrame, sp: pd.DataFrame) -> str:
    """Rule-based flag against the agents' ceremonial labels of the tidy copies.

    The rule-based flag decides for speeches without a labelled tidy copy; the
    labelled ones estimate its precision and recall.
    """
    labelled = set(sp.loc[sp.labelled, "speech_id"])
    x = fr[fr.speech_id.isin(labelled)]
    if x.empty:
        return "No tidy copies with ceremonial labels yet: precision and recall not estimated."
    edge = (x.seq < segment.CEREMONIAL_HEAD) | (
        x.seq >= x.groupby("speech_id").seq.transform("size") - segment.CEREMONIAL_TAIL)
    tp = int((x.regex_ceremonial & x.is_ceremonial).sum())
    flagged, true_all, true_edge = int(x.regex_ceremonial.sum()), int(x.is_ceremonial.sum()), int(
        (x.is_ceremonial & edge).sum())
    return (f"Rule-based ceremonial flag against the agents' labels ({len(labelled):,} labelled "
            f"tidy copies, {len(x):,} fragments): precision {tp / max(flagged, 1):.2f} "
            f"({tp}/{flagged}); recall {tp / max(true_edge, 1):.2f} among fragments in the "
            f"first {segment.CEREMONIAL_HEAD} and last {segment.CEREMONIAL_TAIL} ({tp}/{true_edge}), "
            f"{tp / max(true_all, 1):.2f} overall ({tp}/{true_all}). For these speeches "
            f"is_ceremonial comes from the labels.")


def recurring_lines(short_lines: dict, n_speeches: dict, top: int = 5) -> str:
    """Short kept lines (digits masked as N) that recur in many files of one year:
    page furniture that no rule removed shows up here."""
    rows = []
    for year in sorted(short_lines):
        floor = max(5, 0.05 * n_speeches.get(year, 0))
        common = [(line, n) for line, n in short_lines[year].most_common(top) if n >= floor]
        rows += [{"year": year, "line (digits as N)": line, "files": n} for line, n in common]
    if not rows:
        return "Recurring short lines: none in at least 5% of a year's files."
    return ("Short lines without final punctuation that recur in at least 5% of a year's files "
            "(check for page furniture):\n\n" + _md_table(pd.DataFrame(rows)))


def main() -> int:
    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
