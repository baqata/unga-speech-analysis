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
  - It appears in the year selector as "2026", like any other year, with no label or note (2026-09-29 21:56, s4 r2316).
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

- **Three tabs.** The dashboard opens on "Regiones y mundo" (2026-09-26 18:28, r659; proposed r633).
  - **Regiones y mundo:** the lens strip, the semantic map with its toggle, the world map, the trend, the distinctive-word bars and the excerpts (confirmed 2026-09-26 18:33, r683; proposed r679).
  - **País:** see section 3.9.
  - **Anexo técnico:** how the site was made, in plain words and without tool names: the speeches, the fragments, the fingerprint of meaning, the labelled sample, one model per topic, the settings chosen by cross-validation, the general topics and the map; then, for each topic, its examples and, from the cross-validation, its precision, its recall ("sensibilidad") and their F1, which decides its badge, under those usual names, each explained in plain words (user, 2026-09-30 18:56, s4 r20659); how the site uses the models; and the limits (2026-09-30 17:07, s4 r17922; 17:57, s4 r18894). Thresholds, the readers' agreement and the figures by period stay in the methods note, not on the site (user, 2026-09-30 18:33, s4 r19860; 18:39, s4 r20072). Deep links `#anexo` and `#annex`.
- **Look:**
  - No logo, and no UN or UNODC emblem (2026-09-26 18:02, r476).
  - UN palette and Roboto, following the branding guideline in the repository (2026-09-26 17:22, r2).
  - Selection colours #0077B8, #CF3F0B and #9A58AF. In dark mode they are #009EDB, #E0701C and #A868BE. These come from the mockup and are recorded in the project memory.
  - Light and dark mode, and works on a phone (proposed r591; confirmed 2026-09-26 18:33, r683).

### 3.2 Opening lens strip ("Huella del mandato")

- **It replaces the hero-number cards.** The user rejected those cards as generic and asked for something more visual, with icons (2026-09-26 18:02, r476).
- **Option C was chosen:** every lens with its icon, showing how much the selection over- or under-indexes against the world (2026-09-26 18:12, r575; options page r565).
- **It also works as the topic selector** for the rest of the tab (proposed r565 and r591; confirmed 2026-09-26 18:33, r683).
- **No ratio for a share under 0.05%**, which reads "<0,1 %": at that level the ratio to the world is noise (after the user's question on ROCOL, 2026 and alternative development, 2026-09-30 19:11, s4 r21187).
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

Peace, first shown as a reference lens, is no longer measured or shown: it covered about half of what the speeches say, too broad to set beside the mandate topics, and its passages join the general topics (user, 2026-09-30).

Prevention and treatment, the topic with the fewest examples, is shown like the other topics short of the pass bar, with the "Aprox." badge; its fragments also count within drugs through the umbrella rule and in "all UNODC topics" (user, 2026-09-30 19:11, s4 r21187). The topics short of the pass bar keep their card, with an "Aprox." badge (section 3.7).

### 3.3 Selections and defaults

- **Up to three selections** compared side by side, each with a fixed colour (2026-09-26 17:31, r92; proposed r81).
- **Default:** ROCOL only. The other two slots start empty (2026-09-26 18:02, r476).
- **Overlaps are allowed**, for example ROCOL and Colombia together. The user asked about this in r92; r443 answered that a country in two selections takes the colour of the more specific selection, and the user did not object.
- **Year:** all years by default, with an option to pick a single year (2026-09-26 17:31, r92) or a range of years (2026-09-30 04:20). One slider with two handles: from all years, the first move picks one year, and either handle then widens or narrows the period. The word bars and the alignment are computed for one year or for all years; for a partial range they say so.
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
- **Speeches layer:** each dot is one speech, placed on the fragments' map where its fragments, taken together, sit (r679, confirmed r683; mean (2026-09-29 21:56, s4 r2316)). Hovering shows its topic composition and a passage: of its most probable excerpt about a UNODC topic, where that topic's words weigh most (section 3.8; 2026-09-30 20:09, s4 r23215); in a speech with none, from the fragment closest to the mean of its fragments' vectors, its first and last left out (2026-09-30 04:20).
- **Fragments layer:** hovering shows the country, the year, the fragment's topic and a passage of it on that topic (2026-09-30 04:20).
- **Card on click:** a fragment about a UNODC topic, wherever it is drawn, opens a card on click (a tap on a phone): its whole text, the speaker, and each UNODC topic it is about, the chosen topic first. Each topic shows the model's hit rate at the fragment's probability, as "n of 10": of every 10 fragments with a probability like it on that topic, how many are about it, from the labelled fragments' out-of-fold probabilities (a weighted isotonic fit). Raw probabilities are not shown, since each topic has its own scale: prevention and treatment counts from 0.65 %, and the COL 2022 fragment at 3 % on it has a hit rate of 5 of 10. A labelled fragment shows "read" where the reader placed it. A speech point opens the card of its most probable excerpt, the one its hover quotes. Other points keep their hover (proposed 2026-09-30 20:21, s4 r23691; user, 20:46, s4 r24000, who asked which details to show and noted that raw probabilities would look contradictory; the hit rate is the main agent's answer). Rules: `docs/data-contract.md`, `cards/<iso3>.json`.
- **Highlighting:** light grey for every point of the period (one year, a range or all years), dark grey for the selections' points, and each selection's colour for its points about the chosen topic, all UNODC topics or one; a speech counts when any of its fragments is about it. Points outside the selections are never tinted by topic (2026-09-30 04:37). The country tab, which has no topic choice, colours the country's points about any UNODC topic. Topics marked approximate are tinted like the others (2026-09-30 17:07, s4 r17922). Only the period's points are drawn, the rest of the world included (user, 2026-09-30 19:05, s4 r20943).
- **Region labels:** topic names written from example fragments, in Spanish and English (proposed r591 and r679; confirmed 2026-09-26 18:33, r683), each where its fragments concentrate; both layers show the same labels. Every UNODC topic is named where the fragments about it gather, so alternative development and prevention and treatment, which sit inside the drugs region, are named too, a line above or below when names would overlap (user, 2026-09-30 19:11, s4 r21187).
- **Zoom:** up to 24 times on a computer. Past twice, the whole map appears in a corner with the part in view outlined, and a click on it centres the view there (user, 2026-09-30 19:26, s4 r21772).
- **Points drawn:** the final map shows every fragment (r565; confirmed r683). The mockups show a sample.

### 3.7 World map and trend

- **World map:** a world map of attention to the selected lens and period (2026-09-26 17:31, r92), in five classes that are the same for every topic: under 1%, 1–5%, 5–10%, 10–20% and 20% or more (user, 2026-09-30 19:24, s4 r21744).
- **Trend line:** each year's value, the one a card shows for that year, drawn as a smooth curve through the points (user, 2026-09-30 19:28, s4 r21834).
- **Topics short of the pass bar** (section 4.1, step 7) keep their trend line, world map, map colour and words, with an "Aprox." badge on their card and a "Medición aproximada: ver anexo técnico" link beside the world map and the trend, because their mean probability follows the labelled share (2026-09-30 17:07, s4 r17922). The technical annex explains the badge.

### 3.8 Distinctive words and excerpts

- **Word bars:** ranked bars of z-scores for single words and two-word phrases. No word cloud (2026-09-26 18:02, r476).
  - The method is Fightin' Words log-odds with an informative Dirichlet prior (Monroe et al. 2008) (proposed r565).
  - Each selection is compared with the rest of the world, on the same lens and period (2026-09-26 18:12, r575).
  - A word must be used by at least two of the selection's speeches, and for a group by two of its members, when it has that many: in the first real build a sixth of a group's words came from one member alone (QA of the first real build, 2026-09-30 06:39).
- **Excerpts:** whole fragments in the original English, however long (2026-09-26 17:31, r92; user, 2026-09-30 20:09, s4 r23215). Every fragment about the topic can be shown, and each speech offers its three most probable. Each quote is tagged with every UNODC topic its fragment is about, the chosen topic or its main topic first (user, 2026-09-30 20:34, s4 r23826). A part chosen within the fragment, by the topic's classifier, sometimes quoted the wrong sentence: the classifier learned from whole fragments, and of the 80 alternative development passages read, 3 showed a sentence next to the one about the topic (2026-09-30 20:01, s4 r23080). The site shows the three most probable of the selection in the period, from any of its members, even all from one country, the most recent first on a tie, and with several selections each one's best in turns (user, 2026-09-30; 18:59, s4 r20770). Rules: `docs/data-contract.md`, `excerpts/<lens>.json`.

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
  - The tidy copy feeds the embeddings. No embedding starts before it is complete (proposed r1902; accepted 2026-09-26 23:11, r2061).
  - Status on 2026-09-29 02:25: the tidy copy is complete for all 11,334 speeches (1946–2026). Every year re-applies with the current tool with no errors, and the full-corpus checks pass.
  - Later on 2026-09-29: 2024 was tidied again from the official records (193 statements, where the corpus had 192), and the Dominican Republic's 2026 speech was added, for 11,336 speeches in all. At 13:57 the 2026 cross-check and validation (section 2) were applied, the 2026 audit was clean and the full-corpus test passed.
- **Fragments** of about 150 words, built paragraph first (2026-09-26 18:28, r659; proposed r633):
  - the paragraphs are the tidy copy's, set by reading. Rebuilding them from the source layout, and packing transcripts by sentence, remain only as a fallback for a speech without a current tidy copy;
  - pieces under 60 words are merged, and pieces over 260 are split at a sentence;
  - a piece stays over 260 words only when no cut between sentences keeps every piece within 60 to 260 words. This is almost always because one sentence runs over 200 words. The one exception is a 1972 speech by Guatemala, whose paragraph has three sentences of 42, 190 and 57 words (2026-09-29 01:17, s2 r9207).
- **Embeddings:** Harrier-OSS-v1-0.6B (`microsoft/harrier-oss-v1-0.6b`) for the fragments (2026-09-26 18:28, r659; confirmed r683). Each fragment is embedded as a document, with no instruction, as the model's authors specify for documents; only the lens descriptions, which draw the calibration sample, are embedded as queries with an instruction (`data/lenses/lenses.yaml`).
- **Uses of the embeddings:**
  - Fragments: composition, lens scores, distinctive words, excerpts and the map (r679; confirmed 2026-09-26 18:33, r683).
  - Speeches, each as the mean of its non-ceremonial fragments' vectors: its place on the map, the passage shown on hover when the speech has no fragment about a UNODC topic (the fragment closest to that mean, its first and last left out, section 3.6) and the country alignment, overall and on UNODC topics (2026-09-29 21:56, s4 r2316). On the 387 speeches of 2024 and 2026, the fragment closest to the mean was the speech's first or last in 56% of cases and from the openings-and-closings group in 4% (35% and 6% of all fragments). A speech's 5 most similar speeches of the same year shared its subregion in 53% (2024) and 58% (2026) of cases; chance is 12%.
- **Map** (2026-09-29 18:49, s4 r670; the user asked that settings be judged by experience and checked, not searched by grid):
  - UMAP of the full 1,024-dimension fragment vectors by cosine, with no reduction before it, fitted once with seed 0 and saved.
  - 50 neighbours: at UMAP's default of 15, a quarter of a fragment's nearest fragments are its own country's in other years, so the map would group countries' repetitions rather than subjects; at 50 it is a sixth, and more neighbours barely lower it (measured on 215,090 fragments).
  - Minimum distance 0: each group packed tightly with clear space between groups, as the user asked (2026-09-29 16:30, s2 r24828).
  - Placement of new fragments: the mean position of their 50 nearest mapped fragments by cosine, weighted as UMAP weighs neighbours. A UMAP map has no formula for a new point: UMAP's own transform starts it at this same weighted mean and then adjusts it a little. The adjustment is skipped, so only the saved coordinates are needed and the result repeats exactly. Putting mapped fragments back this way lands them a median 0.7% of the map's diagonal from their place, and 2.2% land where no fragment is near (final map of 2026-09-29, 246,738 fragments, fitted in 9 minutes).
  - Placement of speeches: the same, applied to the mean of the speech's fragment vectors (2026-09-29 20:44). This spreads each year's speeches by subject: the 387 speeches of 2024 and 2026 spread over 0.78 and 0.66 of the fragments' extent on the two axes, and the 1986 speeches sit by apartheid, Central America, disarmament and the Middle East, as that year's debate did.
- **Lenses:** the nine ROCOL lenses, as listed in section 3.2 (proposed r443; accepted 2026-09-26 18:02, r476). Peace, labelled as a reference, is no longer measured or shown (user, 2026-09-30).
- **Scoring** ("mandate component") (2026-09-26 18:02, r476; method replaced 2026-09-29 05:02, s2 r13904):
  - Each fragment gets a probability per lens from a classifier trained on about 25,000 fragments that agents labelled blind, and evaluated by five-fold cross-validation. A fragment can count for more than one lens.
  - Similarity to UNODC's own wording, including older phrasing, is used only to draw the labelled sample.
  - The user does not hand-label. The calibration method is in section 4.1.
- **Metric** (proposed r591; confirmed 2026-09-26 18:33, r683; graded shares 2026-09-29 04:14, s2 r13835):
  - A speech's share on a lens is the mean, over its fragments, of the probability that the fragment is about that lens. A fragment is about a lens when at least one full sentence in it is about that topic; a topic only named in a list does not count (section 4.1).
  - Ceremonial fragments (greetings, thanks) are left out of the percentages.
  - Group figures give each country equal weight: a group's value is the mean of its members' values, and over several years each country's mean over the years it spoke counts once. Speech length and the number of speeches do not weigh (confirmed 2026-09-29 01:17, s2 r9207).
- **Composition** (2026-09-26 18:28, r659; proposed r633):
  - Each fragment counts once: under the UNODC lens with the highest probability, when that probability reaches the lens's threshold (section 4.1, step 6); otherwise under one of the general topics from clustering (2026-09-29 05:02, s2 r13904). The same threshold picks the excerpts shown for a lens.
  - General topics: k-means with 14 groups on the full vectors of the fragments about no UNODC lens, the former peace passages included (10 restarts, the best kept), named by reading. Every such fragment takes its nearest topic, the same main-topic simplification as the bars; a group that reads as a grab-bag is named "Otros temas". The centres are kept, so a new fragment takes the nearest existing topic (2026-09-29 17:48, s4 r643; 18:49, s4 r670). On 215,090 fragments, 14 of the 20 groups came back almost unchanged when k-means was rerun from another start; the broad ones shift at their edges. The run is seeded, so it repeats exactly; another start ends in another, almost equally good split because many fragments sit between subjects (54% are within 0.02 of a second centre). Kept as designed (2026-09-29 21:56, s4 r2316). The number of groups was then tested on 60,000 of the 235,440 fragments the topics cover (2026-09-30, after the user asked whether 20 was right): k-means inertia falls smoothly from 8 to 60 groups, with no elbow; the silhouette is 0.03 to 0.05 at every number, since the passages form a continuum of subjects rather than separate clusters; so neither index can choose. Split-half stability can: fitted on two halves, three times each, 81% of the topics came back (best-match overlap of 0.7 or more) at 14 groups, 60% at 16 and 52% at 20, and fewer groups were no more stable. So 14, the largest number before the topics stop reproducing (2026-09-30).
  - Speech openings and closings: fragments made only of greetings, congratulations and thanks are left out as ceremonial (12,082 of 258,820). Openings and closings that mix courtesy with substance stay; if the final fit gathers them in one group, it gets a plain name such as "Apertura y cierre" (2026-09-29 21:56, s4 r2316).
  - Validation: agents estimate the composition of about 60 whole speeches blind, and the results are compared (r679; confirmed r683).
- **Text processing:** stopword removal applies only to word counts. Embeddings take each fragment's full clean text (stated in r443; not contested).

### 4.1 Lens calibration

The user left the calibration method to the main agent, asking for the most technical yet easiest to explain option, clear, with as little bias as possible, and faithful to the trends around UNODC mandates (2026-09-29 01:17, s2 r9207). The user then asked for one core method rather than a series of alternatives, with up to 10,000 labelled fragments (04:14, s2 r13835), and approved the method below (05:02, s2 r13904; proposed r13900). The user then enlarged the sample to about 25,000 labelled fragments (16:30, s2 r24828). Its numbers and formulas are fixed in `docs/calibration.md`.

1. **What counts.** A fragment counts for a lens when at least one full sentence in it is about that topic, as the codebook defines (`data/lenses/codebook.md`, section 3.2, "substantive"). A topic only named in a list of threats does not count. Prevention, treatment and alternative development also count for drugs (codebook, section 3.4).
2. **Labelled sample.** About 25,000 fragments: the approved design of 10,000, scaled by 2.5 in every part (2026-09-29 16:30, s2 r24828). Only whole fragments are embedded; sentences are not (2026-09-29 03:47, s2 r13474).
   - 2,500 are drawn at random, 500 from each of five periods (1946–1969, 1970–1989, 1990–2009, 2010–2024, 2025–2026).
   - The rest are split equally over the 10 lenses and the five periods. Within each group, most are drawn where the lens is most likely, by similarity to its description in UNODC's own words (`data/lenses/lenses.yaml`), and some lower down, to catch what the classifier would otherwise miss. This is the only use of that similarity.
   - Each fragment's chance of being drawn is recorded, so every figure is weighted back to the whole corpus.
3. **Labelling** (2026-09-29 21:56, s4 r2316).
   - One agent (Opus, medium effort) reads each fragment: 167 batches of about 150, ten agents at a time. It sees only the text and the year, never the country, the speaker or any score. For each lens it records "about it", "only listed" or "not at all", following the codebook (version 1.2, which tightened peace, lists and generic crime after the pilot's 17 disagreements), and notes the deciding rule when a case is close. Scripts only check the format; no label is chosen by a script.
   - A check follows. For each lens, 30 fragments the labeller marked as about it and 30 near-misses it marked as not, about 600 in all, are labelled again, blind, by an agent at maximum effort. A third agent at maximum effort decides where the two differ.
   - After the core labelling, codebook 1.3 settles four kinds of case: accusations and designations of States as sponsors of terrorism, acts and groups the Security Council has called terrorist, extremism without violence, and Security Council action on criminal violence. The check agent and the deciding agent work under it. The check agent also reads a second time, blind, the fragments of the audited fifth (step 4) the labeller was unsure of, every fragment it was most unsure of and the 251 that the new rules may change, about 1,800 in all; the deciding agent settles every difference (2026-09-30 00:30).
   - After the check, every lens rule was checked against UNODC's official definitions and scope, and codebook 1.4 aligns them: the acts defined in the counter-terrorism treaties count by their kind, State support for terrorists is terrorism, the illicit arms trade is organized crime whoever receives the weapons, crime in general and the conduct of police and detention are criminal justice, and fisheries and minerals crime follow UNODC's definitions. Each lens has three positive and two negative examples. Check agents read again, under 1.4, the 1,039 fragments outside the check whose label the new rules may change, and 250 more drawn elsewhere to see what else 1.4 changes, ten agents in two rounds of five; for the 260 such fragments already checked, the deciding agent settles the lenses concerned under 1.4. If more than about one in ten of the 250 change, the user decides between labelling the whole sample again and reading its positives again (2026-09-30 02:48).
   - A lens whose agreement (kappa) falls below 0.8 is brought to the user before the classifiers are fitted.
4. **Audited fifth.** One speech in five is drawn at random (2026-09-29 16:30, s2 r24828). Its sampled fragments, about 5,000, are labelled first, and those the labeller was unsure of are read a second time (step 3), which measures how often a doubtful label changes.
5. **Classifier.** One classifier per lens, a support vector machine with an RBF kernel on the fragment embedding, gives each fragment a probability for that lens (user, 2026-09-30, after a comparison on the final labels: mean average precision 0.746 against 0.717 for logistic regression). Its settings, its calibration and its threshold come from five-fold cross-validation over all the labelled fragments, with the folds split by speech, and the classifier that measures the corpus is fitted on all of them (user, 2026-09-30 17:57, s4 r18894).
6. **Shares.** A speech's share on a lens is the mean of its fragments' probabilities (graded shares). A fragment counts as "about" a lens when its probability reaches that lens's threshold, the probability with the best F1 in the cross-validation (user, 2026-09-30); this is used for the excerpts and the composition bars.
7. **Pass bar.** A lens passes if the F1 of its out-of-fold decisions at its threshold is at least 0.70, over all periods together and in each period with at least 20 labelled examples of that lens; precision and recall weigh the same, and the threshold maximizes F1 (user, 2026-09-30 18:20, s4 r19488). A lens that falls short is brought to the user; no fallback method is tried. The user chose to show the short lenses with an "approximate" badge (2026-09-30 17:07, s4 r17922), prevention and treatment included (19:11, s4 r21187; sections 3.2 and 3.7).
8. **Frozen before results.** The descriptions, the sample, the method and the classifiers are fixed before any trend is computed. The known-event checks of section 6 are run afterwards, as a test, never for tuning.
9. **Published.** The methods note gives, for each lens and period, precision, recall, F1 and the number of labelled positives, and for each lens the agreement between the labeller and the check. The site's technical annex gives the plain-language version: per lens, the cross-validated precision, recall and F1 of the classifiers the site uses (2026-09-30 17:07, s4 r17922; 18:33, s4 r19860; 18:39, s4 r20072).

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
    - precision, recall and agreement on the labelled fragments, by era;
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

## 7. Next work and version 2

Next, to be implemented (user, 2026-09-30 17:57, s4 r18894):

- A reading round, "net and read": every fragment with at least a 2% probability of any topic but terrorism (11,781, of which 2,142 already labelled; a 5% net leaves 5,683 to read), read by the same labeller under the same codebook, marking the sentence that carries each topic, with a checked sample. Trends would become shares of confirmed passages. The user likes the rule (proposed 2026-09-30 17:03, s4 r17918; 17:09, s4 r17956).
- A targeted labelling round: about 300 fragments per topic among those its classifier ranks highest, prevention and treatment and alternative development first, then a refit; it needs a manifest revision (2026-09-30 17:10, s4 r17973).

Version 2:

- The framing axis: how drugs are framed, from security to health (2026-09-26 18:02, r476).
- Comparing a selection's words with its own past (open point 9, 2026-09-29 21:56, s4 r2316).
- Sentence-level scores: about 1.2 million sentences, the same text and about 37 million tokens as the fragments, so about 8 hours or more of embedding. To be evaluated later (user, 2026-09-29 03:55).
- Fine-tuning the embedding model: not now, since the rare topics have about 40 examples and most errors are reading judgements; if ever, LoRA on one shared model, after a larger labelled set (advice of 2026-09-30 17:03, s4 r17918, on the user's question of 16:59, s4 r17836).

## 8. Superseded decisions

| Earlier decision | Replaced by |
|---|---|
| Qwen3-Embedding-4B (r476, r575) | Harrier-OSS-v1-0.6B (2026-09-26 18:28, r659) |
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
| 10,000 labelled fragments (s2 r13904) | About 25,000 (2026-09-29 16:30, s2 r24828) |
| Yes/no fragment shares (r591) | Graded shares: the mean probability (2026-09-29 04:14, s2 r13835) |
| One UMAP per layer, the fragments' through a 64-dimension PCA (r476, r679) | One map fitted on the full fragment vectors; speeches and later fragments placed on it (2026-09-29 18:49, s4 r670) |
| Speeches placed on the map by their whole-text vector (2026-09-29 18:49) | Placed by the mean of their fragments' vectors, which spreads each year's speeches by subject (2026-09-29 20:44) |
| Whole-speech vectors for the hover passage and the country alignment (r679, r683) | The mean of the speech's fragment vectors for its place, its hover passage and the alignment; whole-speech embeddings dropped (2026-09-29 21:56, s4 r2316) |
| A speech's hover passage from the fragment closest to its mean (2026-09-29 21:56) | From its fragment most about a UNODC topic, else the one closest to the mean outside its first and last; fragments get a passage on hover too (2026-09-30 04:20) |
| Passages that start at a sentence with a key term of the lens (overnight build, 2026-09-30) | The part of the fragment most about its topic by the words that set the topic apart, with a minimum and a maximum length (2026-09-30 04:24) |
| Speeches or fragments about the chosen lens tinted on the semantic map (mockup) | Only the rest of the points and the selections (2026-09-30 04:37) |
| Only the rest of the points and the selections, each in one colour (2026-09-30 04:37) | Within the selections, the points about the chosen topic in colour and the others in dark grey (2026-09-30 15:45) |
| A lens short of the pass bar gets passages only: no figure on its card, no trend, no world map, no map colour, no words (`docs/calibration.md`, section 6; 2026-09-30 15:45 for the map colour) | Shown everywhere with an "Aprox." badge linking to the technical annex (2026-09-30 17:07, s4 r17922) |
| Prevention and treatment measured and shown like every lens (r575) | Not shown; its fragments count within drugs (2026-09-30 17:07, s4 r17922) |
| Prevention and treatment not shown (2026-09-30 17:07, s4 r17922) | Shown with the "Aprox." badge (2026-09-30 19:11, s4 r21187) |
| Trend averaged over 3 years (proposed r591; confirmed r683) | Each year's value, drawn as a smooth curve (2026-09-30 19:28, s4 r21834) |
| With a year chosen, the other years as a faint outline on the maps (2026-09-30 04:20) | Only the period's points (2026-09-30 19:05, s4 r20943) |
| Two tabs (r659) | Three: a technical annex added (2026-09-30 17:07, s4 r17922) |
| One year or all years (r92) | Also a range of years (2026-09-30 04:20) |
| Three labellers read every fragment, a fourth decides disagreements, five agents at a time (s2 r13904) | One labeller, ten at a time, with a check of about 600 fragments at maximum effort and a resolver; codebook 1.2 (2026-09-29 21:56, s4 r2316) |
| A check of about 600 fragments only (2026-09-29 21:56) | Also a second reading of the doubtful labels of the audited fifth and of the fragments codebook 1.3 may change, about 1,800 (2026-09-30 00:30) |
| Codebook 1.3 for the check and the resolver (2026-09-30 00:30) | Codebook 1.4, aligned with UNODC's official definitions; the fragments it may change read again or resolved, and a review of 250 more (2026-09-30 01:58, 02:48) |
| "2026 (en curso)" in the year selector (proposed r591; confirmed r683) | "2026", like any other year, with no label or note (2026-09-29 21:56, s4 r2316) |
| Composition by the widest margin over calibrated cut-offs (r659) | The lens with the highest probability, at 0.5 or more (2026-09-29 05:02, s2 r13904) |
| One threshold, 0.5, for every lens (s2 r13904) | Each lens's own threshold, at its best F1 in the cross-validation (2026-09-30) |
| Logistic regression per lens (s2 r13904) | RBF support vector machine per lens, fitted on all the labelled fragments (2026-09-30) |
| Pass bar: precision and recall each at least 0.70 (s2 r13904) | F1 at least 0.70; precision and recall weigh the same (2026-09-30 18:20, s4 r19488) |
| Peace as a reference lens (r476) | Peace not measured or shown; its passages join the general topics (2026-09-30) |
| 20 general topics (s4 r643) | 14, the largest number whose topics reproduce on split halves (2026-09-30) |
| Excerpts from the most recent speeches, one per country, each where its words weigh most for the topic (2026-09-30 04:24) | The three most probable of the selection in the period, from any member, each where the topic's classifier rates it highest (2026-09-30) |
| Up to three excerpts per speech, its most probable fragments, ordered by the fragment's probability (2026-09-30) | Every fragment about the topic a candidate; a passage shown only when its own probability reaches the threshold; the three most probable per speech, ordered by that probability (2026-09-30 18:59, s4 r20770; 19:24, s4 r21744) |
| A speech's hover passage from its fragment most about a UNODC topic (2026-09-30 04:20) | Within its most probable excerpt (2026-09-30 19:24, s4 r21744) |
| Excerpts: the part of the fragment that the topic's classifier rates highest, shown only when that part reaches the threshold (2026-09-30 19:24, s4 r21744) | Whole fragments, however long; the three most probable per speech (user, 2026-09-30 20:09, s4 r23215) |
| A speech's hover passage within the part chosen for its most probable excerpt (2026-09-30 19:24, s4 r21744) | Of its most probable excerpt, where that topic's words weigh most (2026-09-30 20:09, s4 r23215) |
| 2024 texts from the corpus v14 (r92) | The official verbatim records A/79/PV.7–17 (2026-09-29 05:51, s2 r14183) |
| 2026 added when the dataset authors publish it (proposed r81) | Provisional 2026 now (2026-09-26 18:02, r476; 18:12, r575) |

## 9. Open points

None. On 2026-09-29 the user settled points 4, 7 and 10 (s2 r9207) and approved the mockup's handling of the others (2026-09-29 21:56, s4 r2316).

1. **Summary sentence under the strip:** none; the strip stands alone.
2. **Distinctive words on the Country tab:** left out, as in the confirmed plan (r679, r683); selecting a country on the Regions tab shows them.
3. **Label of the no-field-office group:** "Covered from Headquarters" ("Cubiertos desde la Sede"), as confirmed (r659, r683).
4. **Alternative development:** measured like every lens, with 44 labelled examples; the pass bar decides whether it carries the "Aprox." badge (section 3.7).
5. **Strip:** it keeps the "all UNODC topics" tile and opens on it, shows the ratio for the first selection, and a dot for every selection.
6. **Country tab:** it opens on Colombia, "all years" adds the years up, and similarity is shown as a percentile within the year, as `docs/data-contract.md` proposes.
7. **Group weighting:** each country weighs the same, over fragment shares (section 4, Metric); `docs/data-contract.md` says so.
8. **2026:** shown as "2026", like any other year, with no label or note (section 2).
9. **Word comparison with the selection's own past:** version 2 (section 7).
10. **Nauru's new name:** filed under NRO for all years and named Naoero, with "Nauru (2000–2025)" on hover (section 2).

## Design files

- Mockup: https://claude.ai/artifact/BswNTFYGfpVwGZAG7arsZQ (private). Local copies are `docs/design/mockup-v1.html` (the 2026-09-26 template) and `docs/design/mockup-v2.html` (this plan; local only and untracked since 2026-09-29, as 98% of its 9.7 MB is embedded data; the tracked version stays in the git history).
- Summary-strip options: https://claude.ai/artifact/99tqJ7xyp1DgSRiEsArM3t (local copy `docs/design/summary-options.html`).
- Icons: `docs/design/tabler-icons-subset.json`.
