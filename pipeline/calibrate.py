"""Lens calibration, as fixed in docs/calibration.md (docs/PLAN.md, section 4.1).

Commands (from the repo root), in order:
    uv run python -m pipeline.calibrate lens-vectors   # embed each lens's definition (query) and anchors
    uv run python -m pipeline.calibrate scores         # sampling score of every fragment
    uv run python -m pipeline.calibrate sample         # draw the labelled sample, write the labelling batches
    uv run python -m pipeline.calibrate check labels core/b001   # an agent checks its own output file
    uv run python -m pipeline.calibrate checkset       # draw the check set from the core labels
    uv run python -m pipeline.calibrate check labels check/c001
    uv run python -m pipeline.calibrate collect        # agreement of the two labellers; resolver queue
    uv run python -m pipeline.calibrate check resolved r001
    uv run python -m pipeline.calibrate final          # final labels (core, or resolved)
    uv run python -m pipeline.calibrate fit            # one classifier per lens on the training set
    uv run python -m pipeline.calibrate test           # pass bar and share check on the validation set
    uv run python -m pipeline.calibrate fit --final    # the classifiers again, on the training and validation sets
    uv run python -m pipeline.calibrate predict        # probability of every fragment on every lens

Scores need the finalized fragment embeddings (pipeline.embed). The labels are
written by agents into data/gold/labels/<labeller>/<batch>.jsonl and data/gold/resolved/*.jsonl.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.svm import SVC

from pipeline import config, embed
from pipeline.lenses import LENSES_YAML, expand_labels, expand_scores, load_lenses

PERIODS = [(1946, 1969), (1970, 1989), (1990, 2009), (2010, 2024), (2025, 2026)]
SEED = 20260929
TARGET_SIZE = 25000  # about 20,000 to train and tune, about 5,000 to validate (user, 2026-09-29 16:30 UTC)
RANDOM_PER_PERIOD = 500
VALIDATION_SHARE = 0.2  # of the speeches: all their sampled fragments form the validation set
BIN_EDGES = np.array([1 / 100, 1 / 50, 1 / 25, 2 / 25, 4 / 25, 8 / 25])
PER_BIN = 25  # 6 bins x 25 = 150 draws where each lens is most likely, per period
LOWER_PER_STRATUM = 30  # key-term fragments outside the top 8/25, per lens and period
BATCH_SIZE = 150
CORE, CHECKER = "core", "check"  # the core labeller and the check labeller (docs/calibration.md, section 4)
CHECK_PER_GROUP = 30  # per lens: fragments the core labeller marked positive, and near-misses
LOW_CONFIDENCE = 2  # validation fragments the core labeller marked at or below it are read a second time
REVIEW_PER_LENS = 25  # review of codebook 1.4: per lens, half core positives and half near-misses
REVIEW_FILES = 10  # with the reread of codebook 1.4; one check labeller each, five at a time (user, 2026-09-30 02:48 UTC)
KAPPA_BAR = 0.8  # a lens below it goes back to the user
PENALTIES = (0.3, 1.0, 3.0, 10.0)  # C of the RBF support vector machine (user, 2026-09-30, after the comparison)
FOLDS = 5
JOBS = max(1, (os.cpu_count() or 2) - 2)  # fits run in parallel
SVM_CACHE_MB = 300
PASS_BAR = 0.70
MIN_PERIOD_POSITIVES = 20
BOOTSTRAP = 2000

GOLD = config.GOLD
LENS_VECTORS = config.EMB_DIR / "lenses.npz"
SCORES = config.INTERIM / "lens_scores.parquet"
SAMPLE = GOLD / "sample.parquet"
MANIFEST = GOLD / "manifest.json"
BATCHES = GOLD / "batches"
LABELS = GOLD / "labels"
CHECK = GOLD / "check"
CHECKSET = GOLD / "checkset.json"
REREAD = GOLD / "reread.json"  # fragments a codebook revision may change: read again, kept out of the check set
REVIEW = GOLD / "review.json"  # fragments outside the check files, read under codebook 1.4 to see what it changes
REREAD14 = GOLD / "reread14.json"  # fragments codebook 1.4 may change: read again in the review files, or resolved
CHANGES = GOLD / "changes.json"  # how often the final label differs from the core label
AGREEMENT = GOLD / "agreement.json"
RESOLVE = GOLD / "resolve"
RESOLVED = GOLD / "resolved"
FINAL = GOLD / "labels_final.parquet"
FIT = GOLD / "fit.json"
CLASSIFIERS = GOLD / "classifiers.npz"
RESULTS = GOLD / "results.json"
PROBS = config.INTERIM / "lens_probs.parquet"
OOF = config.INTERIM / "lens_oof.parquet"  # out-of-fold probabilities of the last fit (error analysis)
VALIDATION = config.INTERIM / "lens_validation.parquet"  # the test's probabilities (error analysis)
PROTOCOL = config.ROOT / "docs" / "calibration.md"
CODEBOOK = config.LENSES / "codebook.md"


class CalibrationError(Exception):
    """A condition the user must resolve (missing input, invalid records, stale files)."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lens_ids(codebook=None) -> list[str]:
    return [lens["id"] for lens in (codebook or load_lenses())["lenses"]]


def period_of(years) -> np.ndarray:
    """Period index 0-4 of each year (docs/calibration.md, section 1)."""
    years = np.asarray(years)
    out = np.full(len(years), -1, dtype=np.int64)
    for i, (a, b) in enumerate(PERIODS):
        out[(years >= a) & (years <= b)] = i
    if (out < 0).any():
        raise CalibrationError(f"years outside the periods: {sorted(set(years[out < 0]))}")
    return out


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    out = []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise CalibrationError(f"{path}:{n}: not JSON ({exc})") from None
    return out


# ---------------------------------------------------------------------------
# Lens vectors and scores
# ---------------------------------------------------------------------------

def lens_texts(codebook) -> tuple[list[str], list[str], list[int]]:
    """Query texts (instruction + definition, one per lens), anchor texts and each anchor's lens."""
    instruction = codebook["query_instruction"]
    queries = [instruction + " ".join(lens["definition_en"].split()) for lens in codebook["lenses"]]
    anchors, owner = [], []
    for i, lens in enumerate(codebook["lenses"]):
        for text in lens["anchors"]:
            anchors.append(" ".join(text.split()))
            owner.append(i)
    return queries, anchors, owner


def make_lens_vectors(encoder_factory=embed.HarrierEncoder, device: str = "auto") -> dict:
    codebook = load_lenses()
    queries, anchors, owner = lens_texts(codebook)
    encoder = encoder_factory(embed.resolve_device(device))
    # Queries carry the instruction in their text; neither side gets a prompt from the encoder.
    q = embed.encode_checked(encoder, queries)
    a = embed.encode_checked(encoder, anchors)
    info = {"lenses": lens_ids(codebook), "lenses_sha256": sha256(LENSES_YAML),
            "model_revision": encoder.info["model_revision"], "created_at": now()}
    LENS_VECTORS.parent.mkdir(parents=True, exist_ok=True)
    tmp = LENS_VECTORS.with_name(LENS_VECTORS.name + ".tmp")
    with open(tmp, "wb") as f:
        np.savez(f, q=q.astype(np.float32), anchors=a.astype(np.float32),
                 owner=np.asarray(owner, dtype=np.int64), info=np.asarray(json.dumps(info)))
    tmp.replace(LENS_VECTORS)
    return info


def read_lens_vectors() -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    if not LENS_VECTORS.exists():
        raise CalibrationError("No lens vectors; run `uv run python -m pipeline.calibrate lens-vectors`.")
    with np.load(LENS_VECTORS, allow_pickle=False) as z:
        q, a, owner, info = z["q"], z["anchors"], z["owner"], json.loads(str(z["info"]))
    if info["lenses_sha256"] != sha256(LENSES_YAML):
        raise CalibrationError("lenses.yaml changed since the lens vectors were made; make them again.")
    return q, a, owner, info


def item_scores(emb, q, a, owner, chunk: int = 65536) -> tuple[np.ndarray, np.ndarray]:
    """D (cosine to each lens query) and A (best cosine to each lens's anchors) of every row."""
    n, n_lenses = len(emb), len(q)
    d = np.empty((n, n_lenses), dtype=np.float32)
    best = np.empty((n, n_lenses), dtype=np.float32)
    for start in range(0, n, chunk):
        x = np.asarray(emb[start:start + chunk], dtype=np.float32)
        d[start:start + chunk] = x @ q.T
        sims = x @ a.T
        for lens in range(n_lenses):
            best[start:start + chunk, lens] = sims[:, owner == lens].max(axis=1)
    return d, best


def load_embeddings(kind: str) -> tuple[np.ndarray, pd.DataFrame, dict]:
    paths = embed.final_paths(kind)
    if not paths["manifest"].exists():
        raise CalibrationError(f"No finalized {kind} embeddings; run pipeline.embed first.")
    manifest = json.loads(paths["manifest"].read_text())
    current = embed.content_hash(embed.load_input(kind), kind)
    if current != manifest["input_hash"]:
        raise CalibrationError(f"{embed.rel(embed.input_path(kind))} changed since the {kind} "
                               "embeddings were made; embed again.")
    return np.load(paths["embeddings"], mmap_mode="r"), pd.read_parquet(paths["keys"]), manifest


def compute_scores() -> pd.DataFrame:
    """Every fragment's sampling score s per lens (docs/calibration.md, section 2)."""
    q, a, owner, info = read_lens_vectors()
    ids = info["lenses"]
    f_emb, f_keys, f_man = load_embeddings("fragments")
    if f_man["model_revision"] != info["model_revision"]:
        raise CalibrationError(f"Different model revisions: {f_man['model_revision']} (fragments), "
                               f"{info['model_revision']} (lenses).")
    d_score, a_score = item_scores(f_emb, q, a, owner)
    frags = pd.read_parquet(config.FRAGMENTS, columns=["frag_id", "year", "is_ceremonial"])
    frags = frags.set_index("frag_id").loc[f_keys["frag_id"]]
    pop = ~frags["is_ceremonial"].to_numpy()
    z = lambda x: (x - x[pop].mean(axis=0)) / x[pop].std(axis=0)  # noqa: E731
    s_score = (z(d_score) + z(a_score)) / 2

    out = pd.DataFrame({"frag_id": f_keys["frag_id"].to_numpy(), "year": frags["year"].to_numpy(),
                        "is_ceremonial": frags["is_ceremonial"].to_numpy()})
    for i, lens in enumerate(ids):
        out[f"s_{lens}"] = s_score[:, i]
    out = out.sort_values("frag_id").reset_index(drop=True)
    tmp = SCORES.with_name(SCORES.name + ".tmp")
    out.to_parquet(tmp, index=False)
    tmp.replace(SCORES)
    write_json(SCORES.with_suffix(".json"), {"input_hash": f_man.get("input_hash"), "made_at": now()})
    return out


# ---------------------------------------------------------------------------
# Sample
# ---------------------------------------------------------------------------

def term_pattern(terms: list[str]) -> re.Pattern:
    """One case-insensitive pattern for a list of terms, qualifiers in parentheses removed."""
    parts = []
    for term in terms:
        term = re.sub(r"\s*\([^)]*\)", "", term).strip()
        if term:
            parts.append((r"\b" if term[0].isalnum() else "") + re.escape(term)
                         + (r"\b" if term[-1].isalnum() else ""))
    return re.compile("|".join(sorted(parts, key=len, reverse=True)), re.I)


def within_period_rank(scores: np.ndarray, period: np.ndarray, frag_id: np.ndarray) -> np.ndarray:
    """q = rank / N_p, highest score first; ties are broken by frag_id."""
    q = np.empty(len(scores))
    for p in np.unique(period):
        idx = np.flatnonzero(period == p)
        order = idx[np.lexsort((frag_id[idx], -scores[idx]))]
        q[order] = np.arange(1, len(idx) + 1) / len(idx)
    return q


def bin_rates(q: np.ndarray, period: np.ndarray) -> np.ndarray:
    """PER_BIN / (fragments of the same period and rank bin); 0 outside the top 8/25."""
    b = np.searchsorted(BIN_EDGES, q, side="left")
    rate = np.zeros(len(q))
    inside = b < len(BIN_EDGES)
    keys = period[inside] * 16 + b[inside]
    counts = pd.Series(keys).value_counts()
    rate[inside] = PER_BIN / counts.reindex(keys).to_numpy()
    return rate


def lower_rates(hits: np.ndarray, q: np.ndarray, period: np.ndarray) -> np.ndarray:
    """LOWER_PER_STRATUM / |K_Lp| for the key-term fragments outside the top 8/25 of their period."""
    rate = np.zeros(len(q))
    pool = hits & (q > BIN_EDGES[-1])
    for p in np.unique(period[pool]):
        idx = pool & (period == p)
        rate[idx] = LOWER_PER_STRATUM / idx.sum()
    return rate


def solve_lambda(base: np.ndarray, planned: np.ndarray, target: float) -> float:
    """λ such that sum(1 - (1 - base) * prod(1 - min(1, λ planned))) equals target (bisection)."""
    def expected(lam):
        return float((1 - (1 - base) * np.prod(1 - np.minimum(1.0, lam * planned), axis=1)).sum())

    positive = planned[planned > 0]
    top = 1.0 / positive.min() if positive.size else 0.0  # every stratum drawn in full
    if expected(0.0) >= target:
        raise CalibrationError("the random part alone reaches the target size")
    if expected(top) < target:
        raise CalibrationError("the target size cannot be reached")
    lo, hi = 0.0, top
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if expected(mid) < target else (lo, mid)
    return (lo + hi) / 2


def inclusion_probabilities(frags: pd.DataFrame, scores: pd.DataFrame, codebook) -> tuple[pd.DataFrame, float]:
    """π of every fragment of U and of each part (docs/calibration.md, section 3)."""
    frag_id = frags["frag_id"].to_numpy()
    period = period_of(frags["year"].to_numpy())
    n_p = np.bincount(period, minlength=len(PERIODS))
    s = scores.set_index("frag_id").loc[frag_id]
    text = frags["text"]

    pi_r = np.minimum(1.0, RANDOM_PER_PERIOD / n_p[period])
    planned = np.zeros((len(frags), len(codebook["lenses"])))
    for i, lens in enumerate(codebook["lenses"]):
        q = within_period_rank(s[f"s_{lens['id']}"].to_numpy(), period, frag_id)
        hits = text.str.contains(term_pattern(lens["era_terms"])).to_numpy()
        planned[:, i] = bin_rates(q, period) + lower_rates(hits, q, period)
    lam = solve_lambda(pi_r, planned, TARGET_SIZE)
    pi_s = 1 - np.prod(1 - np.minimum(1.0, lam * planned), axis=1)
    pi = 1 - (1 - pi_r) * (1 - pi_s)
    out = pd.DataFrame({"frag_id": frag_id, "year": frags["year"].to_numpy(), "period": period,
                        "pi": pi, "pi_R": pi_r, "pi_S": pi_s})
    return out, lam


def draw_sample(force: bool = False) -> pd.DataFrame:
    """Draw the sample, split it by speech into a training and a validation set, and write the labelling
    batches: the validation set first, so that it is complete even if the training set is cut short."""
    if SAMPLE.exists() and not force:
        raise CalibrationError(f"{SAMPLE} exists; the sample is drawn once (use --force to redraw "
                               "before any label is written).")
    if LABELS.exists() and any(LABELS.rglob("*.jsonl")):
        raise CalibrationError("labels exist; the sample cannot be redrawn.")
    codebook = load_lenses()
    frags = pd.read_parquet(config.FRAGMENTS, columns=["frag_id", "speech_id", "year", "text",
                                                       "is_ceremonial"])
    frags = frags[~frags["is_ceremonial"]].sort_values("frag_id").reset_index(drop=True)
    if not SCORES.exists():
        raise CalibrationError("No scores; run `uv run python -m pipeline.calibrate scores`.")
    scores = pd.read_parquet(SCORES)
    probs, lam = inclusion_probabilities(frags, scores, codebook)

    rng = np.random.default_rng(SEED)
    chosen = rng.random(len(probs)) < probs["pi"].to_numpy()
    sample = probs[chosen].reset_index(drop=True)
    sample["speech_id"] = frags.set_index("frag_id").loc[sample["frag_id"], "speech_id"].to_numpy()
    speeches = np.unique(sample["speech_id"])
    held = speeches[np.random.default_rng(SEED + 1).random(len(speeches)) < VALIDATION_SHARE]
    sample["split"] = np.where(sample["speech_id"].isin(held), "validation", "train")
    rng = np.random.default_rng(SEED + 2)
    sample["gid"] = [f"g{i + 1:05d}" for i in rng.permutation(len(sample))]
    sample["batch"] = ""
    order, b = [], 0
    for split in ("validation", "train"):
        rows = rng.permutation(np.flatnonzero(sample["split"].to_numpy() == split))
        for part in np.array_split(rows, int(np.ceil(len(rows) / BATCH_SIZE))):
            b += 1
            sample.loc[part, "batch"] = f"b{b:03d}"
            order += part.tolist()
    n_batches = b

    text = frags.set_index("frag_id")["text"]
    for batch, rows in sample.loc[order].groupby("batch", sort=True):
        write_jsonl(BATCHES / f"{batch}.jsonl",
                    [{"frag_id": r.gid, "year": int(r.year), "text": text[r.frag_id]}
                     for r in rows.itertuples()])
    GOLD.mkdir(parents=True, exist_ok=True)
    sample.to_parquet(SAMPLE, index=False)
    write_json(MANIFEST, {
        "created_at": now(), "protocol_sha256": sha256(PROTOCOL), "codebook_sha256": sha256(CODEBOOK),
        "lenses_sha256": sha256(LENSES_YAML), "fragments_hash": embed.content_hash(
            embed.load_input("fragments"), "fragments"),
        "seed": SEED, "lambda": lam, "population": len(probs),
        "expected_size": float(probs["pi"].sum()), "drawn": len(sample),
        "per_period": {f"{a}-{b}": int((sample["period"] == i).sum()) for i, (a, b) in enumerate(PERIODS)},
        "splits": sample["split"].value_counts().to_dict(), "validation_speeches": len(held),
        "validation_batches": sorted(sample.loc[sample["split"] == "validation", "batch"].unique().tolist()),
        "batches": n_batches,
    })
    return sample


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

def check_record(rec: dict, ids: list[str], codebook) -> tuple[dict, list[str]]:
    """Validate one codebook record (section 9); return its umbrella-expanded mention types and problems."""
    problems = []
    if set(rec) != {"frag_id", "lenses", "mention_type", "confidence", "note"}:
        problems.append(f"fields {sorted(rec)}")
    lenses, types = rec.get("lenses", []), rec.get("mention_type", {})
    if not isinstance(lenses, list) or not isinstance(types, dict):
        return {}, problems + ["lenses must be a list and mention_type an object"]
    if [x for x in ids if x in lenses] != lenses:
        problems.append(f"lenses not known, repeated or out of order: {lenses}")
    if set(types) != set(lenses):
        problems.append("mention_type keys differ from lenses")
    if any(v not in ("substantive", "list") for v in types.values()):
        problems.append(f"mention types {sorted(set(types.values()))}")
    if rec.get("confidence") not in (1, 2, 3):
        problems.append(f"confidence {rec.get('confidence')!r}")
    if not isinstance(rec.get("note"), str):
        problems.append("note must be a string")
    clean = {k: v for k, v in types.items() if k in ids and v in ("substantive", "list")}
    return expand_labels(clean, codebook), problems


def input_dir(labeller: str) -> Path:
    """Where a labeller's input files are: the sample's batches for the core labeller, the check set's for the
    check labeller."""
    if labeller not in (CORE, CHECKER):
        raise CalibrationError(f"unknown labeller {labeller!r}; the labellers are {CORE} and {CHECKER}")
    return CHECK if labeller == CHECKER else BATCHES


def read_labeller(labeller: str, ids: list[str], codebook) -> tuple[dict, dict]:
    """({gid: expanded mention types}, {gid: record}) for one labeller over all its input files; raises on
    missing or invalid records."""
    out, raw, problems = {}, {}, []
    inputs = sorted(input_dir(labeller).glob("*.jsonl"))
    if not inputs:
        raise CalibrationError(f"no input files for labeller {labeller}")
    for src in inputs:
        path = LABELS / labeller / src.name
        if not path.exists():
            problems.append(f"{labeller}/{src.stem}: missing")
            continue
        expected = {r["frag_id"] for r in read_jsonl(src)}
        seen = set()
        for rec in read_jsonl(path):
            gid = rec.get("frag_id")
            if gid not in expected or gid in seen:
                problems.append(f"{labeller}/{src.stem}: unexpected or repeated id {gid!r}")
                continue
            seen.add(gid)
            types, bad = check_record(rec, ids, codebook)
            problems += [f"{labeller}/{src.stem}/{gid}: {p}" for p in bad]
            out[gid], raw[gid] = types, rec
        if expected - seen:
            problems.append(f"{labeller}/{src.stem}: {len(expected - seen)} id(s) without a record")
    if problems:
        raise CalibrationError("\n".join(problems[:50]) + (f"\n... {len(problems) - 50} more"
                                                           if len(problems) > 50 else ""))
    return out, raw


def check_file(kind: str, name: str) -> list[str]:
    """Problems in one output file: a labeller's batch ("labels", "core/b001" or "check/c001") or a
    resolver's file ("resolved", "r001"). Records must follow their input file, one per line, in order."""
    if kind == "labels":
        labeller, batch = name.split("/")
        if labeller not in (CORE, CHECKER):
            return [f"unknown labeller {labeller!r}; the labellers are {CORE} and {CHECKER}"]
        src, out = input_dir(labeller) / f"{batch}.jsonl", LABELS / labeller / f"{batch}.jsonl"
    else:
        src, out = RESOLVE / f"{name}.jsonl", RESOLVED / f"{name}.jsonl"
    if not out.exists():
        return [f"{out} not found"]
    inputs, problems = read_jsonl(src), []
    try:
        records = read_jsonl(out)
    except CalibrationError as exc:
        return [str(exc)]
    if [r.get("frag_id") for r in records] != [r["frag_id"] for r in inputs]:
        problems.append(f"the frag_id sequence differs from {src.name} ({len(records)} records "
                        f"for {len(inputs)} inputs)")
    codebook = load_lenses()
    ids = lens_ids(codebook)
    for rec, inp in zip(records, inputs):
        if kind == "labels":
            problems += [f"{rec.get('frag_id')}: {p}" for p in check_record(rec, ids, codebook)[1]]
        else:
            dec = rec.get("decisions")
            if set(rec) != {"frag_id", "decisions", "note"} or not isinstance(rec.get("note"), str):
                problems.append(f"{rec.get('frag_id')}: fields must be frag_id, decisions, note")
            if not isinstance(dec, dict) or set(dec) != set(inp["lenses"]) or any(
                    v not in ("substantive", "list", "none") for v in dec.values()):
                problems.append(f"{rec.get('frag_id')}: decisions must cover exactly "
                                f"{inp['lenses']} with substantive, list or none")
    return problems


def cohen_kappa(a, b) -> float | None:
    """Cohen's kappa of two raters' binary labels; None when chance agreement is total."""
    a, b = np.asarray(a, dtype=bool), np.asarray(b, dtype=bool)
    pe = a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean())
    return float(((a == b).mean() - pe) / (1 - pe)) if pe < 1 else None


def draw_checkset(force: bool = False) -> dict:
    """The check set (docs/calibration.md, section 4): for each lens, 30 fragments the core labeller marked
    positive and 30 near-misses, fragments it marked negative whose score is at least the median score of its
    positives; each group drawn at random among the fragments not listed in REREAD, or taken whole when smaller.
    The second reading adds every validation fragment the core labeller marked at confidence 2 or less, every
    fragment at confidence 1 and every fragment listed in REREAD. Both are written together in random order to
    files of up to 150 fragments."""
    if (LABELS / CHECKER).exists() and any((LABELS / CHECKER).glob("*.jsonl")):
        raise CalibrationError("check labels exist; the check set cannot be redrawn.")
    if CHECKSET.exists() and not force:
        raise CalibrationError(f"{CHECKSET} exists; the check set is drawn once (use --force to redraw before "
                               "any check label is written).")
    codebook = load_lenses()
    ids = lens_ids(codebook)
    core, core_raw = read_labeller(CORE, ids, codebook)
    sample = pd.read_parquet(SAMPLE).sort_values("gid").reset_index(drop=True)
    missing = set(sample["gid"]) - set(core)
    if missing:
        raise CalibrationError(f"{len(missing)} sampled fragment(s) have no core label")
    reread = set(json.loads(REREAD.read_text())["fragments"]) if REREAD.exists() else set()
    if reread - set(sample["gid"]):
        raise CalibrationError(f"{len(reread - set(sample['gid']))} fragment(s) of {REREAD.name} are not sampled")
    scores = pd.read_parquet(SCORES).set_index("frag_id").loc[sample["frag_id"]]
    gids = sample["gid"].to_numpy()
    drawable = ~np.isin(gids, sorted(reread))
    rng = np.random.default_rng(SEED + 3)
    lenses, chosen = {}, set()
    for lens in ids:
        y = np.array([core[g].get(lens) == "substantive" for g in gids], dtype=bool)
        s = scores[f"s_{lens}"].to_numpy()
        near = ~y & (s >= np.median(s[y])) if y.any() else np.zeros(len(y), dtype=bool)
        groups = {}
        for name, mask in (("positives", y), ("near_misses", near)):
            pool = gids[mask & drawable]
            pick = pool if len(pool) <= CHECK_PER_GROUP else rng.choice(pool, CHECK_PER_GROUP, replace=False)
            groups[name] = sorted(str(g) for g in pick)
            groups[f"{name}_available"] = int(len(pool))
        lenses[lens] = groups
        chosen.update(groups["positives"] + groups["near_misses"])
    confidence = {str(g): core_raw[g]["confidence"] for g in gids}
    validation = set(sample.loc[sample["split"] == "validation", "gid"])
    second = {"validation_low_confidence": sorted(g for g in validation if confidence[g] <= LOW_CONFIDENCE),
              "confidence_1": sorted(g for g, c in confidence.items() if c == 1),
              "reread": sorted(reread)}
    second_all = set().union(*second.values())
    text = {r["frag_id"]: r for p in sorted(BATCHES.glob("*.jsonl")) for r in read_jsonl(p)}
    order = [str(g) for g in rng.permutation(sorted(chosen | second_all))]
    if CHECK.exists():
        for old in CHECK.glob("*.jsonl"):
            old.unlink()
    files = {}
    for i, part in enumerate(np.array_split(np.arange(len(order)), int(np.ceil(len(order) / BATCH_SIZE))), 1):
        write_jsonl(CHECK / f"c{i:03d}.jsonl", [{"frag_id": order[k], "year": text[order[k]]["year"],
                                                  "text": text[order[k]]["text"]} for k in part])
        files[f"c{i:03d}"] = len(part)
    out = {"drawn_at": now(), "seed": SEED + 3, "per_group": CHECK_PER_GROUP, "fragments": len(order),
           "files": files, "lenses": lenses,
           "second_reading": {**{k: len(v) for k, v in second.items()}, "also_in_check_set": len(second_all & chosen),
                              "fragments": sorted(second_all)}}
    write_json(CHECKSET, out)
    return out


def checked(cs: dict) -> set[str]:
    """The fragments of the check files drawn with the check set: the check set and the second reading."""
    return set(cs["second_reading"]["fragments"]).union(
        *(v["positives"] + v["near_misses"] for v in cs["lenses"].values()))


def reread14() -> dict:
    """{gid: lenses} of the fragments codebook 1.4 may change (REREAD14), or {} before the list exists."""
    if not REREAD14.exists():
        return {}
    return {g: v["lenses"] for g, v in json.loads(REREAD14.read_text())["fragments"].items()}


def draw_review(force: bool = False) -> dict:
    """The review of codebook 1.4 (docs/calibration.md, section 4): for each lens, REVIEW_PER_LENS fragments outside
    the check files, half that the core labeller marked positive and half near-misses (as in the check set), drawn at
    random, each fragment once; when one group is short it is taken whole and the other fills the lens's share, and
    what the lenses cannot fill is drawn among the positives and near-misses left over from all lenses. They
    are written in random order to REVIEW_FILES more check files and read like the second reading: outside the
    agreement, every disagreement to the resolver. The fragments of REREAD14 outside the check files join them; those
    fragments are not drawn for the review, which measures what codebook 1.4 changes elsewhere."""
    if not CHECKSET.exists():
        raise CalibrationError("No check set; run `uv run python -m pipeline.calibrate checkset`.")
    cs = json.loads(CHECKSET.read_text())
    if REVIEW.exists():
        old = json.loads(REVIEW.read_text())
        if any((LABELS / CHECKER / f"{name}.jsonl").exists() for name in old["files"]):
            raise CalibrationError("review labels exist; the review cannot be redrawn.")
        if not force:
            raise CalibrationError(f"{REVIEW} exists; the review is drawn once (use --force to redraw before any "
                                   "review label is written).")
        for name in old["files"]:
            (CHECK / f"{name}.jsonl").unlink(missing_ok=True)
    codebook = load_lenses()
    ids = lens_ids(codebook)
    core, _ = read_labeller(CORE, ids, codebook)
    sample = pd.read_parquet(SAMPLE).sort_values("gid").reset_index(drop=True)
    scores = pd.read_parquet(SCORES).set_index("frag_id").loc[sample["frag_id"]]
    gids = sample["gid"].to_numpy()
    read, affected = checked(cs), set(reread14())
    if affected - set(gids):
        raise CalibrationError(f"{len(affected - set(gids))} fragment(s) of {REREAD14.name} are not sampled")
    reread = sorted(affected - read)
    rng = np.random.default_rng(SEED + 5)
    lenses, chosen, spare = {}, set(), set()
    for lens in ids:
        y = np.array([core[g].get(lens) == "substantive" for g in gids], dtype=bool)
        s = scores[f"s_{lens}"].to_numpy()
        near = ~y & (s >= np.median(s[y])) if y.any() else np.zeros(len(y), dtype=bool)
        free = ~np.isin(gids, sorted(read | affected | chosen))
        pools = {"positives": gids[y & free], "near_misses": gids[near & free]}
        spare.update(str(g) for pool in pools.values() for g in pool)
        want = {"positives": -(-REVIEW_PER_LENS // 2), "near_misses": REVIEW_PER_LENS // 2}
        want = {"positives": want["positives"] + max(0, want["near_misses"] - len(pools["near_misses"])),
                "near_misses": want["near_misses"] + max(0, want["positives"] - len(pools["positives"]))}
        groups = {}
        for name, pool in pools.items():
            pick = pool if len(pool) <= want[name] else rng.choice(pool, want[name], replace=False)
            groups[name] = sorted(str(g) for g in pick)
            groups[f"{name}_available"] = int(len(pool))
        lenses[lens] = groups
        chosen.update(groups["positives"] + groups["near_misses"])
    spare, short = sorted(spare - chosen), REVIEW_PER_LENS * len(ids) - len(chosen)
    fill = sorted(str(g) for g in rng.choice(spare, min(short, len(spare)), replace=False)) if short > 0 else []
    chosen.update(fill)
    text = {r["frag_id"]: r for p in sorted(BATCHES.glob("*.jsonl")) for r in read_jsonl(p)}
    order = [str(g) for g in rng.permutation(sorted(chosen | set(reread)))]
    files = {}
    for i, part in enumerate(np.array_split(np.arange(len(order)), REVIEW_FILES), len(cs["files"]) + 1):
        write_jsonl(CHECK / f"c{i:03d}.jsonl", [{"frag_id": order[k], "year": text[order[k]]["year"],
                                                  "text": text[order[k]]["text"]} for k in part])
        files[f"c{i:03d}"] = len(part)
    out = {"drawn_at": now(), "seed": SEED + 5, "per_lens": REVIEW_PER_LENS, "fragments": len(order),
           "files": files, "lenses": lenses, "fill": fill, "frag_ids": sorted(chosen), "reread": reread,
           "reread_in_check_files": len(affected & read)}
    write_json(REVIEW, out)
    return out


def collect() -> dict:
    """Agreement of the two labellers on the check set (docs/calibration.md, section 4), and the resolver queue:
    every pair (fragment, lens) of the check set, the second reading or the review on which they differ about
    `substantive`, and every pair that REREAD14 lists for a fragment of the check files, read before codebook 1.4."""
    codebook = load_lenses()
    ids = lens_ids(codebook)
    if not CHECKSET.exists():
        raise CalibrationError("No check set; run `uv run python -m pipeline.calibrate checkset`.")
    cs = json.loads(CHECKSET.read_text())
    core, core_raw = read_labeller(CORE, ids, codebook)
    check, check_raw = read_labeller(CHECKER, ids, codebook)
    agreement = {}
    for lens in ids:
        pos, near = cs["lenses"][lens]["positives"], cs["lenses"][lens]["near_misses"]
        a = np.array([core[g].get(lens) == "substantive" for g in pos + near], dtype=bool)
        b = np.array([check[g].get(lens) == "substantive" for g in pos + near], dtype=bool)
        k = cohen_kappa(a, b) if len(a) else None
        agreement[lens] = {"kappa": None if k is None else round(k, 3), "checked": len(a),
                           "positives_confirmed": round(float(b[:len(pos)].mean()), 3) if pos else None,
                           "near_misses_confirmed": round(float(1 - b[len(pos):].mean()), 3) if near else None}
    read = checked(cs)
    forced = {g: lenses for g, lenses in reread14().items() if g in read}
    queue = {}
    for g in sorted(check):
        diff = [lens for lens in ids if lens in forced.get(g, [])
                or (core[g].get(lens) == "substantive") != (check[g].get(lens) == "substantive")]
        if diff:
            queue[g] = diff
    text = {r["frag_id"]: r for p in sorted(CHECK.glob("*.jsonl")) for r in read_jsonl(p)}
    rng = np.random.default_rng(SEED + 4)  # the resolver is not told which record is which
    rows = []
    for g, lenses in queue.items():
        records = [core_raw[g], check_raw[g]]
        if rng.random() < 0.5:
            records.reverse()
        rows.append({"frag_id": g, "year": text[g]["year"], "text": text[g]["text"], "lenses": lenses,
                     "records": records})
    if RESOLVE.exists():
        for old in RESOLVE.glob("r*.jsonl"):
            old.unlink()
    n_files = int(np.ceil(len(rows) / BATCH_SIZE)) if rows else 0
    for i, part in enumerate(np.array_split(np.arange(len(rows)), n_files) if n_files else [], 1):
        write_jsonl(RESOLVE / f"r{i:03d}.jsonl", [rows[k] for k in part])
    second = set(cs.get("second_reading", {}).get("fragments", []))
    rv = json.loads(REVIEW.read_text()) if REVIEW.exists() else {}
    review, reread = set(rv.get("frag_ids", [])), set(rv.get("reread", []))
    summary = {"checked_at": now(), "check_fragments": len(check), "to_resolve": len(rows),
               "second_reading": len(second), "second_reading_to_resolve": len(second & set(queue)),
               "review": len(review), "review_to_resolve": len(review & set(queue)),
               "reread14": len(reread), "reread14_to_resolve": len(reread & set(queue)),
               "reread14_in_check_files": len(forced), "reread14_pairs_forced": sum(map(len, forced.values())),
               "resolve_files": n_files, "kappa_bar": KAPPA_BAR,
               "below_bar": [lens for lens, v in agreement.items() if v["kappa"] is None or v["kappa"] < KAPPA_BAR],
               "agreement": agreement}
    write_json(AGREEMENT, summary)
    return summary


def final_labels() -> pd.DataFrame:
    """Final label per fragment and lens: the core label, or the resolver's decision where the two labellers
    differed (docs/calibration.md, section 4)."""
    codebook = load_lenses()
    ids = lens_ids(codebook)
    if not AGREEMENT.exists():
        raise CalibrationError("No agreement report; run the check and `uv run python -m pipeline.calibrate collect`.")
    sample = pd.read_parquet(SAMPLE)
    core, _ = read_labeller(CORE, ids, codebook)
    queue = {r["frag_id"]: r["lenses"] for p in sorted(RESOLVE.glob("r*.jsonl")) for r in read_jsonl(p)}
    resolved, problems = {}, []
    for path in sorted(RESOLVED.glob("r*.jsonl")) if RESOLVED.exists() else []:
        for rec in read_jsonl(path):
            g, dec = rec.get("frag_id"), rec.get("decisions", {})
            if g not in queue or g in resolved:
                problems.append(f"{path.name}: unexpected or repeated id {g!r}")
            elif set(dec) != set(queue[g]) or any(v not in ("substantive", "list", "none")
                                                  for v in dec.values()):
                problems.append(f"{path.name}/{g}: decisions must cover exactly {queue[g]} "
                                "with substantive, list or none")
            else:
                resolved[g] = dec
    missing = sorted(set(queue) - set(resolved))
    if missing:
        problems.append(f"{len(missing)} queued fragment(s) not resolved: {missing[:5]}")
    if problems:
        raise CalibrationError("\n".join(problems[:50]))
    rows = []
    for g in sample["gid"]:
        types = dict(core[g])
        for lens in queue.get(g, []):
            if resolved[g][lens] == "none":
                types.pop(lens, None)
            else:
                types[lens] = resolved[g][lens]
        types = expand_labels(types, codebook)
        rows.append({"gid": g, **{lens: types.get(lens) == "substantive" for lens in ids}})
    final = sample[["gid", "frag_id", "speech_id", "year", "period", "split", "pi"]].merge(pd.DataFrame(rows),
                                                                                          on="gid")
    final.to_parquet(FINAL, index=False)
    return final


def changes(final: pd.DataFrame) -> dict:
    """How often the final label differs from the core label on some lens (docs/calibration.md, section 4): over the
    doubtful validation fragments of the second reading, all of them and those outside the reread lists (whose rules
    changed), over the review of codebook 1.4 and over REREAD14; with the pairs (fragment, lens) added and removed."""
    codebook = load_lenses()
    ids = lens_ids(codebook)
    core, core_raw = read_labeller(CORE, ids, codebook)
    rows = final.set_index("gid")
    doubtful = {g for g in rows.index[rows["split"] == "validation"] if core_raw[g]["confidence"] <= LOW_CONFIDENCE}
    rereads = set(json.loads(REREAD.read_text())["fragments"]) if REREAD.exists() else set()
    rereads |= set(reread14())
    rv = json.loads(REVIEW.read_text()) if REVIEW.exists() else {}
    groups = {"second_reading_doubtful": doubtful, "second_reading_doubtful_outside_rereads": doubtful - rereads,
              "review": set(rv.get("frag_ids", [])), "reread14": set(reread14())}
    out = {"made_at": now()}
    for name, gids in groups.items():
        added = removed = changed = 0
        for g in gids:
            a = sum(bool(rows.at[g, lens]) and core[g].get(lens) != "substantive" for lens in ids)
            r = sum(not rows.at[g, lens] and core[g].get(lens) == "substantive" for lens in ids)
            added, removed, changed = added + a, removed + r, changed + bool(a or r)
        out[name] = {"fragments": len(gids), "changed": changed,
                     "share": round(changed / len(gids), 3) if gids else None,
                     "pairs_added": int(added), "pairs_removed": int(removed)}
    write_json(CHANGES, out)
    return out


# ---------------------------------------------------------------------------
# Classifiers, test and probabilities
# ---------------------------------------------------------------------------

def rates(d: np.ndarray, y: np.ndarray, w: np.ndarray) -> dict:
    tp, fp, fn = (w * d * y).sum(), (w * d * ~y).sum(), (w * ~d * y).sum()
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": float(p), "recall": float(r), "f1": float(f1)}


def fragment_vectors(frag_ids) -> np.ndarray:
    """The finalized embeddings of the given fragments, in that order."""
    emb, keys, _ = load_embeddings("fragments")
    row = pd.Series(np.arange(len(keys)), index=keys["frag_id"].to_numpy()).reindex(frag_ids)
    if row.isna().any():
        raise CalibrationError(f"{int(row.isna().sum())} fragment(s) without an embedding")
    return np.asarray(emb[row.to_numpy().astype(np.int64)], dtype=np.float32)


def fitted_ids(codebook=None) -> list[str]:
    """The lenses with a classifier: all but the reference lens, which is labelled but not measured (docs/calibration.md,
    section 5)."""
    return [lens["id"] for lens in (codebook or load_lenses())["lenses"] if not lens["reference"]]


def svm(c: float) -> SVC:
    return SVC(C=c, kernel="rbf", gamma="scale", cache_size=SVM_CACHE_MB)


def fold_scores(x: np.ndarray, y: np.ndarray, tr: np.ndarray, va: np.ndarray, c: float) -> np.ndarray:
    return svm(c).fit(x[tr], y[tr]).decision_function(x[va])


def final_svm(x: np.ndarray, y: np.ndarray, c: float) -> tuple:
    m = svm(c).fit(x, y)
    return m.support_, m.dual_coef_[0].copy(), float(m.intercept_[0]), float(m._gamma)


def best_threshold(p: np.ndarray, y: np.ndarray, w: np.ndarray) -> float:
    """The probability from which a fragment is about the lens: the one with the highest weighted F1."""
    order = np.argsort(-p, kind="stable")
    ps, ys, ws = p[order], y[order].astype(bool), w[order]
    tp, fp = np.cumsum(ws * ys), np.cumsum(ws * ~ys)
    f1 = 2 * tp / (tp + fp + tp[-1])
    last = np.r_[ps[1:] != ps[:-1], True]  # a threshold takes every fragment tied at it
    return float(ps[np.argmax(np.where(last, f1, -1.0))])


def fit(final: bool = False) -> dict:
    """One classifier per lens (docs/calibration.md, section 5), on the training set, or with `final` on the training
    and validation sets together once the test has run (section 7). For each lens, C by five-fold cross-validated
    weighted average precision with the folds split by speech, a weighted Platt calibration of the out-of-fold scores,
    and the threshold with the best weighted F1 of the calibrated out-of-fold probabilities, after the umbrella rule."""
    codebook = load_lenses()
    every, ids = lens_ids(codebook), fitted_ids(codebook)
    sets = ["train", "validation"] if final else ["train"]
    if final and not RESULTS.exists():
        raise CalibrationError("Run `test` before fitting on the validation set.")
    labels = pd.read_parquet(FINAL)
    dev = labels[labels["split"].isin(sets)].reset_index(drop=True)
    x = fragment_vectors(dev["frag_id"].to_numpy())
    mean, std = x.mean(axis=0), x.std(axis=0)
    std[std == 0] = 1.0
    xs = ((x - mean) / std).astype(np.float32)
    w = 1 / dev["pi"].to_numpy()
    y = {lens: dev[lens].to_numpy().astype(int) for lens in ids}
    for lens in ids:
        if min(y[lens].sum(), len(dev) - y[lens].sum()) < FOLDS:
            raise CalibrationError(f"{lens}: {int(y[lens].sum())} positive fragment(s); at least {FOLDS} of each "
                                   "class are needed")
    # each lens's folds are seeded by its place among all the lenses, as before the reference lens was left out
    speech = dev["speech_id"].to_numpy()
    splits = {lens: list(StratifiedGroupKFold(FOLDS, shuffle=True, random_state=SEED + 10 + every.index(lens))
                         .split(xs, y[lens], speech)) for lens in ids}
    tasks = sorted(((lens, c, tr, va) for lens in ids for c in PENALTIES for tr, va in splits[lens]),
                   key=lambda t: -int(y[t[0]].sum()))  # the slowest fits first
    scores = Parallel(n_jobs=JOBS)(delayed(fold_scores)(xs, y[lens], tr, va, c) for lens, c, tr, va in tasks)
    oof = {(lens, c): np.empty(len(dev)) for lens in ids for c in PENALTIES}
    for (lens, c, _, va), sc in zip(tasks, scores):
        oof[lens, c][va] = sc
    ap = {lens: {c: float(average_precision_score(y[lens], oof[lens, c], sample_weight=w)) for c in PENALTIES}
          for lens in ids}
    chosen = {lens: max(PENALTIES, key=ap[lens].get) for lens in ids}
    platt, raw = {}, {}
    for lens in ids:
        sc = oof[lens, chosen[lens]]
        m = LogisticRegression(C=np.inf, max_iter=5000).fit(sc[:, None], y[lens], sample_weight=w)
        platt[lens] = (float(m.coef_[0, 0]), float(m.intercept_[0]))
        raw[lens] = 1 / (1 + np.exp(-(platt[lens][0] * sc + platt[lens][1])))
    p = expand_scores(raw, codebook)
    thr = {lens: best_threshold(p[lens], y[lens], w) for lens in ids}
    fits = dict(zip(ids, Parallel(n_jobs=JOBS)(delayed(final_svm)(xs, y[lens], chosen[lens]) for lens in ids)))
    gammas = {fits[lens][3] for lens in ids}
    if len(gammas) != 1:
        raise CalibrationError("The lenses were fitted with different kernel widths.")
    info = {"method": "svm_rbf", "lenses": ids, "sets": sets, "lenses_sha256": sha256(LENSES_YAML),
            "fitted_at": now(), "fragments": len(dev),
            "fragments_hash": embed.content_hash(embed.load_input("fragments"), "fragments")}
    frag = dev["frag_id"].to_numpy()
    CLASSIFIERS.parent.mkdir(parents=True, exist_ok=True)
    tmp = CLASSIFIERS.with_name(CLASSIFIERS.name + ".tmp")
    with open(tmp, "wb") as f:
        np.savez(f, mean=mean, std=std, gamma=np.array(gammas.pop()),
                 intercept=np.array([fits[k][2] for k in ids]), a=np.array([platt[k][0] for k in ids]),
                 b=np.array([platt[k][1] for k in ids]), threshold=np.array([thr[k] for k in ids]),
                 C=np.array([chosen[k] for k in ids]), info=np.asarray(json.dumps(info)),
                 **{f"sv_{k}": frag[fits[k][0]] for k in ids}, **{f"dual_{k}": fits[k][1] for k in ids})
    tmp.replace(CLASSIFIERS)
    table = pd.DataFrame({"frag_id": frag, "split": dev["split"].to_numpy(),
                          **{f"p_{k}": p[k].astype(np.float32) for k in ids}})
    table.to_parquet(OOF, index=False)
    out = {**info, "lenses": {k: {"C": chosen[k], "ap": ap[k][chosen[k]], "ap_by_C": {str(c): v for c, v in ap[k].items()},
                                  "platt": list(platt[k]), "threshold": thr[k], "support": int(len(fits[k][0])),
                                  "oof": rates(p[k] >= thr[k], y[k].astype(bool), w)}
                              for k in ids}}
    write_json(FIT, out)
    return out


def load_classifiers() -> dict:
    """The fitted classifiers, with their support vectors taken from the fragments' embeddings."""
    if not CLASSIFIERS.exists():
        raise CalibrationError("No classifiers; run `uv run python -m pipeline.calibrate fit`.")
    with np.load(CLASSIFIERS, allow_pickle=False) as z:
        clf = {k: z[k] for k in z.files}
    clf["info"] = json.loads(str(clf["info"]))
    if clf["info"].get("method") != "svm_rbf":
        raise CalibrationError("The classifiers file predates the support vector machines; run `fit`.")
    if clf["info"]["lenses_sha256"] != sha256(LENSES_YAML):
        raise CalibrationError("lenses.yaml changed since the classifiers were fitted.")
    if clf["info"]["fragments_hash"] != embed.content_hash(embed.load_input("fragments"), "fragments"):
        raise CalibrationError("The fragments changed since the classifiers were fitted; run `fit` again.")
    ids = clf["info"]["lenses"]
    sv = [np.asarray(clf[f"sv_{k}"]) for k in ids]
    union, inv = np.unique(np.concatenate(sv), return_inverse=True)
    vec = ((fragment_vectors(union) - clf["mean"]) / clf["std"]).astype(np.float32)
    dual = np.zeros((len(union), len(ids)), dtype=np.float32)
    at = 0
    for j, k in enumerate(ids):
        dual[inv[at:at + len(sv[j])], j] = clf[f"dual_{k}"]
        at += len(sv[j])
    clf.update(sv_vectors=vec, sv_sq=(vec.astype(np.float64) ** 2).sum(axis=1).astype(np.float32), dual=dual)
    return clf


def svm_scores(x: np.ndarray, clf: dict, chunk: int = 2048) -> np.ndarray:
    """Decision score of every lens for raw embeddings: the RBF kernel against the support vectors, in blocks."""
    xs = ((x - clf["mean"]) / clf["std"]).astype(np.float32)
    sv, sq, g = clf["sv_vectors"], clf["sv_sq"], np.float32(clf["gamma"])
    out = np.empty((len(xs), clf["dual"].shape[1]))
    for a in range(0, len(xs), chunk):
        xb = xs[a:a + chunk]
        d2 = (xb.astype(np.float64) ** 2).sum(axis=1).astype(np.float32)[:, None] + sq[None, :] - 2 * (xb @ sv.T)
        out[a:a + chunk] = np.exp(-g * np.maximum(d2, 0)) @ clf["dual"] + clf["intercept"]
    return out


def probabilities(x: np.ndarray, clf: dict, codebook) -> np.ndarray:
    """p per fitted lens for raw embeddings: classifier score, weighted Platt calibration, umbrella rule."""
    ids = list(clf["info"]["lenses"])
    p = 1 / (1 + np.exp(-(clf["a"] * svm_scores(x, clf) + clf["b"])))
    p = expand_scores({lens: p[:, i] for i, lens in enumerate(ids)}, codebook)
    return np.column_stack([p[lens] for lens in ids])


def test() -> dict:
    """Pass bar and share check on the validation set (docs/calibration.md, section 6), with each lens's confusion
    matrix. The validation set is used once: the classifiers must be those fitted on the training set, and a second
    run is refused unless the classifiers are the same."""
    codebook = load_lenses()
    clf = load_classifiers()
    if clf["info"]["sets"] != ["train"]:
        raise CalibrationError("These classifiers were fitted with the validation set; the test needs those of `fit`.")
    used = sha256(CLASSIFIERS)
    if RESULTS.exists() and json.loads(RESULTS.read_text()).get("classifiers_sha256") != used:
        raise CalibrationError(f"The validation set was already used, by other classifiers ({embed.rel(RESULTS)}).")
    ids = list(clf["info"]["lenses"])
    thr = dict(zip(ids, clf["threshold"].tolist()))
    final = pd.read_parquet(FINAL)
    tst = final[final["split"] == "validation"].reset_index(drop=True)
    p = probabilities(fragment_vectors(tst["frag_id"].to_numpy()), clf, codebook)
    w = 1 / tst["pi"].to_numpy()
    period = tst["period"].to_numpy()
    speech = pd.factorize(tst["speech_id"])[0]
    rng = np.random.default_rng(SEED + 3)

    def summary(d_l, y, mask):
        """Weighted precision and recall on the masked fragments, with 95% intervals from a bootstrap that
        resamples speeches, since the validation set was drawn by speech."""
        idx = np.flatnonzero(mask)
        est = rates(d_l[idx], y[idx], w[idx])
        units, members = np.unique(speech[idx], return_inverse=True)
        rows_of = np.split(idx[np.argsort(members, kind="stable")], np.cumsum(np.bincount(members))[:-1])
        draws = []
        for _ in range(BOOTSTRAP):
            b = np.concatenate([rows_of[k] for k in rng.integers(0, len(units), len(units))])
            r = rates(d_l[b], y[b], w[b])
            draws.append((r["precision"], r["recall"]))
        lo, hi = np.nanpercentile(np.array(draws), [2.5, 97.5], axis=0)
        return {**est, "precision_ci": [float(lo[0]), float(hi[0])],
                "recall_ci": [float(lo[1]), float(hi[1])], "positives": int(y[idx].sum())}

    def passes(r):
        return r["precision"] >= PASS_BAR and r["recall"] >= PASS_BAR

    def confusion(d, y):
        cells = {"tp": d & y, "fp": d & ~y, "fn": ~d & y, "tn": ~d & ~y}
        return {**{k: int(v.sum()) for k, v in cells.items()},
                "weighted": {k: float(w[v].sum()) for k, v in cells.items()}}

    results = {}
    for i, lens in enumerate(ids):
        y = tst[lens].to_numpy().astype(bool)
        d = p[:, i] >= thr[lens]
        overall = summary(d, y, np.ones(len(tst), dtype=bool))
        periods = {f"{a}-{b}": summary(d, y, period == k)
                   for k, (a, b) in enumerate(PERIODS) if (period == k).any()}
        checked = sorted(k for k, v in periods.items() if v["positives"] >= MIN_PERIOD_POSITIVES)
        shares = {f"{a}-{b}": {"mean_probability": float((w * p[:, i])[period == k].sum() / w[period == k].sum()),
                               "labelled_share": float((w * y)[period == k].sum() / w[period == k].sum())}
                  for k, (a, b) in enumerate(PERIODS) if (period == k).any()}
        results[lens] = {"threshold": thr[lens], "overall": overall, "confusion": confusion(d, y),
                         "average_precision": float(average_precision_score(y, p[:, i], sample_weight=w)),
                         "periods": periods, "checked_periods": checked, "shares": shares,
                         "pass": bool(passes(overall) and all(passes(periods[k]) for k in checked))}
    pd.DataFrame({"frag_id": tst["frag_id"].to_numpy(), **{f"p_{k}": p[:, i].astype(np.float32)
                                                          for i, k in enumerate(ids)}}).to_parquet(VALIDATION, index=False)
    out = {"tested_at": now(), "classifiers_sha256": used, "validation_fragments": len(tst), "lenses": results}
    write_json(RESULTS, out)
    return out


def predict(chunk: int = 65536) -> pd.DataFrame:
    """The probability of every fragment on every fitted lens, for the shares and the excerpts, and the thresholds."""
    codebook = load_lenses()
    clf = load_classifiers()
    emb, keys, man = load_embeddings("fragments")
    p = np.vstack([probabilities(np.asarray(emb[i:i + chunk], dtype=np.float32), clf, codebook)
                   for i in range(0, len(keys), chunk)])
    ids = clf["info"]["lenses"]
    out = pd.DataFrame({"frag_id": keys["frag_id"].to_numpy()})
    for i, lens in enumerate(ids):
        out[f"p_{lens}"] = p[:, i].astype(np.float32)
    out = out.sort_values("frag_id").reset_index(drop=True)
    tmp = PROBS.with_name(PROBS.name + ".tmp")
    out.to_parquet(tmp, index=False)
    tmp.replace(PROBS)
    # which fragments (frag_id is renumbered when the corpus is rebuilt), which classifiers, and each lens's threshold
    write_json(PROBS.with_suffix(".json"), {"input_hash": man.get("input_hash"),
                                            "classifiers_sha256": sha256(CLASSIFIERS), "sets": clf["info"]["sets"],
                                            "thresholds": dict(zip(ids, clf["threshold"].tolist())),
                                            "made_at": now()})
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="uv run python -m pipeline.calibrate", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p_vec = sub.add_parser("lens-vectors", help="embed the lens definitions and anchors")
    p_vec.add_argument("--device", choices=["auto", "mps", "cpu"], default="auto")
    sub.add_parser("scores", help="score every fragment on every lens")
    p_sample = sub.add_parser("sample", help="draw the sample and write the labelling batches")
    p_sample.add_argument("--force", action="store_true", help="redraw (only before any label exists)")
    p_check = sub.add_parser("check", help="check one labeller or resolver output file")
    p_check.add_argument("kind", choices=["labels", "resolved"])
    p_check.add_argument("name", help='"core/b001" or "check/c001" for labels, "r001" for resolved')
    p_cs = sub.add_parser("checkset", help="draw the check set from the core labels")
    p_cs.add_argument("--force", action="store_true", help="redraw (only before any check label exists)")
    p_rev = sub.add_parser("review", help="draw the review of codebook 1.4 and the reread outside the check files")
    p_rev.add_argument("--force", action="store_true", help="redraw (only before any review label exists)")
    sub.add_parser("collect", help="agreement of the two labellers on the check set, resolver queue")
    sub.add_parser("final", help="final labels")
    p_fit = sub.add_parser("fit", help="one classifier per lens on the training set")
    p_fit.add_argument("--final", action="store_true", help="on the training and validation sets, after `test`")
    sub.add_parser("test", help="pass bar and share check on the validation set")
    sub.add_parser("predict", help="probability of every fragment on every lens")
    args = parser.parse_args(argv)
    try:
        if args.command == "lens-vectors":
            print(json.dumps(make_lens_vectors(device=args.device), indent=2))
        elif args.command == "scores":
            out = compute_scores()
            print(f"{len(out):,} fragments scored -> {embed.rel(SCORES)}")
        elif args.command == "sample":
            draw_sample(force=args.force)
            print(MANIFEST.read_text())
        elif args.command == "check":
            problems = check_file(args.kind, args.name)
            print("\n".join(problems) if problems else f"OK: {args.kind} {args.name}")
            return 1 if problems else 0
        elif args.command == "checkset":
            out = draw_checkset(force=args.force)
            print(json.dumps({k: out[k] for k in ("fragments", "files")}, indent=2))
        elif args.command == "review":
            out = draw_review(force=args.force)
            print(json.dumps({k: out[k] for k in ("fragments", "files")}, indent=2))
        elif args.command == "collect":
            print(json.dumps(collect(), indent=2))
        elif args.command == "final":
            final = final_labels()
            print(f"{len(final):,} fragments -> {embed.rel(FINAL)}")
            print(json.dumps(changes(final), indent=2))
        elif args.command == "fit":
            out = fit(final=args.final)
            for lens, r in out["lenses"].items():
                print(f"{lens:<24} C {r['C']:<5} AP {r['ap']:.3f} threshold {r['threshold']:.2f} "
                      f"out-of-fold P {r['oof']['precision']:.2f} R {r['oof']['recall']:.2f}")
        elif args.command == "predict":
            out = predict()
            print(f"{len(out):,} fragments -> {embed.rel(PROBS)}")
        else:
            out = test()
            for lens, r in out["lenses"].items():
                o = r["overall"]
                cm = r["confusion"]
                print(f"{lens:<24} P {o['precision']:.2f} R {o['recall']:.2f} n+ {o['positives']:>4} "
                      f"TP {cm['tp']:>4} FP {cm['fp']:>4} FN {cm['fn']:>4} TN {cm['tn']:>5} "
                      f"{'PASS' if r['pass'] else 'short'}")
    except (CalibrationError, embed.EmbedError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
