# Voces de la Asamblea: agreed plan

A public, static, communication-first dashboard for the UNODC ROCOL Análisis, Monitoreo e Innovación team. It shows how countries, blocs and UNODC offices talk about UNODC mandate topics in the UN General Assembly General Debate, from 1946 to the present. The audience is non-technical leadership.

## How to read this file

- The decisions come from the planning conversation of 2026-09-26 and the project memory.
- Each decision ends with a reference to the user message that settled it: the UTC date and time, and the record number in the planning transcript (`dd18bcc6-13cd-4509-9afe-a1a65a25deff.jsonl`, 0-based line). Example: (2026-09-26 18:28, r659).
- When the user accepted a proposal, the proposal's record is also given, for example "proposed r591".
- On 2026-09-26 at 18:33 (r683) the user confirmed the build plan. That plan is the one proposed in r591, as amended in r679.
- When a decision changed across rounds, only the latest one is recorded here. Earlier versions are listed under "Superseded decisions".
- Decisions from the follow-up conversation (`4612d029-9f25-45a4-bcce-6083447d3a0a.jsonl`) carry the prefix s2, for example (2026-09-29 01:17, s2 r9207). Those from its continuations of 2026-09-29 (`68ffed3e-3711-4999-9822-382141b93d98.jsonl` and `07a5b27e-c9ff-4c09-b7a5-530eb602230e.jsonl`) carry the prefixes s3 and s4.

## 1. Purpose

- **Four questions**, each answered by one view (2026-09-26 17:31, r92; proposed r81):
  1. How much attention do the world, a region or a country give to UNODC mandate topics, and how is it changing?
  2. Where is attention highest? (world map)
  3. Who sounds like whom? (semantic map and country alignment)
  4. What exactly do they say? (excerpts)
- **Scope:** an MVP (2026-09-26 17:31, r92). It became a global tool covering every UNODC office (2026-09-26 18:21, r615).
- **Tone:** minimal captions, no jargon; "more a communicational tool than a tech-development" (2026-09-26 17:22, r2).

## 2. Data coverage

- **Corpus:** the UN General Debate Corpus v14, all speeches from 1946 to 2025 (2026-09-26 17:31, r92).
- **Historical entities:** each code keeps one continuous line, for example RUS for the USSR and CHN for the Republic of China until 1971. The historical name shows on hover, for example "URSS (1946–1991)" (2026-09-26 18:02, r476; proposed r465).
- **Naoero:** at the 81st session (22 September 2026) Nauru restored its name Naoero, and its code changed from NRU to NRO ([AP via CTV News](https://www.ctvnews.ca/world/article/a-nation-renamed-stands-up-at-the-un-say-our-name-naoero/)). It is filed under NRO for all years and named Naoero, with "Nauru (2000–2025)" on hover under the rule above. Source file names and speech ids keep NRU (2026-09-29 01:17, s2 r9207; details in `data/meta/SOURCES.md`).
- **2024–2025 source caveats:** handled in processing. Nothing about them appears on screen (2026-09-26 18:02, r476).
- **2024 from the official records:** the 2024 texts come from the General Assembly's verbatim records A/79/PV.7 to PV.17 (PV.18 covers other agenda items). `pipeline/records.py` splits them into one statement per delegation, 193 in all, and they are tidied under the same guideline as 1946–2023. They replace the corpus texts of that session (2026-09-29 05:51, s2 r14183).
- **2026, provisional:**
  - It covers every country that has spoken so far (2026-09-26 18:12, r575).
  - It follows the corpus file structure but is stored apart, as provisional data (2026-09-26 18:12, r575).
  - It is labelled "2026 (en curso)" in the year selector (proposed r591; confirmed 2026-09-26 18:33, r683).
  - The text comes from the English interpretation audio, transcribed locally, which is the method the dataset authors used for 2025 (downloads approved 2026-09-26 18:21, r615; proposed r605).
  - English stays the core text. The Spanish channel is used only to confirm doubtful passages (2026-09-28 04:57, r7020).
  - Status on 2026-09-29: the debate has closed; 194 statements are transcribed, checked against the Spanish channel and tidied. The UN library files the Dominican Republic's audio under the code DR, not DO, which is why it was missing until 2026-09-29 (retry approved 06:58, s2 r15722). Australia's library files stop at 6:18, so both of its channels were cut from the UN Web TV recording of the meeting (approved 2026-09-29 08:19, s2 r17501).
  - Every 2026 text is cross-checked against the UN's machine transcript of the same meetings (transcripts.un.org, which is not an official record). The audio decides each disagreement. A word that speech-to-text lost is restored only when two fresh decodes clearly hear it and the Spanish channel or a published text confirms it (rule A1: 2026-09-29 05:42, s2 r13958; full cross-check 05:51, s2 r14183; at most 10 agents, 06:58, s2 r15722).
  - Status on 2026-09-29 13:57: the cross-check is complete and applied to all 194 statements. A random validation of 25 statements found 16 major and 52 minor issues. All 16 majors are resolved, 14 of them already by the cross-check. The minors are repaired, or kept with the reason recorded (data/interim/tmp/validation_2026/manifest.md).
  - Slips (user decision 2026-09-29 14:47, s2 r22396: "Yes, narrow rule"): in a statement not delivered in Spanish, an obvious slip by the speaker or the interpreter is corrected only where the word said does not fit the sentence and the Spanish channel, a published text or simple arithmetic shows the intended word; the note keeps what was said (data/tidy/INSTRUCTIONS.md, reason `slip`). Applied 2026-09-29 15:10: 61 corrections in 40 statements; the 2026 audit is clean and the full-corpus test passes.
  - No second validation round (user, same answer, "No, proceed"): 2024 and 2026 are embedded after the stable run, then calibration starts.
- **Language of the source text:** speeches, excerpts and the analysis stay in the original English and are never machine-translated (2026-09-26 17:31, r92).

## 3. Interface

### 3.1 Layout

- **Two tabs.** The dashboard opens on "Regiones y mundo" (2026-09-26 18:28, r659; proposed r633).
  - **Regiones y mundo:** the lens strip, the semantic map with its toggle, the world map, the trend, the distinctive-word bars and the excerpts (confirmed 2026-09-26 18:33, r683; proposed r679).
  - **País:** see section 3.9.
- **Look:**
  - No logo, and no UN or UNODC emblem (2026-09-26 18:02, r476).
  - UN palette and Roboto, following the branding guideline in the repository (2026-09-26 17:22, r2).
  - Selection colours #0077B8, #CF3F0B and #9A58AF. In dark mode they are #009EDB, #E0701C and #A868BE. These come from the mockup and are recorded in the project memory.
  - Light and dark mode, and works on a phone (proposed r591; confirmed 2026-09-26 18:33, r683).

### 3.2 Opening lens strip ("Huella del mandato")

- **It replaces the hero-number cards.** The user rejected those cards as generic and asked for something more visual, with icons (2026-09-26 18:02, r476).
- **Option C was chosen:** every lens with its icon, showing how much the selection over- or under-indexes against the world (2026-09-26 18:12, r575; options page r565).
- **It also works as the topic selector** for the rest of the tab (proposed r565 and r591; confirmed 2026-09-26 18:33, r683).
- **Icons:** Tabler Icons (MIT licence), approved (2026-09-26 18:12, r575):

| Lens | Icon |
|---|---|
| Drugs and drug trafficking | `pill` |
| Prevention and treatment | `heart-handshake` |
| Alternative development | `plant-2` |
| Transnational organized crime | `affiliate` |
| Corruption and economic crime | `coins` |
| Terrorism | `shield-exclamation` |
| Trafficking in persons and migrant smuggling | `users-group` |
| Environmental crime | `trees` |
| Criminal justice | `gavel` |
| Peace (reference) | `peace` |

### 3.3 Selections and defaults

- **Up to three selections** compared side by side, each with a fixed colour (2026-09-26 17:31, r92; proposed r81).
- **Default:** ROCOL only. The other two slots start empty (2026-09-26 18:02, r476).
- **Overlaps are allowed**, for example ROCOL and Colombia together. The user asked about this in r92; r443 answered that a country in two selections takes the colour of the more specific selection, and the user did not object.
- **Year:** all years by default, with an option to pick a single year (2026-09-26 17:31, r92).
- **Unselected points** stay in the background, in grey (2026-09-26 17:31, r92).

### 3.4 Groups

- **Blocs:** Latin America and the Caribbean, EU-27, BRICS (the 10 members), G7, Africa and Asia-Pacific, plus any single country (2026-09-26 17:31, r92; proposed r81).
- **ROCOL:** exactly 8 countries: Argentina, Bolivia, Chile, Colombia, Ecuador, Paraguay, Peru and Uruguay. Brazil is excluded; it belongs to other regions (2026-09-26 18:02, r476).
- **UNODC field offices** (2026-09-26 18:28, r659; proposed r633):
  - Every office that covers more than one country is a group.
  - A single-country office appears as that country.
  - Countries with no field office form a group labelled "Covered from Headquarters".
- **Office list.** This is research output (`data/meta/unodc_offices.csv`), not a user decision:
  - Multi-country offices: ROCOL, ROPAN, ROSEN, ROSAF, ROEA, ROMENA, OGCCR, ROCA, ROSA, ROSEAP, ROSEE and POUKR.
  - Single-country offices: Brazil, Mexico and Nigeria.
  - Headquarters, Brussels and New York host offices only; they do not count as coverage.
- **Per-office link:** each office has its own link that opens with its region selected, for example `…/#ropan` (2026-09-26 18:28, r659).

### 3.5 Language

- **Spanish and English interface**, with an ES/EN switch (2026-09-26 18:12, r575).
- **Spanish is the starting language for everyone** (2026-09-29 01:17, s2 r9207).
- Speech text stays in English (section 2).

### 3.6 Semantic map

- **One global map, fitted once on all the data.** Year and selection only change the highlighting; the layout never changes (2026-09-26 18:02, r476).
- **One geography for both layers, kept across updates.** The map is fitted once on the fragments and saved. Each speech, and each new year's fragments, are placed among the fragments they most resemble, so nothing already on the map moves; a new edition of the map is a deliberate refit (2026-09-29 17:31, s4 r503; the method was left to the main agent, 18:49, s4 r670). Method: section 4, Map.
- **Two layers**, with a "Fragments / Speeches" toggle. Fragments is the default (2026-09-26 18:28, r659; details proposed r679, confirmed 2026-09-26 18:33, r683).
- **Speeches layer:** each dot is one speech, placed on the fragments' map where its fragments, taken together, sit. Hovering shows its topic composition and its most representative passage: the fragment closest to the whole-speech vector (r679; confirmed r683).
- **Region labels:** topic names written from example fragments, in Spanish and English (proposed r591 and r679; confirmed 2026-09-26 18:33, r683), each where its fragments concentrate; both layers show the same labels.
- **Points drawn:** the final map shows every fragment (r565; confirmed r683). The mockups show a sample.

### 3.7 World map and trend

- **World map:** a world map of attention to the selected lens and period (2026-09-26 17:31, r92).
- **Trend line:** averaged over 3 years (proposed r591; confirmed 2026-09-26 18:33, r683).

### 3.8 Distinctive words and excerpts

- **Word bars:** ranked bars of z-scores for single words and two-word phrases. No word cloud (2026-09-26 18:02, r476).
  - The method is Fightin' Words log-odds with an informative Dirichlet prior (Monroe et al. 2008) (proposed r565).
  - Each selection is compared with the rest of the world, on the same lens and period (2026-09-26 18:12, r575).
- **Excerpts:** short passages in the original English (2026-09-26 17:31, r92; proposed r591).

### 3.9 Country tab ("País")

It answers "where does Colombia align in a given year" (2026-09-26 18:21, r615). Pick a country and a year to see four things.

1. **Composition** of the speech: one horizontal 100% bar, with the top 5 topics labelled and the rest grouped as "Otros" (2026-09-26 18:28, r659; proposed r633).
2. **Alignment** (2026-09-26 18:28, r659; proposed r633):
   - the 5 most similar countries that year;
   - how close the country is to each bloc and each UNODC office;
   - both measured overall and on UNODC topics only.
3. **Its fragments** highlighted on the semantic map (r633; confirmed 2026-09-26 18:33, r683).
4. **Its excerpts** (r633; confirmed 2026-09-26 18:33, r683).

## 4. Method

- **Source text:**
  - A tidied copy of the corpus is kept apart from the original (2026-09-26 19:04, r961).
  - Every speech is cleaned under the same rules, with no deviations (2026-09-26 23:11, r2061).
  - Only text that is not the speaker's is dropped. Repairs are minimal and validated, and the text is never regenerated (project memory).
  - The tidy copy feeds both the fragment and the whole-speech embeddings. No embedding starts before it is complete (proposed r1902; accepted 2026-09-26 23:11, r2061).
  - Status on 2026-09-29 02:25: the tidy copy is complete for all 11,334 speeches (1946–2026). Every year re-applies with the current tool with no errors, and the full-corpus checks pass.
  - Later on 2026-09-29: 2024 was tidied again from the official records (193 statements, where the corpus had 192), and the Dominican Republic's 2026 speech was added, for 11,336 speeches in all. At 13:57 the 2026 cross-check and validation (section 2) were applied, the 2026 audit was clean and the full-corpus test passed.
- **Fragments** of about 150 words, built paragraph first (2026-09-26 18:28, r659; proposed r633):
  - the paragraphs are the tidy copy's, set by reading. Rebuilding them from the source layout, and packing transcripts by sentence, remain only as a fallback for a speech without a current tidy copy;
  - pieces under 60 words are merged, and pieces over 260 are split at a sentence;
  - a piece stays over 260 words only when no cut between sentences keeps every piece within 60 to 260 words. This is almost always because one sentence runs over 200 words. The one exception is a 1972 speech by Guatemala, whose paragraph has three sentences of 42, 190 and 57 words (2026-09-29 01:17, s2 r9207).
- **Embeddings:** Harrier-OSS-v1-0.6B (`microsoft/harrier-oss-v1-0.6b`) for both fragments and whole speeches. Every speech fits in its 32,768-token window (2026-09-26 18:28, r659; confirmed r683).
- **Uses of each embedding** (r679; confirmed 2026-09-26 18:33, r683):
  - Whole-speech vectors: the Speeches layer and the country alignment. Fragment averages serve as a cross-check.
  - Fragments: composition, lens scores, distinctive words and excerpts.
- **Map** (2026-09-29 18:49, s4 r670; the user asked that settings be judged by experience and checked, not searched by grid):
  - UMAP of the full 1,024-dimension fragment vectors by cosine, with no reduction before it, fitted once with seed 0 and saved.
  - 50 neighbours: at UMAP's default of 15, a quarter of a fragment's nearest fragments are its own country's in other years, so the map would group countries' repetitions rather than subjects; at 50 it is a sixth, and more neighbours barely lower it (measured on 215,090 fragments).
  - Minimum distance 0: each group packed tightly with clear space between groups, as the user asked (2026-09-29 16:30, s2 r24828).
  - Placement of new fragments: the mean position of their 50 nearest mapped fragments by cosine, weighted as UMAP weighs neighbours. Putting mapped fragments back this way lands them a median 0.7% of the map's diagonal from their place, and 2.2% land where no fragment is near (final map of 2026-09-29, 246,738 fragments, fitted in 9 minutes).
  - Placement of speeches: the same, applied to the mean of the speech's fragment vectors (2026-09-29 20:44). The whole-speech vector, tried first, crowded each year's speeches into one spot: on the 387 speeches of 2024 and 2026 it spread them over 0.57 and 0.48 of the fragments' extent on the two axes, against 0.78 and 0.66 for the mean of their fragments. With the mean, the 1986 speeches sit by apartheid, Central America, disarmament and the Middle East, as that year's debate did. The whole-speech vector still picks the representative passage and measures alignment.
- **Lenses:** the nine ROCOL lenses plus peace as a reference, as listed in section 3.2 (proposed r443; accepted 2026-09-26 18:02, r476).
- **Scoring** ("mandate component") (2026-09-26 18:02, r476; method replaced 2026-09-29 05:02, s2 r13904):
  - Each fragment gets a probability per lens from a classifier trained on about 20,000 fragments that agents labelled blind, and validated on about 5,000 more. A fragment can count for more than one lens.
  - Similarity to UNODC's own wording, including older phrasing, is used only to draw the labelled sample.
  - The user does not hand-label. The calibration method is in section 4.1.
- **Metric** (proposed r591; confirmed 2026-09-26 18:33, r683; graded shares 2026-09-29 04:14, s2 r13835):
  - A speech's share on a lens is the mean, over its fragments, of the probability that the fragment is about that lens. A fragment is about a lens when at least one full sentence in it is about that topic; a topic only named in a list does not count (section 4.1).
  - Ceremonial fragments (greetings, thanks) are left out of the percentages.
  - Group figures give each country equal weight: a group's value is the mean of its members' values, and over several years each country's mean over the years it spoke counts once. Speech length and the number of speeches do not weigh (confirmed 2026-09-29 01:17, s2 r9207).
- **Composition** (2026-09-26 18:28, r659; proposed r633):
  - Each fragment counts once: under the UNODC lens with the highest probability, when that probability is at least 0.5; otherwise under one of about 20 general topics from clustering (2026-09-29 05:02, s2 r13904). The same 0.5 threshold picks the excerpts shown for a lens.
  - General topics: k-means with 20 groups on the full vectors of the fragments about no lens (10 restarts, the best kept), named by reading. Every such fragment takes its nearest topic, the same main-topic simplification as the bars; a group that reads as a grab-bag is named "Otros temas". The centres are kept, so a new fragment takes the nearest existing topic (2026-09-29 17:48, s4 r643; 18:49, s4 r670). On 215,090 fragments, 14 of the 20 groups came back almost unchanged when k-means was rerun from another start; the broad ones shift at their edges.
  - Validation: agents estimate the composition of about 60 whole speeches blind, and the results are compared (r679; confirmed r683).
- **Text processing:** stopword removal applies only to word counts. Embeddings take the full clean text (stated in r443; not contested).

### 4.1 Lens calibration

The user left the calibration method to the main agent, asking for the most technical yet easiest to explain option, clear, with as little bias as possible, and faithful to the trends around UNODC mandates (2026-09-29 01:17, s2 r9207). The user then asked for one core method rather than a series of alternatives, with up to 10,000 labelled fragments (04:14, s2 r13835), and approved the method below (05:02, s2 r13904; proposed r13900). The user then enlarged the sample: about 20,000 fragments to label, train and tune, and about 5,000 more left for validation (16:30, s2 r24828). Its numbers and formulas are fixed in `docs/calibration.md`.

1. **What counts.** A fragment counts for a lens when at least one full sentence in it is about that topic, as the codebook defines (`data/lenses/codebook.md`, section 3.2, "substantive"). A topic only named in a list of threats does not count. Prevention, treatment and alternative development also count for drugs (codebook, section 3.4).
2. **Labelled sample.** About 25,000 fragments: the approved design of 10,000, scaled by 2.5 in every part (2026-09-29 16:30, s2 r24828). Only whole fragments are embedded; sentences are not (2026-09-29 03:47, s2 r13474).
   - 2,500 are drawn at random, 500 from each of five periods (1946–1969, 1970–1989, 1990–2009, 2010–2024, 2025–2026).
   - The rest are split equally over the 10 lenses and the five periods. Within each group, most are drawn where the lens is most likely, by similarity to its description in UNODC's own words (`data/lenses/lenses.yaml`), and some lower down, to catch what the classifier would otherwise miss. This is the only use of that similarity.
   - Each fragment's chance of being drawn is recorded, so every figure is weighted back to the whole corpus.
3. **Labelling.** Three agents read each fragment separately. They see only the text and the year, never the country, the speaker or any score. For each lens they record "about it", "only listed" or "not at all", following the codebook, and quote the deciding sentence. When the three disagree, a fourth agent decides by the codebook. Scripts only check the format; no label is chosen by a script. The agents run five at a time, and their agreement is reported.
4. **Training and validation sets.** One speech in five is drawn at random, and its sampled fragments, about 5,000, form the validation set. The other fragments, about 20,000, train and tune the classifiers. The validation set is labelled first, never used for tuning, and gives every accuracy figure (2026-09-29 16:30, s2 r24828).
5. **Classifier.** One classifier per lens, a logistic regression on the fragment embedding, gives each fragment a probability for that lens. Its settings are tuned by cross-validation within the training set.
6. **Shares.** A speech's share on a lens is the mean of its fragments' probabilities (graded shares). A fragment counts as "about" a lens at a probability of 0.5 or more; this is used for the excerpts and the composition bars.
7. **Pass bar.** A lens gets a trend line and a map only if, on the validation set, precision and recall at 0.5 are both at least 0.70, overall and in each period with at least 20 checked examples of that lens. A lens that falls short is brought to the user; no fallback method is tried.
8. **Frozen before results.** The descriptions, the sample, the method and the classifiers are fixed before any trend is computed. The known-event checks of section 6 are run afterwards, as a test, never for tuning.
9. **Published.** The methods note gives, for each lens and period, precision, recall, agreement between agents and the number of checked examples.

## 5. Hosting and delivery

- **Site:** a public static site on GitHub Pages (2026-09-26 17:31, r92).
- **Repository:** `baqata/unga-speech-analysis` (2026-09-26 18:12, r575).
- **Repository contents:** code, derived data and short excerpts. The raw corpus is not committed; it is cited from Dataverse (proposed r565; the user renamed the repository and approved it, r575).
- **Maintenance:** the user maintains the site, with a one-command yearly update and a runbook (2026-09-26 17:31, r92; proposed r81 and r591).
- **Deliverables:** the public site, the repository, a yearly-update runbook, and a short methods note for technical readers, kept separate from the dashboard (proposed r591 and r679; confirmed 2026-09-26 18:33, r683).

## 6. Quality assurance

- **Who checks:** no human testers for now. Checks are impartial and run by agents that did not build the tool. Human feedback comes later (2026-09-26 18:02, r476).
- **Checks** (proposed r591 and r679; confirmed 2026-09-26 18:33, r683):
  - **Data:** automated tests on counts, fragments, removed introductions and totals.
  - **Measurement:**
    - precision, recall and agreement on the labelled sets, by era;
    - known events must show up: terrorism rising in 2001, a drugs peak around UNGASS 1998, and Latin America ahead of the world on drugs.
  - **Numbers:** every figure on screen is recalculated independently.
  - **Interface:** screenshots on desktop and phone, in light and dark mode, and in ES and EN; no console errors; a page-size limit.
  - **Communication:**
    - "new user" agents see only screenshots and must answer the key questions correctly;
    - a copy check keeps out jargon and any caption longer than one line.
  - **Code:** an adversarial code review.
  - **Usability:**
    - Persona agents do real tasks: the ROCOL Representative, the organized crime lead, the SIMCI lead, a ROPAN officer and a Vienna analyst.
    - They report missing toggles, confusing controls and elements that do not fit a view.
    - Fixes are applied, and the loop repeats until a round comes back clean (2026-09-26 18:28, r659).

## 7. Deferred to version 2

- The framing axis: how drugs are framed, from security to health (2026-09-26 18:02, r476).
- Sentence-level scores: about 1.2 million sentences, the same text and about 37 million tokens as the fragments, so about 8 hours or more of embedding. To be evaluated later (user, 2026-09-29 03:55).

## 8. Superseded decisions

| Earlier decision | Replaced by |
|---|---|
| Qwen3-Embedding-4B (r476, r575) | Harrier-OSS-v1-0.6B for fragments and whole speeches (2026-09-26 18:28, r659) |
| No alignment view (r476) | Country tab with alignment (2026-09-26 18:21, r615; 18:28, r659) |
| Speech vectors as fragment averages only (proposed r633) | Separate whole-speech embeddings, with a map toggle (2026-09-26 18:28, r659) |
| Word cloud (r2; mockup v1) | Z-score bars for words and two-word phrases (2026-09-26 18:02, r476) |
| Hero-number cards (mockup v1) | Lens strip, option C (2026-09-26 18:02, r476; 18:12, r575) |
| Three pre-filled selections (mockup v1) | ROCOL only (2026-09-26 18:02, r476) |
| Spanish by default for everyone (r92) | Starting language follows the browser (2026-09-26 18:28, r659) |
| Starting language follows the browser (r659) | Spanish for everyone (2026-09-29 01:17, s2 r9207) |
| Dotted 2024–2025 segment on the trend (proposed r443) | No visible caveat (2026-09-26 18:02, r476) |
| Sentences scored as well as fragments (method of s2 r9207) | Whole fragments only (2026-09-29 03:47, s2 r13474) |
| Lens scores by similarity to UNODC's wording, with three description variants, a cut-off where precision equals recall and a fallback classifier (s2 r9207) | One logistic regression per lens; similarity only draws the sample (2026-09-29 05:02, s2 r13904) |
| About 2,000 labelled fragments (r591, s2 r9207) | 10,000 labelled fragments (2026-09-29 04:14, s2 r13835; 05:02, r13904) |
| 10,000 labelled fragments in a development half and a test half (s2 r13904) | About 25,000: about 20,000 to train and tune, about 5,000 to validate, split by speech (2026-09-29 16:30, s2 r24828) |
| Yes/no fragment shares (r591) | Graded shares: the mean probability (2026-09-29 04:14, s2 r13835) |
| One UMAP per layer, the fragments' through a 64-dimension PCA (r476, r679) | One map fitted on the full fragment vectors; speeches and later fragments placed on it (2026-09-29 18:49, s4 r670) |
| Speeches placed on the map by their whole-text vector (2026-09-29 18:49) | Placed by the mean of their fragments' vectors, which spreads each year's speeches by subject (2026-09-29 20:44) |
| Composition by the widest margin over calibrated cut-offs (r659) | The lens with the highest probability, at 0.5 or more (2026-09-29 05:02, s2 r13904) |
| 2024 texts from the corpus v14 (r92) | The official verbatim records A/79/PV.7–17 (2026-09-29 05:51, s2 r14183) |
| 2026 added when the dataset authors publish it (proposed r81) | Provisional 2026 now (2026-09-26 18:02, r476; 18:12, r575) |

## 9. Open points

These are not settled. The mockup's handling is noted where it had to choose. Points 4, 7 and 10 were settled on 2026-09-29 (s2 r9207) and are listed after the open ones.

1. **Summary sentence under the strip.** The proposal was option C "with A's sentence under it" (r565); the user answered only "C" (r575). The mockup shows the strip without the sentence.
2. **Distinctive words on the Country tab.** They were in the proposal the user accepted (r633, r659) but are missing from the confirmed plan (r679, r683). The mockup follows the confirmed plan and leaves them out.
3. **Label of the no-field-office group.** The confirmed label is "Covered from Headquarters" (r659, r683). A later internal note, never put to the user, suggested a factual label such as "Sin oficina de terreno de UNODC". The mockup uses the confirmed label.
5. **Strip details:**
   - the default lens, and whether the strip keeps option C's "all UNODC topics" tile (shown in r565, never discussed);
   - how the strip shows two or three selections at once.

   The mockup keeps the tile, opens on it, shows the ratio for the first selection, and shows a dot for every selection.
6. **Country tab details:**
   - the default country;
   - what "all years" shows;
   - how similarity is expressed to non-technical readers.

   The mockup opens on Colombia (the user's own example), adds up all years, and shows similarity as a percentile within the year, as `docs/data-contract.md` proposes.
8. **Visual treatment of provisional 2026.** Beyond the selector label, nothing is agreed, for example on the trend. The mockup predates the 2026 texts, which were tidied on 2026-09-28.
9. **Word comparison with the selection's own past.** It was suggested for version 2 (r565). The user answered only for the MVP (r575).

Settled on 2026-09-29:

- **4. Alternative development:** measured like every lens, and shown with a trend line only if it passes the calibration bar; otherwise through excerpts only (section 4.1, step 6).
- **7. Group weighting:** each country weighs the same, over fragment shares (section 4, Metric); `docs/data-contract.md` now says so.
- **10. Nauru's new name:** filed under NRO for all years and named Naoero, with "Nauru (2000–2025)" on hover (section 2).

## Design files

- Mockup: https://claude.ai/artifact/BswNTFYGfpVwGZAG7arsZQ (private). Local copies are `docs/design/mockup-v1.html` (the 2026-09-26 template) and `docs/design/mockup-v2.html` (this plan).
- Summary-strip options: https://claude.ai/artifact/99tqJ7xyp1DgSRiEsArM3t (local copy `docs/design/summary-options.html`).
- Icons: `docs/design/tabler-icons-subset.json`.
