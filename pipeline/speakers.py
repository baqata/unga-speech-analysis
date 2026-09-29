"""Speaker metadata from Speakers_by_session.xlsx, keyed by (iso3, year).

Sessions after the spreadsheet have provisional speaker lists with the same columns
(data/provisional/speakers_NN_YYYY.csv, built from gadebate.un.org); their rows are added.
The spreadsheet uses a few non-standard codes; CODE_FIXES maps them to the
codes used by the corpus file names, and config.CODE_RENAMES to a country's current code. Posts are free text (reliable only from
1994) and are normalised into a small set of categories by post_category().
"""
import re
from pathlib import Path

import pandas as pd

from pipeline import config

CODE_FIXES = {
    "POR": "PRT", "YDYE": "YMD", "EC": "EU", "CZK": "CSK",
    "DKN": "DNK", "PAR": "PRY", "PKR": "PRK", "ZFA": "ZAF",
}

POST_CATEGORIES = [
    "head_of_state", "head_of_government", "deputy", "foreign_minister",
    "other_minister", "ambassador", "other", "unknown",
]

_UNKNOWN = {"", "not indicated", "missing", "spanish", "nan"}

# Ordered rules: the first pattern that matches decides the category.
_RULES = [
    ("other", r"^personal representative|^president of the european council"),
    ("head_of_government",
     r"^president of (?:the )?government|^president of the council of ministers"),
    ("deputy",
     r"^(?:first |second )?(?:deputy|vice)[- ]?(?:president|prime minister|chancellor|chairman)"
     r"|^first vice-president|^crown prince"),
    ("other_minister",
     r"^(?:deputy|vice) minister|^second minister|^minister at the prime minister"
     r"|^special envoy"),
    ("head_of_state",
     r"^(?:state |constitutional |interim |acting |first executive )?president\b"
     r"|^(?:king|queen|emir|amir|emperor|sultan|sheikh|pope|grand duke|captain regent)\b"
     r"|^(?:sovereign )?prince\b|^(?:acting )?head of state|^commander in chief, head of state"
     r"|^c(?:h)?airman of the presiden|^member of the presidency|^head of the church"
     r"|^chairman of the (?:supreme|transitional military|military|assembly presidium|united national front)"
     r"|^head of the federal military government|^coordinator of the junta|^member of the junta"
     r"|^first secretary of the central committee"),
    ("head_of_government",
     r"\bprime minister\b|^rime minister|^premier\b|^chancellor\b|^taoiseach"
     r"|^head\s+of\s+(?:the\s+)?gover|^chief (?:executive|advis[eo]r)"
     r"|^chairman of the council of ministers"),
    ("foreign_minister",
     r"foreign affairs|external affairs|external relations|foreign minister"
     r"|international relations|international affairs|relations with states"
     r"|^secretary of state\b|minister for foreign and|minister of foreign and"),
    ("other_minister",
     r"minist|secretary of state|cabinet secretary|attorney general|state counsellor"),
    ("ambassador",
     r"representative|ambassador|delegation|charg[ée]"),
]
_RULES = [(cat, re.compile(pat, re.I)) for cat, pat in _RULES]

# Misspellings in the spreadsheet, corrected before the rules are applied
# (every 2005 post reads "Minister for Foregn Affairs").
_TYPOS = {
    "foregn": "foreign", "foriegn": "foreign", "foreing": "foreign",
    "minsiter": "minister", "misnter": "minister",
    "goverment": "government", "govermnent": "government", "coucil": "council",
    "presidensy": "presidency",
}
_TYPO_RE = re.compile(r"\b(?:" + "|".join(_TYPOS) + r")\b", re.I)


def post_category(post) -> str:
    """Map a free-text post to one of POST_CATEGORIES."""
    if post is None or (isinstance(post, float) and pd.isna(post)):
        return "unknown"
    text = re.sub(r"\s+", " ", str(post)).strip()
    if text.lower() in _UNKNOWN:
        return "unknown"
    text = _TYPO_RE.sub(lambda m: _TYPOS[m.group().lower()], text)
    for cat, pat in _RULES:
        if pat.search(text):
            return cat
    return "other"


def _clean_str(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return None if text.lower() in _UNKNOWN else text


def load_speakers(path=config.SPEAKERS_XLSX, provisional_dir=None) -> pd.DataFrame:
    """Return one row per (iso3, year) with speaker_name, speaker_post, post_category.

    Rows from the speakers_*.csv lists in `provisional_dir` are added to the spreadsheet's.

    A few keys (1951-69) have two rows. Distinct names are joined with "; "
    and, because it is unknown which of them the corpus text belongs to,
    such keys get post_category "unknown" unless all posts agree.
    """
    raw = pd.read_excel(path, sheet_name="Sheet1", dtype=str)
    if provisional_dir is not None:
        lists = [pd.read_csv(f, dtype=str) for f in sorted(Path(provisional_dir).glob("speakers_*.csv"))]
        raw = pd.concat([raw, *lists], ignore_index=True)
    df = pd.DataFrame({
        "iso3": raw["ISO Code"].str.strip().replace({**CODE_FIXES, **config.CODE_RENAMES}),
        "year": pd.to_numeric(raw["Year"], errors="coerce"),
        "name": raw["Name of Person Speaking"].map(_clean_str),
        "post": raw["Post"].map(_clean_str),
    }).dropna(subset=["iso3", "year"])
    df["year"] = df["year"].astype(int)

    rows = []
    for (iso3, year), grp in df.groupby(["iso3", "year"], sort=True):
        names = list(dict.fromkeys(n for n in grp["name"] if isinstance(n, str)))
        names = list({n.lower(): n for n in names}.values())
        posts = list(dict.fromkeys(p for p in grp["post"] if isinstance(p, str)))
        cats = {post_category(p) for p in posts}
        if len(names) <= 1 and len(cats) <= 1:
            cat = cats.pop() if cats else "unknown"
        else:
            cat = "unknown"
        rows.append({
            "iso3": iso3,
            "year": year,
            "speaker_name": "; ".join(names) or None,
            "speaker_post": "; ".join(posts) or None,
            "post_category": cat,
            "speaker_rows": len(grp),
        })
    return pd.DataFrame(rows)
