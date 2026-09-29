# Lens labelling: brief for the agents

## Purpose

This is the checked sample of the lens calibration (`docs/calibration.md`). One labeller, the core labeller, reads every fragment. A second labeller then labels a check set of about 600 of them independently, and a resolver decides the lenses on which the two differ. The dashboard's automatic measure is judged against the result, so each label must follow the codebook exactly and come from reading the text.

## Read first, in full

1. `data/lenses/codebook.md` (version 1.2): the rules, the examples and the output format (section 9).
2. `data/lenses/lenses.yaml`: the definitions, include and exclude lists and era vocabulary.

If the two differ, follow the codebook and say so in the record's `note`. Where the codebook itself says that it refines the YAML (as 4.10 does for disarmament), follow it without a note.

## Rules for every agent

- **Decide by reading.** Decide each fragment by reading it in full. Scripts may read files, count, check and write your records. They must never choose a label, whether by keyword rules, similarity scores or any other automatic means.
- **Stay blind.** Use only your input file, the codebook and the lens file. Do not open:
  - `data/gold/sample.parquet`, `data/gold/manifest.json`, the other labellers' folders, `data/gold/pilot-v1.1/` or `data/interim/`;
  - the corpus, the speeches or any other source;
  - any web search.

  Do not try to find out a fragment's country, speaker or source.
- **Only your own files.** Write only your output file. Do not start other agents.

## Labellers

Both labellers follow the same rules. Only their files differ.

| Labeller | Input | Output |
| --- | --- | --- |
| `core` | `data/gold/batches/<batch>.jsonl` | `data/gold/labels/core/<batch>.jsonl` |
| `check` | `data/gold/check/<batch>.jsonl` | `data/gold/labels/check/<batch>.jsonl` |

- **Input:** one fragment per line: `{"frag_id", "year", "text"}`.
- **Output:**
  - One record per input line, in the same order.
  - Each record has exactly the fields of codebook section 9.
  - `lenses` is `[]` when no lens applies. This is the most common answer.
- **Check:** before finishing, go through the checklist of codebook section 9, then run:

  ```
  uv run python -m pipeline.calibrate check labels <labeller>/<batch>
  ```

  Repair every problem it lists.

## Resolver

- **Input:** `data/gold/resolve/<file>.jsonl`, one fragment per line: `{"frag_id", "year", "text", "lenses", "records"}`.
  - `lenses` names the lenses on which the two labellers differ.
  - `records` holds their two records, in no particular order.
- **Decide** each named lens yourself by the codebook, reading the fragment in full.
  - The labellers' notes are arguments, not votes; the rules decide.
  - Record `substantive`, `list` or `none` for each named lens.
  - If `prevention_treatment` or `alternative_development` is `substantive`, `drugs` becomes `substantive` automatically (umbrella rule).
- **Output:** `data/gold/resolved/<file>.jsonl`, one record per input line, in the same order: `{"frag_id", "decisions": {"<lens>": "substantive" | "list" | "none", ...}, "note"}`.
  - `decisions` covers exactly the named lenses.
  - `note` is one short sentence giving the deciding rule (codebook section number) where the case was close, and `""` otherwise.
- **Check:** run `uv run python -m pipeline.calibrate check resolved <file>` and repair every problem it lists.

## Final message

Keep it under 100 words:
- the file done;
- the number of fragments with at least one lens (labellers) or the number of lenses decided each way (resolver);
- any rule you found unclear or contradictory, with the fragment id.
