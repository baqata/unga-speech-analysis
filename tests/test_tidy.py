"""Tests for the tidy tool: normalisation, units, validation and text assembly."""
from pipeline import tidy


def unit_texts(raw):
    return [u["t"] for u in tidy.unitize(raw)["units"]]


def all_kept(data):
    return {"id": "X", "drop": [], "para": [0], "cer": [], "fix": [], "flags": [], "note": ""}


def test_line_endings_and_bom():
    assert unit_texts("﻿One line.\rSecond line.\r\nThird.") == ["One line.", "Second line.", "Third."]


def test_paragraph_numbers_stripped_only_when_numbering():
    numbered = "\n".join(f"{n}.\tParagraph {n} text." for n in range(66, 72))
    assert unit_texts(numbered)[0] == "Paragraph 66 text."
    listed = "Intro sentence here.\n1.\tFirst item;\n2.\tSecond item;\n3.\tThird item.\n" + "\n".join(
        f"Body paragraph {n}." for n in range(6))
    assert "1. First item;" in unit_texts(listed)


def test_boilerplate_patterns():
    raw = ("We support peace [799th meeting] and law (see A/73/PV.6).\n12\n09-52592\n"
           "22/26 15-29876\nA/70/PV.24 01/10/2015\nMr. X (spoke in French): Thank you. (Applause)")
    texts = unit_texts(raw)
    assert texts == ["We support peace and law.", "Mr. X: Thank you."]


def test_speaker_numbers_survive():
    assert unit_texts("In 1945, 51 States signed.\nWe count 193 today.") == [
        "In 1945, 51 States signed.", "We count 193 today."]


def test_mojibake_and_markdown():
    assert unit_texts("â€œPeaceâ€\x9d â€” now\n### Heading\n**Bold** text\n---") == [
        "“Peace” — now", "Heading", "Bold text"]


def test_sentence_split_respects_abbreviations():
    line = ("Mr. Smith of the U.S. met Dr. J. Brown on 5 Sept. 2001 in New York. " * 3).strip()
    parts = tidy.split_sentences(line)
    assert len(parts) == 3 and parts[0].startswith("Mr. Smith") and parts[0].endswith("New York.")


def test_long_lines_become_sentence_units():
    line = " ".join(["This sentence has exactly eight words in it."] * 7)
    data = tidy.unitize(line)
    assert data["layout"] == "single" and len(data["units"]) == 7


def test_marks():
    data = tidy.unitize("First line.\nSecond line.\n\nThird after blank.")
    marks = [(u["nl"], u["bl"]) for u in data["units"]]
    assert marks == [(False, False), (True, False), (True, True)]


def test_round_trip_all_kept():
    raw = "Peace is vital.\nWe must act now.\n\nDevelopment matters too."
    data = tidy.unitize(raw)
    norm, errors, _ = tidy.validate_decision(all_kept(data), data)
    assert not errors
    text = " ".join(p["text"] for p in tidy.build_text(data, norm, {}))
    assert text.split() == raw.split()


def test_dehyphenation():
    data = tidy.unitize("the develop-\nment of fifty-\nsecond sessions")
    d, _, _ = tidy.validate_decision(all_kept(data), data)
    vocab = {"development": 50, "fiftysecond": 0, "fifty-second": 30}
    assert tidy.build_text(data, d, vocab)[0]["text"] == "the development of fifty-second sessions"


def test_validation_errors():
    data = tidy.unitize("\n".join(f"Sentence {i}." for i in range(6)))
    bad = {"id": "X", "drop": [[0, 2, "presider"], [2, 3, "noise"]], "para": [1, 4], "cer": [5],
           "fix": [[4, "Sentence", "Totally different words", "ocr"], [5, "absent", "x", "ocr"]],
           "flags": ["nope"], "note": ""}
    _, errors, _ = tidy.validate_decision(bad, data)
    joined = " ".join(errors)
    for needle in ("overlap", "dropped or out of range", "not paragraph starts", "rewrite", "occurs 0 times",
                   "flags"):
        assert needle in joined


def test_drops_paragraphs_fixes_apply():
    data = tidy.unitize("The Assembly will hear an address.\nColumbia is here.\nPeace now.\nThank you.")
    d = {"id": "X", "drop": [[0, 0, "presider"]], "para": [1, 3], "cer": [3],
         "fix": [[1, "Columbia", "Colombia", "asr_name"]], "flags": [], "note": ""}
    norm, errors, notices = tidy.validate_decision(d, data)
    assert not errors and not notices
    paras = tidy.build_text(data, norm, {})
    assert [p["text"] for p in paras] == ["Colombia is here. Peace now.", "Thank you."]
    assert [p["cer"] for p in paras] == [False, True]


def test_first_kept_unit_is_added():
    data = tidy.unitize("Intro.\nBody one.\nBody two.")
    norm, errors, notices = tidy.validate_decision(
        {"id": "X", "drop": [[0, 0, "presider"]], "para": [2]}, data)
    assert not errors and norm["para"] == [1, 2] and notices


def test_label_fix_removes_text_only():
    data = tidy.unitize("Mr. X (France): We agree.")
    ok = {"id": "X", "para": [0], "fix": [[0, "Mr. X (France): ", "", "label"]]}
    norm, errors, _ = tidy.validate_decision(ok, data)
    assert not errors and tidy.build_text(data, norm, {})[0]["text"] == "We agree."
    bad = {"id": "X", "para": [0], "fix": [[0, "Mr. X (France): ", "Hello ", "label"]]}
    assert tidy.validate_decision(bad, data)[1]


def test_short_asr_names_may_be_respelled():
    data = tidy.unitize("We thank Somdik Desyogunsan for resolution 57 Stroke 26.")
    ok = {"id": "X", "para": [0], "fix": [[0, "Somdik Desyogunsan", "Samdech Techo Hun Sen", "asr_name"],
                                         [0, "57 Stroke 26", "57/26", "asr_term"]]}
    norm, errors, _ = tidy.validate_decision(ok, data)
    assert not errors and "Samdech Techo Hun Sen for resolution 57/26." in tidy.build_text(data, norm, {})[0]["text"]
    ocr = {"id": "X", "para": [0], "fix": [[0, "Somdik Desyogunsan", "Samdech Techo Hun Sen", "ocr"]]}
    long = {"id": "X", "para": [0], "fix": [[0, "We thank Somdik Desyogunsan for", "Other words were said here", "asr_name"]]}
    assert tidy.validate_decision(ocr, data)[1] and tidy.validate_decision(long, data)[1]



def test_interpreter_slip_replaces_the_wrong_words_only():
    data = tidy.unitize("In six years of government we cut crime.")
    ok = {"id": "X", "para": [0], "fix": [[0, "six years", "six months", "interp"]]}
    norm, errors, _ = tidy.validate_decision(ok, data)
    assert not errors and tidy.build_text(data, norm, {})[0]["text"] == "In six months of government we cut crime."
    reworded = {"id": "X", "para": [0], "fix": [[0, "In six years of government we cut crime.",
                                               "In our first months in office crime fell.", "interp"]]}
    assert tidy.validate_decision(reworded, data)[1]


def test_slip_replaces_the_wrong_words_only():
    data = tidy.unitize("We renew our commitment to the Charter of the United States.")
    ok = {"id": "X", "para": [0], "fix": [[0, "United States", "United Nations", "slip"]]}
    norm, errors, _ = tidy.validate_decision(ok, data)
    assert not errors and tidy.build_text(data, norm, {})[0]["text"] == \
        "We renew our commitment to the Charter of the United Nations."
    reworded = {"id": "X", "para": [0], "fix": [[0, "We renew our commitment to the Charter of the United States.",
                                               "The Charter remains our compass.", "slip"]]}
    assert tidy.validate_decision(reworded, data)[1]


def test_pagination_limits():
    blocks = [(f"S{i}", ["=== S%d" % i] + ["x" * 100] * 300) for i in range(5)]
    for lines, _ in tidy.paginate(blocks):
        assert sum(len(ln) + 1 for ln in lines) <= tidy.PAGE_CHARS + 200
    huge = [("BIG", ["=== BIG"] + ["y" * 1000] * 200)]
    pages = tidy.paginate(huge)
    assert len(pages) > 1 and pages[1][0][0].startswith("=== BIG (continued)")


def test_paragraph_numbers_removed_at_assembly():
    lines = [f"{n}. Paragraph {n} starts here and" if n % 2 else f"{n}." for n in range(1, 9)]
    raw = "\n".join(f"{ln}\ncontinues on the next line." for ln in lines)
    data = tidy.unitize(raw)
    starts = [i for i, u in enumerate(data["units"]) if tidy.PARA_NUMBER.match(u["t"])]
    d, errors, _ = tidy.validate_decision({"id": "X", "para": starts}, data)
    assert not errors
    paras = tidy.build_text(data, d, {})
    assert len(paras) == 8 and all(not tidy.PARA_NUMBER.match(p["text"]) for p in paras)
    assert paras[0]["text"] == "Paragraph 1 starts here and continues on the next line."
    assert paras[1]["text"] == "continues on the next line."


def test_short_numbered_list_kept():
    data = tidy.unitize("Our aims:\n1. Peace.\n2. Justice.\n3. Development.")
    d, _, _ = tidy.validate_decision({"id": "X", "para": [0]}, data)
    assert "1. Peace." in tidy.build_text(data, d, {})[0]["text"]


def test_leftover_numbers_in_tab_numbered_record():
    raw = "\n".join(f"{n}.\tParagraph {n}." for n in range(50, 56)) + "\n56. Leftover paragraph."
    data = tidy.unitize(raw)
    d, _, _ = tidy.validate_decision({"id": "X", "para": list(range(len(data["units"])))}, data)
    assert tidy.build_text(data, d, {})[-1]["text"] == "Leftover paragraph."


def test_space_before_punctuation_removed():
    assert tidy.tidy_spacing("the Charter [A/1376] .  Next , item") == "the Charter [A/1376]. Next, item"


def test_line_end_hyphen_before_digits():
    data = tidy.unitize("the post-\n2015 agenda for 2016-\n2017 and a 20-\nyear plan")
    d, _, _ = tidy.validate_decision({"id": "X", "para": [0]}, data)
    assert tidy.build_text(data, d, {})[0]["text"] == "the post-2015 agenda for 2016-2017 and a 20-year plan"


def test_editorial_references_removed():
    cases = {
        "as agreed (resolution 1 (I), para. 5 (c)). Next": "as agreed. Next",
        "the report (A/54/2000, para. 17) says": "the report says",
        "adopted (resolutions 65/283 and 66/291) and": "adopted and",
        "the Agenda (resolution 70/1). We": "the Agenda. We",
        "see the statement (see S/PV.4208).": "see the statement.",
        "Council resolution [242 (1967)] must": "Council resolution must",
        "as stated [A/7601/Add.1, para. 84], we": "as stated, we",
        "resolution 242 (1967) must be applied": "resolution 242 (1967) must be applied",
        "in 1945 (the year of San Francisco) we": "in 1945 (the year of San Francisco) we",
        "Article 51 (self-defence) applies": "Article 51 (self-defence) applies",
    }
    for raw, want in cases.items():
        assert tidy.tidy_spacing(tidy.strip_editorial_refs(raw)) == want, raw


def test_short_paragraph_warning():
    data = {"units": [{"t": "x"}] * 20, "layout": "lines"}
    d = {"drop": [], "fix": []}

    def paras(lengths, cer=()):
        return [{"start": i, "text": "w " * n, "cer": i in cer} for i, n in enumerate(lengths)]

    def short_warn(ps):
        return [w for w in tidy.warnings_for(data, d, ps, 1000, 1000) if "fewer than 60" in w]

    # greetings, one short body paragraph and a short closing line are allowed
    assert not short_warn(paras([20, 100, 40, 100, 100, 100, 10], cer={0}))
    warn = short_warn(paras([100, 40, 100, 30, 100, 100, 100, 100, 100, 100, 100, 100]))
    assert warn and "units 1, 3" in warn[0]
    # two short paragraphs are fine once they are fewer than 1 in 10
    assert not short_warn(paras([100, 40] + [100] * 20 + [30, 100]))


def test_repairs_checked_word_by_word():
    ok = [("answers^ answers", "answers, answers", "ocr"), ("to ? foreign", "to a foreign", "ocr"),
          ("economicdevelopment", "economic development", "merged_word"), ("res pons ib ility", "responsibility", "split_word"),
          ("Secretary- General", "Secretary-General", "hyphen"), ("the wodd today", "the world today", "ocr"),
          ("Kampucheaóare", "Kampuchea—are", "encoding"), ("Srinath Dubego", "Trinidad and Tobago", "asr_name")]
    for old, new, reason in ok:
        assert tidy.repair_problem(old, new, reason) is None, (old, new)
    bad = {("spectators of it This", "spectators of it. This", "ocr"): "adds punctuation",
           ("the General Assembly", "the General Assembly,", "spacing"): "adds punctuation",
           ("have not referred", "I have not referred", "ocr"): "adds a word",
           ("to sued) a challenge", "to such a challenge", "ocr"): "rewrite",
           ("why Srinath Dubego sought", "why Trinidad and Tobago sought", "asr_name"): "rewrite"}
    for (old, new, reason), why in bad.items():
        assert why in (tidy.repair_problem(old, new, reason) or ""), (old, new)
