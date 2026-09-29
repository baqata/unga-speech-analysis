"""UN verbatim records -> one general-debate statement per delegation, in the corpus format.

The UNGDC v14 texts for 2024 are the delegations' own texts (dataverse_files/README.txt), while every
earlier year comes from the General Assembly's verbatim records. The records of the 79th general debate
(A/79/PV.7-18, downloaded to data/sources/un_pv_79) replace them. Each record is read with poppler's
`pdftotext -layout`, whose indentation marks paragraph starts. The page furniture, headings, presiding
officers' turns, stage directions, rights of reply and the speaker labels are removed; each statement is
written as its speech text only, one paragraph per line, like the corpus files of earlier years.

    uv run python -m pipeline.records split --pdf-dir data/sources/un_pv_79 --out "data/official/Session 79 - 2024"
"""
import argparse
import csv
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pycountry

from pipeline import config

# Page furniture, matched on a line with its spaces collapsed.
FURNITURE = [re.compile(p) for p in (
    r"^A ?/\d+/PV\.\d+( \d{1,2}/\d{1,2}/\d{4})?$",   # running head, odd pages
    r"^\d{1,2}/\d{1,2}/\d{4} A/\d+/PV\.\d+$",         # running head, even pages
    r"^\d+/\d+ \d{2}-\d{5}$",                     # folio and job number
    r"^\d{2}-\d{5} \d+/\d+$",
    r"^\d{2}-\d{5} \(E\)$",
    r"^\*\d+\*",                                  # barcode line
)]
DISCLAIMER_START = "This record contains the text of speeches"
DISCLAIMER_END = "documents.un.org)."

TITLES = (r"(?:Mr|Mrs|Ms|Dr)\.|President|Vice-President|Prime Minister|King|Queen|Crown Prince|Prince"
          r"|Princess|Sheikh|Sheikha|Emir|Amir|Sultan|Sir|Dame|Lord|Cardinal|Archbishop|Monsignor"
          r"|Grand Duke|General|Captain|Chancellor")
LABEL = re.compile(r"^(?P<who>The (?:Acting )?President|The Secretary-General|(?:" + TITLES
                   + r") [^:()]{1,60}?)(?: \((?P<where>(?!spoke in|continued in)[^()]*)\))?(?: \((?P<lang>(?:spoke|continued) in"
                   r" [^()]*)\))?(?(lang):? |: )(?:\((?:spoke|continued) in [^()]*\):? )?")
PRESIDERS = {"The President", "The Acting President", "The Secretary-General"}
HEADING = re.compile(r"^(Address by |Agenda items? \d+|General debate$)")
STAGE = re.compile(r"(was escorted (into|from|to|out of) the |(took|returned to) the Chair\.|^The meeting (was called to order"
                   r"|rose|was suspended|resumed)\b)")
LANG_NOTE = re.compile(r"^\((?:spoke|continued) in [^()]*\)$")
INLINE_LANG_NOTE = re.compile(r" ?\((?:spoke|continued) in [^()]*\)")  # a switch of language inside a turn
REPLY = "right of reply"
PRESIDER_WORDS = 250  # longer presiding-officer turns are listed for reading (a label may have been missed)
SUSPECT = re.compile(r"^(?:The (?:Acting )?President(?: \([^)]*\))?:|(?:Mr|Mrs|Ms)\. [^.:()]{1,60} \()")

# UN names that neither the country table nor pycountry resolve.
ALIASES = {
    "European Council": "EU", "European Union": "EU", "Holy See": "VAT", "State of Palestine": "PSE",
    "Kingdom of the Netherlands": "NLD", "Republic of Korea": "KOR",
    "Democratic People's Republic of Korea": "PRK", "United Republic of Tanzania": "TZA",
    "Lao People's Democratic Republic": "LAO", "Republic of Moldova": "MDA",
    "Syrian Arab Republic": "SYR", "Russian Federation": "RUS", "Viet Nam": "VNM",
    "Federated States of Micronesia": "FSM", "Democratic Republic of the Congo": "COD",
    "Brunei Darussalam": "BRN", "Islamic Republic of Iran": "IRN",
    "Bolivarian Republic of Venezuela": "VEN", "Plurinational State of Bolivia": "BOL",
    "Republic of the Congo": "COG", "Nauru": "NRO", "Republic of Nauru": "NRO",
}


def pdf_pages(pdf: Path) -> list[str]:
    out = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True, capture_output=True)
    return out.stdout.decode("utf-8").replace("\b", " ").split("\f")


ZERO_WIDTH = re.compile("[\u00ad\u200b-\u200d\u2060\ufeff]")
SPACED_HYPHEN = re.compile(r"(?<=\w) -(?=\w)")  # layout artefact: 'seventy -ninth' (the records have no ' - ')


def _flat(line: str) -> str:
    return re.sub(r"\s+", " ", ZERO_WIDTH.sub("", line)).strip()


def body_lines(pages: list[str]) -> list[tuple[int, int, str]]:
    """(page, indent relative to the page's text margin, text) for every body line; None text = blank."""
    out = []
    for p, page in enumerate(pages):
        lines = page.split("\n")
        if p == 0:  # masthead down to the "President:" line
            k = next((i for i, ln in enumerate(lines) if ln.startswith("President:")), -1)
            lines = lines[k + 1:]
        keep, in_disclaimer = [], False
        for ln in lines:
            flat = _flat(ln)
            if flat.startswith(DISCLAIMER_START):
                in_disclaimer = True
            if in_disclaimer:
                in_disclaimer = not flat.endswith(DISCLAIMER_END)
                continue
            if flat and any(r.match(flat) for r in FURNITURE):
                continue
            if flat in ("Accessible document", "Please recycle"):
                continue
            keep.append(ln)
        indents = [len(ln) - len(ln.lstrip(" ")) for ln in keep if ln.strip()]
        if not indents:
            continue
        counts = Counter(indents)  # the text margin: the smallest indent of at least three lines
        margin = min((i for i, n in counts.items() if n >= 3), default=counts.most_common(1)[0][0])
        for ln in keep:
            if ln.strip():
                out.append((p, len(ln) - len(ln.lstrip(" ")) - margin, _flat(ln)))
            else:
                out.append((p, 0, None))
    return out


def blocks(lines: list[tuple[int, int, str]]) -> list[str]:
    """Paragraphs: a line indented past the margin, or at the margin after a blank line on the same
    page, starts one; the others continue it. Stage directions are indented on every line, so an
    indented line under an indented line that does not end a sentence continues it. Line-end hyphens
    are kept (the records do not hyphenate words at line ends; 'self-' + 'determination' is one word)."""
    out, cur, prev_blank, prev_page, prev_indent = [], [], False, None, 0
    for page, indent, text in lines:
        if text is None:
            prev_blank = True
            continue
        wrapped = (indent >= 2 and prev_indent >= 2 and abs(indent - prev_indent) <= 1
                   and not prev_blank and cur and not re.search(r"[.!?:;”\"’)]$", cur[-1]))
        new = ((indent >= 2 and not wrapped) or (prev_blank and page == prev_page) or not cur
               or HEADING.match(text))
        if new and cur:
            out.append(cur)
            cur = []
        cur.append(text)
        prev_blank, prev_page, prev_indent = False, page, indent
    if cur:
        out.append(cur)
    joined = []
    for parts in out:
        s = parts[0]
        for t in parts[1:]:
            if s.endswith(" -"):
                s = s[:-2] + "-" + t
            else:
                s = s + t if s.endswith("-") else s + " " + t
        joined.append(SPACED_HYPHEN.sub("-", s))
    return joined


def rejoin_split_words(text: str, vocab: dict, joins: list) -> str:
    """Layout mode sometimes breaks a word in two ('Grenad a', 'und er'). Two tokens are joined when
    the joined word is common in the corpus (>= 50) and one part is rare (< 20); joins are logged."""
    toks = text.split(" ")
    out, i = [], 0
    while i < len(toks):
        a = toks[i]
        if i + 1 < len(toks) and re.fullmatch(r"[A-Za-z]+", a):
            m = re.fullmatch(r"([a-z]+)(\W*)", toks[i + 1])
            if m:
                w = (a + m.group(1)).lower()
                if vocab.get(w, 0) >= 50 and min(vocab.get(a.lower(), 0), vocab.get(m.group(1), 0)) < 20:
                    joins.append(f"{a} {m.group(1)} -> {a}{m.group(1)}")
                    out.append(a + toks[i + 1])
                    i += 2
                    continue
        out.append(a)
        i += 1
    return " ".join(out)


def _name_table() -> dict[str, str]:
    table = {}
    for path in (config.COUNTRIES, config.HISTORICAL_NAMES):
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("name_en"):
                    table.setdefault(row["name_en"].lower(), row["iso3"])
    table.update({k.lower(): v for k, v in ALIASES.items()})
    return table


NAMES = None


def iso3_of(name: str) -> str | None:
    """ISO3 (or EU) of a UN country name, trying each tail after 'of' when the name is a title
    ('President of the Republic of Türkiye' -> TUR); the longest candidate that resolves wins."""
    global NAMES
    if NAMES is None:
        NAMES = _name_table()
    name = name.replace("’", "'").strip().rstrip(".")
    tails = [name] + [name[m.end():] for m in re.finditer(r"\bof ", name)]
    # each tail also without what follows an ' and ' or a comma ('... of Malawi and Commander-in-Chief')
    cands = [c for tail in tails for c in [tail] + [tail[:m.start()] for m in
             reversed(list(re.finditer(r" and |, ", tail)))]]
    for cand in cands:
        t = re.sub(r"^the ", "", cand.strip(), flags=re.I)
        if t.lower() in NAMES:
            return NAMES[t.lower()]
        try:
            c = pycountry.countries.lookup(t)
        except LookupError:
            continue
        return config.CODE_RENAMES.get(c.alpha_3, c.alpha_3)
    return None


def statements(pdf: Path, warnings: list | None = None, vocab: dict | None = None) -> list[dict]:
    """General-debate statements of one record file (A_79_PV.7.pdf)."""
    record = "A/" + pdf.stem.split("_", 1)[1].replace("_", "/")
    return parse_record(pdf_pages(pdf), record, warnings, vocab)


def parse_record(pages: list[str], record: str, warnings: list | None = None,
                 vocab: dict | None = None) -> list[dict]:
    """General-debate statements of one record, in order, with the record's rights of reply dropped.

    A record opens under the item it continues (the general debate's continuation meetings print no
    item heading); an 'Agenda item' heading leaves the debate until a 'General debate' heading.
    Presiding officers' turns longer than PRESIDER_WORDS are added to `warnings` for reading."""
    turns, heading, replies, debate = [], None, False, True
    for block in blocks(body_lines(pages)):
        if HEADING.match(block):
            if block.startswith("Address by "):
                if replies:
                    raise ValueError(f"{record}: an address after the rights of reply: {block[:80]}")
                heading = block[len("Address by "):]
            else:
                debate = block == "General debate"
            continue
        if STAGE.search(block) or LANG_NOTE.match(block):
            continue
        m = LABEL.match(block)
        if m:
            who = m.group("who")
            turn = {"record": record, "who": who, "where": m.group("where"), "lang": m.group("lang"),
                    "heading": heading, "reply": replies, "debate": debate,
                    "paragraphs": [block[m.end():].strip()]}
            if who in PRESIDERS:
                turn["presider"] = True
                replies = replies or REPLY in block
            turns.append(turn)
            continue
        if not turns or not debate:
            if debate:
                raise ValueError(f"{record}: text before the first speaker: {block[:80]}")
            continue  # another item's sub-headings
        turns[-1]["paragraphs"].append(block)
        if turns[-1].get("presider") and REPLY in block:
            replies = True
    out = []
    for t in turns:
        words = sum(len(p.split()) for p in t["paragraphs"])
        if t.get("presider"):
            if t["debate"] and words > PRESIDER_WORDS and warnings is not None:
                warnings.append(f"{record}: {t['who']} speaks {words} words: {t['paragraphs'][0][:90]}")
            continue
        if t["reply"] or not t["debate"]:
            continue
        name = t["where"] or t["heading"] or ""
        t["iso3"] = iso3_of(name)
        checks = []
        if t["where"] is None:  # a head of State: the label is a surname, the heading has the country
            surname = t["who"].split(" ", 1)[1]
            if surname.split()[-1] not in (t["heading"] or ""):
                checks.append("label not in heading")
        checks += [f"label-like paragraph: {p[:60]}" for p in t["paragraphs"][1:] if SUSPECT.match(p)]
        t["check"] = "; ".join(checks)
        t["joins"] = []
        t["paragraphs"] = [INLINE_LANG_NOTE.sub("", p).strip() for p in t["paragraphs"]]
        if vocab is not None:
            t["paragraphs"] = [rejoin_split_words(p, vocab, t["joins"]) for p in t["paragraphs"]]
        out.append(t)
    return out


def write_statements(stmts: list[dict], out_dir: Path, session: int, year: int) -> list[dict]:
    """One file per delegation (file names keep the source codes, e.g. NRU for Naoero)."""
    source_code = {v: k for k, v in config.CODE_RENAMES.items()}
    out_dir.mkdir(parents=True, exist_ok=True)
    by_code, rows = {}, []
    for s in stmts:
        if s["iso3"] is None:
            raise ValueError(f"{s['record']}: no country for {s['who']} ({s['where'] or s['heading']})")
        code = source_code.get(s["iso3"], s["iso3"])
        if code in by_code:
            raise ValueError(f"{code}: two statements ({by_code[code]['record']}, {s['record']})")
        by_code[code] = s
    for code, s in sorted(by_code.items()):
        sid = f"{code}_{session:02d}_{year}"
        paras = [p for p in s["paragraphs"] if p]
        (out_dir / f"{sid}.txt").write_text("\n".join(paras) + "\n", encoding="utf-8")
        rows.append({"speech_id": sid, "record": s["record"], "speaker": s["who"],
                     "delegation": s["where"] or "", "address": s["heading"] if not s["where"] else "",
                     "language": s["lang"] or "", "paragraphs": len(paras),
                     "words": sum(len(p.split()) for p in paras), "check": s["check"],
                     "joined": "; ".join(s.get("joins", []))})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.records")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("split")
    p.add_argument("--pdf-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True, help='folder "Session NN - YYYY"')
    args = ap.parse_args(argv)
    m = re.match(r"^Session (\d{2}) - (\d{4})$", args.out.name)
    if not m:
        ap.error('--out must be a folder named "Session NN - YYYY"')
    pdfs = sorted(args.pdf_dir.glob("A_*_PV.*.pdf"), key=lambda p: int(p.stem.rsplit(".", 1)[1]))
    from pipeline.tidy import load_vocab
    warnings, vocab = [], load_vocab()
    stmts = [s for pdf in pdfs for s in statements(pdf, warnings, vocab)]
    rows = write_statements(stmts, args.out, int(m.group(1)), int(m.group(2)))
    index = args.out.parent / f"records_{m.group(1)}_{m.group(2)}.csv"
    with open(index, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} statements from {len(pdfs)} records -> {args.out} (index {index.name})")
    for r in rows:
        if r["check"]:
            print(f"  CHECK {r['speech_id']}: {r['check']} ({r['speaker']} / {r['address'][:70]})")
    for w in warnings:
        print(f"  PRESIDER {w}")
    joins = [(r["speech_id"], j) for r in rows for j in r["joined"].split("; ") if j]
    print(f"  {len(joins)} split words rejoined:", "; ".join(f"{sid[:3]} {j}" for sid, j in joins))
    return 0


if __name__ == "__main__":
    sys.exit(main())
