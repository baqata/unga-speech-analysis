"""Tidy copy of the corpus: agents decide drops, paragraphs and small fixes; this module applies them.

The speaker's text is never regenerated. Every output word comes from the source units, changed only
by the documented pre-strips, line-end dehyphenation and validated fixes. Rules for the agents live in
data/tidy/INSTRUCTIONS.md; per-year assignments in data/tidy/work/assignments/<year>.md.

    uv run python -m pipeline.tidy plan [--year Y]
    uv run python -m pipeline.tidy status --year Y
    uv run python -m pipeline.tidy apply --year Y | --file PATH [PATH ...]
    uv run python -m pipeline.tidy show ID
    uv run python -m pipeline.tidy audit-view ID [ID ...] --out PATH
    uv run python -m pipeline.tidy validate
    uv run python -m pipeline.tidy report
"""
import argparse
import csv
import difflib
import hashlib
import json
import re
import statistics
import sys
import unicodedata
from collections import Counter
from pathlib import Path

from pipeline.config import CORPUS_TXT, META, OFFICIAL, PROVISIONAL, ROOT

UNITIZER_VERSION = 1

TIDY = ROOT / "data" / "tidy"
WORK = TIDY / "work"
UNITS_DIR = WORK / "units"
VIEWS = WORK / "views"
DRAFTS = WORK / "decisions"
ASSIGN = WORK / "assignments"
VOCAB = WORK / "vocab.json"
OUT_TXT = TIDY / "TXT"
OUT_DEC = TIDY / "decisions"
MANIFEST = TIDY / "manifest.json"

NAME_RE = re.compile(r"^([A-Z]{2,4})_(\d{2})_(\d{4})\.txt$")
PAGE_CHARS = 75_000
PAGE_LINES = 1_900
WRAP_CHARS = 1_800
SPLIT_WORDS = 45  # lines longer than this are split into sentence units

DROP_REASONS = {"presider", "procedural", "header_footer", "interpretation_note", "heading",
                "other_speaker", "repeat", "noise"}
FIX_REASONS = {"hyphen", "spacing", "split_word", "merged_word", "ocr", "encoding", "asr_name",
               "asr_term", "interp", "slip", "markup", "label"}
FLAGS = {"truncated_start", "truncated_end", "gap_suspected", "wrong_country", "not_english",
         "garbled", "mixed_speakers", "third_person_summary", "duplicate_speech"}
MAX_FIXES = 150
ASR_NAME_WORDS = 4  # a misheard name or term, or an interpreter's or speaker's wrong word, may be replaced freely when both sides are this short
SHORT_WORDS = 60  # fewer than 1 in 10 body paragraphs may be shorter (see INSTRUCTIONS.md, rule 3)

# ---------------------------------------------------------------- normalisation and pre-strips

MOJIBAKE = {
    "â€”": "—", "â€“": "–", "â€œ": "“", "â€\x9d": "”", "â€™": "’", "â€˜": "‘", "â€¦": "…",
    "Ã©": "é", "Ã´": "ô", "Ã±": "ñ", "Ã¼": "ü", "Ã\xad": "í", "Ãª": "ê", "Ã³": "ó", "Ã¡": "á",
    "Ã\xa0": "à", "¬": "-",
}
INLINE = {
    "meeting_ref": re.compile(r"[ \t]*\[\d+(?:st|nd|rd|th)\s+(?:plenary\s+)?meeting"
                              r"(?:,\s*paras?\.\s*[\d\s,and]+\.?)?\]"),
    "see_ref": re.compile(r"[ \t]*\((?:[Ss]ee(?: also)?) A/\d+/PV\.\s?\d+\)"),
    "language_note": re.compile(r"[ \t]*\((?:spoke|continued) in [^()]{1,90}\)"
                                r"|[ \t]*\([Ii]nterpretation from [^()]{1,40}\)"),
    "applause": re.compile(r"[ \t]*\([Aa]pplause\.?\)"),
    "md_bold": re.compile(r"\*\*"),
}
LINE_DROP = {
    "page_number": re.compile(r"^\d{1,3}$"),
    "job_number": re.compile(r"^(?:\d{1,3}\s+)?\d{2}-\d{5}(?:\s*\d{1,3})?(?:\s*\(E\))?$"),
    "page_header": re.compile(r"^\d{1,3}/\d{1,3}\s+\d{2}-\d{5}$|^\d{2}-\d{5}\s+\d{1,3}/\d{1,3}$"
                              r"|^(?:\d{2}/\d{2}/\d{4}\s+)?A/\d{2,3}/PV\.\d{1,3}(?:\s+\d{2}/\d{2}/\d{4})?$"),
    "md_rule": re.compile(r"^(?:-{3,}|\*{3,}|_{3,})$"),
}
PARNUM = re.compile(r"^(\d{1,3})\.\t")
MD_HEADER = re.compile(r"^#{1,6}\s+")
SPACES = re.compile(r"[ \t  -   　]+")
ZERO_WIDTH = re.compile(r"[​‌‍﻿]")


def is_paragraph_numbering(lines: list[str]) -> bool:
    """Meeting-wide paragraph numbers ("66.\\t") vs. a short numbered list inside a speech."""
    nums = [int(m.group(1)) for m in map(PARNUM.match, lines) if m]
    nonempty = sum(1 for ln in lines if ln.strip())
    if len(nums) < 3 or not nonempty:
        return False
    steps = sum(1 for a, b in zip(nums, nums[1:]) if 0 < b - a <= 2)
    return len(nums) >= 0.5 * nonempty and steps >= 0.7 * (len(nums) - 1)


def normalise(raw: str) -> tuple[list[str], Counter]:
    """Return cleaned source lines ('' marks a blank line) and counts of what was removed."""
    removed = Counter()
    text = raw.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
    text = unicodedata.normalize("NFC", text)
    for bad, good in MOJIBAKE.items():
        n = text.count(bad)
        if n:
            removed["encoding"] += n
            text = text.replace(bad, good)
    for name, pat in INLINE.items():
        text, n = pat.subn("", text)
        removed[name] += n
    lines = text.split("\n")
    strip_numbers = is_paragraph_numbering(lines)
    out = []
    for line in lines:
        if strip_numbers and PARNUM.match(line):
            line = PARNUM.sub("", line)
            removed["paragraph_number"] += 1
        line = SPACES.sub(" ", ZERO_WIDTH.sub("", line)).strip()
        if MD_HEADER.match(line):
            line = MD_HEADER.sub("", line)
            removed["md_header_mark"] += 1
        hit = next((k for k, p in LINE_DROP.items() if p.match(line)), None)
        if hit:
            removed[hit] += 1
            line = ""
        out.append(line)
    return out, removed


# ---------------------------------------------------------------- units

ABBREV = {"mr", "mrs", "ms", "dr", "st", "no", "nos", "art", "arts", "messrs", "mt", "gen", "col",
          "lt", "sr", "jr", "prof", "rev", "hon", "vs", "cf", "etc", "e.g", "i.e", "jan", "feb", "mar",
          "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "p", "pp", "para", "paras",
          "vol", "fig", "ltd", "co", "inc", "corp", "op", "cit", "ibid", "al", "approx", "dept", "govt",
          "h.e", "u.s", "u.k", "u.n", "u.s.s.r", "s.a", "rep", "sen", "gov", "amb", "excl", "incl"}
SENT_END = re.compile(r"[.!?…][\"”’')\]]*\s+(?=[\"“‘(\[]?[A-Z0-9])")


def split_sentences(line: str) -> list[str]:
    out, start = [], 0
    for m in SENT_END.finditer(line):
        before = line[start:m.start() + 1].rstrip()
        last = before.split()[-1] if before.split() else ""
        token = last.rstrip(".").lstrip("(\"“‘").lower()
        if line[m.start()] == "." and (token in ABBREV or re.fullmatch(r"[a-z]", token)):
            continue
        out.append(line[start:m.end()].strip())
        start = m.end()
    tail = line[start:].strip()
    if tail:
        out.append(tail)
    return out


def layout_of(lines: list[str]) -> str:
    content = [ln for ln in lines if ln]
    if len(content) <= 1:
        return "single"
    words = [len(ln.split()) for ln in content]
    ends = sum(1 for ln in content if re.search(r"[.!?:;…\"”’)]$", ln)) / len(content)
    if len(content) >= 30 and statistics.median(words) < 20 and ends < 0.4:
        return "wrapped"
    return "lines"


def unitize(raw: str) -> dict:
    lines, removed = normalise(raw)
    layout = layout_of(lines)
    units, blank_before, line_no = [], False, 0
    for i, line in enumerate(lines):
        if not line:
            blank_before = bool(units)
            continue
        pieces = split_sentences(line) if len(line.split()) > SPLIT_WORDS else [line]
        for k, piece in enumerate(pieces):
            units.append({"t": piece, "nl": k == 0 and bool(units), "bl": k == 0 and blank_before,
                          "ln": i + 1})
        blank_before = False
    return {"layout": layout, "units": units, "prestrip": dict(+removed)}


# ---------------------------------------------------------------- sources

def sources() -> dict[str, dict]:
    """Speech files by id; a session split from the verbatim records (data/official) replaces the corpus
    folder of that session, as in pipeline.prepare.list_sources."""
    found = {}
    official = {p.name for p in OFFICIAL.glob("Session *") if p.is_dir()}
    for base, source in ((CORPUS_TXT, "ungdc_v14"), (OFFICIAL, "un_records"), (PROVISIONAL, "provisional")):
        if not base.exists():
            continue
        for path in sorted(base.glob("*/*.txt")):
            m = NAME_RE.match(path.name)
            if not m or (base == CORPUS_TXT and path.parent.name in official):
                continue
            found[path.stem] = {"id": path.stem, "iso3": m.group(1), "session": int(m.group(2)),
                                "year": int(m.group(3)), "folder": path.parent.name,
                                "path": str(path.relative_to(ROOT)), "source": source}
    return found


def country_names() -> dict[str, str]:
    names = {}
    path = META / "countries.csv"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                names[row["iso3"]] = row.get("name_en") or row["iso3"]
    return names


def load_units(sid: str, meta: dict) -> dict:
    """Unit cache keyed by source sha1 and unitizer version (rebuilt when either changes)."""
    raw_bytes = (ROOT / meta["path"]).read_bytes()
    sha1 = hashlib.sha1(raw_bytes).hexdigest()
    cache = UNITS_DIR / f"{sid}.json"
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data["sha1"] == sha1 and data["unitizer_version"] == UNITIZER_VERSION:
            return data
    data = unitize(raw_bytes.decode("utf-8", errors="replace"))
    data.update(id=sid, sha1=sha1, unitizer_version=UNITIZER_VERSION)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


# ---------------------------------------------------------------- views

def render(sid: str, meta: dict, data: dict, names: dict, decision: dict | None = None) -> list[str]:
    """Numbered unit lines for one speech; with a decision, drops/paragraphs/fixes are shown inline."""
    units = data["units"]
    words = sum(len(u["t"].split()) for u in units)
    pre = ", ".join(f"{k} {v}" for k, v in sorted(data["prestrip"].items())) or "none"
    head = (f"=== {sid} | {names.get(meta['iso3'], meta['iso3'])} | {meta['year']} | "
            f"layout: {data['layout']} | units 0-{len(units) - 1} | {words:,} words | tool removed: {pre}")
    out = [head]
    if decision:
        st = decision.get("stats", {})
        out.append(f"    decision: flags={decision.get('flags', [])} note={decision.get('note', '')!r} "
                   f"retention={st.get('retention')} paragraphs={st.get('n_paragraphs')} "
                   f"warnings={st.get('warnings', [])}")
    dropped = {}
    fixes = {}
    paras, cer = set(), set()
    if decision:
        for a, b, reason in decision["drop"]:
            for u in range(a, b + 1):
                dropped[u] = reason
        paras, cer = set(decision["para"]), set(decision["cer"])
        for u, old, new, _ in decision["fix"]:
            fixes.setdefault(u, []).append((old, new))
    pno = 0
    for i, u in enumerate(units):
        mark = "¶" if u["bl"] else ("↵" if u["nl"] and data["layout"] != "wrapped" else "")
        text = u["t"]
        for old, new in fixes.get(i, []):
            text = text.replace(old, f"{{{old}→{new}}}", 1)
        prefix = ""
        if i in dropped:
            prefix = f"[DROP {dropped[i]}] "
        elif i in paras:
            pno += 1
            prefix = f"¶P{pno}{' (cer)' if i in cer else ''} "
        line = f"{i}{mark} {prefix}{text}"
        while len(line) > WRAP_CHARS:
            cut = line.rfind(" ", 0, WRAP_CHARS)
            cut = cut if cut > 0 else WRAP_CHARS
            out.append(line[:cut])
            line = "   ⋯ " + line[cut:].lstrip()
        out.append(line)
    out.append("")
    return out


def paginate(blocks: list[tuple[str, list[str]]]) -> list[tuple[list[str], list[str]]]:
    """Group speech blocks into pages; a speech larger than a page continues on the next ones."""
    pages, cur, ids, size = [], [], [], 0
    for sid, lines in blocks:
        n = sum(len(ln) + 1 for ln in lines)
        if cur and (size + n > PAGE_CHARS or len(cur) + len(lines) > PAGE_LINES):
            pages.append((cur, ids))
            cur, ids, size = [], [], 0
        if n > PAGE_CHARS or len(lines) > PAGE_LINES:
            chunk, csize, first = [], 0, True
            for ln in lines:
                if chunk and (csize + len(ln) + 1 > PAGE_CHARS or len(chunk) >= PAGE_LINES):
                    pages.append((chunk, [sid]))
                    chunk, csize, first = [f"=== {sid} (continued)"], 0, False
                chunk.append(ln)
                csize += len(ln) + 1
            cur, ids, size = chunk, [sid], csize
            continue
        cur += lines
        ids.append(sid)
        size += n
    if cur:
        pages.append((cur, ids))
    return pages


# ---------------------------------------------------------------- plan

def build_vocab(all_sources: dict) -> Counter:
    vocab = Counter()
    word = re.compile(r"[a-z]+(?:-[a-z]+)?")
    for sid, meta in all_sources.items():
        data = load_units(sid, meta)
        for u in data["units"]:
            vocab.update(word.findall(u["t"].lower()))
    return vocab


def cmd_plan(args) -> int:
    srcs = sources()
    names = country_names()
    years = sorted({m["year"] for m in srcs.values()})
    if args.year:
        years = [args.year]
    if not VOCAB.exists() or args.vocab:
        vocab = build_vocab(srcs)
        VOCAB.parent.mkdir(parents=True, exist_ok=True)
        VOCAB.write_text(json.dumps({k: v for k, v in vocab.items() if v >= 2}), encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    totals = Counter()
    for year in years:
        ids = sorted(s for s, m in srcs.items() if m["year"] == year)
        blocks, tokens, units = [], 0, 0
        for sid in ids:
            data = load_units(sid, srcs[sid])
            lines = render(sid, srcs[sid], data, names)
            blocks.append((sid, lines))
            tokens += sum(len(ln) for ln in lines) // 4.2
            units += len(data["units"])
        vdir = VIEWS / str(year)
        if vdir.exists():
            for old in vdir.glob("p*.md"):
                old.unlink()
        vdir.mkdir(parents=True, exist_ok=True)
        pages = paginate(blocks)
        page_rows = []
        for k, (lines, pids) in enumerate(pages, 1):
            path = vdir / f"p{k:02d}.md"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            page_rows.append({"page": f"p{k:02d}", "view": str(path.relative_to(ROOT)),
                              "decisions": str((DRAFTS / str(year) / f"p{k:02d}.jsonl").relative_to(ROOT)),
                              "speeches": pids})
        folder = srcs[ids[0]]["folder"]
        manifest[str(year)] = {
            "year": year, "folder": folder, "n_speeches": len(ids), "n_units": units,
            "view_tokens": int(tokens), "speeches": ids, "pages": page_rows,
            "outputs": {"tidy_text": str((OUT_TXT / folder).relative_to(ROOT)),
                        "decisions": str((OUT_DEC / folder).relative_to(ROOT))},
        }
        write_assignment(manifest[str(year)])
        totals.update(speeches=len(ids), units=units, tokens=int(tokens), pages=len(pages))
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(dict(sorted(manifest.items())), indent=1), encoding="utf-8")
    print(json.dumps({"years": len(years), **totals}))
    return 0


def write_assignment(entry: dict) -> None:
    y = entry["year"]
    rows = "\n".join(f"| {p['page']} | {p['view']} | {p['decisions']} | {p['speeches'][0]} … {p['speeches'][-1]} "
                     f"({len(p['speeches'])}) |" for p in entry["pages"])
    text = f"""# Assignment: year {y}

You own year {y}: {entry['n_speeches']} speeches, {len(entry['pages'])} view pages, about {entry['view_tokens']:,} tokens.
Rules and output format: data/tidy/INSTRUCTIONS.md (read it first, and again whenever unsure).

## Read and write, page by page

| page | read this view | write your decisions here | speeches |
| --- | --- | --- | --- |
{rows}

Write only the decision files listed above. Do not edit any other file.

## Commands

    uv run python -m pipeline.tidy status --year {y}      # what is done, what is pending
    uv run python -m pipeline.tidy apply --year {y}       # validate + write the tidy copies
    uv run python -m pipeline.tidy show <ID>              # one speech again, if needed

## What apply produces (your tidy copies)

- {entry['outputs']['tidy_text']}/<ID>.txt
- {entry['outputs']['decisions']}/<ID>.json
"""
    ASSIGN.mkdir(parents=True, exist_ok=True)
    (ASSIGN / f"{y}.md").write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- decisions

SENT_MARK = re.compile(r"[.,;:!?]")
ANY_MARK = re.compile(r"[^\w\s]")
WORD = re.compile(r"[^\W_]+")


def repair_problem(old: str, new: str, reason: str) -> str | None:
    """Why a repair breaks the guideline, checked word by word so extra context in `old` does not hide it."""
    if reason == "encoding":
        return None
    asr = reason in {"asr_name", "asr_term", "interp", "slip"}
    if not asr and len(SENT_MARK.findall(new)) > len(SENT_MARK.findall(old)) \
            and len(ANY_MARK.findall(new)) > len(ANY_MARK.findall(old)):
        return "adds punctuation; only a misread mark may be replaced"
    if asr and max(len(old.split()), len(new.split())) <= ASR_NAME_WORDS:
        return None  # a misheard name or term, or an interpreter's or speaker's wrong word, may be replaced freely
    wo, wn = [w.lower() for w in WORD.findall(old)], [w.lower() for w in WORD.findall(new)]
    marks_gone = len(ANY_MARK.findall(old)) - len(ANY_MARK.findall(new))  # a symbol may be a misread letter
    if len(wn) - len(wo) > max(0, marks_gone) and any(
            op == "insert" for op, *_ in difflib.SequenceMatcher(None, wo, wn).get_opcodes()):
        return "adds a word"
    ow, nw = old.split(), new.split()
    groups = [(" ".join(ow[a:b]), " ".join(nw[c:e]))
              for op, a, b, c, e in difflib.SequenceMatcher(None, ow, nw).get_opcodes() if op == "replace"]
    if any(len(x) > 4 and difflib.SequenceMatcher(None, x, y).ratio() < 0.5 for x, y in groups + [(old, new)]):
        return "looks like a rewrite, not a repair"
    return None


def validate_decision(d: dict, data: dict) -> tuple[dict, list[str], list[str]]:
    """Return (normalised decision, errors, notices)."""
    errors, notices = [], []
    n = len(data["units"])
    extra = set(d) - {"id", "drop", "para", "cer", "fix", "flags", "note"}
    if extra:
        errors.append(f"unknown keys {sorted(extra)}")
    drop, para, cer = d.get("drop", []), d.get("para", []), d.get("cer", [])
    fix, flags, note = d.get("fix", []), d.get("flags", []), d.get("note", "")
    ranges = []
    for r in drop:
        if not (isinstance(r, list) and len(r) == 3 and all(isinstance(x, int) for x in r[:2])):
            errors.append(f"drop entry {r} must be [start, end, reason]")
            continue
        a, b, reason = r
        if not 0 <= a <= b < n:
            errors.append(f"drop {r} outside units 0-{n - 1}")
        if reason not in DROP_REASONS:
            errors.append(f"drop reason {reason!r} not in {sorted(DROP_REASONS)}")
        ranges.append([a, b, reason])
    ranges.sort()
    for (a1, b1, _), (a2, b2, _) in zip(ranges, ranges[1:]):
        if a2 <= b1:
            errors.append(f"drop ranges overlap: [{a1},{b1}] and [{a2},{b2}]")
    dropped = {u for a, b, _ in ranges for u in range(a, b + 1)}
    kept = [u for u in range(n) if u not in dropped]
    if not all(isinstance(u, int) for u in para):
        errors.append("para must be a list of unit ids")
        para = []
    bad = [u for u in para if not 0 <= u < n or u in dropped]
    if bad:
        errors.append(f"para ids {bad} are dropped or out of range")
    para = sorted({u for u in para if 0 <= u < n and u not in dropped})
    if kept and (not para or para[0] != kept[0]):
        para = sorted(set(para) | {kept[0]})
        notices.append(f"added first kept unit {kept[0]} as a paragraph start")
    bad = [u for u in cer if u not in para]
    if bad:
        errors.append(f"cer ids {bad} are not paragraph starts")
    cer = sorted({u for u in cer if u in para})
    fixes = []
    if len(fix) > MAX_FIXES:
        errors.append(f"{len(fix)} fixes exceed the limit of {MAX_FIXES}")
    texts = {u: data["units"][u]["t"] for u in range(n)}
    for f in fix:
        if not (isinstance(f, list) and len(f) == 4 and isinstance(f[0], int)):
            errors.append(f"fix entry {f} must be [unit, old, new, reason]")
            continue
        u, old, new, reason = f
        if not 0 <= u < n or u in dropped:
            errors.append(f"fix on unit {u}: dropped or out of range")
            continue
        if reason not in FIX_REASONS:
            errors.append(f"fix reason {reason!r} not in {sorted(FIX_REASONS)}")
            continue
        if not old or len(old) > 80:
            errors.append(f"fix on unit {u}: old must be 1-80 characters")
            continue
        count = texts[u].count(old)
        if count != 1:
            errors.append(f"fix on unit {u}: {old!r} occurs {count} times in the unit (must be exactly once)")
            continue
        if reason == "label":
            if new != "":
                errors.append(f"fix on unit {u}: a 'label' fix removes text, so new must be \"\"")
                continue
        elif problem := repair_problem(old, new, reason):
            errors.append(f"fix on unit {u}: {old!r} -> {new!r} {problem}")
            continue
        texts[u] = texts[u].replace(old, new, 1)
        fixes.append([u, old, new, reason])
    bad = [x for x in flags if x not in FLAGS]
    if bad:
        errors.append(f"flags {bad} not in {sorted(FLAGS)}")
    norm = {"id": d.get("id"), "drop": ranges, "para": para, "cer": cer, "fix": fixes,
            "flags": sorted(set(flags) & FLAGS), "note": str(note)}
    return norm, errors, notices


PARA_NUMBER = re.compile(r"^(\d{1,3})\.(?:\s+|$)")


def numbered_units(units: list[dict], prestrip: dict | None = None) -> set[int]:
    """Units that open a source line with a paragraph number from a numbered record ("26." or "1. Madam").

    A record is numbered when the tab-form numbers were already stripped from it, or when it has a run
    of at least six (near-)consecutive line-initial numbers; a short numbered list is left alone.
    """
    cands = [(i, int(m.group(1))) for i, u in enumerate(units)
             if (u["nl"] or i == 0) and (m := PARA_NUMBER.match(u["t"]))]
    if (prestrip or {}).get("paragraph_number", 0) >= 3:
        return {i for i, _ in cands}
    nums = [n for _, n in cands]
    steps = sum(1 for a, b in zip(nums, nums[1:]) if 0 < b - a <= 2)
    return {i for i, _ in cands} if len(nums) >= 6 and steps >= 0.8 * (len(nums) - 1) else set()


def build_text(data: dict, d: dict, vocab: dict) -> list[dict]:
    """Paragraphs as [{'start': unit, 'cer': bool, 'text': str}]."""
    dropped = {u for a, b, _ in d["drop"] for u in range(a, b + 1)}
    texts = [u["t"] for u in data["units"]]
    for u, old, new, _ in d["fix"]:
        texts[u] = texts[u].replace(old, new, 1)
    for u in numbered_units(data["units"], data.get("prestrip")):
        texts[u] = PARA_NUMBER.sub("", texts[u], count=1)
    starts, cer = set(d["para"]), set(d["cer"])
    paras, carry = [], None  # carry: a paragraph start whose unit became empty moves to the next unit
    for i, unit in enumerate(data["units"]):
        if i in dropped:
            continue
        if not texts[i].strip():
            if i in starts:
                carry = i in cer
            continue
        if i in starts or carry is not None or not paras:
            paras.append({"start": i, "cer": (i in cer) if carry is None else carry, "parts": [texts[i]]})
            carry = None
            continue
        prev = paras[-1]["parts"][-1]
        cur = texts[i]
        if unit["nl"] and re.search(r"[A-Za-z]-$", prev) and re.match(r"[A-Za-z]", cur):
            w1 = re.search(r"([A-Za-z]+)-$", prev).group(1)
            w2 = re.match(r"[A-Za-z]+", cur).group(0)
            joined, hyph = (w1 + w2).lower(), f"{w1}-{w2}".lower()
            if cur[0].islower() and vocab.get(joined, 0) >= 2 and vocab.get(joined, 0) > vocab.get(hyph, 0):
                paras[-1]["parts"][-1] = prev[:-1] + cur
            else:
                paras[-1]["parts"][-1] = prev + cur
        elif unit["nl"] and re.search(r"[A-Za-z0-9]-$", prev) and re.match(r"[A-Za-z0-9]", cur):
            paras[-1]["parts"][-1] = prev + cur  # "post-" + "2015", "2016-" + "2017", "20-" + "year"
        else:
            paras[-1]["parts"].append(cur)
    return [{"start": p["start"], "cer": p["cer"], "text": tidy_spacing(strip_editorial_refs(" ".join(p["parts"])))}
            for p in paras]


_SYMBOL = (r"(?:[ASE]/(?:RES/)?[0-9A-Z][\w.]*(?:/[\w.]+)*|\d{1,4}\s*\((?:[IVXLCS\-]+|\d{4})\)"
           r"|(?<=resolution )\d{2}/\d{1,3}|(?<=resolutions )\d{2}/\d{1,3})")
_REF_BODY = (r"(?:see\s+(?:also\s+)?)?(?:(?:General Assembly |Security Council )?(?:resolutions?|decisions?)\s+)?"
             + _SYMBOL + r"(?:\s*(?:,|and)\s*(?:" + _SYMBOL + r"|\d{2}/\d{1,3}))*"
             r"(?:,\s*(?:paras?|annex|chap|sect|p)\.?(?:\s*[\w,.-]+(?:\s*\([a-z0-9]{1,3}\))?){0,6})?")
EDITORIAL_REF = re.compile(r"[ \t]*(?:\(" + _REF_BODY + r"\)|\[" + _REF_BODY + r"\])")


def strip_editorial_refs(text: str) -> str:
    """Remove parenthesised document symbols and resolution numbers inserted by record editors."""
    return EDITORIAL_REF.sub("", text)


def tidy_spacing(text: str) -> str:
    """Collapse spaces and drop a space left before punctuation (e.g. after a removed bracket)."""
    return re.sub(r" +([.,;:!?])(?=\s|$)", r"\1", SPACES.sub(" ", text)).strip()


def warnings_for(data: dict, d: dict, paras: list[dict], words_in: int, words_out: int) -> list[str]:
    warns = []
    n = len(data["units"])
    retention = words_out / words_in if words_in else 0
    if retention < 0.85:
        warns.append(f"retention {retention:.2f} < 0.85")
    for a, b, reason in d["drop"]:
        if reason in {"presider", "procedural"} and a > 0.1 * n and b < 0.9 * n:
            warns.append(f"{reason} drop [{a},{b}] in the middle of the speech")
    lengths = [len(p["text"].split()) for p in paras]
    for p, w in zip(paras, lengths):
        if w > 320:
            warns.append(f"paragraph at unit {p['start']} has {w} words")
    body = [(p["start"], w) for p, w in zip(paras[:-1], lengths) if not p["cer"]]  # the last is the closing line
    short = [str(u) for u, w in body if w < SHORT_WORDS]
    if len(short) >= 2 and len(short) > 0.1 * len(body):
        warns.append(f"{len(short)} of {len(body)} paragraphs have fewer than {SHORT_WORDS} words "
                     f"(units {', '.join(short)}); join them until fewer than 1 in 10 remain")
    if len(paras) == 1 and words_out > 300:
        warns.append(f"single paragraph of {words_out} words")
    if len(d["fix"]) > 20:
        warns.append(f"{len(d['fix'])} fixes")
    if not paras:
        warns.append("all units dropped")
    dropped = {u for a, b, _ in d["drop"] for u in range(a, b + 1)}
    if data["layout"] == "single" and n and 0 not in dropped and re.search(
            r"Assembly will|request protocol", data["units"][0]["t"]):
        warns.append("unit 0 looks like the presiding officer's introduction but is kept")
    if any("On behalf of the Assembly" in p["text"] for p in paras):
        warns.append("kept text contains 'On behalf of the Assembly'")
    return warns


def read_drafts(paths: list[Path]) -> tuple[dict, list[str]]:
    decisions, problems = {}, []
    for path in paths:
        for k, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError as e:
                problems.append(f"{path.relative_to(ROOT)}:{k}: invalid JSON ({e.msg})")
                continue
            if not isinstance(d, dict) or "id" not in d:
                problems.append(f"{path.relative_to(ROOT)}:{k}: each line must be an object with an id")
                continue
            decisions[d["id"]] = d  # later lines override earlier ones
    return decisions, problems


def apply_decisions(decisions: dict, srcs: dict, vocab: dict) -> dict[str, str]:
    status = {}
    for sid, d in decisions.items():
        if sid not in srcs:
            print(f"ERROR {sid}: unknown speech id")
            status[sid] = "error"
            continue
        meta = srcs[sid]
        data = load_units(sid, meta)
        norm, errors, notices = validate_decision(d, data)
        if errors:
            print(f"ERROR {sid}: " + "; ".join(errors))
            status[sid] = "error"
            continue
        paras = build_text(data, norm, vocab)
        words_in = sum(len(u["t"].split()) for u in data["units"])
        words_out = sum(len(p["text"].split()) for p in paras)
        warns = warnings_for(data, norm, paras, words_in, words_out)
        by_reason = Counter()
        for a, b, reason in norm["drop"]:
            by_reason[reason] += b - a + 1
        norm.update(unitizer_version=UNITIZER_VERSION, sha1=data["sha1"], layout=data["layout"],
                    stats={"n_units": len(data["units"]), "units_dropped": dict(by_reason),
                           "prestrip": data["prestrip"], "words_in": words_in, "words_out": words_out,
                           "retention": round(words_out / words_in, 4) if words_in else 0,
                           "n_paragraphs": len(paras), "paragraph_words": [len(p["text"].split()) for p in paras],
                           "warnings": warns})
        txt = OUT_TXT / meta["folder"] / f"{sid}.txt"
        dec = OUT_DEC / meta["folder"] / f"{sid}.json"
        txt.parent.mkdir(parents=True, exist_ok=True)
        dec.parent.mkdir(parents=True, exist_ok=True)
        txt.write_text("\n\n".join(p["text"] for p in paras) + "\n", encoding="utf-8")
        dec.write_text(json.dumps(norm, ensure_ascii=False, indent=1), encoding="utf-8")
        status[sid] = "ok"
        if notices:
            print(f"NOTE {sid}: {'; '.join(notices)}")
        for w in warns:
            print(f"WARN {sid}: {w}")
    return status


def canonical(sid: str, meta: dict) -> dict | None:
    path = OUT_DEC / meta["folder"] / f"{sid}.json"
    if not path.exists():
        return None
    d = json.loads(path.read_text(encoding="utf-8"))
    data = load_units(sid, meta)
    ok = d.get("sha1") == data["sha1"] and d.get("unitizer_version") == UNITIZER_VERSION
    return d if ok and (OUT_TXT / meta["folder"] / f"{sid}.txt").exists() else None


def load_vocab() -> dict:
    return json.loads(VOCAB.read_text(encoding="utf-8")) if VOCAB.exists() else {}


def cmd_apply(args) -> int:
    srcs = sources()
    if args.year:
        paths = sorted((DRAFTS / str(args.year)).glob(f"{args.page or '*'}.jsonl"))
        expected = [] if args.page else [s for s, m in srcs.items() if m["year"] == args.year]
    else:
        paths = [Path(p) if Path(p).is_absolute() else ROOT / p for p in args.file]
        expected = []
    decisions, problems = read_drafts(paths)
    for p in problems:
        print(f"ERROR {p}")
    status = apply_decisions(decisions, srcs, load_vocab())
    missing = [s for s in expected if s not in decisions]
    errors = sum(1 for v in status.values() if v == "error") + len(problems)
    if args.page and not paths:
        print(f"ERROR no decisions file for page {args.page} yet")
        errors += 1
    print(f"SUMMARY: {sum(1 for v in status.values() if v == 'ok')} ok, {errors} errors, "
          f"{len(missing)} without a decision yet" + (f": {', '.join(missing[:15])}"
                                                       f"{' …' if len(missing) > 15 else ''}" if missing else ""))
    return 1 if errors or missing else 0


def cmd_status(args) -> int:
    srcs = sources()
    ids = sorted(s for s, m in srcs.items() if m["year"] == args.year)
    drafts, _ = read_drafts(sorted((DRAFTS / str(args.year)).glob("*.jsonl")))
    done = [s for s in ids if canonical(s, srcs[s])]
    drafted = [s for s in ids if s in drafts and s not in done]
    pending = [s for s in ids if s not in drafts and s not in done]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")).get(str(args.year), {})
    todo_pages = [p["page"] for p in manifest.get("pages", []) if any(s in pending for s in p["speeches"])]
    print(json.dumps({"year": args.year, "speeches": len(ids), "applied_ok": len(done),
                      "drafted_not_applied_or_invalid": drafted, "pending": len(pending),
                      "pages_with_pending_speeches": todo_pages}, indent=1))
    return 0


def cmd_show(args) -> int:
    srcs, names = sources(), country_names()
    for sid in args.ids:
        print("\n".join(render(sid, srcs[sid], load_units(sid, srcs[sid]), names)))
    return 0


def cmd_audit_view(args) -> int:
    srcs, names = sources(), country_names()
    lines = []
    for sid in args.ids:
        d = canonical(sid, srcs[sid])
        if d is None:
            lines += [f"=== {sid}: no valid decision yet", ""]
            continue
        lines += render(sid, srcs[sid], load_units(sid, srcs[sid]), names, d)
    out = Path(args.out)
    out = out if out.is_absolute() else ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    pages = paginate([("audit", lines)])
    paths = []
    for k, (page, _) in enumerate(pages, 1):
        path = out if len(pages) == 1 else out.with_name(f"{out.stem}.p{k:02d}{out.suffix}")
        path.write_text("\n".join(page) + "\n", encoding="utf-8")
        paths.append(str(path.relative_to(ROOT)))
    print("\n".join(paths))
    return 0


def cmd_validate(args) -> int:
    srcs = sources()
    bad = {}
    for sid, meta in srcs.items():
        if not canonical(sid, meta):
            bad.setdefault(str(meta["year"]), []).append(sid)
    print(json.dumps({"speeches": len(srcs), "valid": len(srcs) - sum(map(len, bad.values())),
                      "missing_or_invalid_by_year": bad}, indent=1))
    return 1 if bad else 0


def cmd_report(args) -> int:
    srcs = sources()
    rows = []
    for sid, meta in sorted(srcs.items()):
        d = canonical(sid, meta)
        if not d:
            continue
        st = d["stats"]
        rows.append({"id": sid, "year": meta["year"], "layout": d["layout"], "words_in": st["words_in"],
                     "words_out": st["words_out"], "retention": st["retention"],
                     "paragraphs": st["n_paragraphs"],
                     "median_paragraph_words": statistics.median(st["paragraph_words"]) if st["paragraph_words"] else 0,
                     "ceremonial": len(d["cer"]), "fixes": len(d["fix"]),
                     **{f"drop_{r}": st["units_dropped"].get(r, 0) for r in sorted(DROP_REASONS)},
                     "flags": " ".join(d["flags"]), "warnings": len(st["warnings"]), "note": d["note"]})
    if not rows:
        print("no applied decisions yet")
        return 1
    with open(TIDY / "speech_stats.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    by_year = {}
    for r in rows:
        by_year.setdefault(r["year"], []).append(r)
    lines = ["# Tidy corpus report", "",
             f"{len(rows)} of {len(srcs)} speeches tidied. Retention = words kept / words after pre-strip.", "",
             "| year | speeches | retention (median) | paragraphs (median) | words per paragraph (median) "
             "| flagged | with warnings |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for y, rs in sorted(by_year.items()):
        lines.append(f"| {y} | {len(rs)} | {statistics.median(r['retention'] for r in rs):.3f} | "
                     f"{statistics.median(r['paragraphs'] for r in rs):.0f} | "
                     f"{statistics.median(r['median_paragraph_words'] for r in rs):.0f} | "
                     f"{sum(1 for r in rs if r['flags'])} | {sum(1 for r in rs if r['warnings'])} |")
    flags = Counter(f for r in rows for f in r["flags"].split())
    drops = Counter({r_: sum(r[f"drop_{r_}"] for r in rows) for r_ in sorted(DROP_REASONS)})
    lines += ["", "Units dropped by reason: " + ", ".join(f"{k} {v:,}" for k, v in drops.most_common()),
              "", "Flags: " + (", ".join(f"{k} {v}" for k, v in flags.most_common()) or "none")]
    (TIDY / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.tidy")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--year", type=int)
    p.add_argument("--vocab", action="store_true", help="rebuild the dehyphenation vocabulary")
    p = sub.add_parser("status")
    p.add_argument("--year", type=int, required=True)
    p = sub.add_parser("apply")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--year", type=int)
    g.add_argument("--file", nargs="+")
    p.add_argument("--page", help="with --year: apply only this page's decisions, e.g. p03")
    p = sub.add_parser("show")
    p.add_argument("ids", nargs="+")
    p = sub.add_parser("audit-view")
    p.add_argument("ids", nargs="+")
    p.add_argument("--out", required=True)
    sub.add_parser("validate")
    sub.add_parser("report")
    args = ap.parse_args(argv)
    return {"plan": cmd_plan, "status": cmd_status, "apply": cmd_apply, "show": cmd_show,
            "audit-view": cmd_audit_view, "validate": cmd_validate, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
