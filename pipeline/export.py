"""Export the site data (docs/data-contract.md) from the corpus, the embeddings and the lens probabilities.

Commands (from the repo root), in order:
    uv run python -m pipeline.export terms               # single words and two-word phrases of every fragment
    uv run python -m pipeline.export layout fragments    # the map (UMAP of the full vectors), fitted once; later
                                                         # runs place new fragments on it (--refit: a new edition)
    uv run python -m pipeline.export layout speeches     # each speech placed on the same map, from the mean of
                                                         # its fragments' vectors
    uv run python -m pipeline.export topics              # general topics: k-means over the fragments about no lens,
                                                         # fitted once; later runs put fragments in the nearest
                                                         # saved topic (--refit: a new edition, named again)
    uv run python -m pipeline.export site               # write site/data/ and check the size budget

`topics` writes data/interim/export/topic_examples.md. The main agent names each topic by reading its words and
examples and records the names in data/lenses/topics.yaml, with the centres_sha256 of the edition they name,
which `site` reads. With `--placeholder`, `topics` and `site` put pseudo-probabilities made from the sampling scores
in place of the lens probabilities, to build the front end before the calibration ends; meta.json then says so and
the site must show it. Placeholder data is never published. Every cache records the input hash of the fragment
embeddings, and `site` refuses a stale one.
"""
import argparse
import bisect
import gzip
import hashlib
import json
import re
import shutil
import sys
import unicodedata
from datetime import datetime, timezone
from functools import partial

import numpy as np
import pandas as pd
import pycountry
import yaml
from scipy import sparse
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, CountVectorizer
from sklearn.isotonic import IsotonicRegression

from pipeline import calibrate, config, embed, segment
from pipeline.lenses import expand_scores, load_lenses

OUT = config.INTERIM / "export"
TERMS = OUT / "terms.npz"
LAYOUTS = {"fragments": OUT / "layout_fragments.npz", "speeches": OUT / "layout_speeches.npz"}
TOPICS = OUT / "topics.parquet"
TOPIC_CENTRES = OUT / "topic_centres.npy"
TOPIC_EXAMPLES = OUT / "topic_examples.md"
TOPIC_NAMES = config.LENSES / "topics.yaml"

FIRST_YEAR, LAST_YEAR = 1946, 2026
PROVISIONAL = [2026]
PLACEHOLDER_ABOUT = 0.5     # "about" a lens in a placeholder build (never published); real builds use each lens's
                            # threshold (docs/calibration.md, section 5)
                                     # within drugs through the umbrella rule (user, 2026-09-30)
SEED = 0
N_TOPICS = 14               # general topics: the largest number whose topics reproduce on split halves (PLAN 4)
KMEANS_INIT = 10            # k-means restarts; the best one is kept
MAP_NEIGHBORS = 50          # at 15 (UMAP's default) a quarter of a fragment's nearest fragments are its own
                            # country's in other years; at 50 a sixth, and more neighbours barely lower it
MAP_MIN_DIST = 0.0          # packs each group tightly, leaving clear space between groups
MIN_DF = 5                  # fragments that must use a term for it to enter the vocabulary
KEY_TOP = 12                # terms per list in the word bars
KEY_MIN_TOKENS = 200        # single words a selection needs on a lens and period to get word bars
KEY_MIN_COUNT = 3           # times a term must occur in the selection
KEY_MIN_SPREAD = 2          # speeches (for a group, members) that must use a term, when the selection has as many
KEY_MIN_Z = 1.96
PRIOR_SIZE = 1000.0         # alpha_0 of the informative Dirichlet prior
EXCERPTS = 3                # per speech and lens
REP_CHARS = 220            # a speech's passage on hover
SNIP_CHARS = 180            # a fragment's passage on hover (snips/<iso3>.json)
START_BUDGET = 8_000_000    # gzip bytes of the files loaded at start
TOTAL_BUDGET = 400_000_000
START_FILES = ("meta.json", "shares.bin", "frags.bin", "map_frag.bin", "map_speech.bin", "map_labels.json")
# Map points: one column after another, the 2-byte ones first so that each starts at an even offset. Columns
# compress a third smaller than records under the host's gzip (docs/data-contract.md, map files).
MAP_COLUMNS = (("x", "<u2"), ("y", "<u2"), ("c", "<u2"), ("lensmask", "<u2"), ("yr", "u1"), ("topic", "u1"))
NO_TOPIC = 255              # a speech point with no measured fragment

# Multi-country UNODC field offices in selector order, ROCOL first, with the short names of the approved mockup.
OFFICES = {
    "ROCOL": ("Región Andina y Cono Sur", "Andean Region and Southern Cone"),
    "ROPAN": ("Centroamérica y el Caribe", "Central America and the Caribbean"),
    "ROSEN": ("África Occidental y Central", "West and Central Africa"),
    "ROSAF": ("África Meridional", "Southern Africa"),
    "ROEA": ("África Oriental", "Eastern Africa"),
    "ROMENA": ("Oriente Medio y Norte de África", "Middle East and North Africa"),
    "OGCCR": ("Consejo de Cooperación del Golfo", "Gulf Cooperation Council"),
    "ROCA": ("Afganistán, Asia Central, Irán y Pakistán", "Afghanistan, Central Asia, Iran and Pakistan"),
    "ROSA": ("Asia Meridional", "South Asia"),
    "ROSEAP": ("Asia Sudoriental y el Pacífico", "Southeast Asia and the Pacific"),
    "ROSEE": ("Europa Sudoriental", "South-Eastern Europe"),
    "POUKR": ("Ucrania y Moldavia", "Ukraine and Moldova"),
}
HOST_ONLY = {"HQ", "BRULO", "NYLO"}  # host offices, not coverage (docs/PLAN.md, section 3.4)
NOFIELD = {"id": "SEDE", "slug": "sede", "type": "nofield", "es": "Cubiertos desde la Sede",
           "en": "Covered from Headquarters", "short_es": "Sede", "short_en": "HQ"}
BLOCS = {"ALC": ("ALC", "LAC"), "UE": ("UE-27", "EU-27"), "BRICS": ("BRICS", "BRICS"), "G7": ("G7", "G7"),
         "AFR": ("África", "Africa"), "ASP": ("Asia-Pacífico", "Asia-Pacific")}  # short names; long ones in groups.csv

# Word counts (docs/PLAN.md, section 4, Text processing): stopwords, UN boilerplate and country names are dropped.
STOP = set(ENGLISH_STOP_WORDS) | set("""mr president general assembly united nations nation session delegation also
would must shall may us one two new year years today world country countries international people peoples great like
ago week weeks month months days yesterday tomorrow hand
wish made make many every well within without since upon therefore however thus way ms madam secretary
secretary-general excellency excellencies distinguished organization member members state states government
governments let said say says we're i'm don't can't won't isn't aren't doesn't didn't we've we'll i've they're
you're wasn't weren't haven't hasn't couldn't wouldn't shouldn't""".split())
NAME_WORDS_KEPT = set("""united republic republics democratic people state states islands island kingdom federal
federation federated union south north northern new saint central east west plurinational bolivarian islamic socialist
commonwealth great grand holy city independent cooperative co-operative oriental upper ivory gold coast""".split())
DEMONYMS = set("""colombian colombians bolivian bolivians peruvian peruvians paraguayan paraguayans argentine argentines
argentinian chilean chileans ecuadorian ecuadorians uruguayan uruguayans brazilian brazilians chinese russian russians
indian indians african africans european europeans iranian iranians egyptian egyptians ethiopian ethiopians indonesian
indonesians emirati american americans mexican mexicans venezuelan venezuelans cuban cubans afghan afghans pakistani
iraqi iraqis syrian syrians israeli israelis palestinian palestinians lebanese french british german germans italian
japanese canadian canadians spanish turkish ukrainian ukrainians nigerian kenyan somali sudanese libyan yemeni saudi
korean koreans vietnamese thai filipino malaysian burmese nepalese bangladeshi lankan kazakh uzbek tajik kyrgyz turkmen
azerbaijani armenian georgian belarusian polish hungarian czech slovak romanian bulgarian serbian croatian bosnian
albanian greek cypriot maltese irish scottish dutch belgian swiss austrian swedish norwegian danish finnish icelandic
portuguese australian haitian jamaican guatemalan salvadoran honduran nicaraguan panamanian dominican caribbean soviet
yugoslav czechoslovak""".split())
WORD = re.compile(r"[^\W\d_](?:[^\W\d_]|['\-])*[^\W\d_]|[.,;:!?()\[\]\"“”—–]")
CLAUSE = re.compile(r"[,;:]\s+")


class ExportError(Exception):
    """A condition the user must resolve (a missing or stale input, the size budget exceeded)."""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def dumps(data) -> bytes:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def read_side(path) -> dict:
    """The provenance record written beside a cache (same name, .json)."""
    side = path.with_suffix(".json")
    if not path.exists() or not side.exists():
        raise ExportError(f"{embed.rel(path)} is missing; make it first (see `uv run python -m pipeline.export --help`).")
    return json.loads(side.read_text(encoding="utf-8"))


def check_fresh(path, input_hash: str) -> dict:
    side = read_side(path)
    if side.get("input_hash") != input_hash:
        raise ExportError(f"{embed.rel(path)} was made from other fragments or speeches; make it again.")
    return side


# ---------------------------------------------------------------------------
# Words
# ---------------------------------------------------------------------------

def term_ends(text: str, names: frozenset = frozenset(), stop: frozenset = STOP) -> list[tuple[str, int]]:
    """Single words, then two-word phrases of adjacent kept words in the same clause, each with the offset in text
    where it ends."""
    out, prev = [], None
    for m in WORD.finditer(text.lower().replace("’", "'")):
        tok = m.group()
        if tok.endswith("'s"):
            tok = tok[:-2]
        word = tok if len(tok) > 2 and tok[0].isalpha() and tok not in stop and tok not in names else None
        if word:
            out.append((word, m.end()))
            if prev and not (prev in NAME_WORDS_KEPT and word in NAME_WORDS_KEPT):  # not "democratic republic"
                out.append((f"{prev} {word}", m.end()))
        prev = word
    return out


def terms_of(text: str, names: frozenset = frozenset(), stop: frozenset = STOP) -> list[str]:
    """Single words, then two-word phrases of adjacent kept words in the same clause."""
    return [t for t, _ in term_ends(text, names, stop)]


def name_words(codes) -> frozenset:
    """Words of the corpus countries' names, present and historical, with demonyms; generic words are kept."""
    names = []
    for code in codes:
        entry = pycountry.countries.get(alpha_3=code) or pycountry.historic_countries.get(alpha_3=code)
        names += [getattr(entry, a, "") or "" for a in ("name", "official_name", "common_name")] if entry else []
    names += pd.read_csv(config.COUNTRIES, keep_default_na=False, dtype=str)["name_en"].tolist()
    names += pd.read_csv(config.HISTORICAL_NAMES, keep_default_na=False, dtype=str)["name_en"].tolist()
    words = {w for name in names for w in terms_of(name, stop=frozenset()) if " " not in w}
    words |= {unicodedata.normalize("NFKD", w).encode("ascii", "ignore").decode() for w in words}  # Cote, Sao Tome
    return frozenset((words - NAME_WORDS_KEPT - STOP) | DEMONYMS)


def make_terms() -> dict:
    """Counts of every term in every non-ceremonial fragment (rows in frag_id order), for the word bars."""
    frags = pd.read_parquet(config.FRAGMENTS, columns=["frag_id", "iso3", "text", "is_ceremonial"])
    frags = frags[~frags["is_ceremonial"]].sort_values("frag_id")
    names = name_words(sorted(frags["iso3"].unique()))
    vec = CountVectorizer(analyzer=partial(terms_of, names=names), min_df=MIN_DF, dtype=np.int32)
    x = vec.fit_transform(frags["text"]).tocsr()
    vocab = vec.get_feature_names_out().tolist()
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez(TERMS, data=x.data, indices=x.indices, indptr=x.indptr, shape=np.array(x.shape),
             frag_id=frags["frag_id"].to_numpy())
    info = {"input_hash": embed.content_hash(embed.load_input("fragments"), "fragments"), "n_fragments": x.shape[0],
            "n_terms": len(vocab), "n_bigrams": sum(" " in w for w in vocab), "min_df": MIN_DF, "made_at": now(),
            "vocab": vocab}
    calibrate.write_json(TERMS.with_suffix(".json"), info)
    return {k: v for k, v in info.items() if k != "vocab"}


def load_terms(frag_ids, input_hash: str) -> tuple[sparse.csr_matrix, list[str]]:
    info = check_fresh(TERMS, input_hash)
    with np.load(TERMS) as z:
        x = sparse.csr_matrix((z["data"], z["indices"], z["indptr"]), shape=tuple(z["shape"]))
        rows = pd.Series(np.arange(x.shape[0]), index=z["frag_id"])
    return x[rows.loc[frag_ids].to_numpy()], info["vocab"]


def fightin_words(yi, ni, yj, nj, alpha, a0: float | None = None):
    """z-scores of the log-odds ratio with an informative Dirichlet prior (Monroe, Colaresi and Quinn 2008): a
    term's count yi among ni terms of the selection against yj among nj of the rest; alpha sums to a0."""
    a0 = PRIOR_SIZE if a0 is None else a0
    d = np.log((yi + alpha) / (ni + a0 - yi - alpha)) - np.log((yj + alpha) / (nj + a0 - yj - alpha))
    return d / np.sqrt(1 / (yi + alpha) + 1 / (yj + alpha))


def prior(total: np.ndarray, is_bigram: np.ndarray) -> np.ndarray:
    """alpha of each term: PRIOR_SIZE times its share of the text, single words and phrases apart."""
    alpha = np.zeros(len(total))
    for m in (~is_bigram, is_bigram):
        if total[m].sum():
            alpha[m] = PRIOR_SIZE * total[m] / total[m].sum()
    return alpha


def keyness(xs: sparse.csr_matrix, speech_c: np.ndarray, n_countries: int, periods, selections, vocab,
            is_bigram: np.ndarray) -> dict:
    """Word bars of one lens. xs: term counts of the lens's text per speech. For each selection (key, country
    indexes) and period (key, speech mask) with enough text: the top words and two-word phrases by z-score
    against the rest of the world on the same lens and period, as [term, z, count]. A term used in one speech, or by
    one member of a group, is that speech's or member's rather than the selection's, unless the selection has no more
    on the lens in the period."""
    alpha = prior(np.asarray(xs.sum(axis=0)).ravel().astype(np.float64), is_bigram)
    r = [i for i, (_, members) in enumerate(selections) for _ in members]
    c = [m for _, members in selections for m in members]
    ind = sparse.csr_matrix((np.ones(len(r)), (r, c)), shape=(len(selections), n_countries))
    out = {}
    for pkey, pmask in periods:
        rows = np.flatnonzero(pmask)
        if not len(rows):
            continue
        xp = xs[rows]
        tot = np.asarray(xp.sum(axis=0)).ravel().astype(np.float64)
        n_all = np.array([tot[~is_bigram].sum(), tot[is_bigram].sum()])
        sel = ind[:, speech_c[rows]]
        y = (sel @ xp).tocsr()
        used = (xp > 0).astype(np.float64)
        own = sparse.csr_matrix((np.ones(len(rows)), (speech_c[rows], np.arange(len(rows)))),
                                shape=(n_countries, len(rows)))
        by_speech = (sel @ used).tocsr()                                    # the selection's speeches using a term
        by_member = (ind @ ((own @ used) > 0).astype(np.float64)).tocsr()   # its members using it
        has = (np.diff(xp.indptr) > 0).astype(np.float64)                   # speeches with text on the lens
        n_speech, n_member = sel @ has, ind @ ((own @ has) > 0).astype(np.float64)
        for i, (skey, members) in enumerate(selections):
            idx = y.indices[y.indptr[i]:y.indptr[i + 1]]
            cnt = y.data[y.indptr[i]:y.indptr[i + 1]].astype(np.float64)
            big = is_bigram[idx]
            n = np.array([cnt[~big].sum(), cnt[big].sum()])
            if n[0] < KEY_MIN_TOKENS or n_all[0] - n[0] < KEY_MIN_TOKENS:
                continue
            spread, avail = (by_member, n_member) if len(members) > 1 else (by_speech, n_speech)
            keep = (cnt >= KEY_MIN_COUNT) & (spread[i, idx].toarray().ravel() >= min(KEY_MIN_SPREAD, avail[i]))
            idx, cnt, big = idx[keep], cnt[keep], big[keep]
            ni = n[big.astype(int)]
            z = fightin_words(cnt, ni, tot[idx] - cnt, n_all[big.astype(int)] - ni, alpha[idx])
            entry = {}
            for name, m in (("words", ~big), ("bigrams", big)):
                k = np.flatnonzero(m & (z >= KEY_MIN_Z))
                k = k[np.lexsort((idx[k], -z[k]))][:KEY_TOP]
                entry[name] = [[vocab[idx[j]], round(float(z[j]), 1), int(cnt[j])] for j in k]
            if entry["words"] or entry["bigrams"]:
                out.setdefault(skey, {})[pkey] = entry
    return out


# ---------------------------------------------------------------------------
# Maps and topics
# ---------------------------------------------------------------------------

def make_layout(kind: str, refit: bool = False) -> dict:
    """One map for both layers (docs/PLAN.md, section 3.6). Fragments: a UMAP of the full vectors by cosine, fitted
    once; later runs keep every mapped fragment where it is and place the new ones among their nearest mapped
    fragments, unless `refit` asks for a new edition of the map. Each speech is placed the same way, from the mean
    of its fragments' vectors, so both layers share one geography. Ceremonial fragments are not drawn."""
    f_emb, f_keys, f_man = calibrate.load_embeddings("fragments")
    cer = pd.read_parquet(config.FRAGMENTS, columns=["frag_id", "speech_id", "is_ceremonial"]).set_index("frag_id")
    rows = np.flatnonzero(~cer.loc[f_keys["frag_id"], "is_ceremonial"].to_numpy())
    f_ids = f_keys["frag_id"].to_numpy()[rows]
    params = {"n_neighbors": MAP_NEIGHBORS, "min_dist": MAP_MIN_DIST, "metric": "cosine"}
    if kind == "fragments":
        old = None if refit or not LAYOUTS["fragments"].exists() else dict(np.load(LAYOUTS["fragments"]))
        if old is not None and read_side(LAYOUTS["fragments"]).get("params") != params:
            raise ExportError("The saved map was made with other settings; run `layout fragments --refit` for a new "
                              "edition of the map.")
        if old is None:
            import umap
            xy = umap.UMAP(**params, random_state=SEED).fit_transform(
                unit_rows(np.asarray(f_emb[rows], dtype=np.float32))).astype(np.float32)
            info = {"edition": now(), "fitted": len(f_ids), "placed": 0}
        else:
            prev = read_side(LAYOUTS["fragments"])
            at = pd.Series(np.arange(len(old["ids"])), index=old["ids"])
            known = np.isin(f_ids, old["ids"])
            xy = np.empty((len(f_ids), 2), dtype=np.float32)
            xy[known] = old["xy"][at.loc[f_ids[known]].to_numpy()]
            if (~known).any():
                mapped = unit_rows(np.asarray(f_emb[rows[known]], dtype=np.float32))
                xy[~known] = place(unit_rows(np.asarray(f_emb[rows[~known]], dtype=np.float32)), mapped, xy[known])
            info = {"edition": prev["edition"], "fitted": prev["fitted"], "placed": int(prev["placed"] + (~known).sum())}
        ids = f_ids
        input_hash = f_man["input_hash"]
    else:
        # A speech goes where the mean of its mapped fragments' vectors goes. This spreads each year's speeches by
        # subject: the 387 speeches of 2024 and 2026 spread over 0.78 and 0.66 of the fragments' extent on the two axes.
        fxy = load_layout("fragments", f_ids, f_man["input_hash"])
        x_map = unit_rows(np.asarray(f_emb[rows], dtype=np.float32))
        owner, ids = pd.factorize(cer.loc[f_ids, "speech_id"].to_numpy())
        sums = sparse.csr_matrix((np.ones(len(owner), dtype=np.float32), (owner, np.arange(len(owner)))),
                                 shape=(len(ids), len(owner))) @ x_map
        xy = place(unit_rows(np.asarray(sums, dtype=np.float32)), x_map, fxy)
        ids = np.asarray(ids, dtype=str)
        info = {"edition": read_side(LAYOUTS["fragments"])["edition"], "placed": len(ids)}
        input_hash = f_man["input_hash"]
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez(LAYOUTS[kind], ids=ids, xy=xy)
    info = {"input_hash": input_hash, "n": len(ids), "params": params, "seed": SEED, **info, "made_at": now()}
    calibrate.write_json(LAYOUTS[kind].with_suffix(".json"), info)
    return info


def place(x_new: np.ndarray, x_map: np.ndarray, xy_map: np.ndarray, k: int = MAP_NEIGHBORS,
          block: int = 128) -> np.ndarray:
    """Positions on an existing map for new unit vectors: the mean position of their k nearest mapped points by
    cosine, weighted as UMAP weighs a point's neighbours, which is where UMAP's own transform starts. Checked on
    the map of 2026-09-29: a mapped fragment put back this way lands a median 0.7% of the map's diagonal from its
    place, and 2.2% land where no mapped fragment is near. UMAP's transform would then adjust each point a
    little; that step is skipped, so only the saved coordinates are needed and the result repeats exactly."""
    from umap.umap_ import smooth_knn_dist

    k = min(k, len(x_map))
    idx = np.empty((len(x_new), k), dtype=np.int64)
    dist = np.empty((len(x_new), k), dtype=np.float32)
    for a in range(0, len(x_new), block):
        sim = x_new[a:a + block] @ x_map.T
        j = np.argpartition(-sim, k - 1, axis=1)[:, :k]
        d = 1 - np.take_along_axis(sim, j, axis=1)
        o = np.argsort(d, axis=1, kind="stable")
        idx[a:a + block], dist[a:a + block] = np.take_along_axis(j, o, axis=1), np.take_along_axis(d, o, axis=1)
    sigma, rho = smooth_knn_dist(np.maximum(dist, 0), float(k))
    w = np.exp(-np.maximum(dist - rho[:, None], 0) / sigma[:, None])
    return ((w[:, :, None] * xy_map[idx]).sum(axis=1) / w.sum(axis=1, keepdims=True)).astype(np.float32)


def load_layout(kind: str, ids, input_hash: str) -> np.ndarray:
    check_fresh(LAYOUTS[kind], input_hash)
    with np.load(LAYOUTS[kind]) as z:
        pos = pd.Series(np.arange(len(z["ids"])), index=z["ids"])
        missing = pd.Index(ids).difference(pos.index)
        if len(missing):
            raise ExportError(f"{len(missing)} points are not on the {kind} map; make the layout again.")
        return z["xy"][pos.loc[ids].to_numpy()]


def lens_probabilities(frag_ids, input_hash: str, placeholder: bool, codebook) -> tuple[np.ndarray, str, np.ndarray]:
    """p of every fragment on every fitted lens, in codebook order, where it comes from, and each lens's threshold.
    The placeholder maps each sampling score s to 1 / (1 + exp(-3 (s - 2))), about 2% of fragments at 0.5 or more,
    with the umbrella rule."""
    ids = calibrate.fitted_ids(codebook)
    path, prefix = (calibrate.SCORES, "s_") if placeholder else (calibrate.PROBS, "p_")
    side = check_fresh(path, input_hash)
    if not placeholder and set(side.get("thresholds", {})) != set(ids):
        raise ExportError(f"{embed.rel(path)} has no threshold for every measured lens; run `calibrate predict`.")
    table = pd.read_parquet(path, columns=["frag_id"] + [prefix + i for i in ids]).set_index("frag_id")
    missing = pd.Index(frag_ids).difference(table.index)
    if len(missing):
        raise ExportError(f"{len(missing)} fragments have no value in {embed.rel(path)}.")
    p = table.loc[frag_ids].to_numpy(np.float64)
    if placeholder:
        p = expand_scores({i: 1 / (1 + np.exp(-3 * (p[:, k] - 2))) for k, i in enumerate(ids)}, codebook)
        return (np.column_stack([p[i] for i in ids]).astype(np.float32), "placeholder",
                np.full(len(ids), PLACEHOLDER_ABOUT, dtype=np.float32))
    return (p.astype(np.float32), calibrate.sha256(path), np.array([side["thresholds"][i] for i in ids], dtype=np.float32))


def make_topics(placeholder: bool = False, refit: bool = False) -> dict:
    """N_TOPICS general topics over the fragments about no lens (docs/PLAN.md, section 4, Composition): k-means,
    largest first, fitted once and its centres saved; later runs put each such fragment in the nearest saved centre,
    so a new year joins the named topics, unless `refit` asks for a new edition. Placeholder runs fit afresh and
    keep nothing. Writes the examples the main agent reads to name them."""
    codebook = load_lenses()
    emb, keys, man = calibrate.load_embeddings("fragments")
    ids = keys["frag_id"].to_numpy()
    frags = pd.read_parquet(config.FRAGMENTS, columns=["frag_id", "year", "text", "is_ceremonial"])
    frags = frags.set_index("frag_id").loc[ids]
    p, source, thr = lens_probabilities(ids, man["input_hash"], placeholder, codebook)
    rows = np.flatnonzero(~frags["is_ceremonial"].to_numpy() & (p < thr).all(axis=1))
    x = np.asarray(emb[rows], dtype=np.float32)
    if placeholder or refit or not TOPIC_CENTRES.exists():
        from sklearn.cluster import KMeans

        km = KMeans(N_TOPICS, n_init=KMEANS_INIT, random_state=SEED).fit(x)
        order = np.argsort(-np.bincount(km.labels_, minlength=N_TOPICS), kind="stable")
        centres = km.cluster_centers_[order].astype(np.float32)
        edition = {"edition": now(), "fitted": len(rows), "fitted_on": source}
        if not placeholder:
            OUT.mkdir(parents=True, exist_ok=True)
            np.save(TOPIC_CENTRES, centres)
            calibrate.write_json(TOPIC_CENTRES.with_suffix(".json"), edition)
    else:
        centres, edition = np.load(TOPIC_CENTRES), read_side(TOPIC_CENTRES)
        if centres.shape != (N_TOPICS, x.shape[1]):
            raise ExportError("The saved topics have another shape; run `topics --refit` for a new edition.")
    topic = nearest_centre(x, centres)
    OUT.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame({"frag_id": ids[rows], "topic": topic.astype(np.int16)})
    tmp = TOPICS.with_name(TOPICS.name + ".tmp")
    table.to_parquet(tmp, index=False)
    tmp.replace(TOPICS)
    info = {"input_hash": man["input_hash"], "probabilities": source, "n_topics": N_TOPICS,
            "sizes": np.bincount(topic, minlength=N_TOPICS).tolist(), **edition,
            "centres_sha256": hashlib.sha256(centres.tobytes()).hexdigest(), "made_at": now()}
    calibrate.write_json(TOPICS.with_suffix(".json"), info)
    write_topic_examples(frags.iloc[rows], x, topic, centres, man["input_hash"], info)
    return info


def nearest_centre(x: np.ndarray, centres: np.ndarray, block: int = 65536) -> np.ndarray:
    """Each row's nearest centre by Euclidean distance, as k-means assigns."""
    half = 0.5 * (centres.astype(np.float64) ** 2).sum(axis=1)
    return np.concatenate([np.argmax(x[a:a + block] @ centres.T - half, axis=1)
                           for a in range(0, len(x), block)]).astype(np.int64)


def write_topic_examples(frags: pd.DataFrame, x: np.ndarray, topic: np.ndarray, centres: np.ndarray,
                         input_hash: str, info: dict) -> None:
    """For each topic: its size, distinctive words against the other topics, 8 fragments nearest its centre and
    4 at random."""
    words = {}
    if TERMS.exists():
        xt, vocab = load_terms(frags.index.to_numpy(), input_hash)
        is_bigram = np.array([" " in w for w in vocab])
        one = sparse.csr_matrix((np.ones(len(topic)), (topic, np.arange(len(topic)))), shape=(N_TOPICS, len(topic)))
        counts = (one @ xt).toarray().astype(np.float64)
        total = counts.sum(axis=0)
        alpha = prior(total, is_bigram)
        nall = np.array([total[~is_bigram].sum(), total[is_bigram].sum()])[is_bigram.astype(int)]
        for t in range(N_TOPICS):
            yi = counts[t]
            n = np.array([yi[~is_bigram].sum(), yi[is_bigram].sum()])[is_bigram.astype(int)]
            with np.errstate(divide="ignore", invalid="ignore"):
                z = np.where(yi >= 20, fightin_words(yi, n, total - yi, nall - n, alpha), -np.inf)
            words[t] = [", ".join(vocab[j] for j in np.argsort(-np.where(m, z, -np.inf), kind="stable")[:k]
                                  if m[j] and np.isfinite(z[j])) for m, k in ((~is_bigram, 15), (is_bigram, 10))]
    rng = np.random.default_rng(SEED)
    lines = ["# General topics: examples for naming", "",
             f"Made {info['made_at']} from {info['probabilities']} probabilities; topics of the edition of "
             f"{info['edition']}, centres_sha256 {info['centres_sha256']}. Name each topic in data/lenses/topics.yaml "
             "by reading its words and examples.", ""]
    for t in range(N_TOPICS):
        rows = np.flatnonzero(topic == t)
        near = rows[np.argsort(-(x[rows] @ centres[t]))[:8]]
        pick = np.concatenate([near, rng.choice(np.setdiff1d(rows, near), size=min(4, len(rows) - len(near)),
                                                replace=False)])
        lines += [f"## Topic {t} ({len(rows):,} fragments, {len(rows) / len(topic):.1%})", ""]
        if t in words:
            lines += [f"- Words: {words[t][0]}", f"- Phrases: {words[t][1]}", ""]
        for k, r in enumerate(pick):
            lines.append(f"{k + 1}. ({'near' if k < len(near) else 'random'}, {frags['year'].iloc[r]}) "
                         f"{clip(frags['text'].iloc[r], 400)}")
        lines.append("")
    TOPIC_EXAMPLES.write_text("\n".join(lines), encoding="utf-8")


def topic_names(placeholder: bool, info: dict) -> list[dict]:
    """The general topics' names from data/lenses/topics.yaml, which must name this edition's centres."""
    if TOPIC_NAMES.exists():
        data = yaml.safe_load(TOPIC_NAMES.read_text(encoding="utf-8"))
        if data.get("centres_sha256") == info["centres_sha256"]:
            topics = sorted(data["topics"], key=lambda t: t["cluster"])
            if [t["cluster"] for t in topics] != list(range(info["n_topics"])):
                raise ExportError(f"{embed.rel(TOPIC_NAMES)} must name clusters 0 to {info['n_topics'] - 1} once.")
            return [{"id": t["id"], "es": t["es"], "en": t["en"]} for t in topics]
    if not placeholder:
        raise ExportError(f"{embed.rel(TOPIC_NAMES)} does not name the current topics; read "
                          f"{embed.rel(TOPIC_EXAMPLES)} and name them.")
    return [{"id": f"topic_{k}", "es": f"Tema {k + 1}", "en": f"Topic {k + 1}"} for k in range(info["n_topics"])]


def quantize(xy: np.ndarray, lo: np.ndarray | None = None, hi: np.ndarray | None = None) -> np.ndarray:
    """Each axis scaled to 0..65535 between lo and hi (by default the points' own extent)."""
    lo = xy.min(axis=0) if lo is None else lo
    hi = xy.max(axis=0) if hi is None else hi
    q = (xy - lo) / np.where(hi > lo, hi - lo, 1)
    return np.rint(np.clip(q, 0, 1) * 65535).astype(np.uint16)


def map_columns(**cols) -> bytes:
    return b"".join(np.asarray(cols[name], dtype=t).tobytes() for name, t in MAP_COLUMNS)


def read_map(buf: bytes, n: int) -> dict:
    """The columns of a map file (QA and tests)."""
    out, at = {}, 0
    for name, t in MAP_COLUMNS:
        out[name] = np.frombuffer(buf, dtype=t, count=n, offset=at)
        at += n * np.dtype(t).itemsize
    if at != len(buf):
        raise ExportError(f"A map file holds {len(buf):,} bytes, not {at:,}.")
    return out


def label_anchors(q: np.ndarray, members: list, grid: int = 48, spots: int = 3) -> list[dict]:
    """Where to write each topic's name on a map (members: a mask of its points per topic; a topic with none gets no
    name): up to `spots` places, best first, each the mean of the topic's points around a cell where the topic is
    both dense and dominant (its smoothed count squared over that of all points), a sixth of the map apart, so that a
    name another one covers can move to its next place (`alt`)."""
    xy = q.astype(np.float64) / 65535
    cells = np.minimum((xy * grid).astype(int), grid - 1)

    def smooth(c):
        dens = np.zeros((grid + 2, grid + 2))
        np.add.at(dens, (c[:, 0] + 1, c[:, 1] + 1), 1)
        return sum(dens[1 + a:grid + 1 + a, 1 + b:grid + 1 + b] for a in (-1, 0, 1) for b in (-1, 0, 1))

    everyone, apart = smooth(cells), grid // 6
    out = []
    for t, own in enumerate(members):
        if not own.any():
            continue
        score = smooth(cells[own]) ** 2 / np.maximum(everyone, 1)
        top, places = score.max(), []
        while len(places) < spots and score.max() > 0 and score.max() >= top / 4:
            cx, cy = np.unravel_index(np.argmax(score), score.shape)
            near = own & (np.abs(cells[:, 0] - cx) <= 1) & (np.abs(cells[:, 1] - cy) <= 1)
            places.append([round(float(v), 4) for v in xy[near].mean(axis=0)])
            score[max(0, cx - apart):cx + apart + 1, max(0, cy - apart):cy + apart + 1] = 0
        out.append({"t": t, "x": places[0][0], "y": places[0][1], "n": int(own.sum()), "alt": places[1:]})
    return out


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------

def clip(text: str, n: int) -> str:
    """At most n characters, cut at a word boundary with an ellipsis."""
    text = " ".join(str(text).split())
    if len(text) <= n:
        return text
    cut = text[:n - 2]
    return (cut[:cut.rfind(" ")] if " " in cut else cut).rstrip(",;:") + " …"


def candidate_windows(text: str, n: int) -> tuple[str, list[tuple[int, int, bool, bool]]]:
    """A fragment's text with its spaces collapsed, and its candidate passages as (start, end, cut, mid): each starts
    at a sentence, or at a clause of a sentence longer than n (shown after "… "), and runs to the last sentence end
    within n characters, or is cut at a word before n when no sentence ends between n // 2 and n. A start with less
    than n // 2 characters left is not taken, so a passage is never a greeting alone. None when the text fits in n."""
    t = " ".join(str(text).split())
    if len(t) <= n:
        return t, []
    spans = [(a + (t[a] == " "), b) for a, b in segment.sentence_spans(t)]
    starts, ends = [a for a, _ in spans], [b for _, b in spans]
    cands = []
    for a, e in zip(starts, ends):
        cands.append((a, False))
        if e - a > n:
            cands += [(c.end(), True) for c in CLAUSE.finditer(t, a, e)]
    out = []
    for a, mid in cands:
        room = n - 2 if mid else n
        if len(t) - a < n // 2:
            continue
        j = bisect.bisect_right(ends, a + room) - 1
        if j >= 0 and ends[j] - a >= n // 2:
            b, cut = ends[j], False
        elif len(t) - a <= room:
            b, cut = len(t), False
        else:
            b = t.rfind(" ", a, a + room - 1)
            b, cut = (b if b > a else a + room - 2), True
        out.append((a, b, cut, mid))
    return t, out


def passage(t: str, a: int, b: int, cut: bool, mid: bool) -> str:
    out = t[a:b].rstrip(",;: ") + " …" if cut else t[a:b]
    return "… " + out if mid else out


def by_words(t: str, cands: list, weight: dict | None) -> int:
    """The candidate whose terms weigh most in `weight` (term: weight, from topic_weights); on a tie, the one that
    starts nearest those terms (the latest), and the first when no term weighs."""
    pos, cum = [0], [0.0]   # where each term ends, and the running sum of the weights
    for term, end in term_ends(t) if weight else []:
        pos.append(end)
        cum.append(cum[-1] + weight.get(term, 0.0))
    best, top = 0, None
    for i, (a, b, _, _) in enumerate(cands):
        score = cum[bisect.bisect_right(pos, b) - 1] - cum[bisect.bisect_right(pos, a) - 1]
        if top is None or score > top or 0 < score == top:
            best, top = i, score
    return best


def window(text: str, weight: dict | None, n: int) -> str:
    """A fragment's passage on hover, from n // 2 to n characters, where the fragment is most about its topic by
    its words (by_words)."""
    t, cands = candidate_windows(text, n)
    return passage(t, *cands[by_words(t, cands, weight)]) if cands else t


def topic_weights(x: sparse.csr_matrix, members: list, vocab: list, is_bigram: np.ndarray,
                  within: list | None = None) -> list[dict]:
    """For each topic (members: the rows of its fragments in x), the weight of each term in the passages shown for
    it: the term's Fightin' Words z-score in the topic's fragments against all the other fragments, where it is at
    least KEY_MIN_Z. For a sub-lens, plus its z-score against the rest of its parent lens's fragments (within: the
    rows of those fragments), so that an alternative development passage favours what sets it apart from drugs at
    large while its drug words still count. A passage is then chosen for the words that set its topic apart, not
    for a list of key terms."""
    def counts(sets):
        r = np.concatenate([np.full(len(m), i, dtype=np.int64) for i, m in enumerate(sets)])
        ind = sparse.csr_matrix((np.ones(len(r)), (r, np.concatenate(sets))), shape=(len(sets), x.shape[0]))
        return (ind @ x).toarray()

    def z_over(yi, yj):   # the part of the z-scores at or above the bar
        ni = np.array([yi[~is_bigram].sum(), yi[is_bigram].sum()])[kind]
        nj = np.array([yj[~is_bigram].sum(), yj[is_bigram].sum()])[kind]
        with np.errstate(divide="ignore", invalid="ignore"):
            z = fightin_words(yi, ni, yj, nj, alpha)
        return np.where(z >= KEY_MIN_Z, z, 0.0)

    tot = np.asarray(x.sum(axis=0)).ravel().astype(np.float64)
    alpha = prior(tot, is_bigram)
    kind = is_bigram.astype(int)
    y = counts(members)
    subs = [i for i, w in enumerate(within or []) if w is not None]
    parent = dict(zip(subs, counts([within[i] for i in subs]))) if subs else {}
    words = np.asarray(vocab, dtype=object)
    out = []
    for i, yi in enumerate(y):
        w = z_over(yi, tot - yi) + (z_over(yi, parent[i] - yi) if i in parent else 0.0)
        k = np.flatnonzero(w > 0)
        out.append(dict(zip(words[k].tolist(), w[k].tolist())))
    return out


def excerpt_sets(p: np.ndarray, about: np.ndarray, lenses: list) -> tuple[list, np.ndarray]:
    """The candidate excerpts of each lens and of all UNODC lenses, (name, rows, lens of each row): every fragment
    about the lens, and for `all` every fragment about a UNODC lens, on its main one (of the lenses it is about, the
    most probable, a sub-lens on a tie). Also each fragment's main UNODC lens."""
    unodc = np.array([not lens["reference"] for lens in lenses])
    child = np.array([bool(lens.get("parent")) for lens in lenses])
    u_about = about & unodc
    u_best = np.where(u_about & (p == np.where(u_about, p, -1).max(axis=1, keepdims=True)), 1 + child, 0).argmax(axis=1)
    sets = [(lens["id"], np.flatnonzero(about[:, k]), np.full(int(about[:, k].sum()), k)) for k, lens in enumerate(lenses)]
    rows = np.flatnonzero(u_about.any(axis=1))
    return sets + [("all", rows, u_best[rows])], u_best


def about_order(p: np.ndarray, about: np.ndarray, first: int) -> list[int]:
    """The lenses a fragment is about (its row of p and of about): `first`, then the others, most probable first."""
    return [first, *(int(i) for i in np.argsort(-p, kind="stable") if about[i] and i != first)]


def excerpt_pick(s: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Positions of the excerpts kept: up to EXCERPTS per speech s, highest p first."""
    cand = pd.DataFrame({"s": s, "p": p, "i": np.arange(len(s))})
    return cand.sort_values(["s", "p", "i"], ascending=[True, False, True]).groupby("s").head(EXCERPTS)["i"].to_numpy()


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------

def percentile(pool: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Share of the pool at or below x, 0 to 100."""
    pool = np.sort(np.asarray(pool, dtype=np.float64))
    return np.rint(100 * np.searchsorted(pool, x, side="right") / max(1, len(pool))).astype(int)


def align(vecs: np.ndarray, owners: np.ndarray, groups: list) -> dict:
    """Alignment within one period, one unit row per country: the five most similar countries and the similarity
    to each group's centroid (the country itself left out; each member weighs the same), each also as a
    percentile among that period's pairs (countries) or country-group values (groups)."""
    vecs = np.asarray(vecs, dtype=np.float64)
    n = len(vecs)
    sim = vecs @ vecs.T
    pairs = sim[np.triu_indices(n, 1)]
    np.fill_diagonal(sim, -np.inf)
    top = np.argsort(-sim, axis=1, kind="stable")[:, :min(5, n - 1)]
    top_sim = np.take_along_axis(sim, top, axis=1)
    gsim = np.full((n, len(groups)), np.nan)
    for g, members in enumerate(groups):
        mem = np.isin(owners, members)
        if not mem.any():
            continue
        rest = vecs[mem].sum(axis=0)[None, :] - vecs * mem[:, None]
        norm = np.linalg.norm(rest, axis=1)
        ok = (mem.sum() - mem > 0) & (norm > 1e-9)
        gsim[ok, g] = (vecs[ok] * rest[ok]).sum(axis=1) / norm[ok]
    return {"top": top, "top_sim": top_sim, "top_pct": percentile(pairs, top_sim),
            "gsim": gsim, "g_pct": percentile(gsim[np.isfinite(gsim)], np.nan_to_num(gsim))}


def align_record(res: dict, a: int, codes_of_rows, slugs) -> dict:
    return {"top": [[codes_of_rows[b], int(p), round(float(s), 3)]
                    for b, p, s in zip(res["top"][a], res["top_pct"][a], res["top_sim"][a])],
            "groups": [[slugs[g], int(res["g_pct"][a, g]), round(float(res["gsim"][a, g]), 3)]
                       for g in range(len(slugs)) if np.isfinite(res["gsim"][a, g])]}


def alignment_file(v, u, has_u, owners, codes, group_members, slugs) -> dict:
    """{iso3: {overall, unodc}} for one period; v and u hold one unit row per country, owners their indexes."""
    out = {}
    o = align(v, owners, group_members)
    uu = np.flatnonzero(has_u)
    r = align(u[uu], owners[uu], group_members) if len(uu) >= 2 else None
    at_u = {a: k for k, a in enumerate(uu)}
    for a, c in enumerate(owners):
        out[codes[c]] = {"overall": align_record(o, a, [codes[x] for x in owners], slugs),
                         "unodc": align_record(r, at_u[a], [codes[x] for x in owners[uu]], slugs)
                         if r is not None and a in at_u else None}
    return out


def unit_rows(x: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(x, axis=1, keepdims=True)
    return x / np.where(norm > 0, norm, 1)


# ---------------------------------------------------------------------------
# Site
# ---------------------------------------------------------------------------

def country_table(codes) -> list[dict]:
    """meta.countries: names, map id, extra map features, a point for states too small to draw, and the
    historical names shown on hover."""
    table = pd.read_csv(config.COUNTRIES, keep_default_na=False, dtype=str).set_index("iso3")
    hist = pd.read_csv(config.HISTORICAL_NAMES, keep_default_na=False, dtype=str)
    out = []
    for code in codes:
        r = table.loc[code]
        out.append({"iso3": code, "es": r["name_es"], "en": r["name_en"], "map_id": r["map_iso_numeric"] or None,
                    "map_extra": [x for x in r["map_extra_features"].split(";") if x],
                    "point": [float(r["point_lat"]), float(r["point_lon"])] if r["point_lat"] else None,
                    "hist": [{"from": int(h.from_year), "to": int(h.to_year), "es": h.name_es, "en": h.name_en}
                             for h in hist[hist["iso3"] == code].itertuples()]})
    return out


def group_table() -> list[dict]:
    """The selector's groups (docs/PLAN.md, section 3.4): multi-country field offices (ROCOL first), the countries
    with no field office, then blocs and regions. Members as iso3 codes."""
    countries = pd.read_csv(config.COUNTRIES, keep_default_na=False, dtype=str)
    offices = pd.read_csv(config.META / "unodc_offices.csv", keep_default_na=False, dtype=str)
    blocs = pd.read_csv(config.GROUPS, keep_default_na=False, dtype=str)
    out = [{"id": acr, "slug": acr.lower(), "type": "office", "es": es, "en": en, "short_es": acr, "short_en": acr,
            "members": sorted(offices.loc[offices["office_acronym"] == acr, "iso3"])} for acr, (es, en) in OFFICES.items()]
    covered = set(offices.loc[~offices["office_acronym"].isin(HOST_ONLY), "iso3"])
    member = countries["un_member"].str.lower() == "true"
    out.append({**NOFIELD, "members": sorted(countries.loc[member & ~countries["iso3"].isin(covered), "iso3"])})
    for gid, (short_es, short_en) in BLOCS.items():
        rows = blocs[blocs["group_id"] == gid]
        out.append({"id": gid, "slug": gid.lower(), "type": rows["group_type"].iloc[0], "es": rows["name_es"].iloc[0],
                    "en": rows["name_en"].iloc[0], "short_es": short_es, "short_en": short_en,
                    "members": sorted(rows["iso3"])})
    return out


def lens_passes() -> dict:
    """Pass-bar result per fitted lens (docs/calibration.md, section 6), empty before `calibrate fit`."""
    if not calibrate.FIT.exists():
        return {}
    return {k: bool(v["pass"]) for k, v in json.loads(calibrate.FIT.read_text())["lenses"].items()}


def method_facts(codebook, n_all: int, n_ceremonial: int) -> dict | None:
    """What the technical annex states: how many fragments were read, and for every fitted lens the positive
    examples it learned from and its weighted out-of-fold precision, recall and F1. None before `calibrate fit`."""
    if not (calibrate.FIT.exists() and calibrate.FINAL.exists()):
        return None
    fit = json.loads(calibrate.FIT.read_text())
    agree = json.loads(calibrate.AGREEMENT.read_text()) if calibrate.AGREEMENT.exists() else {}
    labels = pd.read_parquet(calibrate.FINAL)

    lenses = []
    for lens in codebook["lenses"]:
        i = lens["id"]
        if i not in fit["lenses"]:
            continue
        f = fit["lenses"][i]
        lenses.append({"id": i, "es": lens["name_es"], "en": lens["name_en"], "icon": lens.get("icon"),
                       "parent": lens.get("parent"), "pass": f["pass"],
                       "examples": int(labels[i].sum()), **{m: f["overall"][m] for m in ("precision", "recall", "f1")}})
    return {"fragments_all": n_all, "ceremonial": n_ceremonial, "labelled": len(labels),
            "reference": [{"es": lens["name_es"], "en": lens["name_en"]} for lens in codebook["lenses"]
                          if lens["reference"]],
            "read_twice": agree.get("check_fragments"), "folds": calibrate.FOLDS, "bar": calibrate.PASS_BAR,
            "min_period": calibrate.MIN_PERIOD_POSITIVES, "lenses": lenses}


def hit_inputs(fid, ids) -> dict | None:
    """What the cards need beyond the probabilities (docs/data-contract.md, cards), None before `calibrate fit`. For
    each lens, its hit rate as the probability rises: a weighted isotonic fit of the labels on the labelled fragments'
    out-of-fold probabilities, kept as the points (x, y) that np.interp follows. For the fragments of `fid`, in that
    order, the labelled ones' out-of-fold probabilities (NaN for the others) and labels (-1 for the others)."""
    if not (calibrate.OOF.exists() and calibrate.FINAL.exists()):
        return None
    labels = pd.read_parquet(calibrate.FINAL, columns=["frag_id", "pi", *ids])
    lab = labels.merge(pd.read_parquet(calibrate.OOF, columns=["frag_id", *(f"p_{k}" for k in ids)]), on="frag_id",
                       validate="1:1")
    if len(lab) != len(labels):
        raise ExportError(f"{embed.rel(calibrate.OOF)} does not cover the labels; run `calibrate fit`.")
    w = 1 / lab["pi"].to_numpy()
    fits = [IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(lab[f"p_{k}"], lab[k], sample_weight=w)
            for k in ids]
    at = lab.set_index("frag_id").reindex(fid)
    return {"curves": [(f.X_thresholds_, f.y_thresholds_) for f in fits],
            "oof": at[[f"p_{k}" for k in ids]].to_numpy(np.float64), "read": at[list(ids)].fillna(-1).to_numpy(np.int8)}


def load_inputs(placeholder: bool = False) -> dict:
    """Everything `build` needs, aligned: fragments (non-ceremonial) in (iso3, year, seq) order, speeches in
    (iso3, year) order. Refuses stale caches."""
    codebook = load_lenses()
    f_emb, f_keys, f_man = calibrate.load_embeddings("fragments")
    h = f_man["input_hash"]
    speeches = pd.read_parquet(config.SPEECHES, columns=["speech_id", "iso3", "year", "speaker_name", "speaker_post"])
    speeches = speeches.sort_values(["iso3", "year"], kind="stable").reset_index(drop=True)
    frags = pd.read_parquet(config.FRAGMENTS, columns=["frag_id", "speech_id", "iso3", "year", "seq", "text",
                                                       "is_ceremonial"])
    n_all, n_ceremonial = len(frags), int(frags["is_ceremonial"].sum())
    frags = frags[~frags["is_ceremonial"]].sort_values(["iso3", "year", "seq"], kind="stable").reset_index(drop=True)
    fid = frags["frag_id"].to_numpy()
    p, source, thr = lens_probabilities(fid, h, placeholder, codebook)
    info = check_fresh(TOPICS, h)
    if info["probabilities"] != source:
        raise ExportError(f"The topics were made from {info['probabilities']} probabilities, not the current "
                          f"{source}; run `uv run python -m pipeline.export topics{' --placeholder' if placeholder else ''}`.")
    tp = pd.read_parquet(TOPICS).set_index("frag_id")["topic"]
    general = tp.reindex(fid).fillna(-1).to_numpy(np.int64)
    frow = pd.Series(np.arange(len(f_keys)), index=f_keys["frag_id"].to_numpy()).loc[fid].to_numpy()
    x, vocab = load_terms(fid, h)
    passes = lens_passes()
    return {
        "speeches": speeches, "frags": frags[["frag_id", "speech_id", "text"]], "P": p, "general": general,
        "femb": np.asarray(f_emb[frow]),
        "fxy": load_layout("fragments", fid, h), "sxy": load_layout("speeches", speeches["speech_id"].to_numpy(), h),
        "X": x, "vocab": vocab, "countries": country_table(sorted(speeches["iso3"].unique())),
        "groups": group_table(), "topics": topic_names(placeholder, info), "passes": passes, "thresholds": thr,
        "lenses": [lens for lens in codebook["lenses"] if not lens["reference"]],
        "method": None if placeholder else method_facts(codebook, n_all, n_ceremonial),
        "hits": None if placeholder else hit_inputs(fid, calibrate.fitted_ids(codebook)),
        "build": {"date": now()[:10], "corpus": "UNGDC v14 + provisional 2026", "model": config.MODEL_ID,
                  "placeholder": placeholder, "probabilities": source},
    }


def build(inp: dict) -> tuple[dict, dict]:
    """The site files (docs/data-contract.md) as {path: bytes}, and a summary."""
    sp, fr, lenses = inp["speeches"], inp["frags"], inp["lenses"]
    L, S, F = len(lenses), len(sp), len(fr)
    codes = [c["iso3"] for c in inp["countries"]]
    if codes != sorted(sp["iso3"].unique()):
        raise ExportError("The country table must list the speeches' countries, in iso3 order.")
    if sp.duplicated(["iso3", "year"]).any():
        raise ExportError("More than one speech for a country and year.")
    ci = {c: i for i, c in enumerate(codes)}
    C, Y = len(codes), LAST_YEAR - FIRST_YEAR + 1
    unodc = np.array([not lens["reference"] for lens in lenses])
    child = np.array([bool(lens.get("parent")) for lens in lenses])
    s_of = pd.Series(np.arange(S), index=sp["speech_id"].to_numpy()).loc[fr["speech_id"]].to_numpy()
    sc = sp["iso3"].map(ci).to_numpy(dtype=np.int64)
    sy = sp["year"].to_numpy() - FIRST_YEAR
    texts = fr["text"].tolist()
    groups = [{**g, "members": [ci[m] for m in g["members"] if m in ci]} for g in inp["groups"]]
    gmem = [np.array(g["members"], dtype=int) for g in groups]
    slugs = [g["slug"] for g in groups]
    files = {}

    # Shares and composition (docs/data-contract.md, Conventions)
    p = np.asarray(inp["P"], dtype=np.float32)
    about = p >= np.asarray(inp["thresholds"], dtype=np.float32)
    n_s = np.bincount(s_of, minlength=S)
    u_max = np.where(unodc, p, 0).max(axis=1)  # slot L, all UNODC topics: each fragment's highest UNODC-lens p
    share = np.column_stack([np.bincount(s_of, weights=w, minlength=S) for w in [*p.T, u_max]]) / np.maximum(n_s, 1)[:, None]
    share[n_s == 0] = np.nan
    shares = np.full((C, Y, L + 1), np.nan, dtype="<f4")
    shares[sc, sy] = share
    counts = np.zeros((C, Y), dtype="<u2")
    counts[sc, sy] = np.minimum(n_s, 65535)
    # of the lenses a fragment is about, the most probable; ties go to a sub-lens (umbrella)
    best = np.where(about & (p == np.where(about, p, -1).max(axis=1, keepdims=True)), 1 + child, 0)
    any_about = about.any(axis=1)
    general = np.asarray(inp["general"])
    n_general = len(inp["topics"])
    if (general[~any_about] < 0).any() or (general[~any_about] >= n_general).any():
        raise ExportError("Some fragments about no lens have no general topic; make the topics again.")
    topic = np.where(any_about, best.argmax(axis=1), L + general)
    T = L + n_general
    if T >= NO_TOPIC:
        raise ExportError(f"{T} topics do not fit the map files.")
    comp = np.zeros((S, T), dtype=np.int64)
    np.add.at(comp, (s_of, topic), 1)
    composition = {}
    for s in np.flatnonzero(n_s):
        order = np.argsort(-comp[s], kind="stable")
        composition.setdefault(codes[sc[s]], {})[str(FIRST_YEAR + sy[s])] = [
            [int(t), round(comp[s, t] / n_s[s], 3)] for t in order if comp[s, t]]
    files["shares.bin"] = shares.tobytes()
    files["frags.bin"] = counts.tobytes()
    files["composition.json"] = dumps(composition)

    # Maps
    bits = (about.astype(np.uint16) << np.arange(L, dtype=np.uint16)).sum(axis=1, dtype=np.uint16)
    s_bits = np.zeros(S, dtype=np.uint16)
    np.bitwise_or.at(s_bits, s_of, bits)
    s_topic = np.where(n_s > 0, comp.argmax(axis=1), NO_TOPIC)
    lo, hi = inp["fxy"].min(axis=0), inp["fxy"].max(axis=0)   # one frame: speeches sit on the fragments' map
    qf, qs = quantize(inp["fxy"], lo, hi), quantize(inp["sxy"], lo, hi)
    files["map_frag.bin"] = map_columns(x=qf[:, 0], y=qf[:, 1], c=sc[s_of], lensmask=bits, yr=sy[s_of], topic=topic)
    files["map_speech.bin"] = map_columns(x=qs[:, 0], y=qs[:, 1], c=sc, lensmask=s_bits, yr=sy, topic=s_topic)
    # a lens is named where the fragments about it gather, so a sub-lens, seldom a fragment's main topic, is named
    # too; a general topic where its fragments gather. The regions are the same on both layers
    anchors = label_anchors(qf, [*about.T, *(topic == t for t in range(L, T))])
    files["map_labels.json"] = dumps({"fragments": anchors, "speeches": anchors})

    # The hover passages come from where a fragment is most about its topic (window): the lenses weigh the terms of
    # the fragments about them (a sub-lens against the rest of its parent's), the general topics those of their
    # fragments. A passage of every fragment for the map's hover, one file per country in point order, on the
    # fragment's topic
    x, vocab = inp["X"], inp["vocab"]
    is_bigram = np.array([" " in w for w in vocab], dtype=bool)
    at = {lens["id"]: k for k, lens in enumerate(lenses)}
    parent_rows = [np.flatnonzero(about[:, k] | about[:, at[lens["parent"]]]) if lens.get("parent") else None
                   for k, lens in enumerate(lenses)]
    weights = topic_weights(x, [np.flatnonzero(about[:, k]) for k in range(L)]
                            + [np.flatnonzero(topic == t) for t in range(L, T)], vocab, is_bigram,
                            parent_rows + [None] * (T - L))
    f_country = sc[s_of]
    for c in range(C):
        rows = np.flatnonzero(f_country == c)
        if len(rows):
            files[f"snips/{codes[c]}.json"] = dumps([window(texts[r], weights[topic[r]], SNIP_CHARS) for r in rows])

    # Excerpts per lens, and across the UNODC lenses: every fragment about the lens, whole, with its probability on
    # the lens and every UNODC lens it is about (that lens first, then the others, most probable first). Up to three
    # per speech, the most probable, which the site orders by that probability
    u_about = about & unodc
    sets, u_best = excerpt_sets(p, about, lenses)
    top = {}   # each speech's most probable excerpt across the UNODC lenses, (probability, row), for its hover
    for name, rows, ks in sets:
        prob = p[rows, ks]
        out = {}
        for j in excerpt_pick(s_of[rows], prob):
            r, k, s = rows[j], int(ks[j]), s_of[rows[j]]
            out.setdefault(codes[sc[s]], {}).setdefault(str(FIRST_YEAR + sy[s]), []).append(
                [about_order(p[r], u_about[r], k), round(float(prob[j]), 4), " ".join(texts[r].split())])
            if name == "all" and prob[j] > top.get(s, (-1,))[0]:
                top[s] = (prob[j], r)
        files[f"excerpts/{name}.json"] = dumps(out)

    # A card for every fragment about a UNODC lens, opened from the map: its whole text, the UNODC lenses it is about
    # (its main one first, then the others, most probable first), the hit rate at its probability on each, and the
    # lenses the reader placed it under when it is a labelled fragment; with each year's speaker. A fragment is found
    # by its place among its country's fragment points
    who = [", ".join(v.strip() for v in (name, post) if isinstance(v, str) and v.strip())
           for name, post in zip(sp["speaker_name"], sp["speaker_post"])]
    cstart = np.searchsorted(f_country, np.arange(C))   # fragments are in country order
    hits = inp.get("hits")
    if hits is not None:
        # a labelled fragment's out-of-fold probability: the final classifiers learned its label and only repeat it
        p_hit = np.where(hits["read"][:, :1] >= 0, hits["oof"], p)
        tenths = np.column_stack([np.floor(10 * np.interp(p_hit[:, k], *hits["curves"][k]) + 0.5) for k in range(L)])
    cards = {}
    for r in np.flatnonzero(u_about.any(axis=1)):
        ls, c, s = about_order(p[r], u_about[r], int(u_best[r])), f_country[r], s_of[r]
        card = cards.setdefault(codes[c], {"who": {}, "frags": {}})
        card["who"][str(FIRST_YEAR + sy[s])] = who[s]
        card["frags"][str(r - cstart[c])] = [
            ls, None if hits is None else [int(tenths[r, k]) for k in ls],
            [] if hits is None else [k for k in ls if hits["read"][r, k] == 1], " ".join(texts[r].split())]
    for code, card in cards.items():
        files[f"cards/{code}.json"] = dumps(card)

    # Each speech as the mean of its fragments' vectors (docs/PLAN.md, section 4), which measures the alignment below.
    # Its passage on hover: of its most probable excerpt across the UNODC lenses, on that excerpt's lens; without
    # one, of the fragment closest to that mean outside the speech's first and last (often greetings), in a speech
    # of three or more, on its topic
    femb = inp["femb"]
    per_speech = sparse.csr_matrix((np.ones(F, dtype=np.float32), (s_of, np.arange(F))), shape=(S, F)).tocsc()
    semb = np.zeros((S, femb.shape[1]), dtype=np.float32)
    for a in range(0, F, 65536):
        semb += per_speech[:, a:a + 65536] @ np.asarray(femb[a:a + 65536], dtype=np.float32)
    semb = unit_rows(semb)
    sims = np.empty(F, dtype=np.float32)
    for a in range(0, F, 65536):
        sims[a:a + 65536] = np.einsum("ij,ij->i", np.asarray(femb[a:a + 65536], dtype=np.float32),
                                      semb[s_of[a:a + 65536]])
    edge = np.r_[True, s_of[1:] != s_of[:-1]] | np.r_[s_of[1:] != s_of[:-1], True]   # fragments are in speech order
    rep = pd.Series(np.where(~edge | (n_s[s_of] < 3), sims, -np.inf)).groupby(s_of).idxmax()
    speeches = {}
    for s, row in enumerate(sp.itertuples(index=False)):
        if s in top:
            r = top[s][1]
            entry = [who[s], window(texts[r], weights[u_best[r]], REP_CHARS), int(u_best[r]),
                     int(r - cstart[f_country[r]])]
        elif s in rep.index:
            entry = [who[s], window(texts[rep[s]], weights[topic[rep[s]]], REP_CHARS), -1, -1]
        else:
            entry = [who[s], "", -1, -1]
        speeches.setdefault(row.iso3, {})[str(row.year)] = entry
    files["speeches.json"] = dumps(speeches)

    # Alignment per year and over all years (all fragments; UNODC-lens fragments)
    urows = np.flatnonzero(u_about.any(axis=1))
    one = sparse.csr_matrix((np.ones(len(urows), dtype=np.float32), (s_of[urows], np.arange(len(urows)))),
                            shape=(S, len(urows)))
    u = unit_rows(one @ np.asarray(femb[urows], dtype=np.float32))
    has_u = np.bincount(s_of[urows], minlength=S) > 0
    for y in range(Y):
        ss = np.flatnonzero(sy == y)
        if len(ss) >= 2:
            files[f"alignment/{FIRST_YEAR + y}.json"] = dumps(
                alignment_file(semb[ss], u[ss], has_u[ss], sc[ss], codes, gmem, slugs))
    cv, cu = np.zeros((C, semb.shape[1])), np.zeros((C, semb.shape[1]))
    np.add.at(cv, sc, semb)
    np.add.at(cu, sc[has_u], u[has_u])
    present = np.flatnonzero(np.bincount(sc, minlength=C))
    cu_ok = np.bincount(sc[has_u], minlength=C)[present] > 0
    files["alignment/all.json"] = dumps(alignment_file(unit_rows(cv[present]), unit_rows(cu[present]), cu_ok,
                                                       present, codes, gmem, slugs))

    # Distinctive words per lens, and across the UNODC lenses
    selections = [(g["slug"], g["members"]) for g in groups] + [(code, [c]) for c, code in enumerate(codes)]
    periods = [("all", np.ones(S, dtype=bool))] + [(str(FIRST_YEAR + y), sy == y) for y in range(Y)]
    masks = [(lens["id"], about[:, k]) for k, lens in enumerate(lenses)] + [("all", u_about.any(axis=1))]
    for name, mask in masks:
        rows = np.flatnonzero(mask)
        per_speech = sparse.csr_matrix((np.ones(len(rows)), (s_of[rows], np.arange(len(rows)))), shape=(S, len(rows)))
        files[f"keyness/{name}.json"] = dumps(keyness((per_speech @ x[rows]).tocsr(), sc, C, periods, selections,
                                                      vocab, is_bigram))

    passes = inp.get("passes", {})
    meta = {
        "build": {**inp["build"], "n_speeches": S, "n_fragments": F},
        "years": {"first": FIRST_YEAR, "last": LAST_YEAR, "provisional": PROVISIONAL},
        "countries": inp["countries"],
        "groups": [{k: g[k] for k in ("id", "slug", "type", "es", "en", "short_es", "short_en", "members")}
                   for g in groups],
        "lenses": [{"id": lens["id"], "icon": lens["icon"], "es": lens["name_es"], "en": lens["name_en"],
                    "reference": bool(lens["reference"]), "pass": passes.get(lens["id"])} for lens in lenses],
        "topics": [{"id": lens["id"], "es": lens["name_es"], "en": lens["name_en"], "kind": "lens"} for lens in lenses]
                  + [{**t, "kind": "general"} for t in inp["topics"]],
        "binaries": {
            "shares.bin": {"dtype": "float32", "shape": [C, Y, L + 1], "all_slot": L},
            "frags.bin": {"dtype": "uint16", "shape": [C, Y]},
            "map_frag.bin": {"columns": [[n, np.dtype(t).name] for n, t in MAP_COLUMNS], "count": F},
            "map_speech.bin": {"columns": [[n, np.dtype(t).name] for n, t in MAP_COLUMNS], "count": S},
        },
        "keyness": {"top": KEY_TOP, "min_tokens": KEY_MIN_TOKENS, "min_count": KEY_MIN_COUNT,
                    "min_spread": KEY_MIN_SPREAD, "min_z": KEY_MIN_Z},
        "method": inp.get("method"),
    }
    files["meta.json"] = dumps(meta)
    summary = {"speeches": S, "fragments": F, "countries": C, "topics": T, "about_share": round(float(any_about.mean()), 4),
               "files": len(files)}
    return files, summary


def check_budget(files: dict) -> dict:
    start = sum(len(gzip.compress(files[f], 6)) for f in START_FILES)
    total = sum(len(b) for b in files.values())
    if start > START_BUDGET or total > TOTAL_BUDGET:
        raise ExportError(f"Size budget exceeded: start-up {start:,} gzip bytes (limit {START_BUDGET:,}), "
                          f"total {total:,} bytes (limit {TOTAL_BUDGET:,}).")
    return {"start_gzip": start, "total": total}


def write_site(files: dict, out=None) -> None:
    """Write the files into a fresh directory, then swap it in for site/data."""
    out = out or config.SITE_DATA
    tmp, old = out.with_name(out.name + ".tmp"), out.with_name(out.name + ".old")
    for d in (tmp, old):
        if d.exists():
            shutil.rmtree(d)
    for rel_path, data in files.items():
        path = tmp / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    if out.exists():
        out.rename(old)
    tmp.rename(out)
    if old.exists():
        shutil.rmtree(old)


def site(placeholder: bool = False) -> dict:
    files, summary = build(load_inputs(placeholder))
    sizes = check_budget(files)
    write_site(files)
    largest = sorted(files, key=lambda f: -len(files[f]))[:8]
    return {**summary, **sizes, "placeholder": placeholder,
            "largest": {f: len(files[f]) for f in largest},
            "sha256_meta": hashlib.sha256(files["meta.json"]).hexdigest()[:16]}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="uv run python -m pipeline.export", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("terms", help="word and two-word counts of every fragment")
    p_layout = sub.add_parser("layout", help="the map: fragments fitted once, new ones and speeches placed on it")
    p_layout.add_argument("kind", choices=list(LAYOUTS))
    p_layout.add_argument("--refit", action="store_true", help="fit a new edition of the fragments map")
    p_topics = sub.add_parser("topics", help="general topics over the fragments about no lens")
    p_topics.add_argument("--placeholder", action="store_true", help="sampling scores in place of probabilities")
    p_topics.add_argument("--refit", action="store_true", help="fit a new edition of the topics (to be named again)")
    p_site = sub.add_parser("site", help="write site/data/")
    p_site.add_argument("--placeholder", action="store_true", help="sampling scores in place of probabilities")
    args = parser.parse_args(argv)
    try:
        if args.command == "terms":
            out = make_terms()
        elif args.command == "layout":
            out = make_layout(args.kind, args.refit)
        elif args.command == "topics":
            out = make_topics(args.placeholder, args.refit)
        else:
            out = site(args.placeholder)
        print(json.dumps(out, indent=2, ensure_ascii=False))
    except (ExportError, calibrate.CalibrationError, embed.EmbedError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
