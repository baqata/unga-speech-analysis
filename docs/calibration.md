# Lens calibration protocol

This protocol implements `docs/PLAN.md`, section 4.1: the single method the user approved on 2026-09-29 (05:02 UTC), with its numbers and formulas fixed before any fragment is labelled. On 2026-09-29 (16:30 UTC) the user enlarged the sample to about 20,000 fragments to train and tune the classifiers and about 5,000 more to validate them; every part of the design was scaled by 2.5. On 2026-09-29 (21:56 UTC) the user replaced the three labellers and their resolver with one labeller and a targeted check (section 4). After the core labelling, the user settled four kinds of case, added to the codebook as version 1.3, and added a second reading of the doubtful validation labels (2026-09-29 22:57 UTC and 2026-09-30 about 00:30 UTC; section 4). After a comparison of methods on the final labels (training set only), the user chose a support vector machine with an RBF kernel, a threshold per lens and a final fit on both sets after the test, and left to the main agent whether to keep measuring the reference lens, which it no longer does (2026-09-30 about 14:30 UTC; sections 5 to 7). The labelling rules are `data/lenses/codebook.md` (version 1.2 for the core labeller, 1.3 for the check labeller and the resolver) and the lens descriptions are `data/lenses/lenses.yaml`. The code is `pipeline/calibrate.py`; the sample, the labels and the results are in `data/gold/`.

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
- **Codebook 1.3.** After the core labelling, the user settled four kinds of case: accusations and designations of States as sponsors of terrorism, acts and groups that the Security Council has called terrorist, extremism without violence, and Security Council action on criminal violence. Codebook 1.3 adds them (4.6, 4.10). The core labels stay as written under 1.2. The 251 fragments that the new rules may change, found by search and in the reviews of the core labels, are listed in `data/gold/reread.json`.
- **Check set.** Once every batch is labelled, the check set is drawn among the fragments not listed in `data/gold/reread.json`, so that the agreement measures the labellers and not the change of rules. For each lens L:
  - 30 of the fragments the core labeller marked positive for L;
  - 30 near-misses: fragments it marked negative whose score s_L is at least the median s_L of its positives for L.

  Each group is drawn at random with seed 20260929 + 3, and taken whole when it has 30 fragments or fewer. The union, about 600 fragments, is written in random order, together with the second reading, to batches of up to 150 (`data/gold/check/`).
- **Second reading.** The check labeller also reads, mixed into the same batches, every validation fragment that the core labeller marked at confidence 1 or 2 (1,544 of 4,841), every fragment at confidence 1 and every fragment of `data/gold/reread.json`: about 1,800 fragments (user, 2026-09-30). They do not count in the agreement. The validation set carries the pass bar (section 6), so its doubtful labels are read twice. If the resolver changes the label of more than about one in ten of them, extending the second reading to the doubtful training fragments (6,123) is put to the user. The share is counted outside the fragments of `data/gold/reread.json` and `data/gold/reread14.json`, whose rules changed; `data/gold/changes.json` gives it with and without them.
- **Codebook 1.4.** After the check labelling, every lens rule was checked against UNODC's official definitions and scope: the conventions, protocols and United Nations resolutions behind each mandate (`data/lenses/SOURCES.md`). Codebook 1.4 aligns the rules (sections 4 to 8) and gives each lens three positive and two negative examples (user, 2026-09-30 02:48 UTC). The labels already written stay as they are. The 1,299 fragments whose label the changed rules may change, found by search, are listed with the lenses concerned in `data/gold/reread14.json`.
- **Review of codebook 1.4.** Two more readings under 1.4, mixed in random order in ten more check files (about 130 fragments each), read by ten check labellers, five at a time (user, 2026-09-30 01:58 and 02:48 UTC):
  - the review: for each lens, 25 fragments outside the check files and outside `data/gold/reread14.json`, half that the core labeller marked positive and half near-misses as defined for the check set, drawn at random with seed 20260929 + 5; what a lens cannot fill is drawn among the positives and near-misses left over from all lenses, so that the review has 250 fragments. It measures what 1.4 changes where the search found nothing;
  - the reread: every fragment of `data/gold/reread14.json` outside the check files (1,039).

  For the fragments of `data/gold/reread14.json` already in the check files (260), the lenses listed for them (280 pairs) go to the resolver even where the two labellers agree. None of these readings counts in the agreement. If the resolver changes the label of more than about one in ten of the review's fragments, the user decides between labelling the whole sample again under 1.4 and reading again only the core labeller's positives, the second when the changes mostly remove labels (user, 2026-09-30 02:48 UTC).
- **Check labeller.** One agent at maximum effort (Opus, max) labels the check set and the second reading blind, under codebook 1.3, and the review files under codebook 1.4, with the same view as the core labeller. It does not know how the fragments were chosen.
- **Resolver.** Another agent at maximum effort decides every pair (fragment, lens) of the check files on which the two labellers differ about `substantive`, and the pairs of `data/gold/reread14.json` in the check files drawn before 1.4. It sees the text, the year, the codebook (1.4) and the two records, unattributed, and nothing else.
- **Final label.** The core label, or the resolver's decision where the two labellers differed.
- **Agreement.** For each lens, Cohen's kappa of the two labellers on the positive class over the lens's fragments in the check set (not the second reading), the share of the core positives the check confirms and the share of near-misses it confirms. A lens with kappa below 0.8, the usual bar for reliable coding in content analysis (Krippendorff), is brought to the user with its disagreements before the classifiers are fitted.
- **Pilot.** Three labellers labelled b001 and b002 under codebook 1.1. Their 17 disagreements led to codebook 1.2 and to this design. Those labels are kept in `data/gold/pilot-v1.1/` and are not used; b001 and b002 are labelled again under 1.2 like every other batch.

## 5. Classifiers and probabilities

- **Weights.** Each sampled fragment carries w = 1/π(f) (Horvitz–Thompson), so that estimates describe U.
- **Features.** The fragment's embedding, standardized with the mean and standard deviation of the training set.
- **Lenses measured.** Every lens but the reference lens `peace`, which stays in the labels but is not fitted: it covered about two fifths of all the text, and its fragments are better described by the general topics of the composition (2026-09-30).
- **Classifier.** One per lens: a support vector machine with an RBF kernel (scikit-learn SVC, kernel width "scale") trained on the training set without weights, so that every fragment drawn near a lens counts fully. The penalty C is chosen from {0.3, 1, 3, 10} by five-fold cross-validated average precision, weighted with w, on the training set, with the folds split by speech. All tuning uses the training set only.
  - The method replaced the logistic regression of the first version of this protocol. On the out-of-fold scores of the training set, seven models were compared (logistic regressions with L1 and L2 penalties, with and without weights; linear and RBF support vector machines), the validation set untouched. The RBF machine had the highest mean average precision, 0.746 against 0.717 for the logistic regression as this protocol chose its penalty, and led by the same margin on the core labels (user, 2026-09-30).
- **Probabilities for the corpus.** The sample is enriched near each lens, and the machine gives a score, not a probability. Its score is therefore turned into a probability by a weighted logistic calibration (Platt scaling with the weights w), fitted on the five-fold out-of-fold scores of the training set at the chosen C. This brings the probabilities to corpus level, which the shares need, while the classifier still learns from every drawn fragment.
- **Umbrella.** The probability for `drugs` is raised to the largest of its own and those of `prevention_treatment` and `alternative_development`: a fragment is at least as likely to be about drugs as about either sub-lens.
- **Decision.** A fragment is "about" a lens when p_L(f) ≥ t_L. The threshold t_L is the probability with the highest weighted F1 over the calibrated out-of-fold probabilities of the training set, after the umbrella rule (user, 2026-09-30). The decision is used for the excerpts, the composition bars and the pass bar.
- **Shares.** A speech's share on a lens is the mean of p_L over its non-ceremonial fragments. Group figures follow `docs/PLAN.md`, section 4.

## 6. Pass bar

- **Precision and recall.** For the decision d(f) = [p_L(f) ≥ t_L] and the label y(f), over the validation set:
  - TP = Σ w·d·y, FP = Σ w·d·(1 − y), FN = Σ w·(1 − d)·y;
  - P = TP / (TP + FP), R = TP / (TP + FN).
- **Confusion matrix.** For each lens, the numbers of true and false positives and negatives on the validation set, as counts and weighted with w.
- **Intervals.** 95% intervals come from 2,000 bootstrap resamples of the validation set's speeches, since it was drawn by speech.
- **Pass.** A lens passes when P ≥ 0.70 and R ≥ 0.70 overall, and the same holds in every period in which the validation set has at least 20 fragments positive for that lens.
- **Share check.** For each lens and period, the weighted mean probability on the validation set is reported beside the weighted share of positive labels. It is reported, not used as a gate.
- **A lens that falls short** gets no trend line and no map, and is brought to the user. No fallback method is tried.

## 7. Freeze and publication

- Before any label is read, `data/gold/manifest.json` records the following. Its `revisions` list records the hashes of every later version of these files, each before any label under it is written:
  - the hashes of this file, `codebook.md` and `lenses.yaml`;
  - the seeds, λ, the expected and drawn sample sizes, and the size of each set.
- The validation set is used once, by `test`, after the classifiers are fitted.
- After the test, the classifiers that measure the corpus are fitted again by the same procedure on the training and validation sets together (C, calibration and threshold by five-fold cross-validation over both), so that they use every label. The test's results describe that procedure and choose nothing (user, 2026-09-30).
- The classifiers are fixed before any trend is computed.
- The known-event checks of `docs/PLAN.md`, section 6, are run afterwards, as a test and never for tuning.
- The methods note gives, for each lens and period:
  - precision and recall with their intervals;
  - the number of positive validation fragments;
  - the agreement of section 4;
  - the share check;
  - the outcome: pass or short.
