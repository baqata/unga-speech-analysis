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

def test_quantize_puts_speeches_in_the_fragments_frame():
    fxy = np.array([[0.0, 0.0], [4.0, 2.0]])
    q = ex.quantize(np.array([[2.0, 1.0], [9.0, -1.0]]), fxy.min(axis=0), fxy.max(axis=0))
    assert q.tolist() == [[32768, 32768], [65535, 0]]  # the middle of the frame; outside it, clipped to the edge


def test_window_starts_at_the_sentence_with_a_key_term_and_fits():
    pattern = calibrate.term_pattern(["drug trafficking"])
    text = "We thank the President. Our region suffers from drug trafficking. It fuels violence. " + "More words. " * 30
    out = ex.window(text, pattern, n=80)
    assert out.startswith("Our region suffers from drug trafficking.") and len(out) <= 80
    long = "In a sentence that goes on " + "and on " * 40 + "about drug trafficking at its end."
    cut = ex.window(long, pattern, n=100)
    assert "drug trafficking" in cut and cut.startswith("… ") and len(cut) <= 100
    assert ex.window("No key term here. Second sentence.", pattern, n=20) == "No key term here."
    assert ex.clip("one two three four", 12) == "one two …"


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
    s_of = [list(SPEECHES).index(r[0]) for r in rows]
    semb = ex.unit_rows(np.array([femb[np.array(s_of) == s].mean(axis=0) for s in range(len(sp))]))
    vec = CountVectorizer(analyzer=ex.terms_of)
    x = vec.fit_transform(fr["text"]).tocsr()
    return {
        "speeches": sp, "frags": fr, "P": np.array([KINDS[r[1]][1] for r in rows], dtype=np.float32),
        "general": np.array([KINDS[r[1]][2] for r in rows]), "femb": femb.astype(np.float16), "semb": semb,
        "fxy": rng.normal(size=(len(rows), 2)), "sxy": rng.normal(size=(len(sp), 2)),
        "X": x, "vocab": vec.get_feature_names_out().tolist(),
        "countries": [{"iso3": c, "es": c, "en": c, "map_id": None, "map_extra": [], "point": None, "hist": []}
                      for c in ("ARG", "COL", "FRA")],
        "groups": [{"id": "ROCOL", "slug": "rocol", "type": "office", "es": "R", "en": "R", "short_es": "ROCOL",
                    "short_en": "ROCOL", "members": ["ARG", "COL", "URY"]},
                   {"id": "UE", "slug": "ue", "type": "bloc", "es": "UE", "en": "EU", "short_es": "UE",
                    "short_en": "EU", "members": ["FRA"]}],
        "lenses": LENSES, "topics": [{"id": "g0", "es": "T0", "en": "T0"}, {"id": "g1", "es": "T1", "en": "T1"}],
        "passes": {"drugs": True}, "build": {"date": "2026-09-29", "placeholder": True},
    }


def test_build_writes_the_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(ex, "KEY_MIN_TOKENS", 3)
    monkeypatch.setattr(ex, "KEY_MIN_COUNT", 1)
    inp = synthetic_inputs()
    files, summary = ex.build(inp)
    load = lambda name: json.loads(files[name])  # noqa: E731
    assert {"meta.json", "shares.bin", "frags.bin", "map_frag.bin", "map_speech.bin", "map_labels.json",
            "speeches.json", "composition.json", "alignment/2025.json", "alignment/all.json", "excerpts/all.json",
            "keyness/all.json"} <= set(files)
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


def test_build_refuses_fragments_without_a_topic():
    inp = synthetic_inputs()
    inp["general"] = np.where(inp["general"] == 1, -1, inp["general"])
    with pytest.raises(ex.ExportError):
        ex.build(inp)
