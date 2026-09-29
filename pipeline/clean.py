"""Cleaning rules for UN General Debate speech texts.

Every rule counts its replacements in a collections.Counter passed by the
caller (rule name -> number of replacements), so the QC report can show what
each rule did. Capitalisation and punctuation are kept: the text goes to a
transformer.

Order used by pipeline.prepare for a raw source file:
  normalise -> strip_editorial -> strip_other_speakers -> strip_markdown -> fix_ocr
  -> strip_presiding (transcripts only) -> split_lines
  -> (segment.rebuild_paragraphs) -> collapse_loops per paragraph
A tidy copy (data/tidy/TXT) already has its paragraphs: each paragraph only
goes through strip_editorial, strip_markdown and fix_ocr.
"""
import itertools
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

import numpy as np

from pipeline.segment import sentence_spans

# ---------------------------------------------------------------------------
# Character-level normalisation
# ---------------------------------------------------------------------------

# Longest keys first: they are applied in this order.
MOJIBAKE = {
    "â€™": "’", "â€˜": "‘", "â€œ": "“", "â€\x9d": "”", "â€”": "—",
    "â€“": "–", "â€¦": "…", "âÃª": "’ê", "âÃ©": "’é",
    "Ã©": "é", "Ã¨": "è", "Ãª": "ê", "Ã´": "ô", "Ã±": "ñ", "Ã¼": "ü",
    "Ã¶": "ö", "Ã¤": "ä", "Ã§": "ç", "Ã³": "ó", "Ã¡": "á", "Ã\xad": "í",
    "Ãº": "ú", "Ã\xa0": "à", "Ã ": "à",
}
_MOJIBAKE_RE = re.compile("|".join(re.escape(k) for k in MOJIBAKE))
# 1998 files also lost the tail of "’" before a possessive s or a capital
# ("Peopleâs", "UNITAâs", "Côte dâIvoire"); the pattern occurs only in 1998.
_MOJIBAKE_APOSTROPHE = re.compile(r"(?<=[A-Za-z])â(?=s\b|[A-Z])")
# U+FFFD replaced quotes and apostrophes in VAT_80_2025 ("this year�s", "�Peace�").
_REPLACEMENT_APOSTROPHE = re.compile(r"(?<=[A-Za-z])\ufffd(?=[A-Za-z])")

_SPACES = re.compile(r"[\u00a0\u2000-\u200a\u202f\u205f\u3000]")
_INVISIBLE = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff\u00ad]")
_LIGATURE_CHARS = re.compile(r"[\ufb00-\ufb06]")


def normalise(raw: str, counts: Counter) -> str:
    """BOM, line endings, exotic spaces, ligature characters and mojibake."""
    text = raw
    if text.startswith("\ufeff"):
        text = text[1:]
        counts["bom"] += 1
    n_crlf = text.count("\r\n")
    text = text.replace("\r\n", "\n")
    n_cr = text.count("\r")
    text = text.replace("\r", "\n")
    counts["crlf"] += n_crlf
    counts["cr_only"] += n_cr
    # Mojibake first: some of its sequences contain a soft hyphen or a no-break space.
    text, n = _MOJIBAKE_RE.subn(lambda m: MOJIBAKE[m.group()], text)
    text, n2 = _MOJIBAKE_APOSTROPHE.subn("’", text)
    text, n3 = _REPLACEMENT_APOSTROPHE.subn("’", text)
    text, n4 = re.subn("\ufffd", '"', text)
    counts["mojibake"] += n + n2 + n3 + n4
    text, n = _SPACES.subn(" ", text)
    counts["unicode_space"] += n
    text, n = _INVISIBLE.subn("", text)
    counts["invisible_char"] += n
    text, n = _LIGATURE_CHARS.subn(lambda m: unicodedata.normalize("NFKC", m.group()), text)
    counts["ligature_char"] += n
    return text


# ---------------------------------------------------------------------------
# Editorial insertions of the verbatim records
# ---------------------------------------------------------------------------

# "[277th meeting]", "[resolution 1514 (XV)]", "[A/8701/Add.1, para. 3]", "[ibid.]".
# Brackets without digits ("[OAU]", "[and]") are kept.
_BRACKET_REF = re.compile(
    r"[ \t]*\[(?=[^\[\]]*\d|\s*(?:see|ibid|idem)\b)[^\[\]]{1,200}\]", re.I)
# OCR often damaged the brackets: "[877th meeting)", "[A/8492J.", "[A/36731 at",
# "[resolution 502 (VI)}", "[resolution 2660 (XXV), annexJ". The removal stops where the
# reference itself ends, so a missing closer never takes speech text with it.
_REF_TAIL = (r"(?:,?\s*(?:annex(?:es)?|paras?\.?|paragraphs?|p\.|pp\.|chap\.|sect\.)"
             r"\s*[\dIVX]*[A-D]?(?:\s*(?:and|,|-)\s*[\dIVX]+)*)*")
_MEETING = (r"(?i:see\s+)?(?=[\dlIB]*\d)[\dlIB]{1,4}(?:st|nd|rd|th)\s+(?:plenary\s+)?meeting"
            + _REF_TAIL)
# Document symbols, also with an OCR-damaged slash ("A]33/241", "Aj33/206") and
# Disarmament Commission symbols ("DC/113").
_SYMBOL = (r"(?:[AS][/\\]|DC/|[AS][\]j](?=\d))\s?[\w/\\-]+(?:\.[\w/\\-]+)*(?:\.[ ]?[\dlI]+\b)?"
           r"(?:,?\s*(?:and\s+)?(?:Add|Corr)\.\s*[\dlI]+)*")
_RESOLUTION = (r"(?:[A-Z]{1,3}-)?[\dlI]{1,5}(?:/[\dlI]{1,4})*(?:\s?[A-Z]\b)?"
               r"\s*(?:[({f][^(){}\[\]\n]{1,12}[)}])?")
_REF_BODY = (
    r"(?i:see\s+)?(?:"
    + _MEETING
    + r"|" + _SYMBOL + r"(?:\s*(?:,|and)\s*" + _SYMBOL + r")*" + _REF_TAIL
    + r"|(?i:resolutions?)\s+" + _RESOLUTION + r"(?:\s*(?:,\s*(?:and\s+)?|and\s+)"
    + _RESOLUTION + r")*(?:[,i]?\s*annex\w*\s*[IVX]*)?" + _REF_TAIL
    # A resolution number without the word: "[377 (V)}", "[1474 (ES-IV)j", "[290 (IV)1".
    + r"|\d{2,4}\s?\((?:[IVXL]+|(?:ES|S)-[IVX]+)\)[1lj]?" + _REF_TAIL
    + r"|(?i:agenda\s+)?items?\s+[\dlI]{1,3}(?:\s?\([a-z]\))?"
    + r"|(?i:ibid)\.?" + _REF_TAIL
    + r")")
_REF_CLOSER = r"(?:\s*\.?\s*[)}|\]!]|\s*\.?\s*[Jj/](?=[\s.,;:?]|$))"
_BRACKET_REF_DAMAGED = re.compile(r"[ \t]*\[\s*" + _REF_BODY + _REF_CLOSER + "?", re.M)
# The same references with the opening bracket read as "/", "|", "{" or "f"
# ("/resolution 3202 (S-VI)]", "|DC/113. annex 5]", "fA/9001/Add.l]"): a closer is required.
_OPENER_REF_DAMAGED = re.compile(
    r"[ \t]*(?:(?<=\s)[/|{]|\bf(?=[AS]/|DC/))\s*" + _REF_BODY + _REF_CLOSER, re.M)
# Meeting references with a damaged opener ("(868th meeting]", "f680th meeting]",
# "{751st meeting}") or none ("1873rd meeting]"), and parenthetical ones ("(144th meeting)").
_MEETING_REF = re.compile(
    r"[ \t]*(?:[\[({]|\bf(?=\d))\s*" + _MEETING + r"\s*[\])}J]"
    r"|[ \t]*\b" + _MEETING + r"\s*[\]}]")
# Quoted-statement citations (1987-1996): "(Official Records of the General Assembly, ...)".
_OFFICIAL_RECORDS = re.compile(
    r"[ \t]*\(\s*(?:see\s+)?Official\s+Records\s+of\b(?:[^()]|\([^()]*\)){0,250}\)", re.I)
# Footnote lines, removed with their line break: "2 See Official Records of the Security
# Council, ...", "6/ Official Records ...", ".2/See ...", or an unnumbered line that starts
# with "Official Records of the <organ>"; and the scanning watermark of the 1974-1976 files.
_FOOTNOTE = re.compile(
    r"^[ \t]*(?:(?:\.?\d{1,2}/?|\^/|['’*])[ \t]*(?:See\s+[A-Z]|Ibid\b|Official Records of\b"
    r"|United Nations(?: publication|, Treaty Series)\b)"
    r"|Official Records of the (?:General Assembly|Security Council|Economic and Social Council)\b)"
    r".{0,300}$\n?", re.M)
_WATERMARK = re.compile(r"[ \t]*Digitized by Dag Hammarskj[oö]ld Library")
_SPEAKER_NOTE = re.compile(r"[ \t]*\[The speaker\b[^\[\]]{0,800}\]")
# "(see A/73/PV.6)", "(see resolution 70/1)", "(see )".
_SEE_REF = re.compile(r"[ \t]*\(\s*see\b(?:[^()\[\]]|\([^()]*\)){0,200}[)\]]", re.I)
# "(resolution 70/1)", "(A/70/PV.5, p. 3)", "(S/2015/1)", "(resolution 2625 (XXV))".
_DOC_REF = re.compile(
    r"[ \t]*\(\s*(?:(?:General Assembly|Security Council)\s+)?"
    r"(?:(?:resolutions?|decisions?|documents?)\s+)?"
    r"(?:[AS]/\s?[A-Z0-9]|\d{1,4}/\d|(?<=resolution )\d{1,4}\s?\([A-Z-]+\)|ibid\b|paras?\.\s?\d)"
    r"(?:[^()]|\([^()]*\)){0,150}\)")
# Verbatim-record boilerplate that OCR placed inside a few speeches (2013, 2017).
_RECORD_NOTE = re.compile(
    r"[ \t]*This record contains the text of speeches delivered in English.{0,700}?"
    r"(?:\(http://documents\.un\.org\)\.|consolidated corrigendum\.)", re.S)
_SPOKE_IN = re.compile(r"[ \t]*\((?:spoke|continued) in [A-Z][^()]{0,100}\)")
_APPLAUSE = re.compile(
    r"[ \t]*(?:[(\[](?i:applause|laughter|cheers|standing ovation)[^()\[\]]{0,30}[)\]]"
    r"|\bAPPLAUSE\b\.?)")


def strip_editorial(text: str, counts: Counter) -> str:
    """Remove meeting/document cross-references, language notes and applause notes."""
    for rule, pat in (("bracket_ref", _SPEAKER_NOTE), ("bracket_ref", _BRACKET_REF),
                      ("bracket_ref", _BRACKET_REF_DAMAGED), ("bracket_ref", _OPENER_REF_DAMAGED),
                      ("bracket_ref", _MEETING_REF),
                      ("see_ref", _SEE_REF), ("doc_ref", _DOC_REF),
                      ("doc_ref", _OFFICIAL_RECORDS), ("footnote", _FOOTNOTE),
                      ("watermark", _WATERMARK), ("record_note", _RECORD_NOTE),
                      ("spoke_in", _SPOKE_IN),
                      ("applause", _APPLAUSE)):
        text, n = pat.subn("", text)
        counts[rule] += n
    return text


# ---------------------------------------------------------------------------
# Markdown (2024 files)
# ---------------------------------------------------------------------------

_MD_BOLD = re.compile(r"\*\*([^*\n]+?)\*\*")
_MD_BOLD_EMPTY = re.compile(r"\*\*")
_MD_ITALIC = re.compile(r"(?<![*\w])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![*\w])")


def strip_markdown(text: str, counts: Counter) -> str:
    """Inline Markdown emphasis. Headers, bullets and rules are handled in split_lines."""
    text, n1 = _MD_BOLD.subn(r"\1", text)
    text, n2 = _MD_BOLD_EMPTY.subn("", text)
    text, n3 = _MD_ITALIC.subn(r"\1", text)
    counts["markdown"] += n1 + n2 + n3
    return text


# ---------------------------------------------------------------------------
# Corpus vocabulary (for hyphenation and ligature repair)
# ---------------------------------------------------------------------------

SUSPENDED = {"and", "or", "nor"}
SUSPENDED_MAX_FREQ = 3  # "interand" occurs once; "island", "command" thousands of times
_VOCAB_TOKEN = re.compile(r"[A-Za-z]+(?:-[A-Za-z]+)*")
_LINE_END_HYPHEN = re.compile(r"[-¬][ \t]*\n\s*")


class Vocab:
    """Lower-cased word counts over the whole corpus.

    Line-end hyphenations are split before counting, so "develop-\\nment"
    never counts as the compound "develop-ment".
    """

    def __init__(self, counts: Counter | None = None):
        self.counts = counts if counts is not None else Counter()
        self.decisions = Counter()  # (hyphenated form, chosen form) -> n, for QC

    def add(self, text: str) -> None:
        text = _LINE_END_HYPHEN.sub(" ", text).replace("¬", " ")
        self.counts.update(t.lower() for t in _VOCAB_TOKEN.findall(text))

    def freq(self, word: str) -> int:
        return self.counts.get(word.lower(), 0)

    def closed_or_hyphenated(self, left: str, right: str, after: str = "") -> tuple[str, bool]:
        """Join a word split by a hyphen: closed form only if it is attested
        more often than the hyphenated compound. Returns (word, closed?).

        `after` is the rest of a compound that continues the right part
        ("-date" in "up-/to-date"); when attested, the whole compound decides.
        A right part "and"/"or"/"nor" whose closed form is unattested is a
        suspended hyphen ("inter- and intra-State") and keeps its space.
        """
        closed, hyphenated = left + right, left + "-" + right
        if right[:1].isupper() or not left[-1:].isalpha():
            result = hyphenated
        elif after and self.freq(closed + after) + self.freq(hyphenated + after) > 0:
            better = self.freq(closed + after) > self.freq(hyphenated + after)
            result = closed if better else hyphenated
        elif right.lower() in SUSPENDED and self.freq(closed) < SUSPENDED_MAX_FREQ:
            result = left + "- " + right
        elif self.freq(closed) > self.freq(hyphenated):
            result = closed
        else:
            result = hyphenated
        self.decisions[(hyphenated, result)] += 1
        return result, result == closed


# ---------------------------------------------------------------------------
# OCR and speech-to-text repairs
# ---------------------------------------------------------------------------

# 2024 PDFs whose ligatures were lost: "Naons", "elecon" (IRN) and
# "Na5ons", "ci:zens", "be>er", "jus=ce", "se‘ng", ":des" (KNA).
LIGATURE_FILES = {"IRN_79_2024", "KNA_79_2024"}
_LIG_SYMBOLS = "5>=‘/:"
_LIG_TOKEN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]*(?:(?:[5>=‘/]|:(?=[A-Za-z,.;]))[A-Za-z]*)+")
_LIG_FILLS = ("ti", "tt", "ft", "fi", "fl", "ff", "ffi", "ffl", "tf", "tti")
_LIG_INSERTS = ("ti", "ft", "tt", "tf", "fi", "fl", "ff", "ffi", "ffl", "t", "f")
_WORD = re.compile(r"\b[A-Za-z]{2,}\b")
_LIG_MIN_FREQ = 5


def _match_case(candidate: str, original: str) -> str:
    return candidate[0].upper() + candidate[1:] if original[0].isupper() else candidate


def _best(cands, vocab: Vocab):
    scored = [(vocab.freq(c), c) for c in cands]
    freq, cand = max(scored) if scored else (0, None)
    return cand if freq >= _LIG_MIN_FREQ else None


def fix_ligatures(text: str, vocab: Vocab, counts: Counter) -> str:
    """Dictionary-checked repair of lost ligatures (only for LIGATURE_FILES)."""
    def symbol(m):
        parts = re.split(f"[{_LIG_SYMBOLS}]", m.group())
        if len(parts) > 4 or sum(len(p) for p in parts) < 2:
            return m.group()
        cands = []
        for fills in itertools.product(_LIG_FILLS, repeat=len(parts) - 1):
            cands.append(parts[0] + "".join(f + p for f, p in zip(fills, parts[1:])))
        cand = _best(cands, vocab)
        if cand is None:
            return m.group()
        counts["ligature_loss"] += 1
        return _match_case(cand.lower(), m.group().lstrip(_LIG_SYMBOLS))

    def missing(m):
        word = m.group()
        if vocab.freq(word) > 0 or word.isupper():
            return word
        low = word.lower()
        cands = [low[:i] + f + low[i:] for i in range(len(low) + 1) for f in _LIG_INSERTS]
        cand = _best(cands, vocab)
        if cand is None:
            return word
        counts["ligature_loss"] += 1
        return _match_case(cand, word)

    text = _LIG_TOKEN.sub(symbol, text)
    return _WORD.sub(missing, text)


# "modem" is an OCR misreading of "modern" (123 files). Replaced only when used
# as an adjective (followed by a word or a comma) and not followed by a telecom
# noun.
_MODEM = re.compile(
    r"\b([Mm])odem\b(?=,|\s+(?!(?:connections?|cables?|speeds?|cards?|routers?|dial)\b)[A-Za-z])")
_NOT_SIGN_EOL = re.compile(r"(?<=[A-Za-z])¬[ \t]*\n")
_NOT_SIGN_INLINE = re.compile(r"\b([A-Za-z]+)¬[ \t]*([A-Za-z]+)")
# OCR "1" for the pronoun "I" before a verb ("60. 1 should like", "and 1 believe"),
# only after sentence punctuation, a comma or a function word.
_ONE_FOR_I = re.compile(
    r"(\S*)(\s+)1 (?=(?:should|shall|would|will|wish|believe|think|hope|have|had|am|was"
    r"|must|can|cannot|could|may|might|do|did|now|also|feel|know|say|said|repeat|trust|come|turn"
    r"|refer|mention|use|consider|recall|agree|see|appeal|express|speak|stress|emphasize|note"
    r"|welcome|regret|thank|reiterate|assure|congratulate|pay|join|extend|associate|venture"
    r"|submit|propose|suggest|request|add|conclude|urge|ask|invite|remain|take|want|need"
    r"|hereby|personally|myself|further|therefore|sincerely|firmly|fully)\b)")
_ONE_FOR_I_BEFORE = {
    "and", "but", "that", "which", "as", "when", "if", "so", "because", "where", "while", "what",
    "before", "after", "since", "why", "how", "than", "whom", "therefore", "now", "here", "today",
    "again", "also", "indeed", "then", "whether", "until", "unless", "although", "though", "or",
    "nor", "yet", "once", "sir", "president", "gentlemen",
}


def _one_for_i(m: re.Match) -> str:
    prev = m.group(1)
    if (not prev or prev[-1] in ".!?:;,\"”’)" or re.fullmatch(r"\d{1,3}\.", prev)
            or prev.lower().strip("(“\"‘") in _ONE_FOR_I_BEFORE):
        return prev + m.group(2) + "I "
    return m.group()


_DISFLUENCY = re.compile(r"(?<![\w'’-])(?:uh|uhm|um|erm|Uh|Uhm|Erm)(?![\w'’-])[,.]?[ \t]?")
# A short prefix whose hyphen lost its digit to a space: "post- 2015", "mid- 1970s",
# "ES- 7/2", "COP- 23" (not "the fifth century- 1,200 years", a dash).
_PREFIX_DIGIT = re.compile(r"\b([A-Za-z]{1,5})- (?=\d)")


def fix_ocr(text: str, speech_id: str, year: int, vocab: Vocab, counts: Counter) -> str:
    """"modem", "1" for "I", "¬" used as a hyphen, "post- 2015", targeted ligature loss,
    disfluencies."""
    if speech_id in LIGATURE_FILES:
        text = fix_ligatures(text, vocab, counts)
    text, n = _MODEM.subn(lambda m: m.group(1) + "odern", text)
    counts["modem"] += n
    # A "¬" at a line end becomes an ordinary line-end hyphen (rejoined later).
    text, n1 = _NOT_SIGN_EOL.subn("-\n", text)

    def inline(m):
        return vocab.closed_or_hyphenated(m.group(1), m.group(2))[0]

    text, n2 = _NOT_SIGN_INLINE.subn(inline, text)
    text, n3 = re.subn("¬", "-", text)
    counts["not_sign"] += n1 + n2 + n3
    text, n = _PREFIX_DIGIT.subn(r"\1-", text)
    counts["prefix_digit"] += n
    if year <= 1991:
        before = text
        text = _ONE_FOR_I.sub(_one_for_i, text)
        if text != before:
            counts["one_for_i"] += before.count(" 1 ") + before.count("\t1 ") - (
                text.count(" 1 ") + text.count("\t1 "))
    text, n = _DISFLUENCY.subn("", text)
    counts["disfluency"] += n
    return text


# ---------------------------------------------------------------------------
# Presiding-officer text in speech-to-text transcripts (2025, provisional 2026)
# ---------------------------------------------------------------------------

_TITLES = (r"(?:president|vice[- ]president|prime minister|deputy prime minister|minister"
           r"|chair|chairman|chairperson|king|queen|emir|amir|crown prince|prince"
           r"|head|secretary|foreign minister|representative|premier|chancellor)")
_INTRO = [re.compile(p, re.I) for p in (
    r"\bassembly (?:now )?will (?:now )?(?:hear|be addressed)\b",
    r"\brequest (?:the )?protocol\b",
    r"\bprotocol to (?:please )?(?:escort|accompany|score|exhort)\b",
    r"\b(?:give|giving) the floor to\b",
    r"\bcall (?:up)?on (?:the next speaker|his excellency|her excellency)\b",
    r"\b(?:invite|inviting) (?:him|her|them|his excellency|her excellency|his majesty|her majesty)\b"
    r".{0,200}?\bto (?:address|speak|take)",
    r"\bcontinue (?:with )?(?:the|our) general debate\b",
    r"\bnext speaker\b",
)]
INTRO_WINDOW = 6  # the introduction is searched in the first sentences only
# Calls to order right after the introduction ("Please, order in the hall.").
_HALL = re.compile(r"^\W*(?:please,? )?(?:order in the hall|(?:please )?be seated|order,? please)\b"
                   r"(?:[^.!?]{0,40})[.!?]?\W*$", re.I)
_SALUTATION = re.compile(
    r"(?<!the )\b(?:Madam(?:e)? President|Mr\.? President|Mister President|Madam Chair"
    r"|Your (?:Excellency|Excellencies|Majesty|Majesties|Highness)|Excellencies|Distinguished"
    r"|Ladies and [Gg]entlemen|Bismillah\w*|Assalamu?\w*|In the name of|Very good (?:morning|afternoon)"
    r"|Good (?:morning|afternoon|evening)|Honou?rable|Mr\.? Secretary)")
# Everything from one of these near the end of a transcript is the presiding officer.
_CLOSING_ANCHOR = re.compile(
    r"On behalf of the (?:General )?Assembly,? I (?:wish to |would like to |want to )?thank"
    r"|I now give the floor to|The (?:General )?Assembly will (?:now )?hear"
    r"|We shall now continue the general debate", re.I)
CLOSING_WINDOW = 1000  # characters at the end of a transcript
_CLOSING = [re.compile(p, re.I) for p in (
    r"^\W*(?:and )?(?:now,? )?i (?:now )?(?:give|call on|call upon|invite)\b.*\b(?:floor|address the|to speak)",
    # "I thank His Excellency, Minister for Foreign Affairs ... of Egypt." but not the
    # speaker's "I thank the President of the General Assembly" or "... for their support".
    r"^\W*i (?:wish to |would like to )?thank,? (?:on behalf of the (?:general )?assembly,? )?"
    r"(?:the|his|her)\b(?!.*\bassembly\b)(?!.*\b(?:you|your|attention|listening)\b)"
    r"(?!.*\bfor (?:their|his|her|its|your|our)\b).*\b(?:of|in)\b",
    r"\bon behalf of the (?:general )?assembly\b",
    r"^\W*we have (?:thus )?heard the last speaker",
    r"^\W*(?:mr\.?|madam|madame) (?:president|prime minister|minister),? thank you",
)]
_CAPTION = re.compile(r"^(?:[A-Z][A-Z'’.-]*,?\s+){4,}(?=[A-Z][a-z])"
                      # Whisper's "Hon Albert CHAN Wai-yip Hon Philip MONG YANG ..." (LAO 2025)
                      r"|^(?:Hon\.?\s+[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*){1,2}\s+){2,}")
_TAIL_JUNK = re.compile(r"^(?!\W*(?:thank|thanks|merci|gracias|muchas|obrigad\w*|grazie|danke"
                        r"|vielen|amen|shukran|asante)\b)"
                        r"\W*[a-z]+(?:\s+[a-z]+)?\W*$|^\W*(?:okay|ok),? here we go\W*$", re.I)
# The speaker's name and title transcribed again after the introduction
# ("Taye Atske Selassie, President of the Federal Democratic Republic of Ethiopia").
_NAME_THEN_TITLE = re.compile(
    r"(?:(?:His|Her) (?:Excellency|Majesty|Highness),?\s+)?(?:(?:Mr|Mrs|Ms|Dr)\.?\s+)?"
    r"((?:[A-Z][\w'’.-]*\s+){0,5}[A-Z][\w'’.-]*),\s+(?:the\s+)?" + _TITLES + r"\b", re.I)
_NOT_A_NAME = re.compile(r"\b(?:President|Madam|Secretary|Excellenc\w*|Minister|Chair\w*"
                         r"|Distinguished|Ladies|General|Assembly|Heads?)\b")
_NAME_JOINERS = {"of", "the", "and", "for", "de", "del", "la", "le", "da", "do", "di", "du",
                 "bin", "bint", "ibn", "al", "el", "van", "von", "der", "y", "e"}


def _repeated_name_and_title(text: str) -> int:
    """Length of an opening that only repeats the speaker's name and title, or 0."""
    spans = sentence_spans(text[:600])
    end = spans[0][1] if spans else 0
    sal = _SALUTATION.search(text, 1, end)
    if sal:
        end = sal.start()
    m = _NAME_THEN_TITLE.match(text, 0, end)
    if not m or _NOT_A_NAME.search(m.group(1)):
        return 0
    words = re.findall(r"[\w’'-]+", text[m.start(1):end])
    if len(words) > 25 or any(w[0].islower() and w.lower() not in _NAME_JOINERS for w in words):
        return 0
    return end


def strip_presiding(text: str, counts: Counter, removed: list | None = None) -> str:
    """Remove the presiding officer's introduction and closing from a transcript."""
    # Introduction: cut after the last introductory sentence among the first ones,
    # or at a salutation when the speaker starts inside that sentence.
    head = sentence_spans(text[:3000])[:INTRO_WINDOW]
    hit = None
    for i, (start, end) in enumerate(head):
        if start > len(text) // 2:  # a short text: this is already the closing
            break
        matches = [m for m in (p.search(text, start, end) for p in _INTRO) if m]
        if matches:
            hit = (i, start, end, max(m.end() for m in matches))
    cut = 0
    if hit is not None:
        i, start, end, match_end = hit
        counts["presiding_intro"] += 1
        sal = _SALUTATION.search(text, match_end, end)
        cut = sal.start() if sal else end
        for start, end in sentence_spans(text[:3000])[i + 1:]:
            if not (start >= cut and _HALL.match(text[start:end])):
                break
            cut = end
        if removed is not None:
            removed.append(("intro", text[:cut].strip()))
    text = text[cut:].lstrip()
    m = _CAPTION.match(text)
    if m:
        counts["transcript_caption"] += 1
        if removed is not None:
            removed.append(("caption", m.group().strip()))
        text = text[m.end():]
    n = _repeated_name_and_title(text) if hit is not None else 0
    if n:
        counts["presiding_intro"] += 1
        if removed is not None:
            removed.append(("name", text[:n].strip()))
        text = text[n:].lstrip()

    # Closing: the presiding officer's thanks and anything after them, then
    # remaining short presiding sentences or transcription debris.
    stop = len(text)
    tail_start = max(0, len(text) - CLOSING_WINDOW)
    m = _CLOSING_ANCHOR.search(text, tail_start)
    if m:
        stop = m.start()
        counts["presiding_closing"] += 1
    spans = sentence_spans(text[:stop])
    for start, end in reversed(spans[-4:]):
        sent = text[start:end]
        if any(p.search(sent) for p in _CLOSING) or _TAIL_JUNK.match(sent):
            counts["presiding_closing"] += 1
            stop = start
        else:
            break
    if removed is not None and stop < len(text):
        removed.append(("closing", text[stop:].strip()))
    return text[:stop].rstrip()


# ---------------------------------------------------------------------------
# Other speakers inside a verbatim-record speech (all years)
# ---------------------------------------------------------------------------

# A speaker attribution at a line start, after an optional paragraph number:
# "The PRESIDENT (interpretation from French):", "The PRESIDENT (translated from Spanish);",
# "Mr. ROSALES (El Salvador):",
# "Mrs. de AMORIM (Sao Tome and Principe) (interpretation from French):".
_ATTRIBUTION = re.compile(
    r"^[ \t]*(?:\d{1,3}\.[ \t]*)?(?:"
    r"(?P<president>The (?:Acting )?(?:PRESIDENT|President)"
    r"(?: \((?:interpretation|translated) from \w+\))?\s?[:;])"
    r"|(?:Mr|Mrs|Ms|Miss|Sir|Mme|Dr)\.? (?:[a-z]{1,4} )?[A-Z][A-Z'-]{2,}(?: [A-Z][A-Z'-]+)*\s*"
    r"\((?P<country>[A-Z][^()\n]{2,60})\)(?:\s*\((?:interpretation|translated) from \w+\))?"
    r"\s*[:;])[ \t]*", re.M)
OWN_LABEL_ZONE = 0.05  # a delegation label in the first 5% of the text is the speaker's own


def _norm_name(name: str) -> str:
    return re.sub(r"^the ", "", re.sub(r"[^a-z ]", "", name.lower()).strip())


def _same_country(label: str, own_names) -> bool:
    label = _norm_name(label)
    return any(n and (n == label or n in label or label in n)
               for n in map(_norm_name, own_names))


def strip_other_speakers(text: str, own_names, counts: Counter,
                         removed: list | None = None) -> str:
    """Remove other speakers' words that the verbatim record left in a speech file.

    Text from the presiding officer's attribution or another delegation's
    ("The PRESIDENT:", "Mr. ROSALES (El Salvador):") is removed up to the next
    label of the speaker's own delegation, or to the end; the speaker's own
    labels are dropped. `own_names` are the speaker's country names; without
    them, delegation labels after the start are left alone.
    """
    pieces, pos, keep = [], 0, True
    for m in _ATTRIBUTION.finditer(text):
        segment = text[pos:m.start()]
        if keep:
            pieces.append(segment)
        elif removed is not None and segment.strip():
            removed.append(("other_speaker", segment.strip()))
        country, drop_label = m.group("country"), True
        if m.group("president"):
            keep = False
        elif m.start() < OWN_LABEL_ZONE * len(text) or _same_country(country, own_names):
            keep = True
            counts["speaker_label"] += 1
        elif own_names:
            keep = False
        else:
            drop_label = False
        if drop_label and not keep:
            counts["other_speaker"] += 1
        pos = m.end() if drop_label else m.start()
    if keep:
        pieces.append(text[pos:])
    elif removed is not None and text[pos:].strip():
        removed.append(("other_speaker", text[pos:].strip()))
    return "".join(pieces)


# ---------------------------------------------------------------------------
# Lines: boilerplate removal and structure markers
# ---------------------------------------------------------------------------

@dataclass
class Line:
    text: str            # stripped, without paragraph number or bullet
    indent: bool         # started with whitespace in the source
    numbered: bool       # started with a paragraph number
    gap: str             # what preceded it: 'none', 'blank', 'page' or 'sep'
    heading: bool = False
    bullet: bool = False


_PAGE_NUMBER = re.compile(r"\d{1,3}")
_JOB = r"\d{2}-\d{5}(?:\s?\(E\))?(?:\s+\*?\d{7}\*?)?"  # job number, optional barcode
_DATE = r"\d{2}/\d{2}/\d{4}"
_PV = r"A/(?:\d{1,2}/)?PV\.\s?\d{1,4}"
_PAGE_OF = r"\d{1,3}(?:/\d{1,3})?"
# Running heads of the 1993-1996 records: "22 General Assembly - Forty-eighth session",
# "Forty-eighth session - 11 October l993 21", "General Assembly 22nd plenary meeting",
# "Fiftieth session 13 October 1995".
_ORDINAL = r"[A-Z][a-z]+(?:-[a-z]+)?(?:th|st|nd|rd)"
_MONTH = (r"(?:January|February|March|April|May|June|July|August|September|October|November"
          r"|December)")
_SESSION_HEAD = (
    rf"(?:{_PAGE_OF}\s+)?General Assembly\s*(?:-\s*)?"
    rf"(?:{_ORDINAL}\s+session|\d{{1,4}}(?:st|nd|rd|th)\s+(?:plenary\s+)?meeting)(?:\s+{_PAGE_OF})?"
    rf"|{_ORDINAL}\s+session(?:\s*-)?\s+\d{{1,2}}\s+{_MONTH}\s+[l1]\d{{3}}(?:\s+{_PAGE_OF})?")
_HEADER_LINE = re.compile(
    rf"(?:{_PAGE_OF}\s+)?{_JOB}(?:\s+{_PAGE_OF})?"
    rf"|(?:(?:{_DATE}|{_PAGE_OF})\s+)?{_PV}(?:\s+and\s+Corr\.\s?[l1I])?(?:\s+{_DATE})?"
    rf"|{_DATE}|{_SESSION_HEAD}")
_INLINE_HEADER = re.compile(
    rf"(?:{_PAGE_OF}\s+{_JOB}|{_JOB}\s+{_PAGE_OF}|{_JOB}|{_DATE}\s+{_PV}|{_PV}\s+{_DATE}"
    rf"|{_SESSION_HEAD})\s+(?=\S)")
_TRAILING_HEADER = re.compile(rf"[\s»,]+{_PV}\s+and\s+Corr\.\s?[l1I]$")
_SEPARATOR = re.compile(r"[-_*=•▪·■—–~#\s]+")
_TRAILING_SEPARATOR = re.compile(r"(?:\s+[*•▪]+)+$")
_PUNCT_ONLY = re.compile(r"[.,;:!?)\]”’\"]+")
_MD_HEADING = re.compile(r"#{1,6}\s+(?:\d{1,2}\.\s+)?")
_BULLET = re.compile(r"(?:[-*•▪·–−]|\d{1,2}\))\s+(?=\S)")
_BULLET_ONLY = "•▪"  # never punctuation: a list marker wherever it opens a line
# Bullets on this many sentence continuations mark printed lines, not list items
# (every line of SUR_79_2024 starts with "•").
DECORATIVE_BULLETS = 3
_LONE_NUMBER = re.compile(r"\d{1,3}\.")
_PARA_NUMBER = re.compile(r"(\d{1,3})\.([\t ]+)(?=\S)")
_INLINE_PARA_NUMBER = re.compile(r"(?<=[.!?:;\"”’)\]])[ \t]+(\d{1,3})\.[ \t]+(?=[A-Z“\"‘'(])")
_LEADING_PUNCT = re.compile(r"[.,;:]+\s+(?=\S)")
_TERMINAL = re.compile(r"[.!?:;…][\"”’'»)\]]*$")


def split_lines(text: str, year: int, counts: Counter) -> list[Line]:
    """Split into content lines, dropping page furniture and recording structure."""
    lines: list[Line] = []
    gap = "none"
    prev_terminal = True
    last_num = None  # last paragraph number seen, to accept numbers in sequence
    number_next = False  # a paragraph number stood alone on the previous line
    continued = 0  # bullets that open a sentence continuation
    for raw in text.split("\n"):
        if "\x0c" in raw:
            counts["form_feed"] += raw.count("\x0c")
            raw = raw.replace("\x0c", " ")
            gap = "page"
        s = raw.rstrip()
        st = s.strip()
        if not st:
            if gap == "none":
                gap = "blank"
            continue
        if _PAGE_NUMBER.fullmatch(st):
            counts["page_number"] += 1
            gap = "page"
            continue
        if _HEADER_LINE.fullmatch(st):
            counts["page_header"] += 1
            gap = "page"
            continue
        if _SEPARATOR.fullmatch(st):
            counts["separator"] += 1
            gap = "sep"
            continue
        if _LONE_NUMBER.fullmatch(st) and (prev_terminal or gap != "none" or not lines):
            counts["para_number"] += 1
            number_next, last_num = True, int(st[:-1])
            continue
        if _PUNCT_ONLY.fullmatch(st) and lines:
            lines[-1].text += st
            continue
        m = _INLINE_HEADER.match(st)
        if m:
            counts["page_header"] += 1
            st = st[m.end():]
            gap = "page"
        m = _TRAILING_HEADER.search(st)
        if m:
            counts["page_header"] += 1
            st = st[:m.start()]
        m = _TRAILING_SEPARATOR.search(st)
        sep_after = bool(m)
        if m:
            counts["separator"] += 1
            st = st[:m.start()]
        line = Line(text=st, indent=s[:1] in (" ", "\t"), numbered=number_next, gap=gap)
        number_next = False
        m = _MD_HEADING.match(line.text)
        if m:
            line.text, line.heading = line.text[m.end():], True
            counts["markdown"] += 1
        at_start = prev_terminal or gap != "none" or not lines
        m = _BULLET.match(line.text)
        if m and (at_start or lines[-1].bullet or line.text[0] in _BULLET_ONLY):
            line.text = line.text[m.end():]
            counts["bullet"] += 1
            if at_start or not line.text[:1].islower():
                line.bullet = True
            else:  # "• from the, disastrous consequences" continues the sentence above
                continued += 1
        for _ in range(4):  # "63.\t31.\t" and ". 86. " occur
            m = _LEADING_PUNCT.match(line.text)
            if m and at_start:
                line.text = line.text[m.end():]
                counts["stray_punct"] += 1
                continue
            m = _PARA_NUMBER.match(line.text)
            if not m:
                break
            num, rest = int(m.group(1)), line.text[m.end():]
            if year <= 1991:
                in_sequence = last_num is not None and 0 < num - last_num <= 3
                ok = "\t" in m.group(2) or at_start or in_sequence
            else:
                ok = at_start and (rest[0].isupper() or rest[0].isdigit() or rest[0] in "“\"'‘(*")
            if not ok:
                break
            line.text, line.numbered, last_num = rest, True, num
            counts["para_number"] += 1
        # Paragraph numbers inside a line (structure lost in the source), 1946-1991.
        parts = [line]
        while year <= 1991 and last_num is not None:
            cur = parts[-1]
            m = next((m for m in _INLINE_PARA_NUMBER.finditer(cur.text)
                      if 0 < int(m.group(1)) - last_num <= 2), None)
            if m is None:
                break
            last_num = int(m.group(1))
            counts["para_number"] += 1
            parts.append(Line(text=cur.text[m.end():], indent=False, numbered=True, gap="none"))
            cur.text = cur.text[:m.start()]
        for part in parts:
            if part.text:
                lines.append(part)
                prev_terminal = bool(_TERMINAL.search(part.text))
        gap = "sep" if sep_after else "none"
    if continued >= DECORATIVE_BULLETS:
        for line in lines:
            line.bullet = False
    return lines


# ---------------------------------------------------------------------------
# Repeated n-gram loops (speech-to-text artefacts, duplicated passages)
# ---------------------------------------------------------------------------

_TOKEN = re.compile(r"\S+")
_KEY_PUNCT = "\"'“”‘’«»()[]{}.,;:!?…—–-*"
LOOP_SHORT_MAX = 14      # n-grams of 1..14 words must repeat >= 4 times
LOOP_SHORT_REPEATS = 4
LOOP_LONG_MAX = 60       # n-grams of 15..60 words collapse when repeated twice


# A deliberate repetition ("I repeat: the French authorities ...") is never a loop.
_NEVER_MATCH = {"", "repeat"}


def _key(token: str) -> str:
    return token.strip(_KEY_PUNCT).lower()


def _ids(keys: list[str]) -> np.ndarray:
    """Integer ids; punctuation-only tokens (empty keys) and "repeat" never match."""
    index = {}
    return np.fromiter((-1 - i if k in _NEVER_MATCH else index.setdefault(k, len(index))
                        for i, k in enumerate(keys)), dtype=np.int64, count=len(keys))


def _needed(n: int) -> int:
    """Length of the run of equal tokens at lag n that makes a loop."""
    return (LOOP_SHORT_REPEATS - 1) * n if n <= LOOP_SHORT_MAX else n


def _loop(ids: np.ndarray, long_loops: bool = True):
    """First (start, n, copies) loop that meets the thresholds, or None."""
    longest = LOOP_LONG_MAX if long_loops else LOOP_SHORT_MAX
    for n in range(1, min(longest, len(ids) // 2) + 1):
        need = _needed(n)
        if len(ids) - n < need:
            continue  # need is not monotonic in n: longer n-grams need fewer repeats
        eq = ids[:-n] == ids[n:]
        if eq.sum() < need:
            continue
        c = np.concatenate(([0], np.cumsum(eq)))
        hits = np.flatnonzero(c[need:] - c[:-need] == need)
        if len(hits):
            start = int(hits[0])
            end = start + need
            while end < len(eq) and eq[end]:
                end += 1
            return start, n, (end - start + n) // n
    return None


def collapse_loops(text: str, counts: Counter, removed: list | None = None,
                   long_loops: bool = True) -> str:
    """Keep one copy of an n-gram repeated back to back (e.g. a Whisper loop).

    Passages of more than LOOP_SHORT_MAX words repeated twice are collapsed only
    with `long_loops` (sources with duplication errors: OCR and transcripts).
    """
    for _ in range(20):
        tokens = list(_TOKEN.finditer(text))
        if len(tokens) < 8:
            return text
        found = _loop(_ids([_key(t.group()) for t in tokens]), long_loops)
        if found is None:
            return text
        start, n, copies = found
        a = tokens[start + n].start()
        b = tokens[start + copies * n].start() if start + copies * n < len(tokens) else len(text)
        if removed is not None:
            removed.append((f"{copies} x {n}-gram", text[tokens[start].start():b]))
        text = text[:a] + text[b:]
        counts["ngram_loop"] += 1
        counts["ngram_loop_words"] += (copies - 1) * n
    return text


def collapse_loops_all(paragraphs: list[str], counts: Counter, removed: list | None = None,
                       long_loops: bool = True) -> list[str]:
    """collapse_loops over a speech; one vectorised check first, since loops are rare."""
    keys = []
    for i, p in enumerate(paragraphs):
        keys.extend(_key(t) for t in p.split())
        keys.append(f"\x00{i}")  # paragraph boundaries never match each other
    if len(keys) < 8 or _loop(_ids(keys), long_loops) is None:
        return paragraphs
    return [collapse_loops(p, counts, removed, long_loops) for p in paragraphs]
