"""Tests for pipeline.prepare: source discovery, a small end-to-end run on a
fixture corpus (including a provisional 2026 transcript), token counting and,
marked slow, the invariants of a full run over the real corpus.

    uv run pytest tests/test_prepare.py -m "not slow"   # fast tests only
    uv run pytest tests/test_prepare.py -m slow         # full corpus (about 4 minutes)
"""
import hashlib
import json
import re
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from pipeline import config, prepare, segment, tidy
from pipeline.speakers import POST_CATEGORIES, load_speakers, post_category

V14_SPEECHES = 11_141 - 192  # the corpus's 2024 texts are replaced by the verbatim records
OFFICIAL_SPEECHES = 193  # data/official/Session 79 - 2024 (A/79/PV.7-17)


class WhitespaceTokenizer:
    """Stand-in for the Harrier tokenizer: one token per whitespace-separated word."""

    def encode_batch(self, texts, add_special_tokens=False):
        return [SimpleNamespace(ids=t.split()) for t in texts]


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def can_cut(sizes: list[int]) -> bool:
    """Can consecutive units of these word counts be grouped into pieces of MIN_WORDS to MAX_WORDS?"""
    ok = [True] + [False] * len(sizes)
    for j in range(1, len(sizes) + 1):
        ok[j] = any(ok[i] and segment.MIN_WORDS <= sum(sizes[i:j]) <= segment.MAX_WORDS
                    for i in range(j))
    return ok[-1]


def check_invariants(speeches: pd.DataFrame, fragments: pd.DataFrame) -> None:
    """Invariants shared by the fixture run and the full-corpus run."""
    assert list(speeches.columns) == prepare.SPEECH_COLUMNS
    assert list(fragments.columns) == prepare.FRAGMENT_COLUMNS
    assert speeches.speech_id.is_unique
    # frag_id is contiguous and follows (year, iso3, seq).
    assert (fragments.frag_id.to_numpy() == np.arange(len(fragments))).all()
    order = fragments.sort_values(["year", "iso3", "seq"], kind="stable").frag_id
    assert (order.to_numpy() == np.arange(len(fragments))).all()
    # Every speech has at least one fragment, and no fragment is empty.
    counts = fragments.groupby("speech_id").size()
    n_fragments = speeches.set_index("speech_id").n_fragments
    assert (n_fragments == counts.reindex(n_fragments.index, fill_value=0)).all()
    assert (speeches.n_fragments >= 1).all()
    assert (fragments.n_words > 0).all() and fragments.text.str.strip().ne("").all()
    # seq runs 0..n-1 within each speech.
    assert (fragments.groupby("speech_id").seq.transform(lambda s: s.to_numpy()
                                                         == np.arange(len(s)))).all()
    # Fragments concatenated equal text_clean up to whitespace.
    joined = fragments.groupby("speech_id", sort=False).text.agg(" ".join)
    clean = speeches.set_index("speech_id").text_clean
    assert all(squash(joined[sid]) == squash(clean[sid]) for sid in clean.index)
    # Word bounds: under MIN_WORDS only for a speech that short (one fragment).
    words = speeches.set_index("speech_id").n_words
    short = fragments[fragments.n_words < segment.MIN_WORDS]
    assert (words[short.speech_id] < segment.MIN_WORDS).all()
    # Over MAX_WORDS only when no cut between sentences (clauses) keeps every piece within the
    # bounds: one sentence is too long, or the sentences too uneven (GTM_27_1972: 42, 190, 57).
    for text in fragments.loc[fragments.n_words > segment.MAX_WORDS, "text"]:
        sizes = [segment.n_words(u) for p in text.split("\n") for u in segment._units_of(p)]
        assert not can_cut(sizes), text[:200]
    # No fragment starts with a paragraph number. An item of a short numbered list (under six
    # items), which pipeline.tidy keeps as printed, may open one (LBN_01_1946: "1.", "2.").
    lead = fragments.text.str.extract(r"^(\d{1,3})\.\s", expand=False).dropna().astype(int)
    assert (lead < 6).all(), fragments.loc[lead[lead >= 6].index, "speech_id"].tolist()
    # Transcripts carry no presiding-officer phrases.
    transcripts = fragments[fragments.year >= 2025]
    assert not transcripts.text.str.contains(prepare.PRESIDING_PHRASES).any()
    assert set(speeches.post_category) <= set(POST_CATEGORIES)
    assert fragments.para_method.isin(set(segment.PARA_METHOD.values())).all()
    assert fragments.is_ceremonial.dtype == bool


# ---------------------------------------------------------------------------
# Fixture corpus
# ---------------------------------------------------------------------------

PARAGRAPH = ("The United Nations was founded to save succeeding generations from the scourge of "
             "war. Our delegation believes that the Charter remains the best guide for the "
             "conduct of States. We must strengthen international co-operation in the economic "
             "and social fields, and we must do so without delay.")

SPEECH_1970 = (
    "\ufeff1.\tMr. President, allow me to congratulate you on your election to the presidency "
    "of the twenty-fifth session of the General Assembly and to wish you every success in your "
    "high office. I also wish to pay a tribute to your predecessor for the able manner in which "
    "he guided our work. We thank the Secretary-General for his tireless efforts and his "
    "dedication to the Organization.\r\n"
    + "".join(f"{i}.\t{PARAGRAPH} [1850th meeting]\r\n" for i in range(2, 8))
    + "8.\tIn conclusion, we reaffirm our faith in the Organization.\r\n")

SPEECH_2024 = "\n\n".join(
    ["**Mr. President, Excellencies,**"] + [f"{PARAGRAPH} (spoke in French)"] * 5
    + ["Thank you. (Applause)"])

TRANSCRIPT_2026 = (
    "The Assembly will now hear an address by His Excellency Juan Perez, President of the "
    "Republic of Testland. I request protocol to escort His Excellency and invite him to "
    "address the Assembly. " + " ".join([PARAGRAPH] * 6) + " Thank you very much. On behalf "
    "of the Assembly, I wish to thank the President of the Republic of Testland.")


@pytest.fixture
def fixture_corpus(tmp_path):
    corpus = tmp_path / "TXT"
    (corpus / "Session 25 - 1970").mkdir(parents=True)
    (corpus / "Session 79 - 2024").mkdir(parents=True)
    (corpus / "Session 25 - 1970" / "PRT_25_1970.txt").write_bytes(SPEECH_1970.encode("utf-8"))
    (corpus / "Session 79 - 2024" / "KEN_79_2024.txt").write_text(SPEECH_2024, encoding="utf-8")
    # Files that are not speeches.
    (corpus / "Session 25 - 1970" / ".DS_Store").write_bytes(b"\x00\x01")
    (corpus / "Session 25 - 1970" / ".DS_Store-to-UTF-8.txt").write_text("x")
    (corpus / "Session 79 - 2024" / "notes.txt").write_text("x")
    (corpus / "misc").mkdir()
    (corpus / "misc" / "USA_25_1970.txt").write_text("x")

    provisional = tmp_path / "provisional"
    (provisional / "Session 81 - 2026").mkdir(parents=True)
    (provisional / "Session 81 - 2026" / "TST_81_2026.txt").write_text(TRANSCRIPT_2026,
                                                                      encoding="utf-8")
    speakers = tmp_path / "speakers.xlsx"
    pd.DataFrame({
        "Year": [1970, 2024],
        "Session": [25, 79],
        "ISO Code": ["POR", "KEN"],  # POR is fixed to PRT
        "Country": ["Portugal", "Kenya"],
        "Name of Person Speaking": ["Rui Patricio", "William Ruto"],
        "Post": ["Minister for Foreign Affairs", "President"],
    }).to_excel(speakers, sheet_name="Sheet1", index=False)
    return SimpleNamespace(corpus=corpus, provisional=provisional, speakers=speakers,
                           out=tmp_path / "interim", report=tmp_path / "qc" / "report.md",
                           tidy=tmp_path / "tidy" / "TXT", official=tmp_path / "official")


def test_list_sources_skips_junk_and_tags_provisional(fixture_corpus):
    sources = prepare.list_sources(fixture_corpus.corpus, fixture_corpus.provisional,
                                   fixture_corpus.official)
    assert [(s["speech_id"], s["session"], s["year"], s["source"]) for s in sources] == [
        ("PRT_25_1970", 25, 1970, "ungdc_v14"), ("KEN_79_2024", 79, 2024, "ungdc_v14"),
        ("TST_81_2026", 81, 2026, "provisional_2026")]


def test_an_official_session_replaces_the_corpus_session(fixture_corpus):
    f = fixture_corpus
    (f.official / "Session 79 - 2024").mkdir(parents=True)
    for code in ("KEN", "DMA"):  # DMA: in the record, not in the corpus
        (f.official / "Session 79 - 2024" / f"{code}_79_2024.txt").write_text(PARAGRAPH + "\n")
    sources = prepare.list_sources(f.corpus, f.provisional, f.official)
    assert [(s["speech_id"], s["source"]) for s in sources] == [
        ("PRT_25_1970", "ungdc_v14"), ("DMA_79_2024", "un_records"), ("KEN_79_2024", "un_records"),
        ("TST_81_2026", "provisional_2026")]
    assert not prepare.is_transcript(2024, prepare.OFFICIAL_SOURCE)


def test_post_category_corrects_spreadsheet_typos():
    # Every 2005 post reads "Minister for Foregn Affairs".
    assert post_category("Minister for Foregn Affairs") == "foreign_minister"
    assert post_category("Minsiter for Foreign and CARICOM Affairs") == "foreign_minister"
    assert post_category("Head of Goverment") == "head_of_government"


def test_load_speakers_adds_provisional_lists(fixture_corpus):
    f = fixture_corpus
    pd.DataFrame({
        "Year": [2026], "Session": [81], "ISO Code": ["TST"], "Country": ["Testland"],
        "Name of Person Speaking": ["Juan Perez"], "Post": ["President"], "Date": ["2026-09-22"],
        "Language": [""], "EN audio": ["yes"], "Source URL": ["https://gadebate.un.org/en/81/testland"],
    }).to_csv(f.provisional / "speakers_81_2026.csv", index=False)
    sp = load_speakers(f.speakers, f.provisional).set_index(["iso3", "year"])
    assert sp.loc[("TST", 2026), "speaker_name"] == "Juan Perez"
    assert sp.loc[("TST", 2026), "post_category"] == "head_of_state"
    assert sp.loc[("KEN", 2024), "speaker_name"] == "William Ruto"
    assert len(load_speakers(f.speakers)) == 2  # without the folder, the spreadsheet alone


def test_renamed_country_is_filed_under_its_current_code(tmp_path):
    folder = tmp_path / "TXT" / "Session 55 - 2000"
    folder.mkdir(parents=True)
    (folder / "NRU_55_2000.txt").write_text("x")
    [src] = prepare.list_sources(tmp_path / "TXT", tmp_path / "provisional", tmp_path / "official")
    assert (src["speech_id"], src["iso3"]) == ("NRU_55_2000", "NRO")  # the id keeps the source file name
    speakers = tmp_path / "speakers.xlsx"
    pd.DataFrame({"Year": [2000], "Session": [55], "ISO Code": ["NRU"], "Country": ["Nauru"],
                  "Name of Person Speaking": ["Test Speaker"], "Post": ["President"]}).to_excel(
        speakers, sheet_name="Sheet1", index=False)
    assert load_speakers(speakers)["iso3"].tolist() == ["NRO"]


def test_is_transcript():
    assert prepare.is_transcript(2025, "ungdc_v14")
    assert prepare.is_transcript(2026, "provisional_2026")
    assert not prepare.is_transcript(2024, "ungdc_v14")


def test_run_on_fixture_corpus(fixture_corpus):
    f = fixture_corpus
    result = prepare.run(f.corpus, f.provisional, f.speakers, f.out, f.report,
                         tokenizer=WhitespaceTokenizer(), log=lambda *a: None, tidy_dir=f.tidy,
                         official_dir=f.official)
    speeches = pd.read_parquet(f.out / "speeches.parquet")
    fragments = pd.read_parquet(f.out / "fragments.parquet")
    check_invariants(speeches, fragments)
    assert len(result["speeches"]) == 3

    sp = speeches.set_index("speech_id")
    assert sp.loc["TST_81_2026", "source"] == "provisional_2026"
    assert sp.loc["TST_81_2026", "session"] == 81
    assert sp.loc["TST_81_2026", "post_category"] == "unknown"  # no speaker row
    assert sp.loc["PRT_25_1970", "speaker_name"] == "Rui Patricio"
    assert sp.loc["PRT_25_1970", "post_category"] == "foreign_minister"
    assert sp.loc["KEN_79_2024", "post_category"] == "head_of_state"

    # Cleaning reached the text: numbers, references, notes and presiding officer removed.
    for text in sp.text_clean:
        assert not re.search(r"\[1850th|spoke in|Applause|\*\*|\ufeff|\r|^\d+\.", text)
    transcript = sp.loc["TST_81_2026", "text_clean"]
    assert transcript.startswith("The United Nations was founded")
    assert transcript.endswith("Thank you very much.")
    assert sp.loc["TST_81_2026", "layout"] == "single"
    assert sp.loc["PRT_25_1970", "layout"] == "line"

    fr = fragments.set_index(["speech_id", "seq"])
    assert fr.loc[("PRT_25_1970", 0), "is_ceremonial"]
    assert fr.loc[("PRT_25_1970", 0), "para_method"] == "line"
    assert (fragments.loc[fragments.speech_id == "TST_81_2026", "para_method"]
            == "sentence_pack").all()
    # Token counts come from the tokenizer (whitespace stand-in here).
    assert (fragments.n_tokens == fragments.n_words).all()
    assert (speeches.n_tokens == speeches.n_words).all()

    counts = result["speech_counts"]
    assert counts["PRT_25_1970"]["bom"] == 1 and counts["PRT_25_1970"]["crlf"] == 8
    assert counts["PRT_25_1970"]["para_number"] == 8
    assert counts["TST_81_2026"]["presiding_intro"] == 1
    report = f.report.read_text(encoding="utf-8")
    for heading in ("## Counts per year", "## Words per fragment by era",
                    "## Paragraph method per year", "## Ceremonial fragments by era",
                    "## Replacements per cleaning rule", "## 20 longest fragments",
                    "## 20 shortest fragments", "## Random fragments by era",
                    "## Anomalies and checks"):
        assert heading in report


CEREMONIAL_KEN = (
    "Mr. President, Excellencies, I congratulate you on your election to the presidency of "
    "the seventy-ninth session and wish you every success in your high office. I also pay "
    "tribute to your predecessor for the able manner in which he guided our work, and I thank "
    "the Secretary-General for his tireless efforts and his dedication to the Organization. "
    "My delegation assures you of its full support.")
TIDY_KEN = "\n\n".join([CEREMONIAL_KEN] + [PARAGRAPH + " Our region needs peace."] * 4)


def write_tidy(f, sha1: str, version: int = tidy.UNITIZER_VERSION) -> None:
    """A tidy copy of KEN_79_2024: five paragraphs starting at units 0, 2, 4, 6, 8,
    the first labelled ceremonial by the agent."""
    folder = "Session 79 - 2024"
    (f.tidy / folder).mkdir(parents=True, exist_ok=True)
    (f.tidy / folder / "KEN_79_2024.txt").write_text(TIDY_KEN + "\n", encoding="utf-8")
    dec = f.tidy.parent / "decisions" / folder
    dec.mkdir(parents=True, exist_ok=True)
    (dec / "KEN_79_2024.json").write_text(json.dumps(
        {"id": "KEN_79_2024", "drop": [], "para": [0, 2, 4, 6, 8], "cer": [0], "fix": [],
         "sha1": sha1, "unitizer_version": version}), encoding="utf-8")


def test_run_prefers_a_current_tidy_copy(fixture_corpus):
    f = fixture_corpus
    raw = (f.corpus / "Session 79 - 2024" / "KEN_79_2024.txt").read_bytes()
    write_tidy(f, hashlib.sha1(raw).hexdigest())
    prepare.run(f.corpus, f.provisional, f.speakers, f.out, None,
                tokenizer=WhitespaceTokenizer(), log=lambda *a: None, tidy_dir=f.tidy,
                official_dir=f.official)
    speeches = pd.read_parquet(f.out / "speeches.parquet")
    fragments = pd.read_parquet(f.out / "fragments.parquet")
    check_invariants(speeches, fragments)
    sp = speeches.set_index("speech_id")
    assert sp.loc["KEN_79_2024", "layout"] == "tidy"
    assert squash(sp.loc["KEN_79_2024", "text_clean"]) == squash(TIDY_KEN)
    assert sp.loc["PRT_25_1970", "layout"] == "line"  # no tidy copy
    ken = fragments[fragments.speech_id == "KEN_79_2024"]
    assert (ken.para_method == "tidy").all()
    assert ken.is_ceremonial.tolist() == [True] + [False] * (len(ken) - 1)


def test_agent_labels_override_the_rule_based_flag():
    paragraphs = [CEREMONIAL_KEN, PARAGRAPH + " " + PARAGRAPH, PARAGRAPH]
    out = prepare._finish(paragraphs, [""] * 3, [False, False, False])
    assert out["regex_ceremonial"][0] and not out["ceremonial"][0]
    out = prepare._finish(paragraphs, [""] * 3, None)
    assert out["ceremonial"] == out["regex_ceremonial"]


def test_stale_tidy_copy_is_ignored(fixture_corpus):
    f = fixture_corpus
    raw = (f.corpus / "Session 79 - 2024" / "KEN_79_2024.txt").read_bytes()
    for sha1, version in (("0" * 40, tidy.UNITIZER_VERSION),
                          (hashlib.sha1(raw).hexdigest(), tidy.UNITIZER_VERSION + 1)):
        write_tidy(f, sha1, version)
        assert prepare.load_tidy(f.tidy, "Session 79 - 2024", "KEN_79_2024",
                                 hashlib.sha1(raw).hexdigest()) is None


def test_tidy_labels_align_with_paragraphs(fixture_corpus):
    f = fixture_corpus
    write_tidy(f, "a" * 40)
    text, labels = prepare.load_tidy(f.tidy, "Session 79 - 2024", "KEN_79_2024", "a" * 40)
    assert text == TIDY_KEN and labels == [True, False, False, False, False]


def test_harrier_tokenizer_counts_without_special_tokens():
    try:
        tok = prepare.load_tokenizer()
    except FileNotFoundError:
        pytest.skip("Harrier tokenizer not in the local Hugging Face cache")
    counts = prepare.count_tokens(tok, ["Drug trafficking fuels violence.", ""], batch_size=1)
    assert counts[1] == 0 and 3 <= counts[0] <= 10


# ---------------------------------------------------------------------------
# Full corpus (slow)
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.skipif(not config.CORPUS_TXT.exists(), reason="corpus not available")
def test_full_corpus_invariants(tmp_path):
    result = prepare.run(out_dir=tmp_path, report_path=tmp_path / "prepare_report.md",
                         log=lambda *a: None)
    speeches = pd.read_parquet(tmp_path / "speeches.parquet")
    fragments = pd.read_parquet(tmp_path / "fragments.parquet")
    assert int((speeches.source == prepare.V14_SOURCE).sum()) == V14_SPEECHES
    assert int((speeches.source == prepare.OFFICIAL_SOURCE).sum()) == OFFICIAL_SPEECHES
    assert set(speeches.source) <= {prepare.V14_SOURCE, prepare.OFFICIAL_SOURCE,
                                    prepare.PROVISIONAL_SOURCE}
    check_invariants(speeches, fragments)
    # Fragments inside the bounds except for the documented exceptions checked above.
    inside = fragments.n_words.between(segment.MIN_WORDS, segment.MAX_WORDS).mean()
    assert inside > 0.999
    assert (fragments.n_tokens > 0).all()
    # A transcript cleaned here (no current tidy copy) loses at least its presiding-officer
    # introduction; a tidy copy's removals are the agents' decisions, not this list.
    raw_transcripts = speeches[(speeches.year >= 2025) & (speeches.layout != "tidy")]
    assert raw_transcripts.empty or len(result["removed"]) > 0
