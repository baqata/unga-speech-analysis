"""Tests for pipeline.calibrate on synthetic data (no model): score arithmetic, the sample
design, the check set and agreement, record checks and a small end-to-end run."""
import json

import numpy as np
import pandas as pd
import pytest

from pipeline import calibrate as cal
from pipeline import config, embed
from pipeline.lenses import load_lenses
from tests.test_embed import FakeEncoder, fake_vector

CODEBOOK = load_lenses()
IDS = cal.lens_ids(CODEBOOK)


def test_item_scores_take_the_best_anchor_of_each_lens():
    q = np.eye(3, 4, dtype=np.float32)
    anchors = np.array([[0, 1, 0, 0], [0, 0, 0, 1], [1, 0, 0, 0]], dtype=np.float32)
    owner = np.array([0, 0, 1])
    x = np.array([[0, 0.6, 0, 0.8]], dtype=np.float32)
    d, a = cal.item_scores(x, q[:2], anchors, owner)
    assert np.allclose(d, [[0, 0.6]]) and np.allclose(a, [[0.8, 0]])


def test_term_pattern_drops_qualifiers_and_respects_word_boundaries():
    pat = cal.term_pattern(["drug abuse (as the name of the problem)", "UNFDAC", "gangs (from 1990)"])
    assert pat.search("the scourge of Drug Abuse")
    assert pat.search("UNFDAC funds") and not pat.search("UNFDACS")
    assert pat.search("gangs") and not pat.search("name of the problem")


def test_bin_rates_plan_the_same_draws_in_every_bin():
    n = 4000
    period = np.repeat([0, 1], n // 2)
    scores = np.random.default_rng(1).normal(size=n)
    q = cal.within_period_rank(scores, period, np.arange(n))
    rate = cal.bin_rates(q, period)
    assert (rate[q > 8 / 25] == 0).all()
    for p in (0, 1):
        b = np.searchsorted(cal.BIN_EDGES, q[period == p])
        for k in range(len(cal.BIN_EDGES)):
            assert rate[period == p][b == k].sum() == pytest.approx(cal.PER_BIN)
    top = np.argsort(-scores[:2000])[:20]  # the top 1/100 of the 2,000 fragments of period 0
    assert np.allclose(rate[top], cal.PER_BIN / 20)


def test_lower_rates_share_the_draws_among_key_term_fragments_outside_the_top():
    q = np.array([0.1, 0.5, 0.9, 0.2, 0.6, 0.7])
    period = np.array([0, 0, 0, 1, 1, 1])
    hits = np.array([True, True, True, True, False, True])
    s = cal.LOWER_PER_STRATUM
    assert np.allclose(cal.lower_rates(hits, q, period), [0, s / 2, s / 2, 0, 0, s])


def test_solve_lambda_hits_the_target_with_capped_rates():
    rng = np.random.default_rng(2)
    base = rng.uniform(0, 0.01, 5000)
    planned = np.where(rng.random((5000, 6)) < 0.3, 1 / rng.integers(5, 200, (5000, 6)), 0)
    planned[:40, 0] = 1.5  # planned above 1: capped
    for target in (400, 1200):
        lam = cal.solve_lambda(base, planned, target)
        expected = (1 - (1 - base) * np.prod(1 - np.minimum(1, lam * planned), axis=1)).sum()
        assert abs(expected - target) < 1e-6
    with pytest.raises(cal.CalibrationError):
        cal.solve_lambda(base, planned, 5000)  # more than every stratum drawn in full
    with pytest.raises(cal.CalibrationError):
        cal.solve_lambda(base, planned, 10)  # the random part alone is larger


def test_cohen_kappa():
    assert cal.cohen_kappa([1, 1, 0, 0], [1, 1, 0, 0]) == 1.0
    # Hand-computed: agreement 3/4, chance agreement 1/2 -> kappa = 1/2.
    assert cal.cohen_kappa([1, 1, 0, 0], [1, 1, 1, 0]) == 0.5
    assert cal.cohen_kappa([1, 1], [1, 1]) is None  # no variation: kappa is undefined


def test_check_record_expands_the_umbrella_and_flags_problems():
    types, problems = cal.check_record(
        {"frag_id": "g1", "lenses": ["prevention_treatment"], "mention_type":
         {"prevention_treatment": "substantive"}, "confidence": 3, "note": ""}, IDS, CODEBOOK)
    assert types == {"drugs": "substantive", "prevention_treatment": "substantive"} and not problems
    _, problems = cal.check_record(
        {"frag_id": "g1", "lenses": ["terrorism", "drugs"], "mention_type": {"drugs": "list"},
         "confidence": 4, "note": None}, IDS, CODEBOOK)
    assert len(problems) == 4


# ---------------------------------------------------------------------------
# Scores from (fake) embeddings
# ---------------------------------------------------------------------------

@pytest.fixture
def paths(tmp_path, monkeypatch):
    for name, value in {"FRAGMENTS": "fragments.parquet", "SPEECHES": "speeches.parquet",
                        "EMB_DIR": "emb", "LOGS": "logs"}.items():
        monkeypatch.setattr(config, name, tmp_path / value)
    monkeypatch.setattr(cal, "LENS_VECTORS", tmp_path / "emb" / "lenses.npz")
    monkeypatch.setattr(cal, "SCORES", tmp_path / "lens_scores.parquet")
    monkeypatch.setattr(cal, "PROBS", tmp_path / "lens_probs.parquet")
    for name in ("SAMPLE", "MANIFEST", "BATCHES", "LABELS", "CHECK", "CHECKSET", "REREAD", "REVIEW", "REREAD14",
                 "CHANGES", "AGREEMENT", "RESOLVE", "RESOLVED", "FINAL", "FIT", "CLASSIFIERS", "RESULTS", "GOLD"):
        rel = getattr(cal, name).relative_to(config.GOLD) if name != "GOLD" else None
        monkeypatch.setattr(cal, name, tmp_path / "gold" / rel if rel else tmp_path / "gold")
    FakeEncoder.calls, FakeEncoder.interrupt_after = [], None
    return tmp_path


def test_scores_of_fragments(paths):
    texts = ["Drug trafficking fuels violence. We seized cocaine.", "We thank the President.",
             "Corruption harms schools. Peace matters.", "Terrorism threatens us all.",
             "Climate change is real."]
    cer = np.array([False, True, False, False, False])
    frags = pd.DataFrame({"frag_id": range(5), "speech_id": ["AAA_01_1950"] * 5, "iso3": "AAA",
                          "year": 1950, "seq": range(5), "text": texts, "n_words": 5, "n_tokens": 9,
                          "para_method": "line", "is_ceremonial": cer})
    frags.to_parquet(config.FRAGMENTS, index=False)
    embed.run("fragments", device="mps", encoder_factory=FakeEncoder)
    embed.finalize("fragments")
    cal.make_lens_vectors(encoder_factory=FakeEncoder, device="mps")
    out = cal.compute_scores()

    # The stored vectors are the fake encoder's: queries and anchors embedded without a prompt.
    queries, anchors, owner = cal.lens_texts(CODEBOOK)
    q = np.stack([fake_vector(t) for t in queries])
    a = np.stack([fake_vector(t) for t in anchors])
    emb, keys, _ = cal.load_embeddings("fragments")
    assert keys.frag_id.tolist() == list(range(5))
    qv, av, own, _ = cal.read_lens_vectors()
    d, best = cal.item_scores(emb, qv, av, own)
    vec = np.stack([fake_vector(t) for t in texts])
    assert np.allclose(d, vec @ q.T, atol=2e-3)
    assert np.allclose(best, [[(a[np.array(owner) == i] @ v).max() for i in range(len(IDS))] for v in vec],
                       atol=2e-3)
    # s = mean of the two z-scores, standardized over the non-ceremonial fragments.
    z = lambda x: (x - x[~cer].mean(axis=0)) / x[~cer].std(axis=0)  # noqa: E731
    cols = [f"s_{x}" for x in IDS]
    assert out.columns.tolist() == ["frag_id", "year", "is_ceremonial"] + cols
    assert np.allclose(out[cols].to_numpy(), (z(d) + z(best)) / 2, atol=1e-5)
    assert np.allclose(out.loc[~cer, cols].mean(), 0, atol=1e-5)


# ---------------------------------------------------------------------------
# End to end on synthetic scores and labels
# ---------------------------------------------------------------------------

def synthetic_corpus(n=6000, dim=32, seed=4):
    """Fragments, sampling scores and embeddings in which each lens moves one coordinate."""
    rng = np.random.default_rng(seed)
    years = rng.integers(1946, 2027, n)
    words = ["drug trafficking", "terrorism", "the economy", "vaccines", "human rights", "peace"]
    text = [f"We discuss {words[i % len(words)]} in year {y}." for i, y in enumerate(years)]
    frags = pd.DataFrame({"frag_id": np.arange(n), "speech_id": [f"C{i % 50:02d}_01_{y}" for i, y in
                                                                  enumerate(years)],
                          "year": years, "text": text, "is_ceremonial": rng.random(n) < 0.03})
    truth = pd.DataFrame({x: rng.random(n) < (0.2 if x == "peace" else 0.04) for x in IDS})
    truth["drugs"] |= truth["prevention_treatment"] | truth["alternative_development"]
    scores = pd.DataFrame({"frag_id": np.arange(n), "year": years,
                           "is_ceremonial": frags.is_ceremonial})
    vectors = rng.normal(size=(n, dim)).astype(np.float32)
    for i, x in enumerate(IDS):
        scores[f"s_{x}"] = rng.normal(size=n) + 2.0 * truth[x]
        vectors[:, i] += 4.0 * truth[x].to_numpy()
    return frags, scores, truth, vectors


def fake_label(rec_text, gid, truth_row, rng, flip=0.03):
    lenses = [x for x in IDS if truth_row[x] != (rng.random() < flip)]
    types = {x: "substantive" for x in lenses}
    return {"frag_id": gid, "lenses": lenses, "mention_type": types, "confidence": 3, "note": ""}


def test_end_to_end(paths, monkeypatch):
    monkeypatch.setattr(cal, "TARGET_SIZE", 1500)
    monkeypatch.setattr(cal, "RANDOM_PER_PERIOD", 50)
    monkeypatch.setattr(cal, "BOOTSTRAP", 50)
    monkeypatch.setattr(cal, "PROTOCOL", paths / "protocol.md")
    (paths / "protocol.md").write_text("protocol")
    frags, scores, truth, vectors = synthetic_corpus()
    monkeypatch.setattr(cal, "load_embeddings", lambda kind: (
        vectors, pd.DataFrame({"frag_id": frags.frag_id}), {}))
    frags.assign(seq=frags.frag_id, iso3="C00", n_words=10, n_tokens=12, para_method="line").to_parquet(
        config.FRAGMENTS, index=False)
    scores.to_parquet(cal.SCORES, index=False)

    sample = cal.draw_sample()
    manifest = json.loads(cal.MANIFEST.read_text())
    assert manifest["expected_size"] == pytest.approx(1500, abs=1e-3)
    assert abs(len(sample) - 1500) < 4 * np.sqrt(1500)
    assert not frags.set_index("frag_id").loc[sample.frag_id, "is_ceremonial"].any()
    assert sample.gid.is_unique and set(sample.split) == {"train", "validation"}
    # The validation set is whole speeches, about a fifth of the sample, in the first batches.
    assert not set(sample.speech_id[sample.split == "train"]) & set(sample.speech_id[sample.split == "validation"])
    assert abs((sample.split == "validation").mean() - cal.VALIDATION_SHARE) < 0.06
    assert sample.groupby("batch").split.nunique().max() == 1
    assert sample.loc[sample.split == "validation", "batch"].max() < sample.loc[sample.split == "train", "batch"].min()
    assert (sample.pi > 0).all() and (sample.pi <= 1).all()
    with pytest.raises(cal.CalibrationError):
        cal.draw_sample()

    # The core labeller reads every batch and never errs; the check labeller reads the check set and
    # errs on 3% of lenses, so every disagreement is its error and the resolver sees it.
    truth_by_gid = truth.loc[sample.set_index("gid").frag_id]
    truth_by_gid.index = sample.gid
    rng = np.random.default_rng(10)
    for path in sorted(cal.BATCHES.glob("b*.jsonl")):
        cal.write_jsonl(cal.LABELS / cal.CORE / path.name, [
            fake_label(r["text"], r["frag_id"], truth_by_gid.loc[r["frag_id"]], rng, flip=0.0)
            for r in cal.read_jsonl(path)])
    assert cal.check_file("labels", "core/b001") == []
    first = cal.read_jsonl(cal.LABELS / "core" / "b001.jsonl")
    cal.write_jsonl(cal.LABELS / "core" / "b001.jsonl", first[1:] + [dict(first[0], confidence=5)])
    assert len(cal.check_file("labels", "core/b001")) == 2  # order and confidence
    cal.write_jsonl(cal.LABELS / "core" / "b001.jsonl", first)
    cal.draw_checkset()
    for path in sorted(cal.CHECK.glob("*.jsonl")):
        cal.write_jsonl(cal.LABELS / cal.CHECKER / path.name, [
            fake_label(r["text"], r["frag_id"], truth_by_gid.loc[r["frag_id"]], rng, flip=0.03)
            for r in cal.read_jsonl(path)])
    summary = cal.collect()
    assert summary["to_resolve"] > 0
    assert all(v["kappa"] > 0.5 for v in summary["agreement"].values())

    # The resolver follows the truth.
    for path in sorted(cal.RESOLVE.glob("r*.jsonl")):
        cal.write_jsonl(cal.RESOLVED / path.name, [
            {"frag_id": r["frag_id"], "note": "",
             "decisions": {x: "substantive" if truth_by_gid.loc[r["frag_id"], x] else "none"
                           for x in r["lenses"]}} for r in cal.read_jsonl(path)])
    assert cal.check_file("resolved", "r001") == []
    final = cal.final_labels()
    assert (final.set_index("gid")[IDS] == truth_by_gid[IDS]).all().all()

    fitted = cal.fit()
    assert all(fitted["lenses"][x]["C"] in cal.PENALTIES for x in IDS)
    results = cal.test()
    for x in IDS:
        r = results["lenses"][x]["overall"]
        assert r["precision"] > 0.7 and r["recall"] > 0.7, x
        assert 0 <= r["precision_ci"][0] <= r["precision_ci"][1] <= 1
        assert results["lenses"][x]["pass"]
    # Weighted Platt brings the probabilities back to corpus level: the weighted mean probability
    # of each period is close to the weighted share of positive labels.
    for x in ("peace", "drugs"):
        for period in results["lenses"][x]["shares"].values():
            assert abs(period["mean_probability"] - period["labelled_share"]) < 0.08

    probs = cal.predict()
    assert len(probs) == len(frags) and probs.frag_id.is_monotonic_increasing
    cols = [f"p_{x}" for x in IDS]
    assert ((probs[cols] >= 0) & (probs[cols] <= 1)).all().all()
    assert (probs.p_drugs >= probs[["p_prevention_treatment", "p_alternative_development"]].max(axis=1)).all()
    # "About" a lens at p >= 0.5 recovers the synthetic truth on the whole corpus.
    about = probs.set_index("frag_id")["p_peace"] >= cal.THRESHOLD
    assert (about == truth["peace"]).mean() > 0.9


# ---------------------------------------------------------------------------
# Check set, agreement and resolution
# ---------------------------------------------------------------------------

CORE_LENS = {"g1": "drugs", "g2": "drugs", "g3": "drugs", "g5": "peace", "g6": "peace"}  # every other fragment: none
SCORE = {"drugs": [.9, .8, .7, .85, .1, .2, .81, .3], "peace": [.85, .1, .1, .1, .9, .7, .1, .1]}


def record(gid, lens=None):
    return {"frag_id": gid, "lenses": [lens] if lens else [], "mention_type": {lens: "substantive"} if lens else {},
            "confidence": 3, "note": ""}


@pytest.fixture
def gold(tmp_path, monkeypatch):
    """Eight sampled fragments in two batches, labelled by the core labeller."""
    for name, rel in {"GOLD": ".", "SAMPLE": "sample.parquet", "BATCHES": "batches", "LABELS": "labels",
                      "CHECK": "check", "CHECKSET": "checkset.json", "REREAD": "reread.json",
                      "REVIEW": "review.json", "REREAD14": "reread14.json", "CHANGES": "changes.json",
                      "AGREEMENT": "agreement.json",
                      "RESOLVE": "resolve", "RESOLVED": "resolved", "FINAL": "labels_final.parquet",
                      "SCORES": "scores.parquet"}.items():
        monkeypatch.setattr(cal, name, tmp_path / rel)
    monkeypatch.setattr(cal, "CHECK_PER_GROUP", 2)
    gids = [f"g{i}" for i in range(1, 9)]
    pd.DataFrame({"gid": gids, "frag_id": [f"f{i}" for i in range(1, 9)], "speech_id": [f"s{i}" for i in range(1, 9)],
                  "year": 1990, "period": 2, "split": "train", "pi": 0.5,
                  "batch": ["b001"] * 4 + ["b002"] * 4}).to_parquet(tmp_path / "sample.parquet")
    pd.DataFrame({"frag_id": [f"f{i}" for i in range(1, 9)],
                  **{f"s_{lens}": SCORE.get(lens, [0.0] * 8) for lens in IDS}}).to_parquet(tmp_path / "scores.parquet")
    for batch, part in (("b001", gids[:4]), ("b002", gids[4:])):
        cal.write_jsonl(tmp_path / "batches" / f"{batch}.jsonl", [{"frag_id": g, "year": 1990, "text": f"text {g}"}
                                                                  for g in part])
        cal.write_jsonl(tmp_path / "labels" / "core" / f"{batch}.jsonl", [record(g, CORE_LENS.get(g)) for g in part])
    return tmp_path


def test_check_set_draws_core_positives_and_near_misses(gold):
    cs = cal.draw_checkset()
    drugs, peace = cs["lenses"]["drugs"], cs["lenses"]["peace"]
    assert len(drugs["positives"]) == 2 and set(drugs["positives"]) <= {"g1", "g2", "g3"}
    assert drugs["near_misses"] == ["g4", "g7"]  # negatives scored at least the positives' median, 0.8
    assert (drugs["positives_available"], drugs["near_misses_available"]) == (3, 2)
    assert peace["positives"] == ["g5", "g6"] and peace["near_misses"] == ["g1"]
    written = [r["frag_id"] for p in sorted((gold / "check").glob("*.jsonl")) for r in cal.read_jsonl(p)]
    assert sorted(written) == sorted(set(drugs["positives"] + drugs["near_misses"] + peace["positives"] + ["g1"]))
    with pytest.raises(cal.CalibrationError):
        cal.draw_checkset()  # drawn once


def test_second_reading_joins_the_check_files_but_not_the_agreement(gold):
    # g2 and g8 are validation fragments; the core labeller was unsure of g8 (2) and of g6 (1, training);
    # g1 is listed for a second reading after a codebook revision, so it cannot enter the check set.
    sample = pd.read_parquet(gold / "sample.parquet")
    sample.loc[sample.gid.isin(["g2", "g8"]), "split"] = "validation"
    sample.to_parquet(gold / "sample.parquet")
    unsure = {"g8": 2, "g6": 1}
    for batch in ("b001", "b002"):
        path = gold / "labels" / "core" / f"{batch}.jsonl"
        cal.write_jsonl(path, [dict(r, confidence=unsure.get(r["frag_id"], 3)) for r in cal.read_jsonl(path)])
    (gold / "reread.json").write_text(json.dumps({"fragments": {"g1": ["named_act_or_group"]}}))
    cs = cal.draw_checkset()
    drugs, peace = cs["lenses"]["drugs"], cs["lenses"]["peace"]
    assert drugs["positives"] == ["g2", "g3"] and drugs["positives_available"] == 2  # g1 is kept out
    assert drugs["near_misses"] == ["g4", "g7"] and peace["near_misses"] == []  # g1 was peace's only near-miss
    second = cs["second_reading"]
    assert second["fragments"] == ["g1", "g6", "g8"] and second["also_in_check_set"] == 1
    assert (second["validation_low_confidence"], second["confidence_1"], second["reread"]) == (1, 1, 1)
    written = [r["frag_id"] for p in sorted((gold / "check").glob("*.jsonl")) for r in cal.read_jsonl(p)]
    assert sorted(written) == [f"g{i}" for i in range(1, 9)]
    # The check labeller agrees, except that it reads g8 as about peace: g8 is queued, the agreement is unchanged.
    for p in sorted((gold / "check").glob("*.jsonl")):
        cal.write_jsonl(gold / "labels" / "check" / p.name,
                        [record(r["frag_id"], "peace" if r["frag_id"] == "g8" else CORE_LENS.get(r["frag_id"]))
                         for r in cal.read_jsonl(p)])
    summary = cal.collect()
    assert summary["agreement"]["drugs"]["kappa"] == 1.0
    assert (summary["to_resolve"], summary["second_reading"], summary["second_reading_to_resolve"]) == (1, 3, 1)
    assert [r["frag_id"] for r in cal.read_jsonl(gold / "resolve" / "r001.jsonl")] == ["g8"]


def test_review_reads_more_fragments_outside_the_check_files(gold, monkeypatch):
    # One positive and one near-miss per lens in the check set leave one drugs positive, one drugs near-miss and one
    # peace positive for the review; peace's only near-miss (g1) is already read, so a positive takes its place.
    monkeypatch.setattr(cal, "CHECK_PER_GROUP", 1)
    monkeypatch.setattr(cal, "REVIEW_PER_LENS", 2)
    monkeypatch.setattr(cal, "REVIEW_FILES", 2)
    with pytest.raises(cal.CalibrationError):
        cal.draw_review()  # needs the check set
    cs = cal.draw_checkset()
    read = {g for v in cs["lenses"].values() for g in v["positives"] + v["near_misses"]}
    rv = cal.draw_review()
    drugs, peace = rv["lenses"]["drugs"], rv["lenses"]["peace"]
    assert len(drugs["positives"]) == 1 and set(drugs["positives"]) <= {"g1", "g2", "g3"} - read
    assert drugs["near_misses"] == sorted({"g4", "g7"} - read)
    assert peace["positives"] == sorted({"g5", "g6"} - read) and peace["near_misses_available"] == 0
    assert rv["files"] == {"c002": 2, "c003": 1} and not set(rv["frag_ids"]) & read
    written = [r["frag_id"] for p in ("c002", "c003") for r in cal.read_jsonl(gold / "check" / f"{p}.jsonl")]
    assert sorted(written) == rv["frag_ids"]
    with pytest.raises(cal.CalibrationError):
        cal.draw_review()  # drawn once
    assert cal.draw_review(force=True)["frag_ids"] == rv["frag_ids"]
    # The check labeller agrees everywhere except on the review's peace positive: it is queued, and the agreement,
    # which counts the check set only, is unchanged.
    odd = peace["positives"][0]
    for p in sorted((gold / "check").glob("*.jsonl")):
        cal.write_jsonl(gold / "labels" / "check" / p.name,
                        [record(r["frag_id"], None if r["frag_id"] == odd else CORE_LENS.get(r["frag_id"]))
                         for r in cal.read_jsonl(p)])
    summary = cal.collect()
    assert summary["agreement"]["peace"]["kappa"] == 1.0 and summary["agreement"]["drugs"]["kappa"] == 1.0
    assert (summary["to_resolve"], summary["review"], summary["review_to_resolve"]) == (1, 3, 1)
    with pytest.raises(cal.CalibrationError):
        cal.draw_review(force=True)  # review labels exist


def test_reread14_joins_the_review_outside_the_check_files_and_goes_to_the_resolver_inside(gold, monkeypatch):
    # Codebook 1.4 may change three fragments: g1, read in the check files before 1.4 (peace's only near-miss), and
    # g8 and a drugs positive left outside them. The two outside are read again in the review files and are not drawn
    # for the review; g1's listed lens goes to the resolver although both labellers left it out.
    monkeypatch.setattr(cal, "CHECK_PER_GROUP", 1)
    monkeypatch.setattr(cal, "REVIEW_PER_LENS", 2)
    monkeypatch.setattr(cal, "REVIEW_FILES", 2)
    cs = cal.draw_checkset()
    read = cal.checked(cs)
    extra = sorted({"g2", "g3"} - read)[0]
    (gold / "reread14.json").write_text(json.dumps({"fragments": {
        "g1": {"lenses": ["terrorism"], "reasons": ["treaty_acts"]},
        "g8": {"lenses": ["criminal_justice"], "reasons": ["ordinary_crime"]},
        extra: {"lenses": ["drugs"], "reasons": ["coca_traditional"]}}}))
    rv = cal.draw_review()
    assert "g1" in read and rv["reread"] == sorted(["g8", extra]) and rv["reread_in_check_files"] == 1
    assert not set(rv["frag_ids"]) & ({"g1", "g8", extra} | read)
    assert extra not in rv["lenses"]["drugs"]["positives"]
    written = [r["frag_id"] for p in rv["files"] for r in cal.read_jsonl(gold / "check" / f"{p}.jsonl")]
    assert sorted(written) == sorted(rv["frag_ids"] + rv["reread"])
    for p in sorted((gold / "check").glob("*.jsonl")):  # the check labeller agrees everywhere
        cal.write_jsonl(gold / "labels" / "check" / p.name,
                        [record(r["frag_id"], CORE_LENS.get(r["frag_id"])) for r in cal.read_jsonl(p)])
    summary = cal.collect()
    assert (summary["to_resolve"], summary["reread14"], summary["reread14_to_resolve"]) == (1, 2, 0)
    assert (summary["reread14_in_check_files"], summary["reread14_pairs_forced"]) == (1, 1)
    assert summary["agreement"]["peace"]["kappa"] == 1.0
    queued = cal.read_jsonl(gold / "resolve" / "r001.jsonl")
    assert [(r["frag_id"], r["lenses"]) for r in queued] == [("g1", ["terrorism"])]
    cal.write_jsonl(gold / "resolved" / "r001.jsonl", [{"frag_id": "g1", "decisions": {"terrorism": "substantive"},
                                                        "note": ""}])
    final = cal.final_labels()
    assert final.set_index("gid")["terrorism"].tolist() == [True] + [False] * 7
    ch = cal.changes(final)
    assert ch["reread14"] == {"fragments": 3, "changed": 1, "share": 0.333, "pairs_added": 1, "pairs_removed": 0}
    assert ch["review"]["fragments"] == len(rv["frag_ids"]) and ch["review"]["changed"] == 0
    assert ch["second_reading_doubtful"]["fragments"] == 0 and json.loads((gold / "changes.json").read_text())


def test_disagreements_go_to_the_resolver_and_its_decision_is_final(gold):
    cal.draw_checkset()
    src = sorted((gold / "check").glob("*.jsonl"))
    for p in src:  # the check labeller agrees, except that it reads g4 as about drugs
        cal.write_jsonl(gold / "labels" / "check" / p.name,
                        [record(r["frag_id"], "drugs" if r["frag_id"] == "g4" else CORE_LENS.get(r["frag_id"]))
                         for r in cal.read_jsonl(p)])
    assert cal.check_file("labels", f"check/{src[0].stem}") == []
    assert cal.check_file("labels", "l1/b001")[0].startswith("unknown labeller")
    summary = cal.collect()
    assert summary["to_resolve"] == 1
    assert summary["agreement"]["drugs"] == {"kappa": 0.5, "checked": 4, "positives_confirmed": 1.0,
                                             "near_misses_confirmed": 0.5}
    assert summary["agreement"]["peace"]["kappa"] == 1.0 and "drugs" in summary["below_bar"]
    queued = cal.read_jsonl(gold / "resolve" / "r001.jsonl")
    assert [(r["frag_id"], r["lenses"], len(r["records"])) for r in queued] == [("g4", ["drugs"], 2)]
    with pytest.raises(cal.CalibrationError):
        cal.final_labels()  # the queue is not resolved yet
    cal.write_jsonl(gold / "resolved" / "r001.jsonl", [{"frag_id": "g4", "decisions": {"drugs": "substantive"},
                                                        "note": ""}])
    final = cal.final_labels().set_index("gid")
    assert final["drugs"].tolist() == [True, True, True, True, False, False, False, False]
    assert final["peace"].tolist() == [False, False, False, False, True, True, False, False]
