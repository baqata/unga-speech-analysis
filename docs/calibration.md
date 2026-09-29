# Lens calibration protocol

This protocol implements `docs/PLAN.md`, section 4.1: the single method the user approved on 2026-09-29 (05:02 UTC), with its numbers and formulas fixed before any fragment is labelled. On 2026-09-29 (16:30 UTC) the user enlarged the sample to about 20,000 fragments to train and tune the classifiers and about 5,000 more to validate them; every part of the design was scaled by 2.5. On 2026-09-29 (21:56 UTC) the user replaced the three labellers and their resolver with one labeller and a targeted check (section 4). The labelling rules are `data/lenses/codebook.md` (version 1.2) and the lens descriptions are `data/lenses/lenses.yaml`. The code is `pipeline/calibrate.py`; the sample, the labels and the results are in `data/gold/`.

## 1. Population and periods

- **Population U.** Every fragment of `data/interim/fragments.parquet` that is not ceremonial (`is_ceremonial` false), from the prepare run on the final tidy copies.
- **Periods.** P1 1946–1969, P2 1970–1989, P3 1990–2009, P4 2010–2024, P5 2025–2026. N_p is the number of fragments of U in period p.
- **Target class.** A fragment is positive for a lens when the lens applies as `substantive` (codebook, section 3.2), after the umbrella rule (`expand_labels`). A lens that applies only as `list` is negative.

## 2. Sampling score

- **Items.** Each fragment, embedded as a document without a prompt. Sentences are not embedded separately (user decision, 2026-09-29 03:47 UTC: too much overhead).
- **Lens vectors.** q_L, the embedding of `query_instruction + definition_en` (a query), and a_L1 … a_Lk, the embeddings of the lens's anchor passages (documents without a prompt).
- **Score.** s_L(f) = (z(cos(f, q_L)) + z(max_j cos(f, a_Lj))) / 2, where z standardizes over U.
- **Use.** s_L decides where the sample is drawn (section 3) and which negatives enter the check set (section 4). It plays no part in the classifiers or the shares.

## 3. Sample

Each fragment of U has a known inclusion probability π(f) and is drawn independently (Poisson sampling): f is in the sample when a seeded uniform draw u(f) is below π(f). Seed: 20260929.

1. **Random (R).** π_R(f) = 500 / N_p for a fragment of period p: 500 per period, 2,500 in all.
2. **Lens strata (S).** For each lens L and period p, 180 draws are planned:
   - 150 where the lens is most likely. The fragments of p are ranked by s_L, highest first, and q = rank / N_p. The top 8/25 is cut into six bins at q = 1/100, 1/50, 1/25, 2/25, 4/25 and 8/25, with 25 draws planned in each; a fragment in a bin of n fragments gets 25 / n. Most draws therefore fall near the top, where the positives are.
   - 30 lower down, to catch what the similarity misses: K_Lp holds the fragments of p outside the top 8/25 that contain one of the lens's `era_terms` (without any parenthetical qualifier, case-insensitive, at word boundaries), and each gets 30 / |K_Lp|.
3. **Scaling.** Strata overlap, because one fragment can rank high for several lenses. The planned rates of part S are multiplied by one factor λ, and each rate is capped at 1, so that the expected size of the whole sample is 25,000:

   π(f) = 1 − (1 − π_R(f)) · Π over (L, stratum) of (1 − min(1, λ · r_L(f))),

   where r_L(f) is the fragment's planned rate in the stratum of lens L it belongs to (0 when it is in none).

The sample file records, for every sampled fragment, π(f), π_R(f), π_S(f), its speech and the set it belongs to.

## 4. Labels

- **Training and validation sets.** A second seeded uniform, drawn per speech, puts one speech in five into the validation set: all the sampled fragments of those speeches, about 5,000. The other fragments, about 20,000, form the training set. Splitting by speech keeps fragments of one speech from appearing on both sides.
- **Order.** The validation batches come first, so that the validation set is complete even if the labelling of the training set stops early. Any run of consecutive training batches is itself a random part of the training set.
- **Core labeller.** One agent (Opus, medium effort) labels every sampled fragment, following the codebook and returning its section 9 records. It sees only an opaque id, the year and the text: not the country, the speaker, the part, the set or any score. Batches of 150 fragments mix all parts in a random order; the agents run ten at a time (user, 2026-09-29 21:56 UTC).
- **Check set.** Once every batch is labelled, the check set is drawn. For each lens L:
  - 30 of the fragments the core labeller marked positive for L;
  - 30 near-misses: fragments it marked negative whose score s_L is at least the median s_L of its positives for L.

  Each group is drawn at random with seed 20260929 + 3, and taken whole when it has 30 fragments or fewer. The union, about 600 fragments, is written in random order to batches of up to 150 (`data/gold/check/`).
- **Check labeller.** One agent at maximum effort (Opus, max) labels the check set blind, under the same rules and with the same view as the core labeller. It does not know how the fragments were chosen.
- **Resolver.** Another agent at maximum effort decides every pair (fragment, lens) of the check set on which the two labellers differ about `substantive`. It sees the text, the year, the codebook and the two records, unattributed, and nothing else.
- **Final label.** The core label, or the resolver's decision where the two labellers differed.
- **Agreement.** For each lens, Cohen's kappa of the two labellers on the positive class over the lens's checked fragments, the share of the core positives the check confirms and the share of near-misses it confirms. A lens with kappa below 0.8, the usual bar for reliable coding in content analysis (Krippendorff), is brought to the user with its disagreements before the classifiers are fitted.
- **Pilot.** Three labellers labelled b001 and b002 under codebook 1.1. Their 17 disagreements led to codebook 1.2 and to this design. Those labels are kept in `data/gold/pilot-v1.1/` and are not used; b001 and b002 are labelled again under 1.2 like every other batch.

## 5. Classifiers and probabilities

- **Weights.** Each sampled fragment carries w = 1/π(f) (Horvitz–Thompson), so that estimates describe U.
- **Features.** The fragment's embedding, standardized with the mean and standard deviation of the training set.
- **Classifier.** One per lens: a logistic regression (scikit-learn, L2 penalty) trained on the training set without weights, so that every fragment drawn near a lens counts fully. The penalty C is chosen from {0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1} by five-fold cross-validated log-loss on the training set, with the folds split by speech. All tuning uses the training set only.
- **Probabilities for the corpus.** The sample is enriched near each lens, so the classifier's own probabilities are too high for the corpus as a whole. Its score is therefore turned into a probability by a weighted logistic calibration (Platt scaling with the weights w), fitted on the five-fold out-of-fold scores of the training set. This brings the probabilities back to corpus level, which the shares need, while the classifier still learns from every drawn fragment.
- **Umbrella.** The probability for `drugs` is raised to the largest of its own and those of `prevention_treatment` and `alternative_development`: a fragment is at least as likely to be about drugs as about either sub-lens.
- **Decision.** A fragment is "about" a lens when p_L(f) ≥ 0.5. This is used for the excerpts, the composition bars and the pass bar.
- **Shares.** A speech's share on a lens is the mean of p_L over its non-ceremonial fragments. Group figures follow `docs/PLAN.md`, section 4.

## 6. Pass bar

- **Precision and recall.** For the decision d(f) and the label y(f), over the validation set:
  - TP = Σ w·d·y, FP = Σ w·d·(1 − y), FN = Σ w·(1 − d)·y;
  - P = TP / (TP + FP), R = TP / (TP + FN).
- **Intervals.** 95% intervals come from 2,000 bootstrap resamples of the validation set's speeches, since it was drawn by speech.
- **Pass.** A lens passes when P ≥ 0.70 and R ≥ 0.70 overall, and the same holds in every period in which the validation set has at least 20 fragments positive for that lens.
- **Share check.** For each lens and period, the weighted mean probability on the validation set is reported beside the weighted share of positive labels. It is reported, not used as a gate.
- **A lens that falls short** gets no trend line and no map, and is brought to the user. No fallback method is tried.

## 7. Freeze and publication

- Before any label is read, `data/gold/manifest.json` records the following. Its `revisions` list records the hashes of every later version of these files, each before any label under it is written:
  - the hashes of this file, `codebook.md` and `lenses.yaml`;
  - the seeds, λ, the expected and drawn sample sizes, and the size of each set.
- The validation set is used once, by `test`, after the classifiers are fitted.
- The classifiers are fixed before any trend is computed.
- The known-event checks of `docs/PLAN.md`, section 6, are run afterwards, as a test and never for tuning.
- The methods note gives, for each lens and period:
  - precision and recall with their intervals;
  - the number of positive validation fragments;
  - the agreement of section 4;
  - the share check;
  - the outcome: pass or short.
