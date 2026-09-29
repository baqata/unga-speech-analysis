"""Sentences, paragraph reconstruction, fragments and ceremonial flags.

Paragraph-first segmentation: keep real paragraphs where the source layout
preserves them, rebuild them where lines are hard-wrapped, and pack sentences
only where there is no structure (single-line transcripts). Fragments then
merge paragraphs shorter than MIN_WORDS and split units longer than MAX_WORDS
at sentence boundaries into near-equal parts of about TARGET_WORDS.
"""
import re

import numpy as np

MIN_WORDS = 60
MAX_WORDS = 260
TARGET_WORDS = 150

PARA_METHOD = {"line": "line", "wrapped": "rebuilt", "notes": "notes", "single": "sentence_pack",
               "tidy": "tidy"}

# ---------------------------------------------------------------------------
# Sentences
# ---------------------------------------------------------------------------

# Titles before a name: never end a sentence.
_TITLES = {
    "mr", "mrs", "ms", "dr", "st", "messrs", "mme", "mmes", "mlle", "prof", "gen", "sen",
    "rep", "gov", "lt", "col", "capt", "sgt", "cmdr", "adm", "maj", "rev", "hon", "fr",
    "sr", "jr", "amb", "pres", "esq", "ste", "mgr", "msgr", "excmo", "sra", "sr",
}
# Abbreviations that precede a number ("No. 5", "Art. 2", "para. 3").
_BEFORE_NUMBER = {"no", "nos", "art", "arts", "para", "paras", "p", "pp", "vol", "vols",
                  "ch", "chap", "sect", "sec", "fig", "op"}
# Abbreviations that never end a sentence.
_ALWAYS = {"e.g", "i.e", "cf", "viz", "vs", "approx", "ca"}

_CANDIDATE = re.compile(
    r"[.!?…]+[\"”’'»)\]]*(?=\s+[\"“‘'«(\[]?[A-Z0-9À-Þ])")
_DOTTED = re.compile(r"(?:[a-z]\.)+[a-z]")


def _is_boundary(text: str, m: re.Match) -> bool:
    if text[m.start()] != ".":
        return True
    if text[m.start():m.start() + 2] == "..":
        return True
    ws = max(text.rfind(" ", 0, m.start()), text.rfind("\n", 0, m.start()))
    token = text[ws + 1:m.start()].lstrip("(\"“‘'«[")
    core = token.lower()
    if core in _TITLES or core in _ALWAYS or _DOTTED.fullmatch(core):
        return False
    if len(token) == 1 and token.isupper():  # initials: "John F. Kennedy"
        return False
    if core in _BEFORE_NUMBER:
        nxt = text[m.end():].lstrip()[:1]
        return not nxt.isdigit()
    return True


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) character spans of sentences; together they cover all text."""
    spans, start = [], 0
    for m in _CANDIDATE.finditer(text):
        if _is_boundary(text, m):
            spans.append((start, m.end()))
            start = m.end()
    if text[start:].strip() or not spans:
        spans.append((start, len(text)))
    else:
        spans[-1] = (spans[-1][0], len(text))
    return spans


def split_sentences(text: str) -> list[str]:
    return [s for s in (text[a:b].strip() for a, b in sentence_spans(text)) if s]


def n_words(text: str) -> int:
    return len(text.split())


# ---------------------------------------------------------------------------
# Layout detection and paragraph reconstruction
# ---------------------------------------------------------------------------

_TERMINAL = re.compile(r"[.!?:;…][\"”’'»)\]]*$")
_ELLIPSIS = re.compile(r"(?:…|\.\.\.)[\"”’'»)\]]*$")
# The word before a line-end hyphen, including a compound ("self-determina-") but
# not a number before it ("50-year-" gives "year").
_HYPHEN_END = re.compile(r"(?<![A-Za-z])([A-Za-z]+(?:-[A-Za-z]+)*)-$")
_DIGIT_HYPHEN_END = re.compile(r"\d-$")
_WORD_START = re.compile(r"[A-Za-z]+")
_COMPOUND_REST = re.compile(r"(?:-[A-Za-z]+)+")


def _first_word_len(text: str) -> int:
    return len(text.split(None, 1)[0])


def layout_stats(lines) -> dict:
    """Per-file statistics used to classify the layout and to judge line ends."""
    wraps = [len(a.text) + 1 + _first_word_len(b.text)
             for a, b in zip(lines, lines[1:])
             if b.gap == "none" and not _TERMINAL.search(a.text) and b.text[:1].islower()]
    stats = {"n_lines": len(lines), "n_wraps": len(wraps), "has_wrap": False,
             "lo": 0.0, "hi": 0.0, "indent_file": False}
    if len(wraps) >= 8:
        p5, p95 = np.percentile(wraps, [5, 95])
        if p95 <= 140 and p95 <= 1.6 * p5:
            stats.update(has_wrap=True, lo=0.92 * p5, hi=1.25 * p95)
    indented = [i for i, ln in enumerate(lines) if ln.indent and i > 0]
    if len(indented) >= 5:
        starts = sum(1 for i in indented if _TERMINAL.search(lines[i - 1].text))
        stats["indent_file"] = starts >= 0.6 * len(indented)
    return stats


def detect_layout(lines, stats: dict) -> str:
    """'single', 'wrapped', 'notes' or 'line' (one paragraph per line)."""
    if not lines:
        return "single"
    words = [n_words(ln.text) for ln in lines]
    total = sum(words)
    if len(lines) <= 2 or (len(lines) <= 4 and max(words) >= 0.8 * total):
        return "single"
    if stats["has_wrap"] and stats["n_wraps"] >= 0.2 * len(lines):
        return "wrapped"
    if len(lines) >= 15 and float(np.median([len(ln.text) for ln in lines])) <= 80:
        return "notes"
    return "line"


# A sentence-final line followed by a line this much shorter than a full line opens a
# paragraph whose indent was lost (share of the lo-hi range of wrap widths). Measured
# against hidden true breaks: 2013-14 blank lines, recall 0.72 -> 0.88 at precision 0.94;
# 1982 paragraph numbers, recall 0.79 -> 0.96 at precision 0.96.
UNDERFILL = 0.2


def _is_break(a, b, layout: str, stats: dict, c=None) -> bool:
    """Does a paragraph end between content lines a and b (c follows b, if any)?"""
    if b.numbered or b.heading or b.bullet or b.gap == "sep" or a.heading:
        return True
    if b.text[:1].islower() or not _TERMINAL.search(a.text):
        return False
    if layout == "notes" and _ELLIPSIS.search(a.text):
        return False
    if not stats["has_wrap"]:
        return True
    # Hard-wrapped text: a sentence-final line can still be a full-width wrap.
    if b.gap == "blank":
        return True
    if stats["indent_file"] and b.indent:
        return True
    width = len(a.text) + 1 + _first_word_len(b.text)
    if not stats["lo"] <= width <= stats["hi"]:
        return True
    # b is the first line of a paragraph that lost its indent: it is under-filled.
    return (c is not None and c.gap == "none" and not (c.numbered or c.heading or c.bullet)
            and not _TERMINAL.search(b.text)
            and len(b.text) + 1 + _first_word_len(c.text)
            < stats["lo"] + UNDERFILL * (stats["hi"] - stats["lo"]))


# Words that cannot end a title: a line ending in one continues a sentence.
_OPEN_END = {
    "a", "an", "the", "of", "and", "or", "nor", "but", "to", "in", "on", "at", "by", "for",
    "with", "from", "as", "into", "onto", "upon", "than", "that", "which", "who", "whose",
    "our", "their", "its", "his", "her", "my", "your", "this", "these", "those", "is", "are",
    "was", "were", "be", "been", "has", "have", "had", "will", "would", "shall", "should",
    "can", "could", "may", "must", "not", "no", "we", "i", "it", "they", "all", "both",
    "between", "against", "under", "over", "among", "about", "through", "without", "within",
    "towards", "toward", "during", "such", "very", "more", "most", "also", "so", "if", "when",
}
TITLE_MAX_WORDS = 10
TITLE_SHORT = 6       # a longer title in sentence case has no comma and no final name
_NOT_TITLE = re.compile(r"\t.*\t|^Page\b|\w/\d")   # tab-aligned text, page stamps, symbols


def _is_title(prev, a, b) -> bool:
    """An unmarked heading: a short line at a paragraph start, without final
    punctuation, followed by a line that starts a sentence
    ("Candidacy for Security Council" / "The irony is ...")."""
    words = a.text.split()
    if (len(words) > TITLE_MAX_WORDS or a.text.count(",") > 1 or _NOT_TITLE.search(a.text)
            or not a.text[:1].isupper() or not a.text[-1:].isalnum()
            or words[-1].lower() in _OPEN_END):
        return False
    long_words = [w for w in words if len(w) > 3]
    if (len(words) > TITLE_SHORT and sum(w[0].isupper() for w in long_words) * 2 < len(long_words)
            and ("," in a.text or words[-1][0].isupper())):
        return False    # a sentence broken by the layout ("..., the seventieth ... of the United")
    return ((prev is None or a.gap != "none" or bool(_TERMINAL.search(prev.text)))
            and b.gap in ("none", "blank") and b.text[:1].isupper())


def mark_titles(lines, layout: str, counts) -> None:
    """Mark unmarked headings in a line or notes layout. Meant for 2015 onwards: in
    older records a short capitalised line is almost always a sentence broken by the
    OCR (a 1946-2014 audit found 50 such lines and no real heading)."""
    if layout not in ("line", "notes"):
        return
    for i in range(len(lines) - 1):
        if not lines[i].heading and _is_title(lines[i - 1] if i else None, lines[i], lines[i + 1]):
            lines[i].heading = True
            counts["title_line"] += 1


def rebuild_paragraphs(lines, layout: str, stats: dict, vocab, counts,
                       marks: list | None = None) -> list[str]:
    """Join content lines into paragraphs according to the layout.

    If `marks` is a list, one mark per paragraph is appended to it:
    "heading" (a heading, kept with the paragraph that follows), "section"
    (a separator line precedes it) or "" (an ordinary paragraph).
    """
    paragraphs, kinds, current = [], [], None
    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if current is not None and not _is_break(lines[i - 1], line, layout, stats, nxt):
            current = _join(current, line.text, vocab, counts)
            continue
        if current is not None:
            paragraphs.append(current)
        current = line.text
        kinds.append("heading" if line.heading else "section" if line.gap == "sep" else "")
    if current is not None:
        paragraphs.append(current)
    if marks is not None:
        marks.extend(kinds)
    return [re.sub(r"\s+", " ", p).strip() for p in paragraphs]


def _join(left: str, right: str, vocab, counts) -> str:
    """Join two lines of one paragraph, repairing a line-end hyphenation."""
    if left.endswith("-") and not left.endswith("--"):
        tail = left[-80:]
        m = _HYPHEN_END.search(tail)
        w = _WORD_START.match(right)
        if m and w:
            rest = _COMPOUND_REST.match(right, w.end())
            word, closed = vocab.closed_or_hyphenated(m.group(1), w.group(),
                                                      rest.group() if rest else "")
            counts["hyphen_rejoined" if closed else
                   "hyphen_suspended" if " " in word else "hyphen_kept"] += 1
            return left[:len(left) - len(tail) + m.start()] + word + right[w.end():]
        if _DIGIT_HYPHEN_END.search(tail) or right[:1].isdigit():  # "20-/year", "post-/2015"
            return left + right
    return left + " " + right


# ---------------------------------------------------------------------------
# Fragments
# ---------------------------------------------------------------------------

def _group_cost(words: int) -> float:
    # A piece under MIN_WORDS costs more than one over MAX_WORDS: a unit that no cut between
    # sentences keeps within the bounds stays whole (42 + 190 + 57 words, GTM_27_1972).
    if words < MIN_WORDS:
        return 1e7 + (MIN_WORDS - words) * 1e4
    if words > MAX_WORDS:
        return 1e6 + (words - MAX_WORDS) * 1e3
    return float((words - TARGET_WORDS) ** 2)


PARAGRAPH_CUT_BONUS = 1500.0  # prefer cuts at paragraph boundaries when sizes allow


_CLAUSE_END = re.compile(r"(?<=;)\s+")


def _units_of(paragraph: str) -> list[str]:
    """Sentences; a sentence longer than MAX_WORDS is cut after its semicolons."""
    out = []
    for s in split_sentences(paragraph) or [paragraph]:
        out.extend(_CLAUSE_END.split(s) if n_words(s) > MAX_WORDS else [s])
    return out


def _split_unit(paragraphs: list[str]) -> list[tuple[str, list[int]]]:
    """Split paragraphs (> MAX_WORDS in total) at sentence boundaries.

    Returns (text, positions in `paragraphs` of the paragraphs it overlaps) per part.
    """
    sents, para_start, owner = [], [], []
    for k, p in enumerate(paragraphs):
        ss = _units_of(p)
        sents.extend(ss)
        para_start.extend([True] + [False] * (len(ss) - 1))
        owner.extend([k] * len(ss))
    w = [n_words(s) for s in sents]
    m = len(sents)
    best = [0.0] + [float("inf")] * m
    back = [0] * (m + 1)
    for j in range(1, m + 1):
        total = 0
        for i in range(j - 1, -1, -1):
            total += w[i]
            cost = best[i] + _group_cost(total)
            if i > 0 and para_start[i]:
                cost -= PARAGRAPH_CUT_BONUS
            if cost < best[j]:
                best[j], back[j] = cost, i
            if total > 2 * MAX_WORDS:
                break
    cuts, j = [], m
    while j > 0:
        cuts.append((back[j], j))
        j = back[j]
    out = []
    for i, j in reversed(cuts):
        text = sents[i]
        for k in range(i + 1, j):
            text += ("\n" if para_start[k] else " ") + sents[k]
        out.append((text, sorted(set(owner[i:j]))))
    return out


def merge_short(paragraphs: list[str], marks: list[str] | None = None,
                kinds: list[bool] | None = None) -> list[list[int]]:
    """Group paragraphs (by index) so that every group has >= MIN_WORDS words
    (if the speech does).

    A heading (mark "heading") always stays with the paragraph that follows it.
    The shortest group below the minimum is merged with a neighbour in the same
    section (sections start at a heading or separator, see rebuild_paragraphs);
    between two such neighbours, the one of the same kind (ceremonial or not,
    from `kinds`) and otherwise the shorter one. Only a group alone in its
    section merges across a section boundary. A short last paragraph therefore
    merges backwards.
    """
    marks = marks or [""] * len(paragraphs)
    units, sizes, starts = [], [], []  # starts: the group opens a section
    glue = False
    for k, (p, mark) in enumerate(zip(paragraphs, marks)):
        if glue:
            units[-1].append(k)
            sizes[-1] += n_words(p)
        else:
            units.append([k])
            sizes.append(n_words(p))
            starts.append(bool(mark))
        glue = mark == "heading"

    def kind(u):
        return all(kinds[k] for k in units[u])

    while len(units) > 1:
        i = min(range(len(units)), key=sizes.__getitem__)
        if sizes[i] >= MIN_WORDS:
            break
        left = i > 0 and not starts[i]
        right = i + 1 < len(units) and not starts[i + 1]
        if left and right:
            j = i - 1 if sizes[i - 1] <= sizes[i + 1] else i + 1
            if kinds is not None and kind(i - 1) != kind(i + 1):
                j = i - 1 if kind(i - 1) == kind(i) else i + 1
        elif left or right:
            j = i - 1 if left else i + 1
        else:  # alone in its section
            j = i - 1 if i == len(units) - 1 or (i > 0 and sizes[i - 1] <= sizes[i + 1]) else i + 1
        a, b = min(i, j), max(i, j)
        units[a] += units.pop(b)
        sizes[a] += sizes.pop(b)
        starts.pop(b)
    return units


def make_fragments(paragraphs: list[str], marks: list[str] | None = None,
                   kinds: list[bool] | None = None, members: list | None = None) -> list[str]:
    """Merge short paragraphs, then split long units into near-equal parts.

    If `members` is a list, the indices of the paragraphs each fragment
    overlaps are appended to it, one list per fragment.
    """
    fragments = []
    for unit in merge_short(paragraphs, marks, kinds):
        texts = [paragraphs[k] for k in unit]
        if sum(n_words(p) for p in texts) <= MAX_WORDS:
            parts = [("\n".join(texts), list(range(len(unit))))]
        else:
            parts = _split_unit(texts)
        for text, pos in parts:
            fragments.append(text)
            if members is not None:
                members.append([unit[k] for k in pos])
    return fragments


# ---------------------------------------------------------------------------
# Ceremonial fragments
# ---------------------------------------------------------------------------

# A sentence is ceremonial when it matches one of these cues.
_CER_CUES = re.compile("|".join((
    r"\bcongratulat", r"\bfelicitat", r"\bpredecessor\b",
    r"\b(?:up)?on (?:your|his|her) (?:unanimous |well-deserved |well deserved |recent |deserved )?"
    r"(?:election|elevation|assumption|appointment|re-?election)",
    r"\b(?:elect\w*|presidency)\b.{0,80}\b(?:President|presidency|Chair|session)\b",
    r"\b(?:pay|paid|pays|paying) (?:a |my |our )?(?:warm |sincere |special |high |well-deserved "
    r"|deserved |heartfelt |respectful )?(?:tribute|respects|homage)",
    r"\b(?:thank|gratitude|appreciation|grateful|commend|praise|admiration|esteem)\w*\b.{0,150}"
    r"\b(?:Secretary[- ]+General|President|presidency|predecessor|outgoing|leadership"
    r"|stewardship|guidance|session|tenure)",
    r"\bthank\w* (?:God|Allah|the Almighty)",
    r"\b(?:greet|greeting|greetings|salute|salutations)\b",
    r"\bwelcom\w*\b.{0,100}\b(?:new(?:est)? |the newest )?(?:State )?(?:Members?|membership"
    r"|family of nations|our Organization)\b",
    r"\bwish(?:es)? (?:you|him|her) (?:well|(?:every|much|all|great|the greatest|full) success)",
    r"\bpresid(?:e|es|ed|ing) over (?:the|this|our)\b",
    r"\bcondolences?\b|\bmourn\w*|\bdeepest sympathy",
    r"\badmission of\b.{0,80}\b(?:Member|Organization|United Nations)\b",
    r"\b(?:success|successful|fruitful)\b.{0,80}\b(?:session|deliberations|tenure|term|mission"
    r"|presidency|endeavours?|task|work)\b",
    r"\b(?:assure|assures|pledge|pledges)\b.{0,120}\b(?:support|co-?operation)",
    r"\b(?:honou?r|privilege|pleasure)\b.{0,50}\b(?:to address|to speak|to be here|to stand"
    r"|to take the floor|of addressing|to participate|to represent)",
    r"\b(?:pleasure|pleased|delighted|happy|proud|gratified)\b.{0,80}\b(?:preside|presiding"
    r"|elect\w*|presidency|Chair)",
    r"\b(?:under|for) (?:your|his|her) (?:able |wise |skil(?:l)?ful |competent |distinguished "
    r"|dynamic |capable |outstanding |excellent |effective |inspired )?(?:leadership|guidance"
    r"|presidency|stewardship)",
    r"\b(?:wise|able|inspired|skil(?:l)?ful|competent|dynamic|distinguished|outstanding|excellent"
    r"|effective|efficient|capable|tireless|untiring|dedicated)\b(?: and \w+)? (?:leadership|guidance"
    r"|stewardship|manner|presidency|efforts)",
    # Praise of the President or Secretary-General as a person.
    r"\b(?:your|his|her)\b(?: [\w,’'-]+){0,5} (?:experience|wisdom|skills?|talents?|qualities"
    r"|competence|abilit(?:y|ies)|capabilit\w+|acumen|stature|standing)\b",
    r"\bconfident that (?:you|he|she|your|his|her|under)\b",
    r"\b(?:ably|skil(?:l)?fully|masterfully|admirably)\b",
    r"\bin the name of (?:god|allah)\b", r"\bbismillah", r"\bmay god bless\b",
    r"^\W*(?:I )?thank you\b",
)), re.I)
# Salutation-only sentences ("Mr. President, Excellencies, ...") are neutral filler.
_SALUTE_ONLY = re.compile(
    r"^\W*(?:(?:Mr\.?|Madam|Madame|Mister|Your|Distinguished|Dear|Honou?rable|Excellenc\w+|Ladies"
    r"|Heads|Secretary|President|Majest\w+|Highness|Members|Colleagues|and|of|the|State|Government"
    r"|Delegat\w+|gentlemen|friends|Chair\w*|General|Assembly|United|Nations|Excellency|guests"
    r"|Sir)\W*)+$",
    re.I)
# UNODC mandate vocabulary anywhere in the fragment: never ceremonial.
_MANDATE = re.compile(r"\b(?:" + "|".join((
    r"drugs?", r"narcotic\w*", r"cocaine", r"heroin", r"opium", r"cannabis", r"terror\w*",
    r"crimes?", r"criminal\w*", r"corrupt\w*", r"traffick\w*", r"smuggl\w*", r"launder\w*",
)) + r")\b", re.I)
# Other substantive vocabulary: in a sentence without a ceremonial cue it vetoes the fragment.
_SUBSTANTIVE = re.compile(r"\b(?:" + "|".join((
    r"weapons?", r"nuclear", r"disarm\w*", r"wars?", r"conflicts?", r"aggression", r"occupation",
    r"genocide", r"refugees?", r"migra\w*", r"climate", r"pandemic", r"covid\w*", r"debt",
    r"poverty", r"sanctions?", r"violence", r"attacks?", r"invasion", r"military", r"troops",
    r"peacekeep\w*", r"hunger", r"famine", r"apartheid", r"colonial\w*", r"human rights",
    r"crisis", r"crises", r"killed", r"massacre\w*", r"justice",
)) + r")\b", re.I)
# Policy vocabulary that makes a sentence without a ceremonial cue non-ceremonial.
_POLICY = re.compile(r"\b(?:" + "|".join((
    r"econom\w*", r"development", r"security", r"reform\w*", r"resolutions?", r"agenda",
    r"trade", r"investment", r"growth", r"energy", r"health", r"education", r"environment\w*",
    r"sustainable", r"treaty", r"negotiat\w*", r"elections",
)) + r")\b", re.I)
# Set phrases that mention a substantive word in passing.
_PASSING = re.compile(r"\b(?:International )?Court of Justice\b"
                      r"|\b(?:these|this|our) (?:\w+ )?times? of crisis\b", re.I)
PASSING_MENTIONS = 1       # substantive or policy words tolerated in a cue sentence
# Share of words in ceremonial or salutation sentences. Measured against the agents'
# paragraph labels (1,841 tidy copies, fragments in the first 4 and last 2): 0.8 gives
# precision 0.98 and recall 0.26; 0.6 gives 0.97 and 0.47 (0.50 with the last three cues).
CEREMONIAL_SHARE = 0.6
CEREMONIAL_HEAD = 4        # only the first fragments of a speech ...
CEREMONIAL_TAIL = 2        # ... and the last ones can be ceremonial


def is_ceremonial_text(text: str) -> bool:
    """Greetings, congratulations, tributes and thanks with no policy content.

    Judged sentence by sentence: a sentence with a ceremonial cue may mention one
    substantive or policy word in passing ("guide the Organization through a
    process of reform"); a sentence without a cue that has a substantive word
    rules the fragment out, and UNODC mandate words anywhere always do.
    """
    if _MANDATE.search(text):
        return False
    cer = total = cues = 0
    for s in split_sentences(text):
        w = n_words(s)
        total += w
        if _SALUTE_ONLY.match(s):
            cer += w
            continue
        plain = _PASSING.sub("", s)
        substantive = len(_SUBSTANTIVE.findall(plain))
        mentions = substantive + len(_POLICY.findall(plain))
        if _CER_CUES.search(s):
            if mentions <= PASSING_MENTIONS:
                cer += w
                cues += 1
        elif substantive:
            return False
    return cues > 0 and total > 0 and cer >= CEREMONIAL_SHARE * total


def is_courtesy(text: str) -> bool:
    """A ceremonial or salutation-only paragraph (used to keep such paragraphs together)."""
    sents = split_sentences(text)
    return bool(sents) and (all(_SALUTE_ONLY.match(s) for s in sents) or is_ceremonial_text(text))


def flag_ceremonial(fragments: list[str]) -> list[bool]:
    n = len(fragments)
    return [(i < CEREMONIAL_HEAD or i >= n - CEREMONIAL_TAIL) and is_ceremonial_text(f)
            for i, f in enumerate(fragments)]
