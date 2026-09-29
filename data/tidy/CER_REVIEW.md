# Ceremonial-label review

Status (2026-09-28): not started. The review is deferred. When it runs, it covers only each speech's first and last paragraphs, and this guideline is narrowed to that scope first.

Some finished years label as ceremonial (`cer`) paragraphs that are substance, or that mix ceremony with substance. This review re-decides `cer` for every speech in your years. Nothing else about the speeches changes.

## The rule

Read the `cer` row of the decision table in `data/tidy/INSTRUCTIONS.md`, and the checklist ("Where to split") in the same file. In short:

- `cer` lists only paragraphs that are purely ceremonial: greetings, congratulations, thanks, tributes, condolences, welcomes to new Members, or protocol, including a closing "I thank you".
- A paragraph that mixes ceremony with substance is not `cer`. If the substance begins at a unit that starts a sentence, and the checklist allows a paragraph start there, split at that unit and label only the ceremonial part. Otherwise leave the whole paragraph unlabelled.
- Substance means the speaker's views, policies or facts about any issue, even when framed as praise ("under your leadership we will continue the reform process" is ceremony; a sentence that states a position on reform is substance).
- Position does not decide. A first or last paragraph is `cer` only when all of it is ceremonial. A ceremonial paragraph in the middle of the speech is `cer` too.
- The short-paragraph limit still applies to any split you make. A ceremonial part under 60 words may stand alone because it is `cer`; a substance part under 60 words needs the checklist's permission, or it joins the next paragraph instead (move that paragraph's start to the split unit).

## Your pages

`data/interim/tmp/cer_review/views/<year>/vNN.txt` shows, for every speech: each paragraph now labelled `cer` (marked `¶Pn (cer)`), the first unlabelled paragraph after the opening, and the last paragraph. Other paragraphs are replaced by a line saying which units are not shown. Units, drops and fixes appear as in the tidy views. You never need to read the rest of a speech; if you want more context for one speech, run `uv run python -m pipeline.tidy audit-view <ID> --out data/interim/tmp/cer_review/ctx/<ID>.txt` and read that file.

## Working method

For each year, page by page:

1. Read the page with the Read tool and decide `cer` for every speech on it by reading. A helper script may list, count, check or write down your decisions, but never choose them (not by keywords, length or position).
2. For each speech that needs a change, take its current decision from `data/tidy/decisions/<Session folder>/<ID>.json`, keeping only the keys `id`, `drop`, `para`, `cer`, `fix`, `flags` and `note`. Change only `cer`, and `para` where a split or join above needs it. Write the full line to `data/tidy/work/decisions/<year>/zcer.jsonl`. A later line for the same id replaces an earlier one. Speeches that need no change get no line.
3. Run `uv run python -m pipeline.tidy apply --year <year> --page zcer` after each page. Fix every `ERROR`; the short-paragraph warning must clear.
4. When the year is done, run `uv run python -m pipeline.tidy apply --year <year>`. It must report `0 errors, 0 without a decision` and no short-paragraph warnings.

Write nothing else: no other decision files, no tool changes. Keep helpers in `data/interim/tmp/cer_review/helpers_<year>/`.

## Final report

A few lines per year: speeches changed (labels removed, splits made, labels added), and any speech where you were unsure.
