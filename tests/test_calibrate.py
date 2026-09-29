"""Tests for pipeline.calibrate on synthetic data (no model): score arithmetic, the sample
design, agreement, record checks and a small end-to-end run."""
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


def test_fleiss_kappa():
    assert cal.fleiss_kappa(np.array([0, 3, 0, 3, 3])) == pytest.approx(1.0)
    # Hand-computed: votes 3,0,2,1 -> P_i = 1, 1, 1/3, 1/3; p = 0.5 -> kappa = 1/3.
    assert cal.fleiss_kappa(np.array([3, 0, 2, 1])) == pytest.approx(1 / 3)


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
    for name in ("SAMPLE", "MANIFEST", "BATCHES", "LABELS", "RESOLVE", "RESOLVED", "FINAL", "FIT",
                 "CLASSIFIERS", "RESULTS", "GOLD"):
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

    # Three fake labellers read the batches and write their records. The first never errs, so
    # every error of the others is a disagreement that the resolver sees.
    truth_by_gid = truth.loc[sample.set_index("gid").frag_id]
    truth_by_gid.index = sample.gid
    for k, lab in enumerate(cal.LABELLERS):
        rng = np.random.default_rng(10 + k)
        for path in sorted(cal.BATCHES.glob("b*.jsonl")):
            recs = [fake_label(r["text"], r["frag_id"], truth_by_gid.loc[r["frag_id"]], rng,
                               flip=0.03 if k else 0.0)
                    for r in cal.read_jsonl(path)]
            cal.write_jsonl(cal.LABELS / lab / path.name, recs)
    assert cal.check_file("labels", "l2/b001") == []
    first = cal.read_jsonl(cal.LABELS / "l2" / "b001.jsonl")
    cal.write_jsonl(cal.LABELS / "l2" / "b001.jsonl", first[1:] + [dict(first[0], confidence=5)])
    assert len(cal.check_file("labels", "l2/b001")) == 2  # order and confidence
    cal.write_jsonl(cal.LABELS / "l2" / "b001.jsonl", first)
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
