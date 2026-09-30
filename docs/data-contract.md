# Site data contract

This contract sits between the pipeline export (`pipeline/export.py`, which writes `site/data/`) and the front end (`site/`). The front end reads only these files. The export writes only these files. Every file is static, served by GitHub Pages, and fetched lazily where noted.

## Conventions

- **Indexes.**
  - `c`: a country index, a position in `meta.countries`.
  - `y`: a year index, `year - 1946`. The provisional year is the last index.
  - `l`: a lens index, a position in `meta.lenses`.
  - `t`: a topic index, a position in `meta.topics`. Topic slot values are `0..L-1` for lenses, followed by the general topics.
- **Shares** are fractions in `[0, 1]` of a speech's fragments, ceremonial fragments left out (`docs/PLAN.md`, sections 4 and 4.1).
  - A lens **share** is the mean, over those fragments, of each fragment's calibrated probability of being about that lens (graded shares, `docs/calibration.md`, section 5). Shares are multi-label, so they need not sum to 1 across lenses.
  - A fragment is **about** a lens when its probability is 0.5 or more.
  - **Composition** is single-assignment over the same fragments:
    - a fragment about one or more lenses goes to the lens with the highest probability;
    - otherwise it goes to its general topic;
    - composition parts sum to 1 per speech.
- **Group values** give each country the same weight: a group's value for a year is the mean of its members' shares that year, and for a period it is the mean, over members, of each member's mean over the years it spoke. The value for "world" does the same over all countries. Speech length and the number of speeches never weigh.
- **Passages** (the excerpts and the map's hover) show the part of a fragment most about the topic they illustrate, not a set key term:
  - each term weighs its Fightin' Words z-score (as for the word bars) in the topic's fragments against all the other fragments, where it is at least 1.96: the fragments about a lens, or those of a general topic. A sub-lens is set against the rest of its parent lens's fragments, so that an alternative development passage shows what sets it apart from drugs at large;
  - a candidate passage starts at a sentence, or at a clause of a sentence too long to show whole (then after "… "), and runs to the last sentence end that fits, or is cut at a word (then ends with " …");
  - it has at least half its maximum length, so it is never a greeting alone; a fragment shorter than the maximum is shown whole;
  - the candidate whose terms weigh most is shown; on a tie, the one that starts nearest those terms; when no term weighs, the first.
- **Missing values** are `null`. A missing value means there is no speech or the text is too little to measure. Missing is never shown as 0.
- **Binaries** are little-endian typed arrays. Each binary's layout is described in `meta.binaries`.
- **Text** fields hold original English and are never translated. Every UI string lives in `site/i18n/{es,en}.json`, not here.

## Files

### `meta.json` (loaded at start)

| Key | What it holds |
| --- | --- |
| `build` | `{date, corpus: "UNGDC v14 + provisional 2026", model: "microsoft/harrier-oss-v1-0.6b", placeholder: bool, probabilities, n_speeches, n_fragments}`. `n_fragments` counts the measured (non-ceremonial) fragments. `placeholder: true` marks a development build whose probabilities stand in for the calibrated ones; the site shows a banner and such a build is never published. |
| `years` | `{first: 1946, last: 2026, provisional: [2026]}`. "All years" means `first` to `last`, the provisional year included. The site shows the provisional year like any other, with no label (`docs/PLAN.md`, section 2). |
| `countries` | `[{iso3, es, en, map_id, map_extra: [...], point: [lat, lon] \| null, hist: [{from, to, es, en}]}]`, in iso3 order. `map_id` is the world-atlas numeric id, or `null` when the country has no polygon (a small state, which has a `point`, or CSK, DDR, YUG, YMD, EU). `map_extra` names further world-atlas features drawn with the country (for example Kosovo with Serbia). `hist` holds the historical names shown on hover. |
| `groups` | `[{id, slug, type: "office"\|"nofield"\|"bloc"\|"region", es, en, short_es, short_en, members: [c...]}]`. `slug` drives deep links (`#rocol`, `#ropan`). ROCOL comes first and is the default selection; the other multi-country offices follow, then the countries with no field office, then blocs and regions. |
| `lenses` | `[{id, icon, es, en, reference: bool, pass: bool \| null}]`, in strip order. `peace` has `reference: true`. `pass` is the calibration pass bar (`docs/calibration.md`, section 6); a lens with `pass: false` gets no trend line and no map. `null` means not yet tested; while any lens is untested, the site shows a small "preliminary" badge. |
| `topics` | `[{id, es, en, kind: "lens"\|"general"}]` |
| `binaries` | The name, dtype and shape (or columns and count) of each `.bin` file below. |
| `keyness` | `{top, min_tokens, min_count, min_z}`, the word-bar settings. |

### `shares.bin` (loaded at start)

- A `Float32` array of shape `[C, Y, L + 1]`, holding the lens share per country and year. It is `NaN` when there is no speech that year.
- Slot `L` is "all UNODC topics": the mean, over the speech's fragments, of each fragment's highest probability among the UNODC lenses (peace, the reference, left out).
- The front end computes any group or period value from it as the equal-weight mean described under Conventions.
- A companion `frags.bin`, `Uint16` `[C, Y]`, holds the number of fragments behind each share (ceremonial ones left out). It is shown in tooltips and used by QA; it never weights a mean.

### `map_frag.bin` and `map_speech.bin` (loaded at start)

One point per fragment or speech, 10 bytes each, stored one column after another in the order below (little-endian), so that every column starts at an even offset and loads as a typed array. Columns compress about a third smaller than one record per point. Ceremonial fragments are not drawn.

| Column | Type |
| --- | --- |
| `x` | `Uint16`, position on the map, quantized in the fragments' frame |
| `y` | `Uint16`, position on the map, quantized in the fragments' frame |
| `c` | `Uint16`, country |
| `lensmask` | `Uint16`, bit `l` set if the fragment is about lens `l` (for a speech point: if any of its fragments is) |
| `yr` | `Uint8`, year index |
| `topic` | `Uint8`, the composition assignment (for a speech point: its largest composition part; 255 when it has no measured fragment) |

- Fragment points are in country, year and speech order. Speech points are in country and year order.
- Both files share one frame: each speech is placed on the fragments' map from the mean of its fragments' vectors, so a position means the same on both layers.
- `map_labels.json` holds `{fragments: [{t, x, y, n}], speeches: [...]}`: where each topic's name is written (the mean of its fragments around their densest cell, `x` and `y` from 0 to 1 like the quantized positions), and `n`, its number of fragments, for label priority. Both layers carry the same list.

### `speeches.json` (lazy, with the Speeches layer or the Country tab)

- Shape: `{ "<iso3>": { "<year>": ["<speaker, post>", "<passage>", l] } }`.
- The passage shown on hover, of 110 to 220 characters (see Passages): from the speech's fragment about a UNODC lens with the highest probability, on that lens, with `l` that lens; in a speech with no such fragment, from the fragment nearest the mean of the speech's fragment vectors, leaving out its first and last fragments (often greetings) when it has three or more, on that fragment's topic, with `l` = -1.
- The site publishes short passages only (this file, the fragment passages and the excerpts), never whole speeches: the corpus itself is cited, not committed (`docs/PLAN.md`, section 5).

### `snips/<iso3>.json` (lazy, on hover over a fragment point)

- One passage per fragment point of the country, in point order (a country's points are consecutive in `map_frag.bin`).
- The passage is on the fragment's topic (its composition assignment), of 90 to 180 characters (see Passages).

### `composition.json` (loaded with the Country tab)

- Shape: `{ "<iso3>": { "<year>": [[t, share], ...] } }`.
- Entries are sorted by share. The front end shows the top 5 plus "Others".

### `alignment/<year>.json` (lazy, per year)

`{ "<iso3>": { overall: {...}, unodc: {...} \| null } }`, and `alignment/all.json` for all years, where each country is the mean of its speech vectors. A speech's vector is the mean of its fragments' vectors.

Each of `overall` and `unodc` holds:
- `top`: `[[iso3, pct, raw], ...]`, the five most similar countries;
- `groups`: `[[slug, pct, raw], ...]`, every group with at least one other member that year.

What the two measures use:
- `overall` uses the mean vector of all the speech's fragments.
- `unodc` uses the mean vector of the speech's fragments about a UNODC lens (peace, the reference, left out). It is `null` when the speech has none.
- A group's vector is the centroid of its members' vectors, the country itself left out, each member weighing the same.
- `pct` is the percentile within the period: among all country pairs for `top`, among all country-group values for `groups`, so that it reads as "more aligned than N% of pairs". `raw` is the cosine, kept for QA.

### `excerpts/<lens>.json` (lazy, per lens)

- Shape: `{ "<iso3>": { "<year>": [[l, p, "passage"], ...] } }`, one file per lens and `excerpts/all.json` across the UNODC lenses (peace left out), where `l` is the lens with the highest probability.
- Holds up to 3 fragments per country-year about that lens, highest probability `p` first.
- Each passage is on its lens, of 150 to 300 characters (see Passages).
- Group and period excerpts are picked on the client from the members' candidates by probability. To keep variety, there is at most one per country.

### `keyness/<lens|all>.json` (lazy)

- Shape: `{ "<group slug|iso3>": { "all": {...}, "<year>": {...} } }`.
- `keyness/all.json` covers the fragments about any UNODC lens (peace left out); the other files one lens each. The period `all` covers every year.
- Each entry holds `{ words: [[term, z, count], ...], bigrams: [[term, z, count], ...] }`: up to 12 terms each by Fightin' Words z-score (log-odds with an informative Dirichlet prior, prior size 1,000, from the lens's own text over all years), selection against the rest of the world, same lens and period. A term needs a count of at least 3 in the selection and z of at least 1.96. The selection's text is pooled over its members.
- Terms are single words and two-word phrases of adjacent words in the same clause, after removing stopwords, UN boilerplate and country names and demonyms (`pipeline/export.py`).
- An entry is omitted when the selection has fewer than 200 single words on the lens in the period, or when no term passes. The UI then shows a short "not enough text" state.

## Size budget

- Start-up payload: under 8 MB after gzip.
- Total `site/data`: under 400 MB.
- The export prints sizes and fails if the budget is exceeded.
- Host: GitHub Pages. A published site may be up to 1 GB, with a soft bandwidth limit of 100 GB a month and a 10-minute deployment limit ([GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)). Pages compresses every file on the fly with gzip, binary files included, but not with Brotli, and caches for 10 minutes (`cache-control: max-age=600`), as seen in its response headers on 2026-09-29. Files are therefore published uncompressed, and the sizes above are measured after gzip.
