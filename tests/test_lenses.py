"""Tests for the lens loader and the committed lens files."""
import json
import re

import numpy as np
import pycountry
import pytest
import yaml

from pipeline.config import LENSES
from pipeline.lenses import (APPROVED_ICONS, LensError, expand_labels, expand_scores,
                             load_lenses, parent_map, validate, word_count)

EXPECTED_IDS = [
    "drugs", "prevention_treatment", "alternative_development", "organized_crime",
    "corruption", "terrorism", "trafficking_smuggling", "environmental_crime",
    "criminal_justice", "peace",
]
EXPECTED_ICONS = {
    "drugs": "pill", "prevention_treatment": "heart-handshake",
    "alternative_development": "plant-2", "organized_crime": "affiliate",
    "corruption": "coins", "terrorism": "shield-exclamation",
    "trafficking_smuggling": "users-group", "environmental_crime": "trees",
    "criminal_justice": "gavel", "peace": "peace",
}


def minimal_lens(lens_id, icon):
    anchor = " ".join(["word"] * 35)
    return {
        "id": lens_id, "name_es": "Nombre", "name_en": "Name", "label_es": "Etiqueta",
        "label_en": "Label", "icon": icon, "reference": False,
        "definition_en": "A definition. A second sentence.",
        "include": ["a"], "exclude": ["b"], "era_terms": ["c"],
        "anchors": [f"{anchor} {lens_id} {i}" for i in range(5)],
    }


@pytest.fixture
def valid_data():
    return {
        "query_instruction": "Instruct: Retrieve passages\nQuery: ",
        "lenses": [minimal_lens("drugs", "pill"), minimal_lens("peace", "peace")],
    }


def write_yaml(tmp_path, data):
    path = tmp_path / "lenses.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def assert_invalid(data, fragment):
    with pytest.raises(LensError, match=fragment):
        validate(data)


# --- loader behaviour on synthetic files -------------------------------------

def test_minimal_file_loads(tmp_path, valid_data):
    data = load_lenses(write_yaml(tmp_path, valid_data))
    assert [l["id"] for l in data["lenses"]] == ["drugs", "peace"]


def test_duplicate_id_rejected(valid_data):
    valid_data["lenses"][1]["id"] = "drugs"
    assert_invalid(valid_data, "duplicate id")


def test_missing_field_rejected(valid_data):
    del valid_data["lenses"][0]["definition_en"]
    assert_invalid(valid_data, "missing fields")


def test_unknown_field_rejected(valid_data):
    valid_data["lenses"][0]["exlude"] = ["typo"]
    assert_invalid(valid_data, "unknown fields")


def test_empty_list_rejected(valid_data):
    valid_data["lenses"][0]["include"] = []
    assert_invalid(valid_data, "'include' must be a non-empty list")


def test_reference_must_be_bool(valid_data):
    valid_data["lenses"][0]["reference"] = "no"
    assert_invalid(valid_data, "'reference' must be true or false")


def test_unapproved_icon_rejected(valid_data):
    valid_data["lenses"][0]["icon"] = "cannabis"
    assert_invalid(valid_data, "not in the approved list")


def test_reused_icon_rejected(valid_data):
    valid_data["lenses"][1]["icon"] = "pill"
    assert_invalid(valid_data, "already used")


@pytest.mark.parametrize("n", [4, 9])
def test_anchor_count_limits(valid_data, n):
    lens = valid_data["lenses"][0]
    lens["anchors"] = [f"{' '.join(['word'] * 35)} {i}" for i in range(n)]
    assert_invalid(valid_data, "anchors, has")


@pytest.mark.parametrize("words", [29, 71])
def test_anchor_length_limits(valid_data, words):
    valid_data["lenses"][0]["anchors"][0] = " ".join(["word"] * words)
    assert_invalid(valid_data, f"has {words} words")


def test_anchor_length_bounds_inclusive(valid_data):
    valid_data["lenses"][0]["anchors"][0] = " ".join(["word"] * 30)
    valid_data["lenses"][0]["anchors"][1] = " ".join(["other"] * 70)
    validate(valid_data)


def test_duplicate_anchor_rejected(valid_data):
    lens = valid_data["lenses"][0]
    lens["anchors"][1] = lens["anchors"][0]
    assert_invalid(valid_data, "duplicates another anchor")


def test_bad_parent_rejected(valid_data):
    valid_data["lenses"][0]["parent"] = "missing"
    assert_invalid(valid_data, "is not another lens id")


def test_nested_parent_rejected(valid_data):
    valid_data["lenses"].append(minimal_lens("prevention_treatment", "heart-handshake"))
    valid_data["lenses"][2]["parent"] = "peace"
    valid_data["lenses"][1]["parent"] = "drugs"
    assert_invalid(valid_data, "must not have a parent itself")


def test_bad_query_instruction_rejected(valid_data):
    valid_data["query_instruction"] = "Retrieve passages"
    assert_invalid(valid_data, "query_instruction")


def test_all_errors_reported_together(valid_data):
    valid_data["lenses"][0]["icon"] = "cannabis"
    del valid_data["lenses"][1]["include"]
    with pytest.raises(LensError) as err:
        validate(valid_data)
    assert "approved list" in str(err.value) and "missing fields" in str(err.value)


def test_word_count():
    assert word_count("  one two\nthree  ") == 3


# --- the committed codebook ---------------------------------------------------

@pytest.fixture(scope="module")
def codebook():
    return load_lenses()


def test_committed_ids_and_order(codebook):
    assert [l["id"] for l in codebook["lenses"]] == EXPECTED_IDS


def test_committed_icons(codebook):
    assert {l["id"]: l["icon"] for l in codebook["lenses"]} == EXPECTED_ICONS
    assert set(EXPECTED_ICONS.values()) == APPROVED_ICONS


def test_only_peace_is_reference(codebook):
    assert [l["id"] for l in codebook["lenses"] if l["reference"]] == ["peace"]


def test_drug_sub_lenses_have_parent(codebook):
    parents = {l["id"]: l.get("parent") for l in codebook["lenses"]}
    assert {k for k, v in parents.items() if v} == {"prevention_treatment", "alternative_development"}
    assert parents["prevention_treatment"] == parents["alternative_development"] == "drugs"


def test_definitions_have_two_or_three_sentences(codebook):
    for lens in codebook["lenses"]:
        sentences = re.findall(r"[.!?](?:\s|$)", lens["definition_en"])
        assert 2 <= len(sentences) <= 3, lens["id"]


def test_ui_names_are_short(codebook):
    for lens in codebook["lenses"]:
        assert word_count(lens["name_en"]) <= 4, lens["id"]
        assert word_count(lens["name_es"]) <= 5, lens["id"]


def test_query_instruction_matches_harrier_format(codebook):
    assert codebook["query_instruction"] == (
        "Instruct: Given a topic description, retrieve passages from UN General Assembly "
        "speeches that discuss this topic\nQuery: ")


def country_names():
    names = set()
    for c in list(pycountry.countries) + list(pycountry.historic_countries):
        for attr in ("name", "common_name", "official_name"):
            value = getattr(c, attr, None)
            if value:
                names.add(value)
    return names


def test_anchors_have_no_country_names(codebook):
    patterns = [re.compile(rf"\b{re.escape(n)}\b") for n in country_names()]
    for lens in codebook["lenses"]:
        for anchor in lens["anchors"]:
            found = [p.pattern for p in patterns if p.search(anchor)]
            assert not found, (lens["id"], found, anchor[:60])


# --- codebook.md worked examples stay consistent with the YAML ------------------

def codebook_examples():
    text = (LENSES / "codebook.md").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.startswith('{"frag_id": "ex-')]


def test_codebook_mentions_every_lens(codebook):
    text = (LENSES / "codebook.md").read_text(encoding="utf-8")
    for lens_id in EXPECTED_IDS:
        assert f"`{lens_id}`" in text, lens_id


def test_codebook_examples_are_valid(codebook):
    examples = codebook_examples()
    ids = set(EXPECTED_IDS)
    for ex in examples:
        assert set(ex) == {"frag_id", "lenses", "mention_type", "confidence", "note"}, ex["frag_id"]
        assert set(ex["lenses"]) <= ids and len(set(ex["lenses"])) == len(ex["lenses"]), ex["frag_id"]
        assert ex["lenses"] == [i for i in EXPECTED_IDS if i in ex["lenses"]], ex["frag_id"]
        assert set(ex["mention_type"]) == set(ex["lenses"]), ex["frag_id"]
        assert set(ex["mention_type"].values()) <= {"substantive", "list"}, ex["frag_id"]
        assert ex["confidence"] in (1, 2, 3), ex["frag_id"]
        # umbrella rule, including mention-type strength
        assert expand_labels(ex["mention_type"], codebook) == ex["mention_type"], ex["frag_id"]


def test_codebook_has_positive_and_negative_examples_per_lens():
    # Three positive and two negative examples per lens (codebook 1.4).
    examples = codebook_examples()
    for lens_id in EXPECTED_IDS:
        n_pos, n_neg = 3, 2
        pos = [e for e in examples if re.fullmatch(rf"ex-{lens_id}-p\d", e["frag_id"])]
        neg = [e for e in examples if re.fullmatch(rf"ex-{lens_id}-n\d", e["frag_id"])]
        assert len(pos) == n_pos and all(lens_id in e["lenses"] for e in pos), lens_id
        assert len(neg) == n_neg and all(lens_id not in e["lenses"] for e in neg), lens_id


def test_boundary_examples_have_notes():
    boundary = [e for e in codebook_examples() if e["frag_id"].startswith("ex-boundary-")]
    assert len(boundary) >= 13
    assert all(e["note"].strip() for e in boundary)


def test_drug_abuse_formulas_are_drugs_only():
    # ex-boundary-01..03: the doublet, burden sharing and the balanced-approach formula
    by_id = {e["frag_id"]: e for e in codebook_examples()}
    for i in (1, 2, 3):
        assert by_id[f"ex-boundary-0{i}"]["lenses"] == ["drugs"]


# --- era terms ------------------------------------------------------------------

# Bare cues that mostly match other senses in the corpus (e.g. "territorial
# integrity", refugee "returnees", aerial "bombings", pre-1990 "gangs").
BARE_FALSE_FRIENDS = {"integrity", "servitude", "returnees", "value chains", "mercury",
                      "bombings", "international crime", "gangs", "extortion"}


def test_era_terms_avoid_bare_false_friends(codebook):
    for lens in codebook["lenses"]:
        assert not BARE_FALSE_FRIENDS & set(lens["era_terms"]), lens["id"]
    pt = next(l for l in codebook["lenses"] if l["id"] == "prevention_treatment")
    assert "drug abuse" not in pt["era_terms"]


# --- umbrella helpers -------------------------------------------------------------

@pytest.fixture
def umbrella_data(valid_data):
    child = minimal_lens("prevention_treatment", "heart-handshake")
    child["parent"] = "drugs"
    valid_data["lenses"].insert(1, child)
    validate(valid_data)
    return valid_data


def test_parent_map(umbrella_data):
    assert parent_map(umbrella_data) == {"prevention_treatment": "drugs"}


@pytest.mark.parametrize("given, expected", [
    ({"prevention_treatment": "list"}, {"drugs": "list", "prevention_treatment": "list"}),
    ({"prevention_treatment": "substantive"},
     {"drugs": "substantive", "prevention_treatment": "substantive"}),
    ({"prevention_treatment": "substantive", "drugs": "list"},
     {"drugs": "substantive", "prevention_treatment": "substantive"}),
    ({"prevention_treatment": "list", "drugs": "substantive"},
     {"drugs": "substantive", "prevention_treatment": "list"}),
    ({"peace": "list", "drugs": "list"}, {"drugs": "list", "peace": "list"}),
    ({}, {}),
])
def test_expand_labels(umbrella_data, given, expected):
    result = expand_labels(given, umbrella_data)
    assert result == expected
    assert list(result) == [k for k in ["drugs", "prevention_treatment", "peace"] if k in result]


def test_expand_scores(umbrella_data):
    scores = {"drugs": np.array([0.1, 0.8]), "prevention_treatment": np.array([0.5, 0.2]),
              "peace": np.array([0.3, 0.3])}
    out = expand_scores(scores, umbrella_data)
    assert np.allclose(out["drugs"], [0.5, 0.8])
    assert out["prevention_treatment"] is scores["prevention_treatment"]
    assert np.allclose(scores["drugs"], [0.1, 0.8])  # input not modified
    assert expand_scores({"prevention_treatment": 0.4}, umbrella_data)["drugs"] == 0.4
