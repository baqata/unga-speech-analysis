import json

import numpy as np
import pandas as pd
import pytest
from scipy import sparse
from sklearn.feature_extraction.text import CountVectorizer

from pipeline import calibrate
from pipeline import export as ex


def test_terms_keep_phrases_within_a_clause_and_drop_names_and_stopwords():
    terms = ex.terms_of("The fight against drug trafficking in Colombia, organized crime; the Palermo Convention.",
                        names=frozenset({"colombia"}))
    assert terms == ["fight", "drug", "trafficking", "drug trafficking", "organized", "crime", "organized crime",
                     "palermo", "convention", "palermo convention"]
    assert "democratic republic" not in ex.terms_of("the Democratic Republic of the Congo")  # a name without its name


def test_name_words_drop_names_and_demonyms_but_keep_generic_words():
    names = ex.name_words(["COL", "CIV", "VAT", "USA"])
    assert {"colombia", "colombian", "d'ivoire", "cote", "vatican", "america"} <= names
    assert not {"united", "states", "city", "holy", "republic"} & names


def test_fightin_words_formula_and_sign():
    alpha = np.array([2.0, 8.0])
    z = ex.fightin_words(np.array([30.0, 5.0]), 100.0, np.array([100.0, 900.0]), 5000.0, alpha, a0=10.0)
    d = np.log(32 / (110 - 32)) - np.log(102 / (5010 - 102))
    assert z[0] == pytest.approx(d / np.sqrt(1 / 32 + 1 / 102))
    assert z[0] > 0 > z[1]


def test_keyness_ranks_overused_terms_and_skips_thin_selections(monkeypatch):
    monkeypatch.setattr(ex, "KEY_MIN_TOKENS", 20)
    monkeypatch.setattr(ex, "PRIOR_SIZE", 10.0)
    vocab = ["coca", "peace", "trade", "coca leaf", "trade talks"]
    is_bigram = np.array([" " in w for w in vocab])
    xs = sparse.csr_matrix(np.array([[40, 5, 5, 60, 0], [2, 30, 30, 0, 60], [1, 1, 1, 0, 0]], dtype=float))
    selections = [("g", [0, 2]), ("A", [0]), ("B", [1]), ("C", [2])]
    out = ex.keyness(xs, np.array([0, 1, 2]), 3, [("all", np.ones(3, bool))], selections, vocab, is_bigram)
    assert [w for w, *_ in out["A"]["all"]["words"]] == ["coca"]
    assert [w for w, *_ in out["A"]["all"]["bigrams"]] == ["coca leaf"]
    assert [w for w, *_ in out["B"]["all"]["words"]] == ["peace", "trade"]  # equal z: vocabulary order
    assert "C" not in out and "g" in out  # three words are too little text
    assert all(z >= ex.KEY_MIN_Z and n >= ex.KEY_MIN_COUNT for e in out.values() for p in e.values()
               for lst in p.values() for _, z, n in lst)


def test_keyness_needs_two_speeches_or_members_when_there_are_two(monkeypatch):
    monkeypatch.setattr(ex, "KEY_MIN_TOKENS", 20)
    monkeypatch.setattr(ex, "PRIOR_SIZE", 10.0)
    vocab = ["coca", "leaf", "peace", "trade"]
    is_bigram = np.zeros(4, bool)
    # speeches 0 and 1 are country 0's, 2 country 1's, 3 the rest of the world's; only speech 0 says "leaf"
    xs = sparse.csr_matrix(np.array([[20, 10, 5, 5], [20, 0, 5, 5], [20, 0, 5, 5], [1, 0, 60, 60]], dtype=float))
    selections = [("g", [0, 1]), ("A", [0])]
    periods = [("all", np.ones(4, bool)), ("y", np.array([True, False, False, True]))]
    words = lambda out, s, p: [w for w, *_ in out[s][p]["words"]]
    out = ex.keyness(xs, np.array([0, 0, 1, 2]), 3, periods, selections, vocab, is_bigram)
    assert words(out, "A", "all") == ["coca"] and words(out, "g", "all") == ["coca"]
    assert "leaf" in words(out, "A", "y") and "leaf" in words(out, "g", "y")  # one speech, one member: all there is
    monkeypatch.setattr(ex, "KEY_MIN_SPREAD", 1)
    out = ex.keyness(xs, np.array([0, 0, 1, 2]), 3, periods, selections, vocab, is_bigram)
    assert "leaf" in words(out, "A", "all") and "leaf" in words(out, "g", "all")


def test_align_leaves_the_country_out_of_its_group():
    v = ex.unit_rows(np.array([[1, 0, 0], [0.9, 0.1, 0], [0, 1, 0], [0, 0.9, 0.1]], dtype=float))
    res = ex.align(v, np.array([0, 1, 2, 3]), [np.array([0, 1]), np.array([2, 3]), np.array([0])])
    assert res["top"][0][0] == 1 and res["top"][2][0] == 3 and res["top_pct"][0][0] == 100
    assert res["gsim"][0, 0] == pytest.approx(v[0] @ v[1])  # its group without itself is row 1
    assert np.isnan(res["gsim"][0, 2])  # a group of only itself
    assert res["gsim"][2, 2] == pytest.approx(v[2] @ v[0])


def test_place_puts_new_points_among_their_nearest_mapped_points():
    rng = np.random.default_rng(0)
    centres = ex.unit_rows(rng.normal(size=(2, 16)))
    x_map = ex.unit_rows(np.repeat(centres, 60, axis=0) + 0.05 * rng.normal(size=(120, 16)))
    xy_map = np.repeat(np.array([[0.0, 0.0], [10.0, 10.0]]), 60, axis=0) + 0.3 * rng.normal(size=(120, 2))
    new = ex.unit_rows(centres + 0.05 * rng.normal(size=(2, 16)))
    xy = ex.place(new, x_map, xy_map, k=15)
    assert np.linalg.norm(xy[0] - [0, 0]) < 1 and np.linalg.norm(xy[1] - [10, 10]) < 1
    assert ex.place(x_map[:1], x_map, xy_map, k=1)[0] == pytest.approx(xy_map[0])  # a mapped point stays put


def test_nearest_centre_gives_the_kmeans_labels():
    from sklearn.cluster import KMeans
    rng = np.random.default_rng(0)
    x = ex.unit_rows(rng.normal(size=(600, 16)).astype(np.float32) + np.repeat(np.eye(16)[:3] * 3, 200, axis=0))
    km = KMeans(3, n_init=3, random_state=0).fit(x)
    assert (ex.nearest_centre(x, km.cluster_centers_.astype(np.float32), block=100) == km.labels_).all()

def test_label_anchors_go_where_a_topic_dominates():
    rng = np.random.default_rng(1)
    alone = rng.normal([0.2, 0.2], 0.01, size=(200, 2))    # topic 0 on its own
    crowd = rng.normal([0.5, 0.5], 0.01, size=(3300, 2))   # more of topic 0, among many more of topic 1
    q = np.rint(np.clip(np.vstack([alone, crowd]), 0, 1) * 65535).astype(np.uint16)
    topic = np.r_[np.zeros(500, dtype=int), np.ones(3000, dtype=int)]
    a = {x["t"]: x for x in ex.label_anchors(q, topic, 2, 50)}
    assert abs(a[0]["x"] - 0.2) < 0.02 and abs(a[0]["y"] - 0.2) < 0.02 and a[0]["n"] == 500
    assert abs(a[1]["x"] - 0.5) < 0.02 and a[1]["alt"] == []


def test_quantize_puts_speeches_in_the_fragments_frame():
    fxy = np.array([[0.0, 0.0], [4.0, 2.0]])
    q = ex.quantize(np.array([[2.0, 1.0], [9.0, -1.0]]), fxy.min(axis=0), fxy.max(axis=0))
    assert q.tolist() == [[32768, 32768], [65535, 0]]  # the middle of the frame; outside it, clipped to the edge


def test_window_shows_where_the_fragment_is_most_about_the_topic():
    w = {"coca": 5.0, "farmers": 3.0, "coca farmers": 4.0}  # no fixed key term: whatever weighs for the topic
    text = ("Thank you, Mr. President. We congratulate you on your election. Our farmers who grow coca need legal "
            "markets and roads, and coca farmers ask for credit. " + "We also discuss many other matters. " * 6)
    out = ex.window(text, w, n=120)
    assert out.startswith("Our farmers who grow coca") and 60 <= len(out) <= 120  # not the greeting before it
    start = ex.window(text, {}, n=120)  # nothing weighs: the start, with more than the greeting
    assert start == "Thank you, Mr. President. We congratulate you on your election."
    long = "In a sentence that goes on " + "and on, " * 30 + "our coca farmers need roads, at its very end."
    cut = ex.window(long, w, n=100)
    assert cut.startswith("… ") and "coca farmers" in cut and 50 <= len(cut) <= 100  # a clause of a long sentence
    tail = "A sentence that is long enough to fill the passage well. " * 3 + "Coca farmers thank you."
    assert ex.window(tail, w, n=100).endswith("Coca farmers thank you.")  # a short last sentence comes with context
    assert all(50 <= len(ex.window(t, w, n=100)) <= 100 for t in (text, long, tail))
    assert ex.window("Short fragment.", w, n=100) == "Short fragment."
    assert ex.clip("one two three four", 12) == "one two …"


def test_model_windows_show_the_passage_the_lens_rates_highest():
    text = ("We thank the President for his election and wish him every success in his work. " * 2
            + "Coca growers need roads and legal markets, and alternative development gives them both. "
            + "We also discuss the reform of the Council at some length today. " * 3)
    asked = []

    def score(passages):  # lens 1 rates the passages about coca; lens 0 rates nothing
        asked.append(list(passages))
        return np.array([[0.0, float("Coca" in x)] for x in passages])

    chosen = ex.model_windows([(0, 1), (1, 1)], [text, "Short fragment."], score, n=120)
    t, span = chosen[0, 1]
    shown = ex.passage(t, *span)
    assert shown.startswith("Coca growers") and 60 <= len(shown) <= 120
    assert chosen[1, 1] == ("Short fragment.", None)  # a fragment that fits is shown whole
    assert len(asked) == 1 and "Short fragment." not in asked[0]  # one call, for the candidates only
    hover = ex.inside(t, span, {"coca": 1.0}, 80)  # the shorter passage lies within the chosen one
    assert hover.startswith("Coca growers") and len(hover) <= 80
    assert ex.inside("Short fragment.", None, {}, 80) == "Short fragment."


def test_topic_weights_favour_the_words_that_set_a_topic_apart():
    texts = ["coca crops and farmers"] * 100 + ["coca trafficking and cartels"] * 100 + ["trade rules and markets"] * 100
    vec = CountVectorizer(analyzer=ex.terms_of)  # enough text for the prior
    x = vec.fit_transform(texts).tocsr()
    vocab = vec.get_feature_names_out().tolist()
    big = np.array([" " in v for v in vocab])
    ad, drugs, trade = np.arange(100), np.arange(200), np.arange(200, 300)
    w = ex.topic_weights(x, [ad, trade, np.array([], dtype=int)], vocab, big)
    assert {"coca", "crops", "farmers"} <= set(w[0]) and not {"trade", "markets"} & set(w[0])
    assert all(v >= ex.KEY_MIN_Z for v in w[0].values()) and w[2] == {}  # a topic with no fragment weighs nothing
    sub = ex.topic_weights(x, [ad], vocab, big, [drugs])[0]  # a sub-lens: also against the rest of its parent's text
    assert sub["crops"] > w[0]["crops"] and sub["coca"] == w[0]["coca"]  # what sets it apart counts twice


def test_excerpts_are_the_most_probable_fragments_of_each_speech():
    s, p = np.array([0, 0, 0, 0, 1, 1]), np.array([.9, .6, .7, .8, .9, .95])
    assert ex.excerpt_pick(s, p).tolist() == [0, 3, 2, 5, 4]


LENSES = [
    {"id": "drugs", "name_es": "Drogas", "name_en": "Drugs & drug trafficking", "icon": "pill", "reference": False,
     "era_terms": ["narcotic drugs"]},
    {"id": "alternative_development", "name_es": "Desarrollo alternativo", "name_en": "Alternative development",
     "icon": "plant-2", "reference": False, "era_terms": ["crop substitution"], "parent": "drugs"},
    {"id": "peace", "name_es": "Paz", "name_en": "Peace and security", "icon": "peace", "reference": True,
     "era_terms": []},
]
KINDS = {  # text, p per lens, general topic
    "drug": ("Drug trafficking and coca crops threaten our region. Shared responsibility is needed.", [.9, .2, .1], -1),
    "ad": ("Crop substitution gives farmers a legal income. Alternative development works.", [.8, .8, .1], -1),
    "peace": ("Peace and security require dialogue among nations and respect for borders.", [.1, 0, .7], -1),
    "g0": ("Climate change threatens small islands and coastal cities everywhere.", [.1, 0, .2], 0),
    "g1": ("Trade rules should favour developing economies and fair markets.", [.2, 0, .1], 1),
}
SPEECHES = {"ARG_79_2024": ["drug", "peace", "g0"], "ARG_80_2025": ["ad", "g1"],
            "COL_80_2025": ["drug", "drug", "ad", "peace"], "COL_81_2026": ["g0", "drug"],
            "FRA_80_2025": ["peace", "g1", "g0"]}


def synthetic_inputs():
    rng = np.random.default_rng(0)
    sp = pd.DataFrame({"speech_id": list(SPEECHES), "iso3": [s[:3] for s in SPEECHES],
                       "year": [int(s[-4:]) for s in SPEECHES],
                       "speaker_name": ["A. Name", None, "C. Name", "D. Name", "E. Name"],
                       "speaker_post": ["President", None, "", "Minister", "President"]})
    rows = [(sid, k) for sid, kinds in SPEECHES.items() for k in kinds]
    fr = pd.DataFrame({"frag_id": np.arange(len(rows)), "speech_id": [r[0] for r in rows],
                       "text": [KINDS[r[1]][0] for r in rows]})
    femb = ex.unit_rows(rng.normal(size=(len(rows), 8)))
    vec = CountVectorizer(analyzer=ex.terms_of)
    x = vec.fit_transform(fr["text"]).tocsr()
    return {
        "speeches": sp, "frags": fr, "P": np.array([KINDS[r[1]][1] for r in rows], dtype=np.float32),
        "general": np.array([KINDS[r[1]][2] for r in rows]), "femb": femb.astype(np.float16),
        "fxy": rng.normal(size=(len(rows), 2)), "sxy": rng.normal(size=(len(sp), 2)),
        "X": x, "vocab": vec.get_feature_names_out().tolist(),
        "countries": [{"iso3": c, "es": c, "en": c, "map_id": None, "map_extra": [], "point": None, "hist": []}
                      for c in ("ARG", "COL", "FRA")],
        "groups": [{"id": "ROCOL", "slug": "rocol", "type": "office", "es": "R", "en": "R", "short_es": "ROCOL",
                    "short_en": "ROCOL", "members": ["ARG", "COL", "URY"]},
                   {"id": "UE", "slug": "ue", "type": "bloc", "es": "UE", "en": "EU", "short_es": "UE",
                    "short_en": "EU", "members": ["FRA"]}],
        "lenses": LENSES, "topics": [{"id": "g0", "es": "T0", "en": "T0"}, {"id": "g1", "es": "T1", "en": "T1"}],
        "passes": {"drugs": True}, "thresholds": np.full(len(LENSES), 0.5, dtype=np.float32),
        "build": {"date": "2026-09-29", "placeholder": True},
    }


def test_build_writes_the_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(ex, "KEY_MIN_TOKENS", 3)
    monkeypatch.setattr(ex, "KEY_MIN_COUNT", 1)
    inp = synthetic_inputs()
    files, summary = ex.build(inp)
    load = lambda name: json.loads(files[name])  # noqa: E731
    assert {"meta.json", "shares.bin", "frags.bin", "map_frag.bin", "map_speech.bin", "map_labels.json",
            "speeches.json", "composition.json", "alignment/2025.json", "alignment/all.json", "excerpts/all.json",
            "keyness/all.json", "snips/ARG.json", "snips/COL.json", "snips/FRA.json"} <= set(files)
    assert {f"excerpts/{lens['id']}.json" for lens in LENSES} | {f"keyness/{lens['id']}.json" for lens in LENSES} \
        <= set(files)

    meta = load("meta.json")
    assert [c["iso3"] for c in meta["countries"]] == ["ARG", "COL", "FRA"]
    assert meta["groups"][0]["slug"] == "rocol" and meta["groups"][0]["members"] == [0, 1]  # URY has no speech
    assert [lens["pass"] for lens in meta["lenses"]] == [True, None, None]
    assert [t["kind"] for t in meta["topics"]] == ["lens"] * 3 + ["general"] * 2
    assert meta["binaries"]["shares.bin"]["shape"] == [3, 81, 4] and meta["build"]["n_fragments"] == 14

    shares = np.frombuffer(files["shares.bin"], dtype="<f4").reshape(3, 81, 4)
    arg24 = inp["P"][inp["frags"]["speech_id"] == "ARG_79_2024"]
    assert shares[0, 2024 - 1946, :3] == pytest.approx(arg24.mean(axis=0))
    assert shares[0, 2024 - 1946, 3] == pytest.approx(arg24[:, :2].max(axis=1).mean())  # all UNODC: peace left out
    assert np.isnan(shares[2, 2024 - 1946]).all() and np.isfinite(shares[1, 2026 - 1946]).all()
    assert np.frombuffer(files["frags.bin"], dtype="<u2").reshape(3, 81)[1, 2025 - 1946] == 4

    comp = load("composition.json")
    assert all(sum(s for _, s in parts) == pytest.approx(1, abs=0.01) for c in comp.values() for parts in c.values())
    assert dict(comp["ARG"]["2025"]) == {1: 0.5, 4: 0.5}  # the umbrella tie goes to the sub-lens

    rec = ex.read_map(files["map_frag.bin"], meta["binaries"]["map_frag.bin"]["count"])
    ad = inp["frags"]["text"].str.startswith("Crop").to_numpy()
    assert len(rec["x"]) == 14 and (rec["lensmask"][ad] == 0b011).all() and (rec["topic"][ad] == 1).all()
    assert rec["c"][inp["frags"]["speech_id"].str.startswith("FRA").to_numpy()].tolist() == [2, 2, 2]
    srec = ex.read_map(files["map_speech.bin"], meta["binaries"]["map_speech.bin"]["count"])
    assert srec["topic"][2] == 0 and srec["yr"][3] == 2026 - 1946

    drugs = load("excerpts/drugs.json")
    assert [round(p, 2) for _, p, _ in drugs["COL"]["2025"]] == [0.9, 0.9, 0.8]
    assert drugs["COL"]["2025"][0][2].startswith("Drug trafficking")
    assert "FRA" not in load("excerpts/all.json") and "FRA" in load("excerpts/peace.json")
    assert load("excerpts/all.json")["ARG"]["2025"][0][0] == 1

    speeches = load("speeches.json")
    assert speeches["ARG"]["2025"][0] == "" and speeches["COL"]["2025"][0] == "C. Name"
    assert speeches["ARG"]["2024"][0] == "A. Name, President" and speeches["FRA"]["2025"][1]
    femb, fr = inp["femb"].astype(np.float32), inp["frags"]
    for sid, iso3, year in inp["speeches"][["speech_id", "iso3", "year"]].itertuples(index=False):
        rows = np.flatnonzero(fr["speech_id"].to_numpy() == sid)
        _, passage, lens = speeches[iso3][str(year)]
        u = inp["P"][rows][:, :2].max(axis=1)  # drugs and alternative development; peace is the reference
        if (u >= 0.5).any():  # the fragment about a UNODC lens with the highest probability (short: shown whole)
            r = rows[np.argmax(u)]
            assert passage == fr["text"][r]
        else:  # the fragment nearest the mean, outside the first and last of a speech of three or more
            inner = rows[1:-1] if len(rows) >= 3 else rows
            best = inner[np.argmax(femb[inner] @ femb[rows].mean(axis=0))]
            assert lens == -1 and passage == fr["text"][best]
    assert [speeches["ARG"]["2025"][2], speeches["COL"]["2025"][2], speeches["FRA"]["2025"][2]] == [1, 0, -1]
    snips = load("snips/ARG.json")  # one passage per fragment point of the country, in point order
    assert len(snips) == 5 and snips[0] == fr["text"][0] and snips[3].startswith("Crop substitution")

    al = load("alignment/2025.json")
    assert set(al) == {"ARG", "COL", "FRA"} and len(al["ARG"]["overall"]["top"]) == 2
    assert al["FRA"]["unodc"] is None and al["ARG"]["unodc"]["top"][0][0] == "COL"
    assert [g for g, *_ in al["ARG"]["overall"]["groups"]] == ["rocol", "ue"]
    assert [g for g, *_ in al["FRA"]["overall"]["groups"]] == ["rocol"]  # alone in its group
    assert set(load("alignment/all.json")) == {"ARG", "COL", "FRA"}

    key = load("keyness/all.json")
    assert all(z >= ex.KEY_MIN_Z for e in key.values() for p in e.values() for lst in p.values() for _, z, _ in lst)
    assert summary["fragments"] == 14 and ex.check_budget(files)["total"] > 0

    ex.write_site(files, tmp_path / "data")
    ex.write_site(files, tmp_path / "data")  # a second export replaces the first
    assert json.loads((tmp_path / "data" / "meta.json").read_text())["build"]["placeholder"] is True
    assert not (tmp_path / "data.tmp").exists() and not (tmp_path / "data.old").exists()


def test_each_lens_has_its_own_threshold():
    inp = synthetic_inputs()
    inp["thresholds"] = np.array([0.85, 0.5, 0.5], dtype=np.float32)  # drugs from 0.85: the "ad" fragments (0.8) are out
    drugs = json.loads(ex.build(inp)[0]["excerpts/drugs.json"])
    assert drugs and all(t.startswith("Drug") for c in drugs.values() for y in c.values() for _, _, t in y)


def test_build_uses_the_classifiers_for_passages_when_it_has_them():
    inp = synthetic_inputs()
    inp["score"] = lambda passages: np.zeros((len(passages), len(LENSES)))
    with_model = json.loads(ex.build(inp)[0]["excerpts/all.json"])
    assert with_model == json.loads(ex.build(synthetic_inputs())[0]["excerpts/all.json"])  # short fragments: whole


def test_build_refuses_fragments_without_a_topic():
    inp = synthetic_inputs()
    inp["general"] = np.where(inp["general"] == 1, -1, inp["general"])
    with pytest.raises(ex.ExportError):
        ex.build(inp)


CODEBOOK = {"lenses": [  # drugs and its two sub-lenses, one hidden
    {"id": "drugs", "name_es": "Drogas", "name_en": "Drugs", "reference": False},
    {"id": "prevention_treatment", "name_es": "Prevención", "name_en": "Prevention", "reference": False,
     "parent": "drugs"},
    {"id": "alternative_development", "name_es": "DA", "name_en": "AD", "reference": False, "parent": "drugs"},
    {"id": "peace", "name_es": "Paz", "name_en": "Peace", "reference": True},
]}


def test_a_hidden_lens_is_left_out_of_the_probabilities(tmp_path, monkeypatch):
    probs = tmp_path / "lens_probs.parquet"
    pd.DataFrame({"frag_id": [1, 2], "p_drugs": [0.9, 0.1], "p_prevention_treatment": [0.9, 0.0],
                  "p_alternative_development": [0.2, 0.1]}).to_parquet(probs)
    thresholds = {"drugs": 0.3, "prevention_treatment": 0.01, "alternative_development": 0.2}
    probs.with_suffix(".json").write_text(json.dumps({"input_hash": "h", "thresholds": thresholds}))
    monkeypatch.setattr(calibrate, "PROBS", probs)
    assert ex.shown_ids(CODEBOOK) == ["drugs", "alternative_development"]
    p, _, thr = ex.lens_probabilities(np.array([2, 1]), "h", False, CODEBOOK)
    assert np.allclose(p, [[0.1, 0.1], [0.9, 0.2]]) and np.allclose(thr, [0.3, 0.2])


def test_method_facts_give_the_cross_validation_per_lens(tmp_path, monkeypatch):
    def overall(pr, rc):
        return {"precision": pr, "recall": rc, "f1": round(2 * pr * rc / (pr + rc), 4)}

    fit = {"lenses": {"drugs": {"pass": False, "overall": overall(0.92, 0.89)},
                      "prevention_treatment": {"pass": False, "overall": overall(0.5, 0.46)},
                      "alternative_development": {"pass": True, "overall": overall(0.8, 0.75)}}}
    agreement = {"check_fragments": 7}
    for name, data in (("FIT", fit), ("AGREEMENT", agreement)):
        path = tmp_path / f"{name.lower()}.json"
        path.write_text(json.dumps(data))
        monkeypatch.setattr(calibrate, name, path)
    final = tmp_path / "labels_final.parquet"
    pd.DataFrame({"drugs": [1, 0, 1], "prevention_treatment": [0, 0, 1], "alternative_development": [1, 0, 0],
                  "peace": [0, 1, 0]}).to_parquet(final)
    monkeypatch.setattr(calibrate, "FINAL", final)
    assert ex.lens_passes() == {"drugs": False, "prevention_treatment": False, "alternative_development": True}
    facts = ex.method_facts(CODEBOOK, 10, 2)
    assert facts["labelled"] == 3 and facts["read_twice"] == 7 and facts["min_period"] == calibrate.MIN_PERIOD_POSITIVES
    assert facts["reference"] == [{"es": "Paz", "en": "Peace"}]
    lenses = {lens["id"]: lens for lens in facts["lenses"]}
    assert list(lenses) == ["drugs", "prevention_treatment", "alternative_development"]  # peace has no model
    drugs = lenses["drugs"]
    assert drugs["examples"] == 2 and drugs["pass"] is False
    assert (drugs["precision"], drugs["recall"], drugs["f1"]) == (0.92, 0.89, 0.9048)
    assert lenses["prevention_treatment"]["shown"] is False and lenses["alternative_development"]["pass"] is True
