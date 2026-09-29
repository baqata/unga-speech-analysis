"""Tests for pipeline.embed.

Most tests use small synthetic parquet fixtures and a fake encoder injected
through run(..., encoder_factory=...), so no model is loaded. The real-model
smoke test is marked `model`; skip it with `-m "not model"`.
"""
import hashlib
import json
import time

import numpy as np
import pandas as pd
import pytest

from pipeline import config
from pipeline import embed


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class FakeEncoder:
    """Deterministic unit vectors derived from the text; records every batch.

    Texts containing "OOM" fail on mps (to exercise the CPU fallback); texts
    containing "BROKEN" fail on every device. Set FakeEncoder.interrupt_after
    to raise KeyboardInterrupt after that many batches (a simulated Ctrl-C).
    """
    calls: list[tuple[str, list[str]]] = []
    interrupt_after: int | None = None

    def __init__(self, device):
        self.device = device
        self.info = {"device": device, "dtype": "fake", "model_id": config.MODEL_ID,
                     "model_revision": "fake-rev", "max_seq_length": embed.MAX_SEQ_LENGTH,
                     "torch": "t", "sentence_transformers": "st", "transformers": "tf"}

    def encode(self, texts):
        if FakeEncoder.interrupt_after is not None and len(FakeEncoder.calls) >= FakeEncoder.interrupt_after:
            raise KeyboardInterrupt
        FakeEncoder.calls.append((self.device, list(texts)))
        if any("BROKEN" in t for t in texts) or (self.device == "mps" and any("OOM" in t for t in texts)):
            raise RuntimeError("MPS backend out of memory (fake)")
        return np.stack([fake_vector(t) for t in texts])


def fake_vector(text: str) -> np.ndarray:
    seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "little")
    v = np.random.default_rng(seed).normal(size=embed.DIM).astype(np.float32)
    return v / np.linalg.norm(v)


def make_fragments(n_speeches=12, per_speech=6, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_speeches):
        speech_id = f"C{s:02d}_{s + 1:02d}_{1946 + s}"
        for seq in range(per_speech):
            rows.append({"speech_id": speech_id, "iso3": speech_id[:3], "year": 1946 + s, "seq": seq,
                         "text": f"Fragment {seq} of {speech_id} on drugs, crime and peace.",
                         "n_words": 10, "n_tokens": int(rng.integers(20, 400)),
                         "para_method": "line", "is_ceremonial": False})
    df = pd.DataFrame(rows)
    df.insert(0, "frag_id", np.arange(len(df), dtype=np.int64))
    # Store in a shuffled row order: nothing may depend on file row order.
    return df.sample(frac=1, random_state=seed).reset_index(drop=True)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Redirect all pipeline paths to a temp dir, use small shards, reset the fake."""
    monkeypatch.setattr(config, "FRAGMENTS", tmp_path / "fragments.parquet")
    monkeypatch.setattr(config, "EMB_DIR", tmp_path / "emb")
    monkeypatch.setattr(config, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(embed, "SHARD_MAX_ITEMS", 10)
    FakeEncoder.calls = []
    FakeEncoder.interrupt_after = None
    make_fragments().to_parquet(config.FRAGMENTS, index=False)
    return tmp_path


def run_fake(kind, **kwargs):
    embed.run(kind, device="mps", encoder_factory=FakeEncoder, **kwargs)


def encoded_texts():
    return [t for _, texts in FakeEncoder.calls for t in texts]


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------

def test_plan_orders_by_length_and_respects_budget(env):
    df = embed.load_input("fragments")
    plan = embed.make_plan(df, "fragments", token_budget=1000)
    assert plan["n_tokens"].is_monotonic_increasing
    assert (plan["pos"] == np.arange(len(plan))).all()
    for _, batch in plan.groupby("batch"):
        assert batch["n_tokens"].max() * len(batch) <= 1000 or len(batch) == 1
        assert batch["shard"].nunique() == 1  # batches never straddle shards
    sizes = plan.groupby("shard").size()
    assert (sizes.iloc[:-1] >= embed.SHARD_MAX_ITEMS).all()
    assert plan["batch"].is_monotonic_increasing and plan["shard"].is_monotonic_increasing


def test_plan_runs_long_items_alone(env):
    df = embed.load_input("fragments")
    df.loc[:2, "n_tokens"] = embed.ALONE_TOKENS  # two of them would fit the budget together
    plan = embed.make_plan(df, "fragments", token_budget=2 * embed.ALONE_TOKENS)
    sizes = plan.groupby("batch")["n_tokens"].agg(["size", "max"])
    assert (sizes["max"] >= embed.ALONE_TOKENS).sum() == 3
    assert (sizes.loc[sizes["max"] >= embed.ALONE_TOKENS, "size"] == 1).all()
    assert (sizes["size"] > 1).any()  # short items are still batched


def test_plan_is_deterministic_and_independent_of_row_order(env):
    df = embed.load_input("fragments")
    shuffled = make_fragments(seed=0).sample(frac=1, random_state=7)
    shuffled.to_parquet(config.FRAGMENTS, index=False)
    df2 = embed.load_input("fragments")
    assert embed.content_hash(df, "fragments") == embed.content_hash(df2, "fragments")
    pd.testing.assert_frame_equal(embed.make_plan(df, "fragments", 1000),
                                  embed.make_plan(df2, "fragments", 1000))


# ---------------------------------------------------------------------------
# Run, resume, input changes
# ---------------------------------------------------------------------------

def test_run_and_finalize_alignment(env):
    run_fake("fragments", token_budget=1000)
    manifest = embed.finalize("fragments")
    paths = embed.final_paths("fragments")
    emb = np.load(paths["embeddings"])
    keys = pd.read_parquet(paths["keys"])
    src = pd.read_parquet(config.FRAGMENTS)

    assert emb.dtype == np.float16 and emb.shape == (len(src), embed.DIM)
    assert (keys["row"] == np.arange(len(keys))).all()
    assert keys[["speech_id", "seq"]].equals(
        keys.sort_values(["speech_id", "seq"])[["speech_id", "seq"]].reset_index(drop=True))
    # Every row holds the vector of its own text, joined on frag_id.
    text = src.set_index("frag_id").loc[keys["frag_id"], "text"]
    expected = np.stack([fake_vector(t) for t in text])
    assert np.abs(emb.astype(np.float32) - expected).max() < 2e-3
    # ... and (speech_id, seq) agree with frag_id.
    merged = keys.merge(src, on="frag_id", suffixes=("", "_src"))
    assert (merged["speech_id"] == merged["speech_id_src"]).all() and (merged["seq"] == merged["seq_src"]).all()
    assert np.allclose(np.linalg.norm(emb.astype(np.float32), axis=1), 1, atol=1e-2)

    on_disk = json.loads(paths["manifest"].read_text())
    assert on_disk == manifest
    assert manifest["n_items"] == len(src) and manifest["dim"] == 1024
    assert manifest["prompt"] is None and manifest["normalized"] is True
    assert manifest["model_revision"] == "fake-rev" and manifest["devices"] == {"mps": len(src)}
    assert manifest["total_tokens"] == int(src["n_tokens"].sum())
    assert (config.LOGS / "embed_fragments.log").read_text().count("shard") >= manifest["n_shards"]


def test_each_item_is_embedded_once_in_plan_batches(env):
    run_fake("fragments", token_budget=1000)
    plan, _ = embed.read_plan("fragments")
    texts = encoded_texts()
    assert len(texts) == len(set(texts)) == len(plan)
    assert len(FakeEncoder.calls) == plan["batch"].nunique()


def test_resume_after_limit_skips_completed_shards(env):
    run_fake("fragments", token_budget=1000, limit=15)
    plan, meta = embed.read_plan("fragments")
    done = embed.done_shards("fragments", meta["n_shards"])
    assert 0 < len(done) < meta["n_shards"]
    first = set(encoded_texts())

    FakeEncoder.calls = []
    run_fake("fragments", token_budget=1000)
    second = set(encoded_texts())
    assert first.isdisjoint(second) and len(first) + len(second) == len(plan)
    assert len(embed.done_shards("fragments", meta["n_shards"])) == meta["n_shards"]

    FakeEncoder.calls = []
    run_fake("fragments")  # everything done: no model calls at all
    assert FakeEncoder.calls == []


def test_resume_after_interrupt_matches_uninterrupted_run(env, tmp_path, monkeypatch):
    FakeEncoder.interrupt_after = 5
    with pytest.raises(KeyboardInterrupt):
        run_fake("fragments", token_budget=1000)
    _, meta = embed.read_plan("fragments")
    done = embed.done_shards("fragments", meta["n_shards"])
    assert 0 < len(done) < meta["n_shards"]
    # A half-written shard from a crash is ignored and overwritten.
    embed.shard_path("fragments", len(done)).with_suffix(".npz.tmp").write_bytes(b"garbage")

    FakeEncoder.interrupt_after = None
    run_fake("fragments", token_budget=1000)
    embed.finalize("fragments")
    resumed = np.load(embed.final_paths("fragments")["embeddings"])
    resumed_keys = pd.read_parquet(embed.final_paths("fragments")["keys"])

    # Fresh uninterrupted run into another directory.
    monkeypatch.setattr(config, "EMB_DIR", tmp_path / "emb_fresh")
    run_fake("fragments", token_budget=1000)
    embed.finalize("fragments")
    fresh = np.load(embed.final_paths("fragments")["embeddings"])
    assert np.array_equal(resumed, fresh)
    assert resumed_keys.equals(pd.read_parquet(embed.final_paths("fragments")["keys"]))


def test_changed_input_is_refused(env):
    run_fake("fragments", token_budget=1000, limit=5)
    df = pd.read_parquet(config.FRAGMENTS)
    df.loc[df.index[0], "text"] = "An edited fragment."
    df.to_parquet(config.FRAGMENTS, index=False)
    with pytest.raises(embed.EmbedError, match="changed since the plan"):
        run_fake("fragments")
    with pytest.raises(embed.EmbedError, match="changed since the plan"):
        embed.finalize("fragments")
    assert embed.main(["run", "fragments", "--device", "cpu"]) == 1  # refuses before loading a model


def test_reordered_input_resumes(env):
    run_fake("fragments", token_budget=1000, limit=5)
    pd.read_parquet(config.FRAGMENTS).iloc[::-1].to_parquet(config.FRAGMENTS, index=False)
    run_fake("fragments")
    embed.finalize("fragments")


def test_finalize_refuses_incomplete_run(env):
    run_fake("fragments", token_budget=1000, limit=5)
    with pytest.raises(embed.EmbedError, match="not done"):
        embed.finalize("fragments")


def test_concurrent_run_is_refused(env):
    # flock locks belong to the open file, so a second open in this process conflicts
    # exactly as a second process would.
    with embed.kind_lock("fragments"):
        with pytest.raises(embed.EmbedError, match="in progress"):
            run_fake("fragments", token_budget=1000)
        assert embed.main(["finalize", "fragments"]) == 1
        assert FakeEncoder.calls == []
        embed.snapshot("fragments.late", years=[1950])
        run_fake("fragments.late")  # the lock is per kind: a part has its own
    run_fake("fragments", token_budget=1000)  # released when the holder exits
    embed.finalize("fragments")


def test_lock_is_released_after_interrupt(env):
    FakeEncoder.interrupt_after = 2
    with pytest.raises(KeyboardInterrupt):
        run_fake("fragments", token_budget=1000)
    FakeEncoder.interrupt_after = None
    run_fake("fragments", token_budget=1000)


def test_progress_is_logged_inside_long_shards(env, monkeypatch):
    monkeypatch.setattr(embed, "PROGRESS_SECONDS", 0)
    run_fake("fragments", token_budget=1000)
    assert "in progress:" in (config.LOGS / "embed_fragments.log").read_text()


def test_changed_token_budget_keeps_plan(env):
    run_fake("fragments", token_budget=1000, limit=5)
    run_fake("fragments", token_budget=4000)
    _, meta = embed.read_plan("fragments")
    assert meta["token_budget"] == 1000
    assert "Ignoring --token-budget 4000" in (config.LOGS / "embed_fragments.log").read_text()


# ---------------------------------------------------------------------------
# Failures and fallback
# ---------------------------------------------------------------------------

def test_failed_item_falls_back_to_cpu(env):
    df = pd.read_parquet(config.FRAGMENTS)
    target = df.loc[df["seq"] == 2].iloc[0]
    df.loc[df["frag_id"] == target["frag_id"], "text"] = "OOM trigger " + target["text"]
    df.to_parquet(config.FRAGMENTS, index=False)

    run_fake("fragments", token_budget=1000)
    manifest = embed.finalize("fragments")
    keys = pd.read_parquet(embed.final_paths("fragments")["keys"])
    assert keys.loc[keys["frag_id"] == target["frag_id"], "device"].item() == "cpu"
    assert manifest["devices"] == {"cpu": 1, "mps": len(df) - 1}
    assert set(manifest["compute_dtypes"]) == {"cpu", "mps"}
    emb = np.load(embed.final_paths("fragments")["embeddings"])
    row = keys.index[keys["frag_id"] == target["frag_id"]][0]
    assert np.abs(emb[row].astype(np.float32) - fake_vector("OOM trigger " + target["text"])).max() < 2e-3
    assert "Retrying" in (config.LOGS / "embed_fragments.log").read_text()


def test_item_failing_everywhere_does_not_stop_the_run(env):
    df = pd.read_parquet(config.FRAGMENTS)
    df.loc[0, "text"] = "BROKEN " + df.loc[0, "text"]
    df.to_parquet(config.FRAGMENTS, index=False)

    run_fake("fragments", token_budget=1000)
    _, meta = embed.read_plan("fragments")
    assert len(embed.done_shards("fragments", meta["n_shards"])) == meta["n_shards"]
    with pytest.raises(embed.EmbedError, match="failed on every device"):
        embed.finalize("fragments")


def test_status_reports_progress(env, capsys):
    run_fake("fragments", token_budget=1000, limit=5)
    embed.snapshot("fragments.late", years=[1950])
    assert embed.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "fragments:" in out and "fragments.late:" in out and "no plan yet" in out
    assert "input: " in out and "(unchanged)" in out and "finalized: no" in out


# ---------------------------------------------------------------------------
# Real model (slow): uv run pytest -m model -s
# ---------------------------------------------------------------------------

SMOKE_TEXTS = [
    "Drug trafficking networks smuggle cocaine across our borders and fuel violence in our cities.",
    "Criminal organizations move narcotics illegally through the region, leaving bloodshed behind.",
    "Rising sea levels and extreme weather caused by climate change threaten small island States.",
    "We call for the peaceful settlement of disputes in accordance with the Charter.",
    "Corruption diverts public resources away from schools and hospitals.",
    "Terrorism in all its forms is a threat to international peace and security.",
    "Human trafficking and the smuggling of migrants exploit the most vulnerable.",
    "Illegal logging and wildlife trafficking destroy our forests and biodiversity.",
    "An effective and fair criminal justice system is the foundation of the rule of law.",
    "Alternative development offers farmers a legal livelihood instead of coca cultivation.",
    "Prevention and treatment of drug use disorders must be grounded in public health.",
    "Money laundering allows organized crime to infiltrate the legitimate economy.",
    "The reform of the Security Council is long overdue.",
    "Nuclear disarmament remains a priority for my delegation.",
    "We welcome the election of the President of the General Assembly.",
    "Poverty eradication is the central goal of sustainable development.",
]


@pytest.mark.model
def test_real_model_smoke(tmp_path, monkeypatch):
    """Embed 16 short texts end to end with the real model on the available device."""
    from tokenizers import Tokenizer

    snapshot, revision = embed.resolve_snapshot()
    tok = Tokenizer.from_file(str(snapshot / "tokenizer.json"))
    n_tokens = [len(e.ids) for e in tok.encode_batch(SMOKE_TEXTS, add_special_tokens=False)]
    monkeypatch.setattr(config, "FRAGMENTS", tmp_path / "fragments.parquet")
    monkeypatch.setattr(config, "EMB_DIR", tmp_path / "emb")
    monkeypatch.setattr(config, "LOGS", tmp_path / "logs")
    pd.DataFrame({"frag_id": np.arange(16), "speech_id": [f"T{i:02d}_01_2000" for i in range(16)],
                  "seq": 0, "text": SMOKE_TEXTS, "n_tokens": n_tokens}).to_parquet(config.FRAGMENTS)

    t0 = time.time()
    embed.run("fragments", device="auto")
    wall = time.time() - t0
    manifest = embed.finalize("fragments")
    emb = np.load(embed.final_paths("fragments")["embeddings"]).astype(np.float32)
    keys = pd.read_parquet(embed.final_paths("fragments")["keys"])

    assert emb.shape == (16, 1024)
    assert np.allclose(np.linalg.norm(emb, axis=1), 1, atol=1e-2)
    assert manifest["model_revision"] == revision and manifest["prompt"] is None
    vec = dict(zip(keys["frag_id"], emb))
    drugs_a, drugs_b, climate = vec[0], vec[1], vec[2]
    assert drugs_a @ drugs_b > drugs_a @ climate and drugs_a @ drugs_b > drugs_b @ climate

    tok_s = manifest["total_tokens"] / manifest["seconds"]
    print(f"\nSmoke: device {manifest['devices']}, {manifest['total_tokens']} tokens, "
          f"encode {manifest['seconds']:.2f}s ({16 / manifest['seconds']:.1f} texts/s, {tok_s:.0f} tok/s), "
          f"wall incl. model load {wall:.1f}s; cos(drugs, drugs')={drugs_a @ drugs_b:.3f}, "
          f"cos(drugs, climate)={drugs_a @ climate:.3f}")


# ---------------------------------------------------------------------------
# Parts: embed some years now, the rest later, then assemble
# ---------------------------------------------------------------------------

LATE = [1950, 1951]


def embed_part(kind, part, **years):
    embed.snapshot(f"{kind}.{part}", **years)
    run_fake(f"{kind}.{part}", token_budget=1000)
    return embed.finalize(f"{kind}.{part}")


def renumber(df: pd.DataFrame) -> pd.DataFrame:
    """frag_id as prepare assigns it: running index in (speech_id, seq) order."""
    df = df.drop(columns="frag_id").sort_values(["speech_id", "seq"]).reset_index(drop=True)
    df.insert(0, "frag_id", np.arange(len(df), dtype=np.int64))
    return df


def test_parts_assemble_like_a_full_run(env):
    embed_part("fragments", "stable", exclude_years=LATE)
    embed_part("fragments", "late", years=LATE)
    manifest = embed.assemble("fragments", ["stable", "late"])
    paths = embed.final_paths("fragments")
    emb, keys = np.load(paths["embeddings"]), pd.read_parquet(paths["keys"])
    src = pd.read_parquet(config.FRAGMENTS)
    assert len(keys) == len(src) and (keys["row"] == np.arange(len(keys))).all()
    text = src.set_index("frag_id").loc[keys["frag_id"], "text"]
    assert np.abs(emb.astype(np.float32) - np.stack([fake_vector(t) for t in text])).max() < 2e-3
    assert set(keys.loc[keys["part"] == "late", "speech_id"].str[-4:].astype(int)) == set(LATE)
    assert manifest["input_hash"] == embed.content_hash(embed.load_input("fragments"), "fragments")
    assert set(manifest["parts"]) == {"stable", "late"} and manifest["n_items"] == len(src)
    assert "assembled" in capture_status()


def capture_status():
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        embed.status()
    return buf.getvalue()


def test_late_years_can_change_and_renumber_after_the_stable_part(env):
    embed_part("fragments", "stable", exclude_years=LATE)
    src = pd.read_parquet(config.FRAGMENTS)
    late = src["speech_id"].str.endswith(("1950", "1951"))
    src.loc[late & (src["seq"] == 0), "text"] = "Revised late text."
    extra = src[late].iloc[[0]].assign(seq=99, text="A new late fragment.")
    renumber(pd.concat([src, extra])).to_parquet(config.FRAGMENTS, index=False)
    FakeEncoder.calls = []
    embed_part("fragments", "late", years=LATE)
    assert set(encoded_texts()) <= set(src.loc[late, "text"]) | {"A new late fragment."}
    embed.assemble("fragments", ["stable", "late"])
    paths = embed.final_paths("fragments")
    emb, keys = np.load(paths["embeddings"]), pd.read_parquet(paths["keys"])
    live = pd.read_parquet(config.FRAGMENTS).set_index("frag_id")
    expected = np.stack([fake_vector(t) for t in live.loc[keys["frag_id"], "text"]])
    assert np.abs(emb.astype(np.float32) - expected).max() < 2e-3


def test_assemble_refuses_a_changed_stable_text(env):
    embed_part("fragments", "stable", exclude_years=LATE)
    embed_part("fragments", "late", years=LATE)
    src = pd.read_parquet(config.FRAGMENTS)
    src.loc[src["speech_id"].str.endswith("1946") & (src["seq"] == 1), "text"] = "Edited after embedding."
    src.to_parquet(config.FRAGMENTS, index=False)
    with pytest.raises(embed.EmbedError, match="changed since their part was embedded"):
        embed.assemble("fragments", ["stable", "late"])


def test_assemble_refuses_rows_in_no_part_or_in_two(env):
    embed_part("fragments", "stable", exclude_years=LATE)
    with pytest.raises(embed.EmbedError, match="in no part"):
        embed.assemble("fragments", ["stable"])
    embed_part("fragments", "late", years=LATE + [1946])
    with pytest.raises(embed.EmbedError, match="more than one part"):
        embed.assemble("fragments", ["stable", "late"])


def test_snapshot_is_frozen_once_planned(env):
    embed.snapshot("fragments.late", years=LATE)
    embed.snapshot("fragments.late", years=LATE)  # same content: no-op
    run_fake("fragments.late", token_budget=1000, limit=1)
    src = pd.read_parquet(config.FRAGMENTS)
    src.loc[src["speech_id"].str.endswith("1950"), "text"] = "Changed."
    src.to_parquet(config.FRAGMENTS, index=False)
    with pytest.raises(embed.EmbedError, match="different snapshot"):
        embed.snapshot("fragments.late", years=LATE)
    with pytest.raises(embed.EmbedError, match="not a part"):
        embed.snapshot("fragments", years=LATE)


def test_cli_accepts_parts(env):
    assert embed.main(["snapshot", "fragments.stable", "--exclude-years", *map(str, LATE)]) == 0
    assert embed.input_path("fragments.stable").exists()
    with pytest.raises(SystemExit):
        embed.main(["run", "fragments.Bad!"])
