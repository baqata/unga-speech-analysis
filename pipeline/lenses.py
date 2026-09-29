"""Load and validate the UNODC lens codebook (data/lenses/lenses.yaml).

Usage:
    from pipeline.lenses import load_lenses
    codebook = load_lenses()
    for lens in codebook["lenses"]:
        print(lens["id"], len(lens["anchors"]))

Run `uv run python -m pipeline.lenses` to validate the file and print a summary.

Umbrella rule: a sub-lens (field `parent`) implies its parent. Apply it with
expand_labels (coded or predicted labels) and expand_scores (model scores), so
that calibration and export count the parent the same way.
"""
import re
from pathlib import Path

import numpy as np
import yaml

from pipeline.config import LENSES

LENSES_YAML = LENSES / "lenses.yaml"

# Tabler icon names approved for the UI (one per lens).
APPROVED_ICONS = {
    "pill", "heart-handshake", "plant-2", "affiliate", "coins",
    "shield-exclamation", "users-group", "trees", "gavel", "peace",
}

STRING_FIELDS = ["id", "name_es", "name_en", "label_es", "label_en", "icon", "definition_en"]
LIST_FIELDS = ["include", "exclude", "era_terms", "anchors"]
REQUIRED_FIELDS = STRING_FIELDS + LIST_FIELDS + ["reference"]
OPTIONAL_FIELDS = ["parent"]

MIN_ANCHORS, MAX_ANCHORS = 5, 8
MIN_ANCHOR_WORDS, MAX_ANCHOR_WORDS = 30, 70

ID_PATTERN = re.compile(r"^[a-z][a-z_]*$")


class LensError(ValueError):
    """The lens file is malformed; the message lists every problem found."""


def word_count(text):
    """Whitespace-delimited word count, the unit used for anchor limits."""
    return len(text.split())


def validate(data):
    """Raise LensError listing all problems in a parsed lens file."""
    errors = []
    if not isinstance(data, dict):
        raise LensError("top level must be a mapping with 'query_instruction' and 'lenses'")

    instruction = data.get("query_instruction")
    if not isinstance(instruction, str) or not instruction.startswith("Instruct: ") \
            or not instruction.endswith("\nQuery: "):
        errors.append("query_instruction must look like 'Instruct: ...\\nQuery: '")

    lenses = data.get("lenses")
    if not isinstance(lenses, list) or not lenses:
        raise LensError("\n".join(errors + ["'lenses' must be a non-empty list"]))

    seen_ids, seen_icons, seen_anchors = set(), set(), set()
    for i, lens in enumerate(lenses):
        where = f"lens #{i + 1}"
        if not isinstance(lens, dict):
            errors.append(f"{where}: must be a mapping")
            continue
        if isinstance(lens.get("id"), str):
            where = f"lens '{lens['id']}'"

        missing = [f for f in REQUIRED_FIELDS if f not in lens]
        unknown = [f for f in lens if f not in REQUIRED_FIELDS + OPTIONAL_FIELDS]
        if missing:
            errors.append(f"{where}: missing fields {missing}")
        if unknown:
            errors.append(f"{where}: unknown fields {unknown}")

        for field in STRING_FIELDS:
            value = lens.get(field)
            if field in lens and (not isinstance(value, str) or not value.strip()):
                errors.append(f"{where}: '{field}' must be a non-empty string")
        for field in LIST_FIELDS:
            value = lens.get(field)
            if field in lens and (not isinstance(value, list) or not value
                                  or not all(isinstance(v, str) and v.strip() for v in value)):
                errors.append(f"{where}: '{field}' must be a non-empty list of strings")
        if "reference" in lens and not isinstance(lens["reference"], bool):
            errors.append(f"{where}: 'reference' must be true or false")

        lens_id = lens.get("id")
        if isinstance(lens_id, str):
            if not ID_PATTERN.match(lens_id):
                errors.append(f"{where}: id must be lowercase letters and underscores")
            if lens_id in seen_ids:
                errors.append(f"{where}: duplicate id")
            seen_ids.add(lens_id)

        icon = lens.get("icon")
        if isinstance(icon, str):
            if icon not in APPROVED_ICONS:
                errors.append(f"{where}: icon '{icon}' is not in the approved list")
            elif icon in seen_icons:
                errors.append(f"{where}: icon '{icon}' is already used by another lens")
            seen_icons.add(icon)

        anchors = lens.get("anchors")
        if isinstance(anchors, list):
            if not MIN_ANCHORS <= len(anchors) <= MAX_ANCHORS:
                errors.append(f"{where}: needs {MIN_ANCHORS}-{MAX_ANCHORS} anchors, has {len(anchors)}")
            for j, anchor in enumerate(anchors, 1):
                if not isinstance(anchor, str):
                    continue
                n = word_count(anchor)
                if not MIN_ANCHOR_WORDS <= n <= MAX_ANCHOR_WORDS:
                    errors.append(f"{where}: anchor {j} has {n} words "
                                  f"(allowed {MIN_ANCHOR_WORDS}-{MAX_ANCHOR_WORDS})")
                if anchor in seen_anchors:
                    errors.append(f"{where}: anchor {j} duplicates another anchor")
                seen_anchors.add(anchor)

    # A parent must be another top-level lens (one level of nesting only).
    by_id = {l["id"]: l for l in lenses if isinstance(l, dict) and isinstance(l.get("id"), str)}
    for lens_id, lens in by_id.items():
        parent = lens.get("parent")
        if parent is None:
            continue
        if parent == lens_id or parent not in by_id:
            errors.append(f"lens '{lens_id}': parent '{parent}' is not another lens id")
        elif by_id[parent].get("parent") is not None:
            errors.append(f"lens '{lens_id}': parent '{parent}' must not have a parent itself")

    if errors:
        raise LensError("\n".join(errors))


def load_lenses(path=LENSES_YAML):
    """Read, validate and return the lens file as a dict.

    Returns {"query_instruction": str, "lenses": [lens dict, ...]} with lenses
    in display order.
    """
    with open(Path(path), encoding="utf-8") as f:
        data = yaml.safe_load(f)
    validate(data)
    return data


def parent_map(codebook=None):
    """{sub-lens id: parent id}, e.g. {"prevention_treatment": "drugs", ...}."""
    codebook = codebook or load_lenses()
    return {l["id"]: l["parent"] for l in codebook["lenses"] if l.get("parent")}


def expand_labels(mention_type, codebook=None):
    """Apply the umbrella rule to one fragment's labels.

    mention_type maps lens id -> "substantive" or "list" (the codebook output
    field). Each parent of a labelled sub-lens is added, or upgraded, so that its
    type is at least as strong as the sub-lens's. Returns a new dict in display order.
    """
    codebook = codebook or load_lenses()
    out = dict(mention_type)
    for child, parent in parent_map(codebook).items():
        if child in out:
            types = {out[child], out.get(parent)}
            out[parent] = "substantive" if "substantive" in types else "list"
    order = [l["id"] for l in codebook["lenses"]]
    return {i: out[i] for i in order if i in out}


def expand_scores(scores, codebook=None):
    """Apply the umbrella rule to model scores or probabilities.

    scores maps lens id -> a number or an array with one value per fragment. Each
    parent's score becomes the maximum of its own and its sub-lenses' scores, the
    smallest value consistent with "sub-lens implies parent". Returns a new dict.
    """
    out = dict(scores)
    for child, parent in parent_map(codebook).items():
        if child in out:
            out[parent] = np.maximum(out.get(parent, out[child]), out[child])
    return out


if __name__ == "__main__":
    codebook = load_lenses()
    for lens in codebook["lenses"]:
        words = [word_count(a) for a in lens["anchors"]]
        print(f"{lens['id']:<24} {lens['icon']:<19} anchors={len(words)} "
              f"words={min(words)}-{max(words)} era_terms={len(lens['era_terms'])}"
              + (" (reference)" if lens["reference"] else "")
              + (f" parent={lens['parent']}" if lens.get("parent") else ""))
    print(f"OK: {len(codebook['lenses'])} lenses in {LENSES_YAML.relative_to(LENSES.parents[1])}")
