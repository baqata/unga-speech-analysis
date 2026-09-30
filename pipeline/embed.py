"""Embed fragments with Harrier-OSS-v1-0.6B, resumably.

Commands (from the repo root):
    uv run python -m pipeline.embed run fragments [--limit N] [--device auto|mps|cpu] [--token-budget T]
    uv run python -m pipeline.embed finalize fragments
    uv run python -m pipeline.embed status
    uv run python -m pipeline.embed snapshot fragments.<part> (--years Y ... | --exclude-years Y ...)
    uv run python -m pipeline.embed assemble fragments --parts <part> ...

A kind is the base kind "fragments" or one of its parts, "fragments.<part>" (see Parts).
A speech's vector is the mean of its non-ceremonial fragments' vectors; pipeline.export
computes it.

How a run works:
1. A plan is written once per kind to EMB_DIR/<kind>/plan.parquet (+ plan.json).
   Items are sorted by n_tokens (ties by key), packed into batches so that
   max_len x batch_size <= token budget, and consecutive batches are grouped
   into shards. plan.json stores a content hash of the input (keys + text).
2. Each shard is embedded batch by batch and written atomically (tmp file,
   then rename) to EMB_DIR/<kind>/shards/. Completed shards are skipped on
   re-run, so a run resumes after a crash, sleep or Ctrl-C. If the input
   changed since the plan was written, the run refuses to resume. A lock file
   (EMB_DIR/<kind>/run.lock) allows one run or finalize per kind at a time.
3. finalize assembles EMB_DIR/<kind>.f16.npy (N x 1024, float16, L2-normalised),
   EMB_DIR/<kind>_keys.parquet (row-aligned keys) and EMB_DIR/<kind>_manifest.json.

Parts: a part (kind "fragments.<part>", e.g. fragments.stable) embeds a frozen
snapshot of some years of the fragments (EMB_DIR/<kind>/input.parquet, written
by `snapshot`), so years still under revision can be embedded later. run and
finalize work on a part exactly as on fragments. `assemble` joins finalized
parts into the final files of fragments, aligned with the live input: rows match
on (speech_id, seq), never on frag_id, which prepare renumbers. It refuses if a
live row is missing, found in two parts, or has a text that differs from the one
embedded.

Documents are embedded WITHOUT any prompt. Queries (not embedded here) need
"Instruct: <task>\nQuery: <text>".
"""
import argparse
import fcntl
import functools
import gc
import hashlib
import json
import logging
import os
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline import config

# Never reach the network: the model is read from the local Hugging Face cache.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

DIM = 1024
MAX_SEQ_LENGTH = 32768          # model context; longer items are truncated
DEFAULT_TOKEN_BUDGET = 16384    # max_len x batch_size per forward pass
ALONE_TOKENS = 8192             # items this long always run one at a time
MAX_BATCH_ITEMS = 256
SHARD_MAX_ITEMS = 2048          # a shard closes at the first batch boundary past either cap;
SHARD_MAX_TOKENS = 500_000      # the token cap bounds what a crash can lose (~9 min at 900 tok/s, ~25 min at 330)
PROGRESS_SECONDS = 300          # log a progress line at least this often inside a shard
NORM_TOLERANCE = 1e-2           # float16 storage keeps norms within ~1e-3 of 1

KINDS = {
    "fragments": {"keys": ["frag_id", "speech_id", "seq"], "id": "frag_id",
                  "order": ["speech_id", "seq"]},
}


PART_RE = re.compile(r"^fragments\.([a-z0-9_]+)$")


def base_kind(kind: str) -> str:
    return kind.split(".", 1)[0]


def spec_of(kind: str) -> dict:
    return KINDS[base_kind(kind)]


def is_part(kind: str) -> bool:
    return "." in kind


class EmbedError(Exception):
    """A condition the user must resolve (missing input, changed input, incomplete run)."""


# ---------------------------------------------------------------------------
# Paths and logging
# ---------------------------------------------------------------------------

def input_path(kind: str) -> Path:
    if is_part(kind):
        return kind_dir(kind) / "input.parquet"  # the part's frozen snapshot
    return config.FRAGMENTS


def kind_dir(kind: str) -> Path:
    return config.EMB_DIR / kind


def shard_path(kind: str, shard: int) -> Path:
    return kind_dir(kind) / "shards" / f"shard_{shard:05d}.npz"


def final_paths(kind: str) -> dict[str, Path]:
    return {"embeddings": config.EMB_DIR / f"{kind}.f16.npy",
            "keys": config.EMB_DIR / f"{kind}_keys.parquet",
            "manifest": config.EMB_DIR / f"{kind}_manifest.json"}


def rel(path: Path) -> str:
    """Path relative to the repo root when possible (for logs and manifests)."""
    try:
        return str(Path(path).relative_to(config.ROOT))
    except ValueError:
        return str(path)


@contextmanager
def kind_lock(kind: str):
    """Hold an exclusive lock on EMB_DIR/<kind>/run.lock, or raise EmbedError if taken.

    The OS releases the lock when the process exits, even after a crash, so a
    stale lock file never blocks a later run.
    """
    path = kind_dir(kind) / "run.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise EmbedError(f"Another embed run or finalize for {kind} is in progress "
                             f"(it holds {rel(path)}); wait for it to finish or stop it.") from None
        yield


def locked(func):
    """Run func(kind, ...) while holding the lock for that kind."""
    @functools.wraps(func)
    def wrapper(kind, *args, **kwargs):
        with kind_lock(kind):
            return func(kind, *args, **kwargs)
    return wrapper


def get_logger(kind: str) -> logging.Logger:
    """Log to stdout and to LOGS/embed_<kind>.log."""
    log = logging.getLogger(f"embed.{kind}")
    for handler in list(log.handlers):
        handler.close()
        log.removeHandler(handler)
    log.setLevel(logging.INFO)
    config.LOGS.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    for handler in (logging.StreamHandler(sys.stdout),
                    logging.FileHandler(config.LOGS / f"embed_{kind}.log", encoding="utf-8")):
        handler.setFormatter(fmt)
        log.addHandler(handler)
    return log


# ---------------------------------------------------------------------------
# Input and plan
# ---------------------------------------------------------------------------

def load_input(kind: str) -> pd.DataFrame:
    """Keys, text and n_tokens in canonical key order (independent of file row order)."""
    spec = spec_of(kind)
    path = input_path(kind)
    if not path.exists():
        raise EmbedError(f"Input not found: {rel(path)} (written by the corpus-preparation step).")
    df = pd.read_parquet(path, columns=spec["keys"] + ["text", "n_tokens"])
    for cols in {tuple([spec["id"]]), tuple(spec["order"])}:
        dup = df.duplicated(list(cols))
        if dup.any():
            raise EmbedError(f"{rel(path)}: {dup.sum()} duplicated keys {list(cols)}.")
    if df["text"].isna().any() or df["n_tokens"].isna().any():
        raise EmbedError(f"{rel(path)}: missing text or n_tokens values.")
    return df.sort_values(spec["order"], kind="stable").reset_index(drop=True)


def content_hash(df: pd.DataFrame, kind: str) -> str:
    """SHA-256 of keys + text, in canonical key order."""
    h = hashlib.sha256()
    for row in df[spec_of(kind)["keys"] + ["text"]].itertuples(index=False):
        h.update("\x1f".join(map(str, row)).encode("utf-8"))
        h.update(b"\x1e")
    return h.hexdigest()


def make_plan(df: pd.DataFrame, kind: str, token_budget: int) -> pd.DataFrame:
    """Order items by length and assign each one a batch and a shard.

    Sorting by n_tokens keeps padding minimal. Because lengths ascend, the item
    being added always sets the padded length of its batch.
    """
    spec = spec_of(kind)
    plan = (df[spec["keys"] + ["n_tokens"]]
            .sort_values(["n_tokens"] + spec["order"], kind="stable")
            .reset_index(drop=True))
    batches, shards = [], []
    batch = shard = batch_items = shard_items = shard_tokens = 0
    for n in plan["n_tokens"].to_numpy():
        n = max(int(n), 1)
        if batch_items and (n >= ALONE_TOKENS or n * (batch_items + 1) > token_budget
                            or batch_items >= MAX_BATCH_ITEMS):
            batch += 1
            batch_items = 0
            if shard_items >= SHARD_MAX_ITEMS or shard_tokens >= SHARD_MAX_TOKENS:
                shard += 1
                shard_items = shard_tokens = 0
        batches.append(batch)
        shards.append(shard)
        batch_items += 1
        shard_items += 1
        shard_tokens += n
    plan["batch"] = np.asarray(batches, dtype=np.int64)
    plan["shard"] = np.asarray(shards, dtype=np.int64)
    plan.insert(0, "pos", np.arange(len(plan), dtype=np.int64))
    return plan


def read_plan(kind: str) -> tuple[pd.DataFrame, dict] | None:
    meta_path = kind_dir(kind) / "plan.json"
    if not meta_path.exists():
        return None
    return pd.read_parquet(kind_dir(kind) / "plan.parquet"), json.loads(meta_path.read_text())


def write_plan(kind: str, plan: pd.DataFrame, meta: dict) -> None:
    """plan.parquet first, plan.json last: plan.json marks a complete plan."""
    out = kind_dir(kind)
    (out / "shards").mkdir(parents=True, exist_ok=True)
    tmp = out / "plan.parquet.tmp"
    plan.to_parquet(tmp, index=False)
    os.replace(tmp, out / "plan.parquet")
    tmp = out / "plan.json.tmp"
    tmp.write_text(json.dumps(meta, indent=2))
    os.replace(tmp, out / "plan.json")


def load_or_create_plan(kind, df, input_hash, token_budget, log) -> tuple[pd.DataFrame, dict]:
    existing = read_plan(kind)
    if existing is not None:
        plan, meta = existing
        if meta["input_hash"] != input_hash:
            raise EmbedError(
                f"{rel(input_path(kind))} changed since the plan was written "
                f"({meta['created_at']}); refusing to resume. To start over, delete "
                f"{rel(kind_dir(kind))} (and any finalized {kind} files).")
        if token_budget is not None and token_budget != meta["token_budget"]:
            log.warning("Ignoring --token-budget %d: the existing plan uses %d.",
                        token_budget, meta["token_budget"])
        return plan, meta
    budget = token_budget or DEFAULT_TOKEN_BUDGET
    plan = make_plan(df, kind, budget)
    meta = {"kind": kind, "model_id": config.MODEL_ID, "input": rel(input_path(kind)),
            "input_hash": input_hash, "n_items": len(plan), "n_tokens": int(plan["n_tokens"].sum()),
            "n_batches": int(plan["batch"].max() + 1) if len(plan) else 0,
            "n_shards": int(plan["shard"].max() + 1) if len(plan) else 0,
            "token_budget": budget, "alone_tokens": ALONE_TOKENS,
            "shard_max_items": SHARD_MAX_ITEMS, "shard_max_tokens": SHARD_MAX_TOKENS,
            "created_at": now()}
    write_plan(kind, plan, meta)
    too_long = int((plan["n_tokens"] >= MAX_SEQ_LENGTH).sum())
    if too_long:
        log.warning("%d item(s) have >= %d tokens and will be truncated.", too_long, MAX_SEQ_LENGTH)
    log.info("Plan written: %d items, %d tokens, %d batches, %d shards (token budget %d).",
             meta["n_items"], meta["n_tokens"], meta["n_batches"], meta["n_shards"], budget)
    return plan, meta


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

def resolve_snapshot() -> tuple[Path, str]:
    """Local snapshot directory and revision hash of the cached model.

    Reads the cache layout directly because this cache has no refs/main,
    which makes offline loading by repo id fail.
    """
    from huggingface_hub.constants import HF_HUB_CACHE

    repo = Path(HF_HUB_CACHE) / ("models--" + config.MODEL_ID.replace("/", "--"))
    ref = repo / "refs" / "main"
    if ref.exists():
        revision = ref.read_text().strip()
    else:
        snapshots = sorted(p.name for p in (repo / "snapshots").glob("*") if p.is_dir())
        if len(snapshots) != 1:
            raise EmbedError(f"Expected one cached snapshot of {config.MODEL_ID} in {repo}, "
                             f"found {len(snapshots)}.")
        revision = snapshots[0]
    path = repo / "snapshots" / revision
    if not (path / "model.safetensors").exists():
        raise EmbedError(f"{config.MODEL_ID} is not fully cached at {path}.")
    return path, revision


def resolve_device(device: str) -> str:
    if device != "auto":
        return device
    import torch
    return "mps" if torch.backends.mps.is_available() else "cpu"


class HarrierEncoder:
    """Harrier-OSS-v1-0.6B via sentence-transformers: fp16 on MPS, fp32 on CPU.

    The seam used by the runner (and faked in tests) is: HarrierEncoder(device)
    -> object with .encode(texts) -> (n, DIM) array and an .info dict.
    """

    def __init__(self, device: str):
        import sentence_transformers
        import torch
        import transformers
        from sentence_transformers import SentenceTransformer

        path, revision = resolve_snapshot()
        dtype = torch.float16 if device == "mps" else torch.float32
        self.model = SentenceTransformer(str(path), device=device, local_files_only=True,
                                         model_kwargs={"dtype": dtype})
        self.model.max_seq_length = MAX_SEQ_LENGTH
        if self.model.default_prompt_name is not None:
            raise EmbedError("The model defines a default prompt; documents must have none.")
        self.info = {"device": device, "dtype": str(dtype).removeprefix("torch."),
                     "model_id": config.MODEL_ID, "model_revision": revision,
                     "max_seq_length": MAX_SEQ_LENGTH, "torch": torch.__version__,
                     "sentence_transformers": sentence_transformers.__version__,
                     "transformers": transformers.__version__}

    def encode(self, texts: list[str]) -> np.ndarray:
        # No prompt for documents; one forward pass per call.
        return self.model.encode(texts, prompt=None, batch_size=len(texts),
                                 normalize_embeddings=True, convert_to_numpy=True,
                                 show_progress_bar=False)


def release_memory() -> None:
    """Free cached accelerator memory after a failure (no-op when torch is not loaded)."""
    gc.collect()
    torch = sys.modules.get("torch")
    if torch is not None and torch.backends.mps.is_available():
        torch.mps.empty_cache()


def encode_checked(encoder, texts: list[str]) -> np.ndarray:
    """Encode and return float32 unit vectors; raise if the output is unusable."""
    emb = np.asarray(encoder.encode(texts), dtype=np.float32)
    if emb.shape != (len(texts), DIM):
        raise ValueError(f"expected shape {(len(texts), DIM)}, got {emb.shape}")
    if not np.isfinite(emb).all():
        raise ValueError("non-finite values in embeddings")
    return emb / np.linalg.norm(emb, axis=1, keepdims=True)


def embed_batch(texts, ids, device, get_encoder, log) -> tuple[np.ndarray, list[str]]:
    """Embed one batch without ever raising on a model error.

    On failure (e.g. MPS out of memory) the batch is retried item by item; an
    item that still fails is retried on CPU (fp32); an item that fails on every
    device gets a NaN row and device "failed" (finalize refuses such runs).
    """
    encoder = get_encoder(device)  # loading errors are fatal on purpose
    try:
        return encode_checked(encoder, texts), [device] * len(texts)
    except Exception as exc:
        log.warning("Batch of %d item(s) %s failed on %s: %s: %s", len(texts),
                    short_ids(ids), device, type(exc).__name__, str(exc)[:300])
        release_memory()
    if len(texts) > 1:
        parts = [embed_batch([t], [i], device, get_encoder, log) for t, i in zip(texts, ids)]
        return np.vstack([p[0] for p in parts]), [d for p in parts for d in p[1]]
    if device != "cpu":
        log.warning("Retrying %s on cpu (fp32).", ids[0])
        return embed_batch(texts, ids, "cpu", get_encoder, log)
    log.error("FAILED %s on every device; stored as NaN.", ids[0])
    return np.full((1, DIM), np.nan, dtype=np.float32), ["failed"]


def short_ids(ids) -> str:
    ids = [str(i) for i in ids]
    return ", ".join(ids[:3]) + (f", ... (+{len(ids) - 3})" if len(ids) > 3 else "")


# ---------------------------------------------------------------------------
# Shards
# ---------------------------------------------------------------------------

def write_shard(path: Path, pos, ids, emb, devices, meta: dict) -> None:
    """Write a shard atomically: a crash leaves either no shard or a complete one."""
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as f:
        np.savez(f, pos=np.asarray(pos, dtype=np.int64), ids=np.asarray(list(ids)),
                 emb=np.asarray(emb, dtype=np.float16), device=np.asarray(devices, dtype=str),
                 meta=np.asarray(json.dumps(meta)))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read_shard(path: Path) -> dict:
    with np.load(path, allow_pickle=False) as z:
        shard = {name: z[name] for name in z.files}
    shard["meta"] = json.loads(str(shard["meta"]))
    return shard


def done_shards(kind: str, n_shards: int) -> list[int]:
    return [s for s in range(n_shards) if shard_path(kind, s).exists()]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@locked
def run(kind: str, limit: int | None = None, device: str = "auto",
        token_budget: int | None = None, encoder_factory=HarrierEncoder) -> None:
    """Embed all pending shards of one kind (resumable)."""
    log = get_logger(kind)
    spec = spec_of(kind)
    df = load_input(kind)
    plan, meta = load_or_create_plan(kind, df, content_hash(df, kind), token_budget, log)
    n_shards, total_items, total_tokens = meta["n_shards"], meta["n_items"], meta["n_tokens"]

    done = set(done_shards(kind, n_shards))
    pending = [s for s in range(n_shards) if s not in done]
    in_done = plan["shard"].isin(done)
    items_done, tokens_done = int(in_done.sum()), int(plan.loc[in_done, "n_tokens"].sum())
    log.info("%s: %d/%d shards done (%d/%d items); %d pending.", kind, len(done), n_shards,
             items_done, total_items, len(pending))
    if not pending:
        log.info("Nothing to do. Next: uv run python -m pipeline.embed finalize %s", kind)
        return

    device = resolve_device(device)
    encoders = {}

    def get_encoder(dev: str):
        if dev not in encoders:
            log.info("Loading %s on %s ...", config.MODEL_ID, dev)
            t0 = time.time()
            encoders[dev] = encoder_factory(dev)
            log.info("Loaded in %.1fs: %s", time.time() - t0, encoders[dev].info)
        return encoders[dev]

    get_encoder(device)
    shard_path(kind, 0).parent.mkdir(parents=True, exist_ok=True)
    text_by_id = df.set_index(spec["id"])["text"]
    session_items = session_tokens = 0
    session_seconds = 0.0
    try:
        for shard in pending:
            rows = plan[plan["shard"] == shard]
            t0 = time.time()
            emb = np.empty((len(rows), DIM), dtype=np.float32)
            devices = [""] * len(rows)
            start = shard_tok = 0
            last_log = t0
            for _, batch in rows.groupby("batch", sort=True):
                ids = batch[spec["id"]].tolist()
                vecs, devs = embed_batch(text_by_id.loc[ids].tolist(), ids, device, get_encoder, log)
                emb[start:start + len(ids)] = vecs
                devices[start:start + len(ids)] = devs
                start += len(ids)
                shard_tok += int(batch["n_tokens"].sum())
                if start < len(rows) and time.time() - last_log >= PROGRESS_SECONDS:
                    # Heartbeat inside long shards, so a slow run can be told apart from a hung one.
                    last_log = time.time()
                    log.info("%s shard %d/%d in progress: %d/%d items, %d tokens in %s (%.0f tok/s)",
                             kind, shard + 1, n_shards, start, len(rows), shard_tok,
                             format_duration(last_log - t0), shard_tok / max(last_log - t0, 1e-9))
            seconds = time.time() - t0
            n_tok = int(rows["n_tokens"].sum())
            shard_meta = {"shard": shard, "n_items": len(rows), "n_tokens": n_tok,
                          "seconds": round(seconds, 3), "finished_at": now(),
                          "encoders": {d: encoders[d].info for d in sorted(set(devices)) if d in encoders}}
            write_shard(shard_path(kind, shard), rows["pos"], rows[spec["id"]], emb, devices, shard_meta)

            items_done += len(rows)
            tokens_done += n_tok
            session_items += len(rows)
            session_tokens += n_tok
            session_seconds += seconds
            rate = session_tokens / session_seconds if session_seconds else 0.0
            eta = (total_tokens - tokens_done) / rate if rate else 0.0
            failed = devices.count("failed")
            log.info("%s shard %d/%d: %d items, %d tokens in %.1fs (%.0f tok/s) | "
                     "total %d/%d items (%.1f%%) | ETA %s%s", kind, shard + 1, n_shards, len(rows),
                     n_tok, seconds, n_tok / seconds if seconds else 0.0, items_done, total_items,
                     100 * items_done / total_items, format_duration(eta),
                     f" | {failed} FAILED item(s)" if failed else "")
            if limit is not None and session_items >= limit:
                log.info("Stopping after %d items (--limit %d); re-run to continue.", session_items, limit)
                break
    except KeyboardInterrupt:
        log.warning("Interrupted; completed shards are kept. Re-run to resume.")
        raise
    remaining = n_shards - len(done_shards(kind, n_shards))
    log.info("Session: %d items, %d tokens in %s (%.0f tok/s); %d shard(s) remaining.",
             session_items, session_tokens, format_duration(session_seconds),
             session_tokens / session_seconds if session_seconds else 0.0, remaining)


@locked
def finalize(kind: str) -> dict:
    """Assemble shards into the final matrix, keys and manifest; verify norms and NaN."""
    log = get_logger(kind)
    spec = spec_of(kind)
    existing = read_plan(kind)
    if existing is None:
        raise EmbedError(f"No plan for {kind}; run `uv run python -m pipeline.embed run {kind}` first.")
    plan, meta = existing
    if input_path(kind).exists():
        if content_hash(load_input(kind), kind) != meta["input_hash"]:
            raise EmbedError(f"{rel(input_path(kind))} changed since the plan was written; "
                             f"refusing to finalize. Delete {rel(kind_dir(kind))} and re-run.")
    else:
        log.warning("%s not found; cannot re-check the input hash.", rel(input_path(kind)))
    missing = [s for s in range(meta["n_shards"]) if not shard_path(kind, s).exists()]
    if missing:
        raise EmbedError(f"{len(missing)}/{meta['n_shards']} {kind} shards are not done; "
                         f"run `uv run python -m pipeline.embed run {kind}` first.")

    n = len(plan)
    emb = np.full((n, DIM), np.nan, dtype=np.float16)
    device = np.full(n, "", dtype=object)
    seen = np.zeros(n, dtype=bool)
    shard_metas = []
    for s in range(meta["n_shards"]):
        shard = read_shard(shard_path(kind, s))
        pos = shard["pos"]
        if not (plan.loc[pos, "shard"].to_numpy() == s).all() or \
                not (plan.loc[pos, spec["id"]].to_numpy() == shard["ids"]).all():
            raise EmbedError(f"Shard {s} does not match the plan; delete it and re-run.")
        emb[pos], device[pos], seen[pos] = shard["emb"], shard["device"], True
        shard_metas.append(shard["meta"])
    if not seen.all():
        raise EmbedError(f"{(~seen).sum()} planned items are missing from the shards.")
    failed = plan.loc[device == "failed", spec["id"]].tolist()
    if failed:
        raise EmbedError(f"{len(failed)} item(s) failed on every device ({short_ids(failed)}); "
                         "delete their shards and re-run.")

    norms = np.linalg.norm(emb.astype(np.float32), axis=1)
    if not np.isfinite(emb).all():
        raise EmbedError("NaN or infinite values in the embeddings.")
    if np.abs(norms - 1).max() > NORM_TOLERANCE:
        raise EmbedError(f"Norms outside 1 +/- {NORM_TOLERANCE}: min {norms.min():.4f}, max {norms.max():.4f}.")

    # Final rows follow the natural key order; the keys file is row-aligned.
    order = plan.sort_values(spec["order"], kind="stable")["pos"].to_numpy()
    keys = plan.loc[order, spec["keys"] + ["n_tokens"]].reset_index(drop=True)
    keys["device"] = device[order].astype(str)
    keys.insert(0, "row", np.arange(n, dtype=np.int64))

    infos = [info for m in shard_metas for info in m["encoders"].values()]
    revisions = sorted({i["model_revision"] for i in infos})
    if len(revisions) > 1:
        raise EmbedError(f"Shards were made with different model revisions {revisions}; "
                         f"delete {rel(kind_dir(kind))} and re-run.")
    paths = final_paths(kind)
    manifest = {
        "kind": kind, "model_id": config.MODEL_ID, "model_revision": revisions[0] if revisions else None,
        "dim": DIM, "dtype": "float16", "normalized": True, "prompt": None, "pooling": "lasttoken",
        "max_seq_length": MAX_SEQ_LENGTH,
        "files": {name: p.name for name, p in paths.items() if name != "manifest"},
        "row_order": spec["order"], "keys": spec["keys"],
        "n_items": n, "total_tokens": int(plan["n_tokens"].sum()),
        "seconds": round(sum(m["seconds"] for m in shard_metas), 1),
        "devices": {d: int(c) for d, c in keys["device"].value_counts().sort_index().items()},
        "compute_dtypes": {i["device"]: i["dtype"] for i in infos},
        "torch_version": one_or_list(i["torch"] for i in infos),
        "sentence_transformers_version": one_or_list(i["sentence_transformers"] for i in infos),
        "transformers_version": one_or_list(i["transformers"] for i in infos),
        "input": meta["input"], "input_hash": meta["input_hash"],
        "token_budget": meta["token_budget"], "n_shards": meta["n_shards"],
        "norm_min": round(float(norms.min()), 5), "norm_max": round(float(norms.max()), 5),
        "plan_created_at": meta["created_at"], "finalized_at": now(),
    }

    write_final(paths, emb[order], keys, manifest)
    log.info("Finalized %s: %d x %d float16, norms %.4f-%.4f, devices %s -> %s", kind, n, DIM,
             norms.min(), norms.max(), manifest["devices"], rel(paths["embeddings"]))
    return manifest


def write_final(paths: dict[str, Path], emb: np.ndarray, keys: pd.DataFrame, manifest: dict) -> None:
    config.EMB_DIR.mkdir(parents=True, exist_ok=True)
    tmp = paths["embeddings"].with_name(paths["embeddings"].name + ".tmp")
    with open(tmp, "wb") as f:
        np.save(f, emb)
    os.replace(tmp, paths["embeddings"])
    tmp = paths["keys"].with_name(paths["keys"].name + ".tmp")
    keys.to_parquet(tmp, index=False)
    os.replace(tmp, paths["keys"])
    tmp = paths["manifest"].with_name(paths["manifest"].name + ".tmp")
    tmp.write_text(json.dumps(manifest, indent=2))
    os.replace(tmp, paths["manifest"])  # written last: its presence marks a complete finalize


def snapshot(kind: str, years=None, exclude_years=None) -> pd.DataFrame:
    """Freeze the rows of some years of the fragments as the input of part <kind>.

    Writing the same snapshot again is a no-op. A different snapshot is refused
    once the part has a plan: delete the part's folder to start it over.
    """
    if not PART_RE.match(kind):
        raise EmbedError(f"{kind!r} is not a part; name it fragments.<part>.")
    if (years is None) == (exclude_years is None):
        raise EmbedError("Give either years or exclude_years.")
    spec = spec_of(kind)
    src = input_path(base_kind(kind))
    if not src.exists():
        raise EmbedError(f"Input not found: {rel(src)} (written by the corpus-preparation step).")
    df = pd.read_parquet(src, columns=spec["keys"] + ["text", "n_tokens", "year"])
    keep = df["year"].isin(years) if years is not None else ~df["year"].isin(exclude_years)
    df = df[keep].sort_values(spec["order"], kind="stable").reset_index(drop=True)
    if df.empty:
        raise EmbedError(f"No row of {rel(src)} falls in {kind}.")
    out = input_path(kind)
    if out.exists():
        if content_hash(load_input(kind), kind) == content_hash(df, kind):
            return df
        if read_plan(kind) is not None:
            raise EmbedError(f"{kind} was planned on a different snapshot; to start the part over, "
                             f"delete {rel(kind_dir(kind))}.")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, out)
    return df


def merged_field(values):
    """One value when all parts agree, else the sorted distinct values (lists are flattened)."""
    flat = [x for v in values for x in (v if isinstance(v, list) else [v])]
    return one_or_list(flat)


def assemble(kind: str, parts: list[str]) -> dict:
    """Join finalized parts into the final files of base kind <kind>, aligned with its live input."""
    if kind not in KINDS:
        raise EmbedError(f"assemble takes a base kind ({', '.join(KINDS)}), not {kind!r}.")
    if not parts or len(set(parts)) != len(parts):
        raise EmbedError("Name each part once.")
    spec = KINDS[kind]
    log = get_logger(kind)
    with kind_lock(kind):
        live = load_input(kind)
        pools, manifests = [], {}
        for part in parts:
            pk = f"{kind}.{part}"
            paths = final_paths(pk)
            if not PART_RE.match(pk) or not paths["manifest"].exists():
                raise EmbedError(f"{pk} is not finalized; run and finalize it first.")
            man = json.loads(paths["manifest"].read_text())
            snap = load_input(pk)
            if content_hash(snap, pk) != man["input_hash"]:
                raise EmbedError(f"The snapshot of {pk} changed after it was embedded; embed the part again.")
            keys = pd.read_parquet(paths["keys"])
            if not keys[spec["order"]].equals(snap[spec["order"]]):
                raise EmbedError(f"{pk}: its keys do not match its snapshot.")
            pool = snap[spec["order"] + ["text"]].copy()
            pool["part"], pool["row"], pool["device"] = part, keys["row"].to_numpy(), keys["device"].to_numpy()
            pools.append(pool)
            manifests[part] = man
        pool = pd.concat(pools, ignore_index=True)
        doubled = pool.duplicated(spec["order"], keep=False)
        if doubled.any():
            raise EmbedError(f"{int(doubled.sum())} rows are in more than one part "
                             f"({short_ids(pool.loc[doubled, spec['order'][0]])}).")
        merged = live.merge(pool, on=spec["order"], how="left", suffixes=("", "_part"), validate="one_to_one")
        missing = merged["part"].isna()
        if missing.any():
            raise EmbedError(f"{int(missing.sum())} rows of {rel(input_path(kind))} are in no part "
                             f"({short_ids(merged.loc[missing, spec['id']])}); snapshot and embed them.")
        changed = merged["text"] != merged["text_part"]
        if changed.any():
            raise EmbedError(f"{int(changed.sum())} rows changed since their part was embedded "
                             f"({short_ids(merged.loc[changed, spec['id']])}); embed that part again.")
        revisions = sorted({m["model_revision"] for m in manifests.values()})
        if len(revisions) > 1:
            raise EmbedError(f"Parts were made with different model revisions {revisions}.")

        emb = np.empty((len(live), DIM), dtype=np.float16)
        for part in manifests:
            sel = (merged["part"] == part).to_numpy()
            part_emb = np.load(final_paths(f"{kind}.{part}")["embeddings"], mmap_mode="r")
            emb[sel] = part_emb[merged.loc[sel, "row"].to_numpy(dtype=np.int64)]
        norms = np.linalg.norm(emb.astype(np.float32), axis=1)
        if not np.isfinite(emb).all() or np.abs(norms - 1).max() > NORM_TOLERANCE:
            raise EmbedError("Assembled embeddings have NaN values or norms away from 1.")
        keys = live[spec["keys"] + ["n_tokens"]].copy()
        keys["device"] = merged["device"].to_numpy()
        keys["part"] = merged["part"].to_numpy()
        keys.insert(0, "row", np.arange(len(keys), dtype=np.int64))

        paths = final_paths(kind)
        mans = list(manifests.values())
        manifest = {
            "kind": kind, "model_id": config.MODEL_ID, "model_revision": revisions[0],
            "dim": DIM, "dtype": "float16", "normalized": True, "prompt": None, "pooling": "lasttoken",
            "max_seq_length": MAX_SEQ_LENGTH,
            "files": {name: p.name for name, p in paths.items() if name != "manifest"},
            "row_order": spec["order"], "keys": spec["keys"] + ["part"],
            "n_items": len(live), "total_tokens": int(live["n_tokens"].sum()),
            "seconds": round(sum(m["seconds"] for m in mans), 1),
            "devices": {d: int(c) for d, c in keys["device"].value_counts().sort_index().items()},
            "compute_dtypes": {d: t for m in mans for d, t in m["compute_dtypes"].items()},
            "torch_version": merged_field(m["torch_version"] for m in mans),
            "sentence_transformers_version": merged_field(m["sentence_transformers_version"] for m in mans),
            "transformers_version": merged_field(m["transformers_version"] for m in mans),
            "parts": {part: {"input": m["input"], "input_hash": m["input_hash"], "n_items": m["n_items"],
                             "finalized_at": m["finalized_at"]} for part, m in manifests.items()},
            "input": rel(input_path(kind)), "input_hash": content_hash(live, kind),
            "norm_min": round(float(norms.min()), 5), "norm_max": round(float(norms.max()), 5),
            "finalized_at": now(),
        }
        write_final(paths, emb, keys, manifest)
    log.info("Assembled %s from parts %s: %d x %d float16 -> %s", kind, list(manifests), len(live), DIM,
             rel(paths["embeddings"]))
    return manifest


def all_kinds() -> list[str]:
    parts = (sorted(p.name for p in config.EMB_DIR.iterdir() if p.is_dir() and PART_RE.match(p.name))
             if config.EMB_DIR.exists() else [])
    return list(KINDS) + parts


def status() -> None:
    """Print plan, progress and finalize state for each kind and part."""
    for kind in all_kinds():
        print(f"{kind}:")
        path = input_path(kind)
        current_hash = content_hash(load_input(kind), kind) if path.exists() else None
        existing = read_plan(kind)
        if existing is None:
            print(f"  input: {rel(path)} ({'present' if path.exists() else 'missing'}); no plan yet")
            manifest_path = final_paths(kind)["manifest"]
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text())
                match = "matches input" if manifest["input_hash"] == current_hash else "STALE"
                print(f"  assembled: {manifest['finalized_at']} from parts {list(manifest.get('parts', {}))} ({match})")
            continue
        plan, meta = existing
        state = ("missing" if current_hash is None
                 else "unchanged" if current_hash == meta["input_hash"] else "CHANGED since plan")
        print(f"  input: {rel(path)} ({state})")
        print(f"  plan: {meta['n_items']:,} items, {meta['n_tokens']:,} tokens, {meta['n_shards']} shards, "
              f"token budget {meta['token_budget']:,} ({meta['created_at']})")
        done = done_shards(kind, meta["n_shards"])
        in_done = plan["shard"].isin(done)
        failed, seconds = 0, 0.0
        for s in done:
            shard = read_shard(shard_path(kind, s))
            failed += int((shard["device"] == "failed").sum())
            seconds += shard["meta"]["seconds"]
        pct = 100 * in_done.sum() / meta["n_items"] if meta["n_items"] else 100.0
        print(f"  done: {len(done)}/{meta['n_shards']} shards, {in_done.sum():,} items ({pct:.1f}%), "
              f"{plan.loc[in_done, 'n_tokens'].sum():,} tokens in {format_duration(seconds)}"
              + (f", {failed} FAILED item(s)" if failed else ""))
        manifest_path = final_paths(kind)["manifest"]
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            match = "matches plan" if manifest["input_hash"] == meta["input_hash"] else "STALE"
            print(f"  finalized: {manifest['finalized_at']} ({match}), devices {manifest['devices']}")
        else:
            print("  finalized: no")


# ---------------------------------------------------------------------------
# Helpers and CLI
# ---------------------------------------------------------------------------

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def format_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{s:02d}s"


def one_or_list(values):
    unique = sorted(set(values))
    return unique[0] if len(unique) == 1 else unique


def kind_arg(value: str) -> str:
    if value in KINDS or PART_RE.match(value):
        return value
    raise argparse.ArgumentTypeError(f"expected fragments or fragments.<part>, got {value!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="uv run python -m pipeline.embed", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="embed pending shards (resumable)")
    p_run.add_argument("kind", type=kind_arg)
    p_run.add_argument("--limit", type=int, default=None,
                       help="stop after about N items in this invocation (whole shards); re-run to continue")
    p_run.add_argument("--device", choices=["auto", "mps", "cpu"], default="auto")
    p_run.add_argument("--token-budget", type=int, default=None,
                       help=f"max_len x batch_size per forward pass for a new plan (default {DEFAULT_TOKEN_BUDGET})")
    p_fin = sub.add_parser("finalize", help="assemble shards into the final matrix, keys and manifest")
    p_fin.add_argument("kind", type=kind_arg)
    p_snap = sub.add_parser("snapshot", help="freeze some years of the input as the input of a part")
    p_snap.add_argument("kind", type=kind_arg, help="fragments.<part>")
    years = p_snap.add_mutually_exclusive_group(required=True)
    years.add_argument("--years", type=int, nargs="+")
    years.add_argument("--exclude-years", type=int, nargs="+")
    p_asm = sub.add_parser("assemble", help="join finalized parts into the final files of a base kind")
    p_asm.add_argument("kind", choices=KINDS)
    p_asm.add_argument("--parts", nargs="+", required=True)
    sub.add_parser("status", help="show progress for every kind and part")
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            run(args.kind, limit=args.limit, device=args.device, token_budget=args.token_budget)
        elif args.command == "finalize":
            finalize(args.kind)
        elif args.command == "snapshot":
            df = snapshot(args.kind, years=args.years, exclude_years=args.exclude_years)
            print(f"{args.kind}: {len(df):,} rows, {df['n_tokens'].sum():,} tokens, years "
                  f"{df['year'].min()}-{df['year'].max()} ({df['year'].nunique()} years) -> {rel(input_path(args.kind))}")
        elif args.command == "assemble":
            assemble(args.kind, args.parts)
        else:
            status()
    except EmbedError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
