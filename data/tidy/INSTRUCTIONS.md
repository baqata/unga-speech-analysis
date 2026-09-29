# Tidying General Debate speeches: guideline for agents

## Your job

For every speech in your assigned year you produce a tidy copy. A tidy copy contains only the speaker's own words, grouped into complete, meaningful paragraphs.

You do not retype any text. You read numbered view pages and write one decision line per speech, saying three things:
- what to drop;
- where each paragraph starts;
- which small repairs to make.

The tool then builds the tidy copy from the original words and checks your decisions. Your assignment file, `data/tidy/work/assignments/<year>.md`, lists the pages to read, the decision files to write, the commands and, where there are any, revision items for your year.

Every year of the corpus follows these same rules. Apply exactly what this file says, and nothing else. When a case is not covered here, keep the text and explain it in `note`.

## Reading a view page

```
=== ARG_81_2026 | Argentina | 2026 | layout: single | units 0-231 | 3,051 words | tool removed: none
0 The Assembly will now hear an address by His Excellency ...
1 I request protocol to escort His Excellency ...
2 When we took office of a country in ruins ...
17¶ A unit after a blank line in the source.
18↵ A unit that starts a new source line.
```

- **Units.** Each numbered line is a unit: a sentence, or a printed line of the source.
- **Marks.**
  - `¶` means a blank line came before this unit in the source.
  - `↵` means the unit starts a new source line.
  - In `wrapped` layouts every unit is a printed line, so `↵` is omitted.
- **Header fields.**
  - `layout` tells you how the source was formatted.
  - `tool removed` lists boilerplate that has already been stripped, such as paragraph numbers, page numbers, meeting references and "(spoke in French)" notes.
- **Long units** continue on lines starting with `⋯`. These are display only; the unit keeps its one number.
- **Paragraph numbers** at the start of a source line in numbered records (a unit that is just `26.`, or a line starting `1. Madam President`) are removed automatically when you apply. Do not drop or fix them. Treat them as a strong sign that the speaker's paragraph starts there.

## Decision line (one per speech, JSON)

```
{"id":"ARG_81_2026","drop":[[0,1,"presider"],[229,231,"presider"]],"para":[2,9,15],"cer":[2],"fix":[[40,"Millay","Milei","asr_name"]],"flags":[],"note":""}
```

| Key | What it holds |
| --- | --- |
| `drop` | Inclusive unit ranges `[start, end, reason]` to remove. Ranges must not overlap. |
| `para` | Unit ids where each paragraph starts, ascending. The first kept unit always starts a paragraph. |
| `cer` | The paragraph starts, from `para`, of paragraphs that are purely ceremonial: greetings, congratulations, thanks, tributes or protocol. These stay in the text and are only labelled. A paragraph that mixes ceremony with substance is not `cer`: where the substance begins at a sentence start that the checklist allows, split there and label only the ceremonial part; otherwise leave the whole paragraph unlabelled. Being the first or last paragraph does not make a paragraph ceremonial. |
| `fix` | Small repairs `[unit, old, new, reason]`. `old` must appear exactly once in that unit. |
| `flags` | Problems a reviewer should know about (see "Flags" below). |
| `note` | One short sentence, only when useful. |

Every speech needs exactly one line, even when nothing is dropped or fixed; `para` is always required. If you write a second line for the same id, the later line replaces the earlier one.

## What goes and what stays

The tidy copy keeps every word the speaker said, and nothing else. Use this table for every case.

| In the source | Action | How |
| --- | --- | --- |
| The presiding officer's words: introductions ("The Assembly will hear an address by ...", "I request protocol to escort ..."), "I call on ...", thanks after the speech ("On behalf of the Assembly, I wish to thank ..."), the next speaker's introduction, hall chatter at the end of an audio file ("Okay, here we go.") | Remove | `drop`, reason `presider` |
| Meeting-record lines: "The meeting rose at ...", agenda or record lines, a heading such as "Address by Mr. X, President of Y", "Mr. X was escorted into the General Assembly Hall" | Remove | `drop`, reason `procedural` |
| Page headers and footers, document symbols, and page or job numbers that the tool missed | Remove | `drop`, reason `header_footer` |
| Language, interpretation and applause notes that the tool missed, such as "(spoke in French)" or "(Applause)" | Remove | `drop`, reason `interpretation_note`; inside a unit, a `label` fix |
| Section headings of a written statement that were not spoken (mostly 2024) | Remove | `drop`, reason `heading` |
| Another speaker's words: another delegation's statement or right of reply, the President's own remarks | Remove | `drop`, reason `other_speaker` |
| A second statement by the same country in the same record, such as a head of state's address, a later statement by another member of the delegation, or the speaker's own right of reply given within the statement | Keep: it is the country's statement | Nothing to drop; say so in `note` |
| A passage repeated by a duplication or a transcription loop | Remove the repetition; keep the first occurrence | `drop`, reason `repeat` |
| OCR debris, isolated symbols, footnote blocks under a separator line | Remove | `drop`, reason `noise`; inside a unit, a `label` fix |
| A speaker label inside a unit: "Mr. X (Country): We ..." | Remove the label only | `label` fix |
| Document references the record added in parentheses or square brackets: "(A/54/2000, para. 17)", "(resolution 70/1)", "(see S/PV.4208)", "[A/1376]", "[resolution 289 (IV)]" | Removed by the tool | Leave them alone |
| The same kinds of references in a form the tool does not recognise, often damaged by scanning: "[Al36/547]", "[A,/1323]", "[see 1753rd meeting]" | Remove | `label` fix |
| Source notes the record added: "(ibid.)", "[ibid., para. 16]", "(The Holy Koran, V: 3)", "(Luke 2.14)", "[item 67]", "(agenda item 94)" | Remove | `label` fix |
| An acronym, expansion or alternative name the record added in square brackets right after a name: "Organization of African Unity [OAU]", "SALT [Strategic Arms Limitation Talks]", "Peking [Beijing]" | Remove | `label` fix |
| Any other words in square brackets, inside a quotation or a sentence: "[the United Nations]", "support[s]", "[s]mall", "[Security Council] resolution 435 (1978)" | Keep as they are | Nothing |
| Any other text in parentheses | Keep: it is the speaker's | Nothing |
| Bullet symbols (•) and leftover Markdown (`**`, `#`) | Remove | `markup` fix |
| Greetings, congratulations, thanks, tributes and closing words ("I thank you") | Keep | List the paragraph in `cer` only when all of it is ceremonial |

When unsure whether text belongs to the speaker, keep it and add a flag or a note.

## What the tidy copy looks like

The tool writes every tidy copy the same way:
- One paragraph is one block of text on a single line, with no line breaks inside it.
- Paragraphs are separated by exactly one blank line.
- There is no header, no numbering and no markup.

Each paragraph becomes one searchable passage on the dashboard, so paragraphs must make sense on their own.

## Where to split: the checklist

Go through the kept units in order. Start a new paragraph at a unit (put its id in `para`) only when all three hold:

1. **The previous unit ends a sentence**, with `.`, `?`, `!`, `…`, `:` or a closing quote, and this unit starts a new one. If the sentence is still running, never split, whatever the marks say. When the scan lost the mark at the end of a sentence (the unit ends without one and the next unit clearly begins a new sentence with a capital letter), count it as a sentence end, but do not add the mark. The one exception to rule 1 is an opening salutation, such as "Mr. President, Excellencies, ladies and gentlemen,", which may stand as its own `cer` paragraph whatever punctuation ends it.
2. **The subject moves on.** Examples: a new topic, country, region or issue; a new part of the argument; a shift from greetings to substance; the closing section.
3. **Size stays reasonable.** Aim for **60–250 words** per paragraph.
   - A paragraph under 60 words is allowed only for greetings or thanks (label them `cer`), the closing line, a single sentence that stands alone rhetorically, or a complete point that neither neighbour shares.
   - Pieces of one larger point join together, even when the source prints them as separate paragraphs. Several short paragraphs on one issue, country or region become one paragraph.
   - Go longer only when one argument cannot be cut without breaking it.

The source's own breaks (`↵` in `lines` layouts, and `¶` in 2013–2014) are the speaker's paragraphs. Keep them when rule 1 holds, with two exceptions:
- **Join short source paragraphs** as rule 3 says. Some records, mostly from the 1980s, print many paragraphs of 30 to 50 words; there, most of them join a neighbour. Also join a sentence cut by a page break.
- **Split very long ones.** Split a source paragraph only when it runs past about 300 words and changes subject inside.

**Short-paragraph limit.** Apart from greetings and the closing line, fewer than 1 paragraph in 10 of a speech may be under 60 words; a single one is always allowed. The tool warns when a speech has more and lists their units. That warning must clear: join the listed paragraphs with the neighbour closest in subject, pieces of a larger point first, until it disappears.

## Paragraphs: complete, coherent, continuous

A paragraph is one complete passage about one point.

**Never start a paragraph in the middle of a sentence.** A sentence interrupted by a page break or line break continues in the same paragraph. This is the continuity rule. For example, a unit ending "... it" followed by a unit starting "also poses ..." belongs together, even across a `¶`.

**Follow the source's own paragraphs where they exist.** In `lines` layouts (1946–1968, 1970–1981, 1983–1991, 2015–2023), each `↵` usually starts one of the speaker's paragraphs. Keep those breaks unless:
- the break is a page-break artifact, where the next unit continues the sentence; or
- a paragraph runs past about 300 words and changes topic inside; split it at the topic shift;
- a paragraph is under 60 words and rule 3 does not allow it to stand alone; join it with its neighbour.

**Handle wrapped layouts carefully.** In 1969, 1982 and 1992–2014 every unit is a printed line.
- A `¶` there is usually a page break, often mid-sentence and often next to a page or job number. It is not a paragraph.
- A real paragraph starts on a line that begins a new sentence after the previous line ended one, where the subject moves on.
- In 2013–2014, `¶` usually does mark a real paragraph.

**Create paragraphs where the source has none.** This covers single-line transcripts (2025, 2026 and a few 2024 files), speaking-note layouts (one phrase per line, such as GBR 2024) and wrapped text without breaks.
- Break at topic shifts.
- Aim for 60–250 words per paragraph, as in the checklist.
- Group speaking-note phrases into full paragraphs.

**Avoid fragments.** Make a one-sentence paragraph only when it stands alone rhetorically, such as a closing "I thank you." Otherwise attach it to the neighbour it belongs with. Keep a list together with its lead-in sentence.

## Repairs (`fix`): only certain, local artifacts

Allowed reasons:

| Reason | What it repairs |
| --- | --- |
| `hyphen` | A broken hyphenation inside one unit. The tool already handles hyphens at line ends; do not fix those. |
| `spacing`, `split_word`, `merged_word` | Words split or glued by extraction. |
| `ocr` | Clear scanning misreads, e.g. "modem" when "modern" is clearly meant, "wodd" → "world", or "Na5ons" → "Nations" from lost ligatures in a PDF text layer. |
| `encoding` | Leftover encoding debris. |
| `markup` | Bullet symbols and leftover Markdown. |
| `asr_name` | A speech-to-text mishearing of the name of a country, place, organisation or well-known leader, when certain. Example: "Columbia" in a Colombian speech. |
| `asr_term` | A speech-to-text mishearing of a term or ordinary word, when certain: the written word sounds like the intended one but does not fit, and the context or, in 2026, the Spanish channel confirms the intended word. Examples: "multinaturalism" → "multilateralism"; "the climb of the Caspian Sea" → "the decline", where the Spanish says "descenso". |
| `interp` | An interpreter's slip, or a mishearing of the interpretation, that changes a number, date, name or key word, when the speaker's own words prove it. Replace only the wrong word or words with the English equivalent of what the speaker said, and quote the speaker's words in `note`. Example: "six years" → "six months" where the speaker said "seis meses". |
| `slip` | 2026 only, in speeches not delivered in Spanish: an obvious slip by the speaker or the English interpreter, under the second 2026 exception below. Example: "the Charter of the United States" → "United Nations". |
| `label` | Removes text that is not the speaker's inside a unit, as listed in "What goes and what stays". `new` must be `""`. |

`asr_name` and `asr_term` apply only to texts transcribed from audio: 2025 and 2026. Every other year comes from printed records, whose errors are scanning misreads (`ocr`). The 2024 records are born-digital: their text layer has no scanning misreads, so repairs there are rare (`split_word`, `merged_word`, `spacing`).

In audio transcripts, names are the weak point. Check every proper name of a person, place, programme or document that looks unusual against a published source: the speaker's official text or news reports of the speech, the UN General Debate site, or official government and UN pages. Repair it with `asr_name` when the source confirms the intended name, and put the source in `note`. Examples from 2026: "Esprilla" for "Espriella", "Capino" for "Scappini", "Burgess" for "Borges", "homos" for "Hormuz". In long stretches without punctuation, speech-to-text also writes names and the pronoun "I" in lowercase ("paraguay", "i want"); restore their capital letters with `asr_name` or `asr_term`. A word that sounds unlike the one you suspect is the interpreter's wording, not a mishearing: leave it unless `interp` applies.

Speech-to-text also closes a segment with a full stop, or a question mark, and writes the next word in lowercase ("political reality. and this is not"). Read each such place and repair it with `asr_term`:
- When the words after the mark finish the sentence before it, remove the mark, provided the joined sentence reads correctly. These are the rest of a phrase, list or clause begun before the mark, a verb whose subject comes before it, or a relative clause. Example: "Only a fully sovereign Lebanon. will be able to disarm" becomes "Only a fully sovereign Lebanon will be able to disarm".
- Otherwise restore the capital of the first word: "reality. and this is not" becomes "reality. And this is not". This includes a phrase that the speaker sets apart and that can stand alone, such as an aside, an example or a "because" clause.

Leave abbreviations ("U.S.", "etc.") and an ellipsis as they are. Never put another mark in place of the one removed.

`interp` applies only to 2026 speeches delivered in Spanish, where the Spanish audio channel carries the speaker's own words. Compare the English with the Spanish only where the English looks doubtful: a number, date or name that seems wrong, or a phrase that does not fit the argument. Correct the wrong word only; never reword a sentence, and leave differences of style, emphasis or word order alone. For speeches in other languages the Spanish channel is a second interpretation: it may help confirm a name or a number for `asr_name`, but it never proves an `interp` repair (it may show the intended word of a `slip`, below).

Some 2026 units come from a second speech-to-text pass over pauses the first pass skipped (`pipeline.regap`). Treat them like any other text: a lone "Thank you." or stray words heard in a pause are `noise`, and presiding-officer lines are `presider`.

Repair a word only when the damaged letters clearly show the intended word. A real word counts as damaged only when it cannot fit the sentence and differs from the intended word by a common scanning confusion, such as "die" for "the", "arc" for "are" or "modem" for "modern". Never:
- complete a word cut off by a page break, or add a missing word;
- choose a word from context when the letters do not show it;
- add punctuation, except where the scan misread one mark as another (such as "^" or "," printed for a full stop). A mark that is simply missing stays missing;
- rephrase, translate, modernise spelling or correct grammar (an `interp` repair of the wrong words is the only translation allowed);
- change names you are not certain about, or change what the speaker said, even where it looks wrong (the one exception is a 2026 `slip`, below).

Where text is visibly missing, leave it and add the `gap_suspected` flag.

One exception applies to 2026 only (user decision, 2026-09-29): a word that speech-to-text dropped may be restored when the audio clearly holds it, because two fresh decodes of the English channel both hear it, and a second source confirms it: the Spanish channel or a published text of the speech. Restore only the dropped word or words, with `asr_term` (`asr_name` for a name), and give both sources in `note`. Without both, the text stays as it is.

A second exception applies to 2026 only (user decision, 2026-09-29): in speeches not delivered in Spanish, an obvious slip by the speaker or the English interpreter may be corrected with `slip`. The word said must not fit the sentence, and the Spanish channel, a published text of the speech or simple arithmetic must show the intended word, which must be the evident counterpart of the word said: "escalate" said for "de-escalate", "United States" for "United Nations", or a date on which the Spanish channel and a published record agree. Replace only the wrong word or words, and record in `note` what was actually said and the evidence. When the word said fits the sentence, or the evidence does not settle the intended word, the text stays as delivered.

The tool allows at most 150 fixes per speech and checks each changed word. It rejects a repair that adds a word, adds a punctuation mark, or rewrites a word instead of repairing it. Adding context to `old` does not change this. When a repair is rejected, leave the text as it is. A misheard name or term, or an interpreter's or speaker's wrong word, of up to four words may be replaced freely with `asr_name`, `asr_term`, `interp` or `slip`; keep `old` to the wrong words only.

## Flags

| Flag | When to use it |
| --- | --- |
| `truncated_start`, `truncated_end` | The speech visibly starts or stops mid-way. |
| `gap_suspected` | The text jumps, for example a missing page. |
| `wrong_country` | The text clearly belongs to a country other than the file's. |
| `not_english` | The text is not in English. |
| `garbled` | The text is unreadable debris. |
| `mixed_speakers` | More than one speaker's words appear and cannot be separated. |
| `third_person_summary` | A summary record in the third person ("He said that ..."), not verbatim. |
| `duplicate_speech` | The same speech appears again. |

## Working method

1. Run `uv run python -m pipeline.tidy status --year <year>` to see what is done.
2. Work page by page:
   - Read the whole page with the Read tool.
   - Decide every speech on it.
   - Write the decisions to that page's `pNN.jsonl`.
   - Run `uv run python -m pipeline.tidy apply --year <year> --page pNN`.
   - Fix every `ERROR`.
   - Read each `WARN`. Fix it if it shows a mistake, such as a presider line kept, a missed break, or a 400-word paragraph mixing topics; otherwise leave it. The short-paragraph warning is the exception: it must always clear (see "Short-paragraph limit").
3. Decide while the text is fresh; do not read ahead. Read only your pages, never the raw corpus files. Write only your year's decision files.
4. When all pages are done, run `uv run python -m pipeline.tidy apply --year <year>`. It must report `0 errors, 0 without a decision`.
5. If you lose track (for example after a long session), re-read this file and your assignment, then run `status`. It lists the pages with pending speeches.
6. Every decision comes from reading the text: what to drop, where paragraphs start, which paragraphs join, and every repair. A helper script may list, count, check or write down the decisions you made, but it must never choose them (for example by word overlap, length or position).
7. Do not edit the tool or any other file. If you want a helper script, keep it in `data/interim/tmp/tidy_<year>/` only. If the tool misbehaves, stop and report it.

### Continuing a year that an earlier agent started

- `status` lists the pages with pending speeches. Work only on the pending speeches; the speeches already applied are done.
- If a page's decision file already exists, keep every line in it and add the missing speeches' lines at the end.

### Revising applied speeches

Your assignment may list revision items: applied speeches that do not yet follow this guideline. For each item:
1. Run `uv run python -m pipeline.tidy show <ID>` to see the speech's units.
2. Take the speech's current decision from `data/tidy/decisions/<Session folder>/<ID>.json`, keeping only the keys `id`, `drop`, `para`, `cer`, `fix`, `flags` and `note`.
3. Change only what the item requires, following this guideline, and write the full line to `data/tidy/work/decisions/<year>/r01.jsonl`. A line there replaces the speech's earlier line.
4. Run `uv run python -m pipeline.tidy apply --year <year> --page r01`.

### Final report

A few lines only:
- speeches done, and errors left (must be 0);
- revision items done;
- ids you flagged;
- anything unusual about your year's layout that the tool did not handle.
