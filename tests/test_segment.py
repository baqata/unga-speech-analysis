"""Unit tests for sentences, layouts, paragraph rebuilding, fragments and
ceremonial flags (pipeline.segment)."""
import random
import textwrap
import re
from collections import Counter

from pipeline import clean, segment
from pipeline.clean import Vocab
from pipeline.segment import MAX_WORDS, MIN_WORDS, n_words


def sentences(n: int, words: int = 20, start: int = 0) -> list[str]:
    """Distinct sentences of a fixed length."""
    return [" ".join(f"w{start + i}x{j}" for j in range(words - 1)).capitalize() + " end."
            for i in range(n)]


def para(n_sentences: int, words: int = 20, start: int = 0) -> str:
    return " ".join(sentences(n_sentences, words, start))


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Sentences
# ---------------------------------------------------------------------------

def test_sentence_split_with_abbreviations():
    text = ("Mr. Smith went to Washington. He met Dr. Jones, e.g. The talks at the U.S. Mission "
            "on Art. 2 and No. 5 continued. John F. Kennedy spoke. In 1945. 51 States signed. "
            "Did they? Yes! See para. 3 of the report... Then we left.")
    assert segment.split_sentences(text) == [
        "Mr. Smith went to Washington.",
        "He met Dr. Jones, e.g. The talks at the U.S. Mission on Art. 2 and No. 5 continued.",
        "John F. Kennedy spoke.", "In 1945.", "51 States signed.", "Did they?", "Yes!",
        "See para. 3 of the report...", "Then we left.",
    ]


def test_sentence_spans_cover_the_text():
    text = "  First sentence. “Quoted second.” (Third one.) Last words without a stop"
    spans = segment.sentence_spans(text)
    assert "".join(text[a:b] for a, b in spans) == text
    assert len(spans) == 4


# ---------------------------------------------------------------------------
# Layouts and paragraph reconstruction
# ---------------------------------------------------------------------------

def lines_of(raw: str, year: int = 2000):
    return clean.split_lines(raw, year, Counter())


def rebuild(raw: str, year: int = 2000, vocab: Vocab | None = None):
    lines = lines_of(raw, year)
    stats = segment.layout_stats(lines)
    layout = segment.detect_layout(lines, stats)
    counts = Counter()
    paragraphs = segment.rebuild_paragraphs(lines, layout, stats, vocab or Vocab(), counts)
    return layout, paragraphs, counts


WRAPPED = """At the outset, allow me to extend to you, Sir, our warmest
congratulations on your election to the presidency of the General
Assembly at its fifty-fifth session. We are confident that under your
leadership the work of the Assembly will be crowned with success. We
also wish to thank your predecessor for the able manner in which he
guided the work of the previous session and for his develop-
ment of new working methods.
The world has changed profoundly since the end of the cold war. The
threats we face today are no longer confined within national borders.
Terrorism, drug trafficking and organized crime know no frontiers and
demand a collective response from all Member States of this Organization.

The third paragraph starts after a blank line and it is also wrapped
at a fixed width like the others in this document.
"""


def test_wrapped_layout_rebuilds_paragraphs_and_hyphenation():
    layout, paragraphs, counts = rebuild(WRAPPED, vocab=Vocab(Counter({"development": 9})))
    assert layout == "wrapped"
    assert len(paragraphs) == 3
    assert paragraphs[0].startswith("At the outset") and paragraphs[0].endswith(
        "his development of new working methods.")
    assert paragraphs[1].startswith("The world has changed")
    assert paragraphs[2].startswith("The third paragraph")
    assert counts["hyphen_rejoined"] == 1


def test_line_layout_keeps_one_paragraph_per_line():
    raw = "\n".join(para(3, start=10 * i) for i in range(6))
    layout, paragraphs, _ = rebuild(raw, 1970)
    assert layout == "line"
    assert paragraphs == raw.split("\n")


def test_line_layout_joins_lines_that_continue_a_sentence():
    raw = "The General Assembly has before it\nthe question of Cyprus.\nA new paragraph."
    _, paragraphs, _ = rebuild(raw * 2, 1970)
    assert paragraphs[0] == "The General Assembly has before it the question of Cyprus."


def test_notes_layout():
    raw = "\n".join(["Excellencies,", "Ladies and gentlemen,"] +
                    [f"Point {i} of our statement is short." for i in range(14)] +
                    ["We will continue...", "and we will prevail."])
    layout, paragraphs, _ = rebuild(raw, 2024)
    assert layout == "notes"
    assert paragraphs[-1] == "We will continue... and we will prevail."


def test_single_line_layout():
    layout, paragraphs, _ = rebuild(para(40), 2025)
    assert layout == "single"
    assert len(paragraphs) == 1


# ---------------------------------------------------------------------------
# Fragments
# ---------------------------------------------------------------------------

def check_fragments(paragraphs, fragments):
    assert fragments and all(f.strip() for f in fragments)
    assert squash(" ".join(fragments)) == squash(" ".join(paragraphs))


def test_short_paragraphs_merge_and_short_last_merges_backwards():
    paragraphs = [para(1, 30, 0), para(5, 20, 10), para(1, 20, 20), para(4, 20, 30),
                  para(1, 15, 40)]
    fragments = segment.make_fragments(paragraphs)
    check_fragments(paragraphs, fragments)
    assert all(MIN_WORDS <= n_words(f) <= MAX_WORDS for f in fragments)
    assert fragments[-1].endswith(paragraphs[-1])
    assert "\n" in fragments[0]  # paragraphs inside a fragment are separated by a newline


def test_long_paragraph_splits_into_near_equal_parts():
    paragraphs = [para(40, 20)]  # 800 words
    fragments = segment.make_fragments(paragraphs)
    check_fragments(paragraphs, fragments)
    sizes = [n_words(f) for f in fragments]
    assert len(fragments) in (5, 6)
    assert max(sizes) - min(sizes) <= 20
    assert all(MIN_WORDS <= s <= MAX_WORDS for s in sizes)


def test_splits_prefer_paragraph_boundaries():
    paragraphs = [para(8, 20, 0), para(8, 20, 100)]  # 2 x 160 words
    fragments = segment.make_fragments(paragraphs)
    assert fragments == paragraphs


def test_speech_shorter_than_minimum_is_one_fragment():
    paragraphs = ["Thank you.", "We support peace."]
    assert segment.make_fragments(paragraphs) == ["Thank you.\nWe support peace."]


def test_overlong_sentence_is_cut_at_semicolons():
    clauses = [" ".join(f"c{i}w{j}" for j in range(29)) + ";" for i in range(12)]
    sentence = " ".join(clauses) + " end."
    fragments = segment.make_fragments([sentence])  # one 360-word sentence
    check_fragments([sentence], fragments)
    assert all(n_words(f) <= MAX_WORDS for f in fragments)


def test_unit_that_no_cut_keeps_within_bounds_stays_whole():
    # As in GTM_27_1972: every cut between these sentences (42, 190 and 57 words) leaves a
    # piece under MIN_WORDS, which costs more than one fragment over MAX_WORDS.
    paragraph = " ".join(sentences(1, 42) + sentences(1, 190, 1) + sentences(1, 57, 2))
    assert segment.make_fragments([paragraph]) == [paragraph]


def test_fragment_word_bounds_hold_for_many_shapes():
    rng = random.Random(1)
    for _ in range(200):
        paragraphs = [para(rng.randint(1, 15), rng.randint(5, 40), 100 * k)
                      for k in range(rng.randint(1, 12))]
        fragments = segment.make_fragments(paragraphs)
        check_fragments(paragraphs, fragments)
        total = sum(n_words(p) for p in paragraphs)
        if total >= MIN_WORDS:
            assert all(n_words(f) >= MIN_WORDS for f in fragments)
        assert all(n_words(f) <= MAX_WORDS for f in fragments)


# ---------------------------------------------------------------------------
# Ceremonial fragments
# ---------------------------------------------------------------------------

CEREMONIAL = (
    "Mr. President, allow me to congratulate you on your well-deserved election to the "
    "presidency of the General Assembly at its fifty-ninth session. I am confident that under "
    "your able leadership our deliberations will be crowned with success. I also wish to pay "
    "tribute to your predecessor for the skilful manner in which he guided our work. We thank "
    "the Secretary-General for his tireless efforts.")


def test_ceremonial_positive():
    assert segment.is_ceremonial_text(CEREMONIAL)
    assert segment.is_ceremonial_text("Mr. President, Excellencies, Ladies and gentlemen, "
                                      "Bismillahirrahmanirrahim. I thank you.")


def test_ceremonial_negative():
    # Substantive content anywhere in the fragment vetoes the flag.
    assert not segment.is_ceremonial_text(
        CEREMONIAL + " The fight against drug trafficking remains our priority.")
    # Policy words inside a congratulation make that sentence substantive.
    assert not segment.is_ceremonial_text(
        "We congratulate the President on the adoption of the 2030 Agenda for Sustainable "
        "Development, which will guide economic reform in our region for years to come.")
    # No ceremonial cue at all.
    assert not segment.is_ceremonial_text("Mr. President, Excellencies. Our island is small.")


def test_flag_ceremonial_only_at_the_edges():
    frags = [CEREMONIAL] * 8
    flags = segment.flag_ceremonial(frags)
    assert flags == [True] * segment.CEREMONIAL_HEAD + [False] * 2 + [True] * segment.CEREMONIAL_TAIL


# ---------------------------------------------------------------------------
# Review fixes: lost indents, hyphen joins, titles, sections, ceremonial cues
# ---------------------------------------------------------------------------

_WORDS = ("peace security development cooperation nations people country region world "
          "future challenge progress dialogue justice respect support effort commitment "
          "growth trade health climate water energy children women rights law order").split()


def indent_lost_speech(seed: int, n_paras: int = 8):
    """Paragraphs hard-wrapped at 64 characters whose first-line indent was stripped."""
    rnd = random.Random(seed)
    paras, lines = [], []
    for _ in range(n_paras):
        paras.append(" ".join("The " + " ".join(rnd.choice(_WORDS)
                                                for _ in range(rnd.randint(9, 16))) + "."
                              for _ in range(rnd.randint(3, 5))))
        wrapped = textwrap.wrap(paras[-1], 64, initial_indent=" " * 10)
        lines += [wrapped[0].lstrip()] + wrapped[1:]
    return paras, "\n".join(lines)


def test_underfilled_first_line_opens_a_paragraph(monkeypatch):
    # A sentence-final full-width line followed by a short first line: the indent
    # was lost (2013-14 records). Width alone finds 5 of the 8 paragraphs here.
    paras, raw = indent_lost_speech(1)
    layout, paragraphs, _ = rebuild(raw, 2013)
    assert layout == "wrapped" and paragraphs == paras
    monkeypatch.setattr(segment, "UNDERFILL", 0.0)
    assert len(rebuild(raw, 2013)[1]) < len(paras)


def test_line_end_hyphen_joins():
    vocab = Vocab(Counter({"year-old": 5, "up-to-date": 4, "into": 50, "development": 9}))
    cases = [("a 50-year-", "old man", "a 50-year-old man", "hyphen_kept"),
             ("the post-", "2015 agenda", "the post-2015 agenda", None),
             ("a 20-", "year plan", "a 20-year plan", None),
             ("inter-", "and intra-State wars", "inter- and intra-State wars", "hyphen_suspended"),
             ("keep it up-to-", "date", "keep it up-to-date", "hyphen_kept"),
             ("came in-", "to force", "came into force", "hyphen_rejoined"),
             ("the develop-", "ment agenda", "the development agenda", "hyphen_rejoined"),
             ("a dash --", "then more", "a dash -- then more", None)]
    for left, right, joined, rule in cases:
        counts = Counter()
        assert segment._join(left, right, vocab, counts) == joined, left
        if rule:
            assert counts[rule] == 1, left


def test_unmarked_titles_in_line_layouts():
    raw = ("Food Security\nThe pandemic has disrupted supply chains everywhere.\n"
           "We appreciate the UN's assistance in developing the National\n"
           "Strategy of our country against poverty.\nPage 4|6\nOur work goes on.\n"
           "Ocean Resources\nOur ocean is our future.\nMr. President,\nThank you.")
    lines = lines_of(raw, 2024)
    counts = Counter()
    segment.mark_titles(lines, "line", counts)
    assert [ln.text for ln in lines if ln.heading] == ["Food Security", "Ocean Resources"]
    assert counts["title_line"] == 2


def test_headings_glue_forward_and_sections_bound_merges():
    body = para(4)                                   # 80 words
    paragraphs = ["Climate Change", body, "We will act.", para(4, start=10), para(4, start=20)]
    marks = ["heading", "", "", "section", ""]
    units = segment.merge_short(paragraphs, marks)
    # The heading stays with its paragraph; the short last paragraph of the first
    # section merges backwards, not across the separator.
    assert units == [[0, 1, 2], [3], [4]]


def test_short_courtesy_paragraph_merges_with_its_own_kind():
    # Without kinds, the short paragraph would join the shorter (substantive) neighbour.
    paragraphs = [para(4), "Mr. President, I thank you.", para(3, start=10)]
    assert segment.merge_short(paragraphs) == [[0], [1, 2]]
    assert segment.merge_short(paragraphs, kinds=[True, True, False]) == [[0, 1], [2]]


CEREMONIAL_CUES = [
    "We welcome the new Member State to our family of nations.",
    "I wish you well in your important task.",
    "I assure you of the full support of my delegation.",
    "Your wisdom and long experience are well known to us all.",
    "I am confident that you will steer our work to a successful conclusion.",
    "The outgoing President ably guided the seventy-eighth session.",
    "We are pleased to see a son of Africa presiding over this Assembly.",
    "We offer our condolences to the people of Morocco.",
    "We are glad to see the admission of Tuvalu as a Member of the United Nations.",
]


def test_ceremonial_new_cues():
    for sentence in CEREMONIAL_CUES:
        assert segment.is_ceremonial_text("Mr. President, " + sentence), sentence


def test_ceremonial_tolerates_one_passing_mention():
    # One policy word in a congratulation (BHS 2019) is a passing mention.
    assert segment.is_ceremonial_text(
        "We congratulate the Secretary-General on his leadership of the reform of the "
        "Organization. I also congratulate the new President of the International Court of "
        "Justice on his election.")
    assert not segment.is_ceremonial_text(
        "We congratulate you. Nuclear weapons remain the gravest threat to humanity.")
