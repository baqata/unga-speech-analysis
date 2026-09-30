# Retired: the held-out validation split

This folder records how the lens classifiers were evaluated until 2026-09-30, when the user made five-fold cross-validation over all the labelled fragments the only evaluation (2026-09-30 17:57 UTC, s4 r18894). The current method is `docs/calibration.md`; nothing here is used by the pipeline or the site.

## The design

- **Split** (user, 2026-09-29 16:30 UTC, s2 r24828). A seeded uniform per speech (seed 20260929 + 1) put one speech in five into a validation set: 4,841 sampled fragments from 1,862 speeches, labelled first (batches b001 to b033). The other 20,053 fragments trained and tuned the classifiers.
- **Second reading.** The doubtful core labels (confidence 1 or 2) of the validation set were read a second time, because that set carried the pass bar. The same 4,841 fragments are now the audited fifth, and that second reading keeps its place in the protocol.
- **Method comparison.** The comparison that chose the RBF support vector machine, against logistic regression and linear support vector machines, was run on the training set only (20,053 fragments), with the validation set untouched.
- **Pass bar.** A lens passed when precision and recall on the validation set were both at least 0.70, overall and in every period with at least 20 validation positives. The validation set was to be used once, by `calibrate test`; afterwards `calibrate fit --final` fitted the classifiers again on both sets.

## The one-shot test

Classifiers fitted on the training set (2026-09-30, 595 s) were tested once on the validation set on 2026-09-30 at 14:51 UTC (`results.json`, classifiers `8d4f16390d6b...`). Weighted precision and recall at each lens's threshold:

| Lens | Precision | Recall | Validation positives | Periods checked | Outcome |
|---|---|---|---|---|---|
| drugs | 0.96 | 0.85 | 246 | 3 | pass |
| prevention_treatment | 0.24 | 0.25 | 12 | 0 | short |
| alternative_development | 0.85 | 0.58 | 11 | 0 | short |
| organized_crime | 0.58 | 0.75 | 179 | 3 | short |
| corruption | 0.71 | 0.46 | 76 | 2 | short |
| terrorism | 0.88 | 0.85 | 449 | 4 | pass |
| trafficking_smuggling | 0.51 | 0.91 | 22 | 0 | short |
| environmental_crime | 0.82 | 0.62 | 17 | 0 | short |
| criminal_justice | 0.52 | 0.46 | 75 | 2 | short |

The classifiers were then fitted on all 24,894 labelled fragments (`fit --final`, 1,050 s). These are the classifiers the site uses. The first published technical annex (commit 5a5c637; gh-pages 2909e36) showed their out-of-fold figures, the test above under "more figures", and an "Aprox." badge on the six shown lenses that fell short in the test (user, 2026-09-30 17:07 UTC, s4 r17922).

## What replaced it

- `calibrate fit` is the only mode: all labelled fragments, five folds split by speech. Its pooled out-of-fold decisions give the pass bar, its intervals and the share check. The classifiers did not change: the refit of 2026-09-30 reproduced every array of the published classifiers.
- The pass bar judges F1 ≥ 0.70 overall and in every period with at least 20 labelled positives, with precision and recall weighing the same (user, 2026-09-30 18:20 UTC, s4 r19488). With all the labels, more periods are judged than in the validation set. The outcome: drugs, alternative development and trafficking in persons pass; terrorism, organized crime, corruption, environmental crime and criminal justice are shown as approximate; prevention and treatment stays hidden.
- Renamed in the gold record, with values unchanged:
  - `sample.parquet` and `labels_final.parquet`: the column `split` (`train`, `validation`) became the boolean `audit`;
  - `manifest.json`: `splits`, `validation_speeches` and `validation_batches` became `audit_fragments`, `audit_speeches` and `audit_batches`, and the revision notes were reworded to match;
  - `checkset.json`: `second_reading.validation_low_confidence` became `audit_low_confidence`.
- Removed from the code: `calibrate test`, `fit --final`, `results.json` and `lens_validation.parquet`.

## Where the old material is

- `results.json` in this folder: the test's full output, with intervals, confusion matrices, periods and the share check.
- Git history up to commit 5a5c637: the protocol, the plan, the gold record, `pipeline/calibrate.py` with `test`, and the site annex as they were.
- Kept locally, outside the repository, in `data/interim/archive/validation-split/`: the test's probabilities, the training-only classifiers, the logs of both fits, the method comparison's working files, the morning and error briefs of 2026-09-30, and the run log as it stood before this change.
