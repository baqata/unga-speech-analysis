# UNODC lens codebook: labelling guide for speech fragments

Version 1.4 (September 2026). Version 1.1 added the boundary rules and examples of section 5 after review;
1.2 tightens `peace` (4.10), series and lists (3.2) and generic crime (5.2, section 6) after the pilot labelling;
1.3 settles, after the core labelling, accusations and designations of States as sponsors of terrorism, acts
and groups that the Security Council has called terrorist, and extremism without violence (4.6), and Security
Council action on criminal violence (4.10). 1.4 aligns every lens with UNODC's official definitions and scope
after a review of each rule against the conventions, protocols and United Nations resolutions that define the
mandates (section 1): the acts of the universal instruments against terrorism count by their kind, State
support for terrorists is `terrorism`, the illicit arms trade is `organized_crime` whoever receives the
weapons, crime in general and the conduct of police and detention are `criminal_justice`, and fisheries and
minerals crime follow UNODC's definitions (sections 4 to 8); each lens has three positive and two negative
examples.
Companion to `data/lenses/lenses.yaml`, which holds the
machine-readable definitions, include and exclude lists, era vocabulary and anchor
passages. Where this guide and the YAML differ, report the difference; do not resolve it
silently.

## 1. Task

Each item is a fragment of a statement delivered in the General Debate of the United Nations
General Assembly (1946-2026), usually one paragraph of about 150 words (range roughly 60 to 260).
For each fragment, decide which of ten thematic lenses it discusses. Nine lenses correspond to
mandate areas of the United Nations Office on Drugs and Crime (UNODC); the tenth, `peace`, is a
reference lens used as a benchmark.

The labels are used to measure how often and how substantively countries talk about UNODC topics.
Precision matters as much as recall: a lens that fires on metaphors or ceremonial language inflates
the measure, and a lens that misses older vocabulary distorts the historical trend.

The lenses follow UNODC's official definitions and scope: the conventions and protocols it serves, the
United Nations resolutions that define each mandate and UNODC's own texts. Where a rule names an act or a
subject by its kind (an act defined in a counter-terrorism treaty, illicit trafficking in firearms, crime in
general), it counts whatever words the speaker uses, subject to the threshold of 3.2.

Inputs per fragment: `frag_id`, the fragment text and, when provided, the year. Use the year only
to interpret vocabulary (section 7). Never use the speaker's country, or knowledge of what that
country usually says, to infer a topic that the text does not state.

## 2. The lenses

| id | Name (en / es) | Scope in one line |
|---|---|---|
| `drugs` | Drugs & drug trafficking / Drogas y narcotráfico | The world drug problem: illicit drugs, their cultivation, production, trafficking and use, supply control, drug control treaties and policy. Umbrella for the next two. |
| `prevention_treatment` | Prevention & treatment / Prevención y tratamiento | Drug demand reduction: prevention of drug use, treatment, rehabilitation, health responses, access to controlled medicines. |
| `alternative_development` | Alternative development / Desarrollo alternativo | Development alternatives for communities affected by illicit coca, poppy or cannabis cultivation or other illicit drug-related activities; crop substitution. |
| `organized_crime` | Organized crime / Delincuencia organizada | Criminal organizations and networks, Palermo Convention, illicit trafficking in firearms and small arms, piracy, cybercrime, kidnapping, extortion. |
| `corruption` | Corruption & economic crime / Corrupción y delitos económicos | Bribery, embezzlement, UNCAC, asset recovery, money laundering, illicit financial flows, fraud and other economic crime. |
| `terrorism` | Terrorism / Terrorismo | Terrorist acts and groups, the acts defined in the counter-terrorism treaties (hijacking, hostage-taking, attacks on diplomats and others), State support for terrorists, counter-terrorism law, financing of terrorism, violent extremism. |
| `trafficking_smuggling` | Human trafficking & smuggling / Trata y tráfico de migrantes | Trafficking in persons for exploitation, and smuggling of migrants. |
| `environmental_crime` | Environmental crime / Delitos ambientales | Wildlife, forest, fisheries, minerals and waste crime. |
| `criminal_justice` | Criminal justice / Justicia penal | Crime in general and its prevention, police, courts, prisons and detention, access to justice, violence against women as crime, citizen security. |
| `peace` | Peace and security / Paz y seguridad | Reference lens: war, conflict, peace processes, peacekeeping, collective security, disarmament. |

Full definitions, include and exclude bullets, and period vocabulary are in `lenses.yaml`. Read
them before labelling; the rules below refine them.

## 3. General rules

### 3.1 Multi-label

A fragment may carry zero, one or several lenses. Most fragments in the corpus carry none; an
empty label set is a normal and correct answer. Label every lens that meets the threshold in 3.2,
independently of the others, subject to the co-labelling rules in section 5.

### 3.2 When a lens applies: `substantive` or `list`

A lens applies to a fragment only in one of two ways.

**Substantive.** At least one complete sentence in the fragment is about the lens topic. A
sentence is about a topic when the topic is its subject or the object of its main claim, so that
removing the topic would remove the point of the sentence. One such sentence is enough; the rest
of the fragment may be about something else.

- Yes: "Drug trafficking has become the main source of violence in our cities." (`drugs`)
- Yes: "We have ratified the Convention against Corruption and created an anti-corruption agency." (`corruption`)
- Yes: a sentence devoted to two paired topics counts for both: "Terrorism and organized crime are increasingly intertwined." (`organized_crime`, `terrorism`)
- Yes: a sentence whose claim is the link between several items is substantive for each of them, however many there are: "Terrorism, drug trafficking and organized crime are increasingly intertwined"; "Drug money finances terrorism." (`drugs`, `organized_crime`, `terrorism`, all substantive in the first; `drugs` and `terrorism` in the second)
- Not paired topics: fixed formulas and names whose parts are not discussed separately, such as "drug abuse and illicit trafficking" or "supply reduction and demand reduction" (section 5.2).

**List.** The lens topic appears only as one item in an enumeration of distinct threats,
challenges, priorities or agenda items, and no sentence develops it further. Enumerations usually
have three or more items ("terrorism, drug trafficking, pandemics and climate change"), or two
items presented as examples of a broader category ("new threats such as terrorism and drug
trafficking"). An enumeration that only names the items as examples is `list`; one whose sentence
claims a link between them is `substantive` (above).

- Yes: "The new threats we face, from terrorism and drug trafficking to pandemics, know no borders." (`drugs` list, `terrorism` list)

A series can also be one of commitments, demands or means, written as verb phrases: "to fight against
poverty, violence, terror and crime"; "it must release the political prisoners, abstain from
sponsoring terrorism and respect the freedom of the press"; "they used every means, from alliances with
organized crime to support from terrorist networks". An item of a series is `list` unless the
fragment develops that item with a fact, actor, cause, effect, place or measure of its own. A subject
shared by the whole series, such as the State to which all the demands are addressed, develops no
single item. A meeting, conference or special session named in a list of meetings is `list` for its
topic.

A series can run across sentences. A sentence that makes a claim about its own item ("Nor have we
advanced on disarmament: the conference has not held a substantive session for years") develops it,
and the item is `substantive`.

If a lens is both listed and developed in a full sentence elsewhere in the fragment, record
`substantive`.

**Neither (do not label).**

- The topic appears only inside a modifier, a name or a date: "the Vienna meeting on drugs, which I attended, showed the value of multilateralism"; "the peace agreement includes a programme of crop substitution" gives `alternative_development` and `drugs`, not `peace`. Exception: nouns that name an actor or asset by its crime count as a mention of that crime, because the crime is what the noun refers to: "drug cartels", "drug traffickers", "drug-trafficking organizations", "drug lords", "drug money", "terrorist groups", "human traffickers", "people smugglers", "poachers". "Cartels" alone counts for `drugs` only when the fragment identifies them as drug cartels.
- The topic appears only in a subordinate clause that adds no claim about it: "... prisons full of small-scale offenders ..." inside a sentence about drug policy does not add `criminal_justice`.
- The topic appears only in a relative or participial clause that identifies an actor or adds a means, while the main clause makes a claim about something else: "the ivory is smuggled out by the same networks that traffic arms and drugs" (no `drugs`); "the terrorist groups that finance themselves with cocaine are weaker than ever" (no `drugs`); "..., buying the silence of officials" (no `corruption` from that clause alone). A topic counts when it is the subject, the main verb or the object of the main verb of a clause of its own. A relative clause that carries the point of the sentence, such as a consequence or a risk ("we oppose a hasty withdrawal of the mission, which would let the militias return to the villages"), is a clause of its own.
- Metaphor, invective or ceremony: "corruption of values", "a gang of criminals" said of a government, "peace-loving nations", "held hostage by the veto".
- Pronouns or allusions whose referent is not identifiable inside the fragment ("this scourge", "that plague"). Fragments are labelled on their own text only; do not look at neighbouring fragments. Mention the unresolved referent in `note`.

### 3.3 Topic, not stance

Label what the fragment talks about, not whether the speaker supports or opposes a policy. A
fragment that criticizes the war on drugs, denies corruption allegations or rejects a
counter-terrorism resolution still carries the lens. The exception is a State's designation on a national list
of State sponsors of terrorism and demands to remove it, which follow 4.6.

### 3.4 Umbrella rule for drugs

`prevention_treatment` and `alternative_development` are sub-lenses of `drugs` (field `parent` in
the YAML). Whenever you label either of them, also label `drugs`, with a mention type at least as
strong as the sub-lens (if the sub-lens is `substantive`, `drugs` is `substantive`). Supply-reduction
content other than alternative development (interdiction, seizures, eradication, precursor control) gives
`drugs` without any sub-lens. As a result, counts for `drugs` include every
prevention, treatment and alternative development fragment; the display label says so ("Problema
mundial de las drogas (incluye prevención, tratamiento y desarrollo alternativo)"). Downstream code
applies the rule with `expand_labels` (labels) and `expand_scores` (model scores) in
`pipeline/lenses.py`, so calibration and export treat it the same way.

### 3.5 Confidence

One value per fragment, reflecting the least certain decision you made, including decisions to
leave a lens out.

- 3: clear; any trained coder would agree, including cases that a rule of this guide settles unambiguously.
- 2: a rule of this guide applies but the reading of the text is debatable, or a plausible alternative labelling exists.
- 1: uncertain; the text is garbled, ambiguous or depends on a referent outside the fragment.

Use `note` (one short sentence) whenever confidence is below 3 or a boundary rule decided the case.

## 4. Per-lens decision rules and examples

Each lens lists its key decision rules, then three positive and two negative examples. Negative
examples are near misses: fragments a careless coder might label with that lens. Expected outputs
follow the format in section 9. Boundary cases between lenses have their own examples in section 5.3.

### 4.1 `drugs` (Drugs & drug trafficking)

- Label any substantive discussion of illicit drugs: production, cultivation (as a supply problem), trafficking, seizures, eradication, precursor control, drug control treaties and bodies, drug-related violence, and drug policy debates (decriminalization, regulation, war on drugs).
- Access to medicines, patents, generic or antiretroviral "drugs": not this lens. Medical access to controlled medicines is `prevention_treatment`; their diversion to illicit markets is `drugs`.
- "Cartels" in the 1960s-1980s usually means commodity or oil cartels: not this lens.
- Add `organized_crime` only when a sentence is about the criminal organizations themselves (section 5).
- `drugs` only, without `prevention_treatment`: "drug abuse" or addiction named as the problem, the doublet "drug abuse and illicit trafficking" and the names built on it, the "balanced approach" formula, and calls on consumer countries to reduce demand (section 5.2).
- UNODC, UNDCP and UNFDAC count for `drugs` only when the fragment refers to their drug work; UNODC's work on crime, corruption or terrorism gives the lens of that work (ST/SGB/2004/6).
- The traditional uses of the coca leaf and its status under the conventions are `drugs` only (1988 Convention, art. 14(2)); coca growers' livelihoods give `alternative_development` when development alternatives are discussed (4.3).

P1 (1980s)
> The illicit production of and traffic in narcotic drugs have reached alarming proportions. My Government has destroyed clandestine laboratories, seized record quantities of cocaine and extradited traffickers wanted abroad. But producer countries cannot bear this burden alone while the consuming nations do little to curb demand.

```json
{"frag_id": "ex-drugs-p1", "lenses": ["drugs"], "mention_type": {"drugs": "substantive"}, "confidence": 3, "note": "Asking consuming nations to curb demand is burden sharing, not a prevention or treatment response (5.2)."}
```

P2 (2000s)
> The threats to our security are now transnational: terrorism, drug trafficking, organized crime, pandemics and the degradation of the environment. No State can confront them alone, and this Organization must adapt to respond to them.

```json
{"frag_id": "ex-drugs-p2", "lenses": ["drugs", "organized_crime", "terrorism"], "mention_type": {"drugs": "list", "organized_crime": "list", "terrorism": "list"}, "confidence": 3, "note": "Enumeration of threats; environmental degradation is not framed as crime."}
```

P3 (2010s)
> For decades we were told that the war on drugs could be won. The results are before us: prisons full of small-scale offenders, violence in our cities and markets that adapt to every blow. The time has come to discuss regulation and public health approaches openly, without abandoning the fight against the criminal organizations that profit from prohibition.

```json
{"frag_id": "ex-drugs-p3", "lenses": ["drugs", "prevention_treatment"], "mention_type": {"drugs": "substantive", "prevention_treatment": "substantive"}, "confidence": 2, "note": "Public health approaches are the object of the main verb, so the health response counts; prisons and criminal organizations stay in subordinate positions."}
```

N1 (2000s)
> Access to affordable medicines remains beyond the reach of millions. The rules on intellectual property must not prevent developing countries from producing generic drugs to fight HIV/AIDS, tuberculosis and malaria.

```json
{"frag_id": "ex-drugs-n1", "lenses": [], "mention_type": {}, "confidence": 3, "note": "Pharmaceutical drugs, not controlled substances."}
```

N2 (1970s)
> The developing countries, which depend on the export of a few primary commodities, are at the mercy of prices dictated by powerful cartels and monopolies in the industrialized world.

```json
{"frag_id": "ex-drugs-n2", "lenses": [], "mention_type": {}, "confidence": 3, "note": "Commodity cartels in the economic sense."}
```

### 4.2 `prevention_treatment` (Prevention & treatment)

- The test: at least one sentence is about a response to drug use, namely prevention (education, awareness, family, school or community programmes), treatment, rehabilitation, aftercare, social reintegration, harm reduction, HIV and overdose prevention among people who use drugs, a public health approach to drug use, or access to controlled medicines. A call to adopt such a response counts ("we must treat addiction as a health problem").
- Demand reduction counts only as a named policy or programme with content, meaning the sentence says what is done, for whom or how (the 1998 Declaration on the Guiding Principles of Drug Demand Reduction; "a national demand reduction plan with prevention in every school").
- `drugs` only, not this lens: "drug abuse", addiction or consumption named only as the problem or scourge; the doublet "drug abuse and illicit trafficking" and the names built on it (the 1987 International Conference, UNFDAC, the International Day against Drug Abuse and Illicit Trafficking); the "balanced approach" formula giving equal weight to "supply reduction and demand reduction"; and calls by producer or transit countries on consumer countries to reduce demand (burden sharing). Examples ex-boundary-01 to 03 in section 5.3.
- General health, mental health or youth policy without drug use: not this lens. Alcohol or tobacco only when grouped with drugs as substance abuse (confidence 2).
- Always add `drugs` (umbrella rule).

P1 (1980s)
> Drug abuse among our young people has become a matter of national concern. We have introduced drug education into the school curriculum and opened rehabilitation centres where addicts receive medical care and vocational training so that they may be reintegrated into society.

```json
{"frag_id": "ex-prevention_treatment-p1", "lenses": ["drugs", "prevention_treatment"], "mention_type": {"drugs": "substantive", "prevention_treatment": "substantive"}, "confidence": 3, "note": ""}
```

P2 (2000s)
> In our region the epidemic is driven by the sharing of needles among people who inject drugs. We have expanded opioid substitution therapy and needle exchange programmes, and we call on donors to support services that reduce the harms associated with drug use.

```json
{"frag_id": "ex-prevention_treatment-p2", "lenses": ["drugs", "prevention_treatment"], "mention_type": {"drugs": "substantive", "prevention_treatment": "substantive"}, "confidence": 3, "note": "HIV and harm reduction among people who inject drugs."}
```

P3 (2010s)
> My Government's social agenda covers universal health coverage, quality education, the prevention of drug addiction among adolescents and the protection of older persons.

```json
{"frag_id": "ex-prevention_treatment-p3", "lenses": ["drugs", "prevention_treatment"], "mention_type": {"drugs": "list", "prevention_treatment": "list"}, "confidence": 3, "note": "One item in a list of priorities; umbrella gives drugs the same type."}
```

N1 (2020s)
> Mental health must be given the same priority as physical health. Depression and anxiety affect hundreds of millions of people, and our health systems must integrate psychological care at the primary level.

```json
{"frag_id": "ex-prevention_treatment-n1", "lenses": [], "mention_type": {}, "confidence": 3, "note": "No drug use mentioned."}
```

N2 (2010s)
> Our navy intercepted more than forty tonnes of cocaine last year, and we have installed scanners in every major port to detect drug shipments.

```json
{"frag_id": "ex-prevention_treatment-n2", "lenses": ["drugs"], "mention_type": {"drugs": "substantive"}, "confidence": 3, "note": "Supply side only."}
```

### 4.3 `alternative_development` (Alternative development)

- Label crop substitution, alternative livelihoods and rural development aimed at illicit coca, poppy or cannabis growers, market access for their products, and the eradication-versus-development debate when development alternatives are discussed. Since the 2016 special session (A/RES/S-30/1, paras. 7(d), 7(j) and 7(k)), development alternatives for other communities affected by illicit drug-related activities, rural or urban, count too.
- The traditional uses of the coca leaf and its treaty status are `drugs` only (4.1).
- Eradication or spraying alone: `drugs` only.
- "Alternative development model/strategy/path" in the 1970s-1980s economic sense (self-reliance, new international economic order): not this lens and not `drugs`.
- Always add `drugs` (umbrella rule).

P1 (1980s)
> Under the programme financed by the United Nations Fund for Drug Abuse Control, farmers in the northern highlands have replaced the poppy with coffee, tea and fruit trees, and new roads now bring their products to market.

```json
{"frag_id": "ex-alternative_development-p1", "lenses": ["drugs", "alternative_development"], "mention_type": {"drugs": "substantive", "alternative_development": "substantive"}, "confidence": 3, "note": ""}
```

P2 (1990s)
> Crop substitution cannot succeed unless the legal products of our farmers find markets abroad. We therefore ask our partners to maintain the trade preferences granted to countries fighting the drug trade and to open their markets to our flowers, fruit and textiles.

```json
{"frag_id": "ex-alternative_development-p2", "lenses": ["drugs", "alternative_development"], "mention_type": {"drugs": "substantive", "alternative_development": "substantive"}, "confidence": 3, "note": "Market access for substitution products."}
```

P3 (2010s)
> The peace agreement includes a national programme for the voluntary substitution of illicit crops. Tens of thousands of families have signed agreements to uproot their coca in exchange for support for productive projects, and the State must honour its commitments to them.

```json
{"frag_id": "ex-alternative_development-p3", "lenses": ["drugs", "alternative_development"], "mention_type": {"drugs": "substantive", "alternative_development": "substantive"}, "confidence": 2, "note": "The peace agreement is only the frame of the sentence; peace not labelled."}
```

N1 (1970s)
> The developing countries must seek an alternative development model, one based on collective self-reliance and a new international economic order rather than on dependence on the markets of the North.

```json
{"frag_id": "ex-alternative_development-n1", "lenses": [], "mention_type": {}, "confidence": 3, "note": "Economic-ideology sense of 'alternative development'."}
```

N2 (2000s)
> Aerial spraying of the plantations continued this year, and more than one hundred thousand hectares of coca were eradicated, a record in our history.

```json
{"frag_id": "ex-alternative_development-n2", "lenses": ["drugs"], "mention_type": {"drugs": "substantive"}, "confidence": 3, "note": "Eradication without any development alternative."}
```

### 4.4 `organized_crime` (Organized crime)

- Label criminal organizations, networks, mafias, gangs and cartels discussed as such (their power, violence, territorial control, finances, diversification), the Palermo Convention and cooperation against organized crime (extradition, mutual legal assistance, joint investigations), the illicit trade in firearms (below), modern maritime piracy, cybercrime and online scams, kidnapping, extortion, counterfeiting, trafficking in cultural property.
- The illicit manufacturing of and trafficking in firearms, small arms and light weapons, their parts or ammunition (illicit trade, transfers, flows or smuggling, or their illicit proliferation) is this lens whoever receives them, criminals or armed groups: the Firearms Protocol defines illicit trafficking by the unauthorized or unmarked transfer, not by the recipient (A/RES/55/255, annex, art. 3(e)). Add `peace` when a sentence treats the armed conflict or disarmament. Arms control, disarmament, the arms race and arms transfers between States, with no illicit trade: `peace` only.
- "Air piracy" is hijacking: `terrorism` (4.6).
- Invective against governments ("criminal regime", "gangsters", "international banditry"): not this lens.
- Naming the Palermo Protocols only as part of the Convention ("the Convention and its Protocols") does not add `trafficking_smuggling`; a sentence about the Trafficking in Persons Protocol or the Migrant Smuggling Protocol itself does (4.7), and one about the Firearms Protocol is this lens.
- Kidnapping for ransom, extortion, fraud and scams by criminal groups are this lens; the same acts by public officials are `corruption`, and so are fraud, tax crimes and corporate crimes by individuals or companies (economic crime, 4.5). Criminal groups using "terrorist methods" stay here unless the acts are called terrorism. Homicide or kidnapping rates as crime statistics are `criminal_justice` (section 5.2).
- Online child sexual abuse or exploitation material and the online grooming of children are cybercrime offences (Convention against Cybercrime, A/RES/79/243, annex, arts. 14 and 15): this lens; add `trafficking_smuggling` only if the trafficking of children is discussed.

P1 (2000s)
> We have ratified the Convention against Transnational Organized Crime and its three protocols. Criminal organizations exploit the differences between our legal systems; only through extradition, mutual legal assistance and joint investigations can we deny them safe haven.

```json
{"frag_id": "ex-organized_crime-p1", "lenses": ["organized_crime"], "mention_type": {"organized_crime": "substantive"}, "confidence": 3, "note": "Protocols named only as part of the Convention."}
```

P2 (2010s)
> The gangs that terrorize our neighbourhoods extort small traders, recruit children and settle their disputes with murder. We are confronting them with intelligence-led policing and by seizing their assets, while offering young people alternatives through education and employment.

```json
{"frag_id": "ex-organized_crime-p2", "lenses": ["organized_crime"], "mention_type": {"organized_crime": "substantive"}, "confidence": 2, "note": "Policing and prevention are described only as means against gangs, so criminal_justice is not added; 'terrorize' is not terrorism."}
```

P3 (2020s)
> Ransomware attacks have paralysed our hospitals and municipal services. These are not isolated hackers but organized criminal enterprises, often operating from jurisdictions that refuse to cooperate. The new convention against cybercrime must be ratified quickly and implemented with safeguards for human rights.

```json
{"frag_id": "ex-organized_crime-p3", "lenses": ["organized_crime"], "mention_type": {"organized_crime": "substantive"}, "confidence": 3, "note": ""}
```

N1 (1970s)
> Air piracy has become an intolerable threat to international civil aviation, and the Assembly must act to ensure that those who seize aircraft are punished wherever they may be.

```json
{"frag_id": "ex-organized_crime-n1", "lenses": ["terrorism"], "mention_type": {"terrorism": "substantive"}, "confidence": 3, "note": "'Air piracy' means aircraft hijacking."}
```

N2 (1980s)
> The racist regime is a criminal gang whose repeated aggression against neighbouring States violates every principle of the Charter and threatens the peace of the whole region.

```json
{"frag_id": "ex-organized_crime-n2", "lenses": ["peace"], "mention_type": {"peace": "substantive"}, "confidence": 3, "note": "'Criminal gang' is invective; the substance is inter-State aggression."}
```

### 4.5 `corruption` (Corruption & economic crime)

- Label bribery, embezzlement, kleptocracy, illicit enrichment, anti-corruption laws and bodies, UNCAC, asset recovery and return of stolen assets, money laundering and anti-money-laundering systems, illicit financial flows, the 1970s "illicit payments" by transnational corporations, and economic and financial crime by individuals or companies: fraud (financial, corporate, identity or document fraud), tax evasion and other tax crimes, and corporate crimes (Doha Declaration, A/RES/70/174, annex, para. 8(f)). Fraud by criminal groups stays `organized_crime`.
- "Corruption of values", moral decay: not this lens. "Good governance", "transparency" or "accountability" without mention of corruption or economic crime: not this lens.
- Illicit financial flows follow the definition of SDG indicator 16.4.1, of which UNODC is co-custodian: flows from crime and corruption, from tax evasion or illegal commercial practices, and cross-border aggressive tax avoidance by multinational enterprises (profit shifting, transfer mispricing, treaty shopping). Tax rates, tax cooperation, debt and capital flight discussed as fiscal or economic policy, with no illicit or avoidance framing: not this lens.
- Money laundering counts when laundering, its channels or the measures against it are the subject or main claim of a sentence or independent clause. Laundering named as one more activity of criminals in a sentence about their crimes ("... and laundering the proceeds") gives the crime lens only.
- Criminals bribing, infiltrating or capturing police, officials or institutions count when that is the main claim of a clause ("the cartels have infiltrated the police"); not when it appears only in a participial or subordinate clause (section 5.2).

P1 (1970s)
> The revelations of bribes paid by transnational corporations to high officials in order to obtain contracts confirm the need for a code of conduct and for an international agreement to prohibit illicit payments.

```json
{"frag_id": "ex-corruption-p1", "lenses": ["corruption"], "mention_type": {"corruption": "substantive"}, "confidence": 3, "note": ""}
```

P2 (2000s)
> Billions of dollars stolen by former rulers lie in banks abroad. We ask the financial centres concerned to cooperate under the Convention against Corruption so that these assets can be returned to the people from whom they were taken.

```json
{"frag_id": "ex-corruption-p2", "lenses": ["corruption"], "mention_type": {"corruption": "substantive"}, "confidence": 3, "note": "Asset recovery."}
```

P3 (2010s)
> Our Government has made three commitments to the nation: to restore security, to reduce poverty and to eradicate corruption at every level of the State.

```json
{"frag_id": "ex-corruption-p3", "lenses": ["corruption"], "mention_type": {"corruption": "list"}, "confidence": 3, "note": "'Restore security' is too vague for criminal_justice."}
```

N1 (1990s)
> Consumerism and the cult of money are corrupting the values of our youth and the moral foundations of the family.

```json
{"frag_id": "ex-corruption-n1", "lenses": [], "mention_type": {}, "confidence": 3, "note": "Moral sense of 'corrupting'."}
```

N2 (2010s)
> Good governance, transparency and accountability are essential for the success of the 2030 Agenda, and the United Nations itself must set the example through the reform of its working methods.

```json
{"frag_id": "ex-corruption-n2", "lenses": [], "mention_type": {}, "confidence": 3, "note": "Governance rhetoric without corruption or economic crime."}
```

### 4.6 `terrorism` (Terrorism)

- Label terrorist acts and groups, the acts defined in the universal instruments against terrorism (next rule), State support for terrorists (below), counter-terrorism law and cooperation, financing of terrorism, foreign terrorist fighters, violent extremism and radicalization to violence, and victims of terrorism.
- The acts defined in the universal instruments against terrorism count by their kind, whether or not the fragment calls them terrorism (UNODC, E4J Counter-Terrorism Module 4, "Treaty-based crimes of terrorism"): the hijacking of civil aircraft ("air piracy") and its sabotage or other violence on board; violence at international airports; the use of civil aircraft as weapons; the seizure of ships, violence endangering the safety of maritime navigation and attacks on fixed platforms on the continental shelf; hostage-taking outside a war between States (5.2); murder, kidnapping or other violent attacks on internationally protected persons (diplomats and other officials entitled to special protection under international law, and Heads of State or Government or foreign ministers while abroad) or on their official premises, private residence or means of transport; and the unlawful taking, possession or use of nuclear material. Acts of a State's armed or security forces (downing or forcing down a civil aircraft, seizing or boarding a ship), acts in a war between States and disputes between States over diplomatic law stay out (`peace` if the conflict is discussed). Bombings and other attacks on people follow the next rule: they count when the fragment or the Security Council calls them terrorist.
- One rule for "terrorist" labels in every era. Label `terrorism` when (a) the fragment describes terrorist acts or groups as such, whoever is accused, including a neighbour sending "terrorists" across a border ("we arrested 47 terrorists who had infiltrated our territory"); or (b) it discusses what counts as terrorism: its definition or causes, its distinction from national liberation struggles, "State terrorism" as a form of terrorism, or an explicit rebuttal of the label ("they are not terrorists, as the occupier claims, but patriots").
- Do not label `terrorism` when "terror", "terrorist" or "terrorism" is only an epithet for a State's army, government, occupation or war ("acts of terrorism" by colonial or occupation forces against a population, "State terrorism" for military operations, "terrorist regime"), and neither a terrorist act nor the concept is discussed. Label `peace` if the conflict is discussed.
- War, invasion, occupation or insurgency not described as terrorism: `peace`.
- Acts and groups that the Security Council has itself called terrorist count as described as such under (a), even when the fragment does not use the word, if the fragment discusses the act, the group or the handling of the act (an investigation, a trial, sanctions against the group). The list is closed:
  - groups: Al-Qaida, ISIL (Da'esh) and the other groups on the Security Council's ISIL (Da'esh) and Al-Qaida sanctions list, such as Boko Haram and the Al-Nusrah Front; Al-Shabaab;
  - acts, with the resolution that names them: the bombings of Pan Am flight 103 over Lockerbie and of UTA flight 772 (731); the bombing of the AMIA building in Buenos Aires in 1994; the attempt on the life of the President of Egypt in Addis Ababa in 1995 (1044); the bombings of the embassies in Nairobi and Dar es Salaam on 7 August 1998 (1189); the attacks of 11 September 2001 (1368); the bombings in Bali on 12 October 2002 (1438); the taking of hostages in Moscow on 23 October 2002 (1440); the attacks at Kikambala, Kenya, and on an Arkia airliner on 28 November 2002 (1450); the bombing in Bogotá on 7 February 2003 (1465); the bombings in Istanbul in November 2003 (1516); the bombings in Madrid on 11 March 2004 (1530); the bombing that killed Rafiq Hariri in Beirut on 14 February 2005, its investigation and the Special Tribunal for Lebanon (1595); the attacks in London on 7 July 2005 (1611); and the attacks of 2015 in Sousse, Ankara, Beirut and Paris and on the airliner over Sinai (2249).

  A name or date used only to mark time ("since 11 September", "the world after 9/11") does not count. Any other bombing, attack or group counts only when the fragment itself calls it terrorist, however it is described elsewhere (the acts of the universal instruments count by their kind, as above); do not rely on your own view of whether an attack was terrorism.
- An accusation that a State organizes, instigates, finances, arms, trains, harbours or tolerates terrorists or terrorist activities, and a State's explicit denial of such an accusation, give `terrorism`: support for terrorists is part of counter-terrorism (Security Council resolution 1373 (2001), para. 2(a); Global Counter-Terrorism Strategy, A/RES/60/288, annex, section II, para. 1). A State's designation on a national list of State sponsors of terrorism, and demands to remove it from such a list or to lift the measures attached, are about sanctions and relations between States: they give `terrorism` only when the fragment also discusses terrorism itself (terrorist acts, groups, victims or perpetrators, a State's support for terrorists, cooperation against terrorism, or its definition). An accusation described as a pretext for an armed attack also gives `peace` for the attack (4.10).
- "Extremism" or "extremists" without "violent" counts as violent extremism only when the fragment ties it to violence against people: extremist attacks or killings, extremists as perpetrators of violence, or extremism named as one threat together with such violence. As an ideology, a political position, a social ill or an insult, with no violence, it gives no `terrorism`.
- "Radicalization" counts only as radicalization to violence or into terrorist or violent extremist groups (A/70/674; Security Council resolution 2178 (2014)); political or social radicalization with no violence gives no `terrorism`.
- Security Council resolution 1540 (2004), and the risk that terrorists or other non-State actors acquire, traffic in or use nuclear, chemical or biological weapons or material, are this lens; non-proliferation between States is `peace`.
- "Balance of terror", "nuclear terror" in the deterrence sense, "economic terrorism", "media terrorism": not this lens.
- The formula "terrorism is a threat to international peace and security" does not add `peace`.

P1 (1970s)
> The hijacking of aircraft, the taking of hostages and the kidnapping and murder of diplomats endanger innocent lives and the conduct of relations between States. We support the drafting of an international convention against the taking of hostages, and we urge all States to extradite or prosecute those who commit such acts.

```json
{"frag_id": "ex-terrorism-p1", "lenses": ["terrorism"], "mention_type": {"terrorism": "substantive"}, "confidence": 3, "note": "Hijacking, hostage-taking and attacks on diplomats are acts of the universal instruments against terrorism and count by their kind (4.6)."}
```

P2 (2010s)
> The terrorist group that seized parts of our territory recruited young people through social media with promises of money and glory. Military victory alone will not end this threat; we must counter violent extremism in schools, places of worship and prisons, and reintegrate those who renounce violence.

```json
{"frag_id": "ex-terrorism-p2", "lenses": ["terrorism"], "mention_type": {"terrorism": "substantive"}, "confidence": 3, "note": "Prisons appear only as a setting; criminal_justice not added."}
```

P3 (1980s)
> We condemn all acts of terrorism, whoever the perpetrators. But we cannot accept that the heroic struggle of peoples for national liberation be labelled terrorism, nor that the terrorism practised by States against defenceless peoples be ignored.

```json
{"frag_id": "ex-terrorism-p3", "lenses": ["terrorism"], "mention_type": {"terrorism": "substantive"}, "confidence": 3, "note": "Debate on the definition of terrorism."}
```

N1 (2020s)
> The bombardment of cities and the displacement of hundreds of thousands of civilians during the invasion must be condemned. The aggressor must withdraw its troops and respect the sovereignty of its neighbour.

```json
{"frag_id": "ex-terrorism-n1", "lenses": ["peace"], "mention_type": {"peace": "substantive"}, "confidence": 3, "note": "Armed aggression not described as terrorism."}
```

N2 (2000s)
> Extremism and intolerance are eroding the values that hold our societies together. We must promote dialogue among cultures and religions and teach our young people respect for others.

```json
{"frag_id": "ex-terrorism-n2", "lenses": [], "mention_type": {}, "confidence": 3, "note": "Extremism as a social ill, with no violence against people (4.6)."}
```

### 4.7 `trafficking_smuggling` (Human trafficking & smuggling)

- Label trafficking in persons (older wording: "traffic in women and children", "white slave traffic"): the recruitment, transport, transfer, harbouring or receipt of persons by threat or use of force or other coercion, abduction, fraud, deception, abuse of power or of a position of vulnerability, or payments to a person having control over the victim, for exploitation; for children no such means is needed (Trafficking in Persons Protocol, art. 3). Also modern slavery framed as present-day exploitation, and the smuggling of migrants, by networks or individuals.
- Sale of children, child prostitution, child sexual abuse material, the exploitation of the prostitution of others and the organ trade count only when framed as trafficking: persons recruited, moved, sold, bought or held for exploitation. "Organ trafficking" counts only when persons are trafficked for the removal of their organs; the trade in organs alone does not (A/RES/71/322 distinguishes the two). Online child sexual abuse material and grooming are `organized_crime` (4.4).
- The abduction, sale or holding of women and girls for sexual slavery, sexual exploitation or forced marriage, including by armed groups in war, is trafficking in persons: this lens, with `peace` for the conflict (S/2024/292, para. 3; Security Council resolution 2331 (2016)).
- A sentence about the Trafficking in Persons Protocol or the Migrant Smuggling Protocol counts; the Protocols named only as part of the Convention do not (4.4).
- Spanish-origin translations distinguish "trata" (trafficking in persons) from "tráfico de migrantes" (migrant smuggling); both belong here.
- Migration, refugee or asylum policy without traffickers or smugglers: not this lens. The historical slave trade and reparations: not this lens.
- Add `organized_crime` only when the fragment frames the trafficking in broader organized crime terms (section 5).

P1 (2000s)
> Every year thousands of young women from our country are lured abroad by false promises of work and forced into prostitution. We have adopted a law against trafficking in persons, set up shelters for victims and signed agreements with countries of destination to prosecute the traffickers.

```json
{"frag_id": "ex-trafficking_smuggling-p1", "lenses": ["trafficking_smuggling"], "mention_type": {"trafficking_smuggling": "substantive"}, "confidence": 3, "note": ""}
```

P2 (2010s)
> Smugglers charge thousands of dollars for a place in an overcrowded boat, and many of those they take on board never reach the other shore. Dismantling these criminal networks must go hand in hand with opening safe and legal pathways for migration.

```json
{"frag_id": "ex-trafficking_smuggling-p2", "lenses": ["trafficking_smuggling"], "mention_type": {"trafficking_smuggling": "substantive"}, "confidence": 3, "note": "Networks are smuggling networks, not framed as broader organized crime."}
```

P3 (1950s)
> We attach great importance to the convention for the suppression of the traffic in persons and of the exploitation of the prostitution of others, and we hope that all Members will soon accede to it.

```json
{"frag_id": "ex-trafficking_smuggling-p3", "lenses": ["trafficking_smuggling"], "mention_type": {"trafficking_smuggling": "substantive"}, "confidence": 3, "note": "Older wording for trafficking in persons."}
```

N1 (2010s)
> Migration is a positive force for development. The global compact must protect the rights of migrant workers, facilitate remittances and ensure the portability of social security benefits.

```json
{"frag_id": "ex-trafficking_smuggling-n1", "lenses": [], "mention_type": {}, "confidence": 3, "note": "Migration policy without trafficking or smuggling."}
```

N2 (2010s)
> The transatlantic slave trade tore millions of Africans from their homeland. Reparatory justice for this crime against humanity is a debt the former colonial Powers have yet to pay.

```json
{"frag_id": "ex-trafficking_smuggling-n2", "lenses": [], "mention_type": {}, "confidence": 3, "note": "Historical slave trade and reparations."}
```

### 4.8 `environmental_crime` (Environmental crime)

- Label poaching and wildlife trafficking, illegal logging and timber trafficking, crimes in the fisheries sector, illegal mining and minerals crime, and illegal traffic in or dumping of toxic and hazardous wastes (a frequent 1988-1992 topic).
- Fisheries: illegal fishing presented as crime (criminal groups, prosecution, criminal penalties) and the crimes along the fisheries value chain (falsified catch or licence documents, corruption, money laundering, tax or customs fraud, trafficking in persons or forced labour on fishing vessels) count; add the lens of that crime when a sentence is about it. Illegal, unreported and unregulated (IUU) fishing named only as a threat to fish stocks, livelihoods or sovereignty gives no lens: UNODC distinguishes these crimes from IUU fishing, a fisheries-management matter led by FAO and in many jurisdictions not a crime (UNODC Approach to Crimes in the Fisheries Sector; UNODC, Combating Crimes in the Fisheries Sector: A Guide to Good Legislative Practices, 2023).
- The decisive test is an illegal or criminal framing. Climate change, emissions, deforestation, pollution or conservation without it: not this lens.
- One exception to the test, the waste trade: the export or dumping of toxic, hazardous, industrial or nuclear wastes into developing countries by companies, traders or unnamed actors ("our continent is not the dustbin of the industrialized world") counts even without the word "illegal", because the General Assembly itself framed it as "illegal traffic in toxic and dangerous products and wastes". Dumping, disposal or storage by States or State programmes (proposals by Powers to dump nuclear waste in the Pacific), nuclear testing, and waste dumping named only as one environmental problem among others do not count (section 5.2).
- Ecocide or environmental harm proposed as an international crime under the Rome Statute is international criminal justice: no lens, as for the International Criminal Court in 4.9. Domestic criminalization of environmental harm is this lens.
- Conflict diamonds and minerals, and gold, gems or other minerals mined or traded illicitly by armed groups, are minerals crime (A/RES/55/56; A/RES/76/185, para. 1): this lens, with `peace` when a sentence is about the war they finance. Environmental damage by armed forces: `peace`.

P1 (1980s)
> Our continent must not become the dumping ground for the industrial waste of the rich countries. We condemn the companies that ship toxic waste to our shores in violation of our laws, and we call for a binding convention to ban this criminal traffic.

```json
{"frag_id": "ex-environmental_crime-p1", "lenses": ["environmental_crime"], "mention_type": {"environmental_crime": "substantive"}, "confidence": 3, "note": "Waste crime."}
```

P2 (2010s)
> Elephant poaching has reached its highest level in decades, and the ivory is smuggled out by the same networks that traffic arms and drugs. We have deployed rangers, destroyed our stockpiles and imposed heavy prison sentences on the traffickers.

```json
{"frag_id": "ex-environmental_crime-p2", "lenses": ["organized_crime", "environmental_crime"], "mention_type": {"organized_crime": "substantive", "environmental_crime": "substantive"}, "confidence": 2, "note": "Convergence of networks across crimes frames it as organized crime; drugs appear only in a clause."}
```

P3 (2000s)
> Diamonds mined illegally in the areas held by the rebels are smuggled across our borders and sold abroad, and their proceeds finance the war. The Kimberley Process must be strengthened so that no conflict diamond reaches the market.

```json
{"frag_id": "ex-environmental_crime-p3", "lenses": ["environmental_crime", "peace"], "mention_type": {"environmental_crime": "substantive", "peace": "substantive"}, "confidence": 3, "note": "The illicit trade in conflict diamonds is minerals crime; the war it finances gives peace (4.8)."}
```

N1 (2020s)
> Deforestation and emissions from fossil fuels are pushing the planet towards catastrophe. We call on the developed countries to honour their pledges on climate finance and to reduce their emissions without delay.

```json
{"frag_id": "ex-environmental_crime-n1", "lenses": [], "mention_type": {}, "confidence": 3, "note": "Climate policy without a criminal framing."}
```

N2 (2010s)
> Small island States face threats that are existential: rising seas, illegal, unreported and unregulated fishing, and the pollution of our ocean by plastics.

```json
{"frag_id": "ex-environmental_crime-n2", "lenses": [], "mention_type": {}, "confidence": 3, "note": "IUU fishing named only as a threat to stocks and livelihoods is fisheries management, not fisheries crime (4.8)."}
```

### 4.9 `criminal_justice` (Criminal justice)

- Label crime in general and its prevention and control, the core of the United Nations crime prevention and criminal justice programme (A/RES/46/152, annex, para. 16): a sentence about crime, criminality or delinquency with no type named ("crime is rising in our cities", "the fight against crime"; 5.2). Also citizen security, homicide, kidnapping and other crime rates, violence reduction, police, prosecution, courts and prisons as institutions, prison conditions and reform, pre-trial detention, alternatives to imprisonment, juvenile justice, access to justice and legal aid, victims and witnesses, the Crime Congresses and UN standards and norms.
- International cooperation in criminal matters in general (extradition, mutual legal assistance, transfer of sentenced persons or of proceedings, police cooperation) is this lens (Kyoto Declaration, A/RES/76/181, annex, para. 62); cooperation against one named crime gives that crime's lens (5.1).
- Police and detention count whoever the victims (Code of Conduct for Law Enforcement Officials, A/RES/34/169; Nelson Mandela Rules, A/RES/70/175): the use of force by police, or by security forces exercising police powers, against demonstrators or in arrests; arbitrary arrest; torture or ill-treatment in custody and deaths in detention; and conditions of detention, including those of political prisoners.
- Violence against women and girls, femicide and gender-based violence count only when the fragment names a criminal-justice element: femicide or other criminal offences, police, prosecution, courts, protection orders, impunity, crime prevention programmes, victim support services (shelters, hotlines, legal, medical or psychological assistance), or prevention measures such as awareness or education campaigns against this violence (A/RES/65/228). Violence against women named only as a gender-equality or human-rights goal ("eliminate all forms of violence against women") gets no lens. Conflict-related sexual violence is `peace`; add this lens only if its prosecution by national authorities is discussed, and `trafficking_smuggling` when persons are abducted, sold or held for sexual slavery or forced marriage (4.7).
- Enforcement against a crime covered by another lens (arresting traffickers, prosecuting terrorists) does not add this lens unless a sentence addresses the justice system or crime prevention in general.
- Not this lens: "rule of law" and "justice" rhetoric; the International Criminal Court and atrocity-crime tribunals; "crime" or "crimes" said of aggression, apartheid, colonialism, genocide or war, or of a government or an army; prisoners of war; demands to release political prisoners; and repression by armed forces in war or occupation (`peace` if the conflict is discussed).

P1 (1980s)
> The Seventh United Nations Congress on the Prevention of Crime and the Treatment of Offenders adopted important guidelines. Crime is increasingly linked to rapid urbanization and unemployment, and crime prevention must form part of development planning.

```json
{"frag_id": "ex-criminal_justice-p1", "lenses": ["criminal_justice"], "mention_type": {"criminal_justice": "substantive"}, "confidence": 3, "note": ""}
```

P2 (2010s)
> Our prisons hold three times the number of inmates they were built for, and half of them have never been tried. We are introducing electronic monitoring, expanding public defender services and applying the Mandela Rules to restore dignity to our penitentiary system.

```json
{"frag_id": "ex-criminal_justice-p2", "lenses": ["criminal_justice"], "mention_type": {"criminal_justice": "substantive"}, "confidence": 3, "note": "Prison reform and pre-trial detention."}
```

P3 (2020s)
> Every day women are murdered in our region simply because they are women. We have typified femicide in our penal code, created specialized prosecution units and trained police and judges, but impunity remains the rule rather than the exception.

```json
{"frag_id": "ex-criminal_justice-p3", "lenses": ["criminal_justice"], "mention_type": {"criminal_justice": "substantive"}, "confidence": 3, "note": "Gender-based violence treated as crime."}
```

N1 (1990s)
> An international order based on the rule of law, justice and respect for the Charter is the best guarantee for small States.

```json
{"frag_id": "ex-criminal_justice-n1", "lenses": [], "mention_type": {}, "confidence": 3, "note": "Rule-of-law rhetoric at the international level."}
```

N2 (2000s)
> The International Criminal Court must be supported in its task of ending impunity for genocide, war crimes and crimes against humanity. There can be no lasting peace without justice for the victims.

```json
{"frag_id": "ex-criminal_justice-n2", "lenses": [], "mention_type": {}, "confidence": 2, "note": "International criminal justice is outside this lens; the peace clause is a formula, not a discussion of a conflict."}
```

### 4.10 `peace` (Peace and security, reference lens)

- Label `peace` for a sentence about a concrete matter of peace and security:
  - a specific war, armed conflict, occupation, aggression or dispute between States or armed parties, named or identifiable in the fragment; the parties, the place or the act are enough ("arms keep reaching the invading forces", "the shelling of our border towns", "our dispute with our neighbour over the river");
  - relations between rival Powers or blocs discussed as tension, détente or the danger of war (the cold war, the arms race);
  - ceasefires, conflict prevention and mediation, peace processes and agreements (including the demobilization and reintegration of combatants), peacekeeping and peacebuilding;
  - disarmament and arms control, however framed: a sentence on what disarmament would do for development is `peace` (this refines the YAML's "framed in terms of peace and security"); the illicit trade in small arms also gives `organized_crime` (4.4);
  - the Security Council's action on a situation, its reform, its working methods or the veto, and the sanctions or embargoes it decides. Council action is `peace` even when the situation is gang or criminal violence without armed conflict, and so is a force or mission that the Council authorizes for it (the Multinational Security Support mission and the Gang Suppression Force in Haiti); the gangs also give `organized_crime` when the fragment develops them.
- General invocations carry no label: peace as an aspiration or a value ("lasting peace", "the cause of peace", "a world of peace"), conflict or war among the world's ills with no referent ("conflict remains the enemy of development"), and "the maintenance of international peace and security" as the purpose of the Organization or a general duty of its Members. In an enumeration they are `list` (3.2).
- Apartheid, racism and colonialism are not `peace` by themselves. Add `peace` when a sentence is about armed struggle, military attacks or aggression, military occupation, or Security Council measures connected with them. Calls on States to isolate or boycott a regime are not Security Council measures.
- The release of hostages or detainees demanded only as a term of a ceasefire, exchange or end of a war, with no sentence about the taking of hostages itself, and hostages in a war between States are `peace` only (section 5.2).
- Ceremonial uses ("peace-loving", congratulations, "a world of peace and prosperity"), peaceful uses of nuclear energy, social peace in a domestic economic sense: not this lens.
- Crime or violence without armed conflict, including "war on drugs" or "war on crime": not this lens, except Security Council action on it (above).
- Do not add `peace` for the formula "X threatens international peace and security" inside a sentence about another lens.

P1 (1960s)
> The war in the region continues to claim thousands of lives. We call on the parties to accept an immediate ceasefire and to negotiate, under the auspices of the United Nations, a settlement that respects the independence of all States of the area.

```json
{"frag_id": "ex-peace-p1", "lenses": ["peace"], "mention_type": {"peace": "substantive"}, "confidence": 3, "note": ""}
```

P2 (1970s)
> The resources swallowed by the arms race could transform the prospects of the developing world. Even a tenth of military budgets, released by genuine disarmament, would finance the programmes of this Development Decade.

```json
{"frag_id": "ex-peace-p2", "lenses": ["peace"], "mention_type": {"peace": "substantive"}, "confidence": 3, "note": "Disarmament is peace however framed, including by its benefits for development (4.10)."}
```

P3 (2020s)
> The gangs that control most of our capital kill, kidnap and extort with impunity. We thank the Security Council for authorizing the Gang Suppression Force, and we call on Member States to provide it with troops and funding.

```json
{"frag_id": "ex-peace-p3", "lenses": ["organized_crime", "peace"], "mention_type": {"organized_crime": "substantive", "peace": "substantive"}, "confidence": 3, "note": "Security Council action on gang violence is peace (4.10); the gangs are organized_crime."}
```

N1 (2010s)
> We believe that lasting peace can only rest on development and justice. Our foreign policy is guided by the cause of peace, friendship among nations and respect for international law.

```json
{"frag_id": "ex-peace-n1", "lenses": [], "mention_type": {}, "confidence": 3, "note": "Peace invoked as an aspiration and a value, with no war, process or measure (4.10)."}
```

N2 (1970s)
> The Assembly must intensify the campaign against apartheid. We call on all States to break off trade and cultural relations with the racist regime until the majority of the people enjoy their rights.

```json
{"frag_id": "ex-peace-n2", "lenses": [], "mention_type": {}, "confidence": 3, "note": "Apartheid and a call to isolate the regime, with no armed struggle, occupation or Security Council measure (4.10)."}
```

## 5. Co-labelling and boundary rules

The crime lenses overlap in real speeches. Apply these rules so that different coders make the
same call. The rows decide which lens a situation belongs to; they do not lower the threshold of
3.2. Each lens named in a row still needs its own qualifying sentence (`substantive`) or
enumeration item (`list`), and the clause rules of 3.2 apply to it.

### 5.1 Overlapping crime lenses

| Situation | Label |
|---|---|
| Drug trafficking, with no sentence about the criminal groups as such | `drugs` |
| A sentence about drug cartels or drug-trafficking organizations themselves (power, violence, infiltration, diversification, finances); "drug cartels" is a drug mention (3.2) | `drugs` + `organized_crime` |
| Trafficking in persons, migrant smuggling or wildlife trafficking by "networks" | the specific lens only |
| The same networks described as running several crimes, or linked to the Palermo Convention in general | specific lens + `organized_crime` |
| Narco-terrorism as such, or a sentence about terrorists' drug financing ("the drug trade finances the terrorist groups") | `drugs` + `terrorism` (+ `organized_crime` if a sentence treats the crime-terror nexus as such) |
| A sentence whose claim is the link between several crimes ("terrorism, drug trafficking and organized crime are intertwined") | each crime lens, `substantive` (3.2) |
| Money laundering, its channels or anti-money-laundering measures as the subject or main claim of a sentence or independent clause | `corruption` (+ the predicate-crime lens if a sentence is about it) |
| Laundering named as one more activity of criminals in a sentence about their crimes | the crime lens only |
| Financing of terrorism only | `terrorism` |
| Criminals bribing, infiltrating or capturing police, judges, officials or institutions as the main claim of a clause | `corruption` + the crime lens |
| The same only in a participial or subordinate clause ("..., buying the silence of officials") | the crime lens only |
| Fraud, extortion or embezzlement by public officials | `corruption` |
| Fraud, scams or extortion by criminal groups | `organized_crime` |
| Fraud, tax crimes or corporate crimes by individuals or companies | `corruption` |
| Illicit manufacturing of or trafficking in firearms, small arms, parts or ammunition, whoever receives them (criminals or armed groups) | `organized_crime`; add `peace` if a sentence treats the armed conflict or disarmament |
| Arms control, disarmament, the arms race or arms transfers between States, with no illicit trade | `peace` |
| Online child sexual abuse material, online grooming of children | `organized_crime` (cybercrime); add `trafficking_smuggling` only if trafficking is discussed |
| Diamonds, gold or other minerals mined or traded illicitly by armed groups | `environmental_crime`; add `peace` if a sentence is about the war |
| Modern piracy at sea | `organized_crime`; "air piracy" (hijacking): `terrorism` |
| Justice-system or crime prevention reform in general | `criminal_justice`, alongside any crime lens discussed |
| Prosecution or arrest as a means against one crime | that crime's lens only |
| Extradition, mutual legal assistance or other cooperation in criminal matters against one named crime | that crime's lens |
| The same cooperation in general, with no crime named | `criminal_justice` |
| Drug courts, or treatment, education, rehabilitation or reintegration offered to drug users as an alternative to conviction or punishment | `prevention_treatment` + `drugs`; add `criminal_justice` if the justice system itself is discussed |
| Other non-custodial or proportionate sentencing for drug offences | `drugs`; add `criminal_justice` if the justice system itself is discussed |
| Peace agreements dealing with illicit crops or drug trafficking | the drug lenses; add `peace` only if a sentence is about the peace process itself |
| "X is a threat to international peace and security" | lens X only |

### 5.2 Boundary rules

**Drug demand and supply (`drugs` versus `prevention_treatment`).** "Drug abuse" was the usual
name of the whole drug problem in 1980-1999 (the doublet "drug abuse and illicit traffic(king)"
alone appears in over 60 speeches), so it does not signal the demand side by itself.

| Situation | Label |
|---|---|
| "Drug abuse", addiction or consumption named only as the problem or scourge ("the scourge of drug abuse threatens our youth") | `drugs` |
| The doublet "drug abuse and illicit trafficking", and the names built on it: the 1987 International Conference, UNFDAC, the International Day against Drug Abuse and Illicit Trafficking | `drugs` |
| The "balanced approach" formula: "supply reduction and demand reduction", "reducing supply and reducing demand", "equal weight to both" | `drugs` |
| Producer or transit countries asking consumer countries to reduce their demand (burden sharing, co-responsibility) | `drugs` |
| A sentence about a prevention, treatment, rehabilitation, reintegration, harm-reduction or public health response to drug use, including a call to adopt one | `drugs` + `prevention_treatment` |
| Demand reduction as a named policy or programme with content (what is done, for whom or how) | `drugs` + `prevention_treatment` |

**Hostages, kidnapping and armed-group violence.** "Hostages" appears in over 140 speeches of
2020-2025, many of them ceasefire demands in 2024-2025. The rows apply in every era. Hostage-taking is
seizing or detaining a person and threatening to kill, injure or keep detaining them in order to compel a
third party (International Convention against the Taking of Hostages, art. 1). The Convention leaves out
only acts in armed conflicts where the Geneva Conventions oblige States to prosecute or hand over the
hostage-taker (art. 12): wars between States and, for States bound by Additional Protocol I, wars of national
liberation. Civil wars and other armed conflicts stay inside it. A fragment rarely shows which treaties bind
the parties, so the rows below set apart wars between States only.

| Situation | Label |
|---|---|
| (a) A sentence about the taking or holding of hostages outside a war between States, whoever the victims (civilians, travellers, diplomats) and whoever the takers (individuals, groups, armed groups in a civil war or another armed conflict); hostages held by a group the fragment calls terrorist; the International Convention against the Taking of Hostages | `terrorism`; add `peace` if a sentence treats the armed conflict |
| (b) Release of hostages, detainees or prisoners demanded only as a term of a ceasefire, exchange or end of a war, with no sentence about the taking itself; hostages and prisoners in a war between States | `peace` only |
| (c) Kidnapping for ransom or extortion by criminal groups | `organized_crime` |
| (d) Kidnappings or attacks by insurgents or armed groups that the speaker calls terrorism | `terrorism`; add `peace` if a sentence treats the armed conflict, demobilization or a peace process |
| (e) Homicide or kidnapping rates as crime statistics | `criminal_justice`; add `organized_crime` only if a sentence discusses the perpetrators as criminal groups |
| (f) Criminal groups using "terrorist methods" (bomb attacks, terrorizing communities) | `organized_crime`; add `terrorism` only when the fragment calls the acts terrorism or terrorist acts |

**Waste and environmental harm (`environmental_crime`).**

| Situation | Label |
|---|---|
| Export or dumping of toxic, hazardous, industrial or nuclear wastes into developing countries by companies, traders or unnamed actors, with or without the word "illegal" | `environmental_crime` |
| Dumping, disposal or storage of waste by States or State programmes (proposals by Powers to dump nuclear waste at sea) | no lens |
| Nuclear weapons testing | `peace` when framed as nuclear weapons or disarmament; otherwise no lens |
| Waste dumping named only as one environmental problem among others (acid rain, ozone, ocean pollution) | no lens |
| Ecocide or environmental harm as an international crime (Rome Statute, International Criminal Court) | no lens; `peace` only when tied to an armed conflict |
| Environmental offences in national criminal law, prosecution of environmental crimes | `environmental_crime` |

**Violence against women (`criminal_justice`).**

| Situation | Label |
|---|---|
| Violence against women or girls with a criminal-justice element: femicide or other criminal offences, police, prosecution, courts, protection orders, impunity, crime prevention programmes | `criminal_justice` |
| Violence against women named only as a gender-equality or human-rights goal | no lens |
| Victim support services (shelters, hotlines, legal, medical or psychological assistance) or prevention and awareness campaigns against violence against women | `criminal_justice` |
| Conflict-related sexual violence | `peace`; add `criminal_justice` only if its prosecution by national authorities is discussed, and `trafficking_smuggling` when persons are abducted, sold or held for sexual slavery, sexual exploitation or forced marriage |

**Crime in general.** Crime with no type named ("crime", "crimes", "criminality", "criminal
activities", "delinquency", "the fight against crime") is the core subject of the United Nations crime
prevention and criminal justice programme, whose goals are "the prevention of crime within and among
States" and "the control of crime both nationally and internationally" (A/RES/46/152, annex, para. 16). It
gives `criminal_justice`: `substantive` when a sentence is about it ("crime is rising in our cities and
my Government has made its prevention a priority"), `list` in an enumeration ("violence, terror and crime"
gives `criminal_justice` and `terrorism`, both `list`). A sentence about crime together with a named crime
counts for both: "criminal and terrorist activities threaten the whole region" gives `criminal_justice`
and `terrorism`. Label `organized_crime` when the fragment names organized or transnational crime, or
criminal groups, gangs, cartels, mafias or networks, and a specific lens when it names a specific crime;
"transnational crime" alone is `organized_crime`, not `criminal_justice`. "Crime" or "crimes" said of
aggression, apartheid, colonialism, genocide, war crimes or other atrocities, or of a government or an army
("the crimes of the occupier"), is not this lens.

**Terrorist labels.** Apply the single rule in 4.6 in every era: terrorist acts or groups
described as such, the acts of the universal instruments by their kind, or a discussion of what counts
as terrorism (including an explicit rebuttal of the label), give `terrorism`; "terrorist" used only as an
epithet for a State's army, government or war does not.

### 5.3 Boundary examples

These examples apply the rules of 5.1 and 5.2. Several are modelled on real passages; all are
written for this guide.

B01 (1987)
> The International Conference on Drug Abuse and Illicit Trafficking adopted a Comprehensive Multidisciplinary Outline. My delegation believes that the struggle against drug abuse and illicit trafficking must be waged with equal vigour on every front, and that the United Nations Fund for Drug Abuse Control deserves increased contributions.

```json
{"frag_id": "ex-boundary-01", "lenses": ["drugs"], "mention_type": {"drugs": "substantive"}, "confidence": 3, "note": "The doublet and the names built on it are drugs only; no prevention or treatment response is described."}
```

B02 (1989)
> It is the insatiable demand for cocaine in the rich countries that fuels the traffic and the violence we suffer. As long as there are consumers willing to pay any price, there will be traffickers willing to take any risk. The consuming nations must reduce their demand with the same determination with which we are fighting the traffickers.

```json
{"frag_id": "ex-boundary-02", "lenses": ["drugs"], "mention_type": {"drugs": "substantive"}, "confidence": 3, "note": "A producer country asking consumer countries to reduce demand is burden sharing, not a prevention or treatment response."}
```

B03 (2015)
> We look forward to the special session on the world drug problem in 2016. Our approach remains comprehensive, integrated and balanced, giving equal weight to reducing supply and reducing demand, on the basis of common and shared responsibility.

```json
{"frag_id": "ex-boundary-03", "lenses": ["drugs"], "mention_type": {"drugs": "substantive"}, "confidence": 3, "note": "The balanced supply-and-demand formula is drugs only."}
```

B04 (1968)
> The young men who fall in the occupied lands are not terrorists, as the occupying Power cynically describes them. They are patriots resisting occupation, and the Assembly must recognize the legitimacy of their struggle.

```json
{"frag_id": "ex-boundary-04", "lenses": ["terrorism", "peace"], "mention_type": {"terrorism": "substantive", "peace": "substantive"}, "confidence": 2, "note": "An explicit rebuttal of the terrorist label is part of the debate on what counts as terrorism; the occupation gives peace."}
```

B05 (2024)
> We call for an immediate ceasefire, the unconditional release of all hostages and unimpeded humanitarian access. The atrocities committed at the start of this war cannot justify the collective punishment of an entire people.

```json
{"frag_id": "ex-boundary-05", "lenses": ["peace"], "mention_type": {"peace": "substantive"}, "confidence": 3, "note": "Release of hostages as a term of a ceasefire, with no sentence about the taking itself: peace only (5.2, row (b))."}
```

B06 (2025, transcript)
> in our country international crime based on extortion uses terrorist methods such as bomb attacks against buses and small businesses to submit citizens to its will we have declared a state of emergency and deployed the armed forces to support the police

```json
{"frag_id": "ex-boundary-06", "lenses": ["organized_crime"], "mention_type": {"organized_crime": "substantive"}, "confidence": 2, "note": "Criminal extortion using 'terrorist methods' is organized crime; the acts are not called terrorism, and the emergency is a means against one crime."}
```

B07 (2003)
> During the past year kidnappings fell by a third and homicides by a fifth. The terrorist groups that finance themselves with cocaine and ransom money are weaker than ever, and more than three thousand of their members have laid down their arms and joined our reintegration programme.

```json
{"frag_id": "ex-boundary-07", "lenses": ["terrorism", "criminal_justice", "peace"], "mention_type": {"terrorism": "substantive", "criminal_justice": "substantive", "peace": "substantive"}, "confidence": 2, "note": "Crime rates give criminal_justice; cocaine appears only in a relative clause identifying the groups; demobilization and reintegration give peace."}
```

B08 (1989)
> Our continent will not become the dustbin of the industrialized world. The dumping of toxic and nuclear wastes on our soil is a new form of colonialism, and we welcome the decision to draw up a convention banning the import of such wastes.

```json
{"frag_id": "ex-boundary-08", "lenses": ["environmental_crime"], "mention_type": {"environmental_crime": "substantive"}, "confidence": 2, "note": "Waste shipped into developing countries is waste crime even without the word 'illegal'."}
```

B09 (1983)
> We reaffirm our opposition to the proposals of certain Governments to dispose of their radioactive wastes in the waters of our region. The ocean on which our peoples depend must not become a dumping ground for the nuclear Powers.

```json
{"frag_id": "ex-boundary-09", "lenses": [], "mention_type": {}, "confidence": 3, "note": "Waste disposal by States is not waste crime."}
```

B10 (2021)
> Gender equality is a pillar of our foreign policy. We are determined to eliminate all forms of violence against women and girls, which the pandemic has made more visible, and to ensure women's full participation in decision-making.

```json
{"frag_id": "ex-boundary-10", "lenses": [], "mention_type": {}, "confidence": 3, "note": "Violence against women as a gender-equality goal, with no criminal-justice element."}
```

B11 (2019)
> Organized criminal groups are defrauding our elderly citizens through telephone and online scams, and laundering the proceeds through cryptocurrency platforms that escape supervision.

```json
{"frag_id": "ex-boundary-11", "lenses": ["organized_crime"], "mention_type": {"organized_crime": "substantive"}, "confidence": 2, "note": "Fraud by criminal groups is organized crime; laundering is only one more activity of the groups in the same sentence."}
```

B12 (2023)
> The climate crisis is the greatest injustice of our time. That is why we are leading the call to recognize ecocide as a fifth international crime under the Rome Statute.

```json
{"frag_id": "ex-boundary-12", "lenses": [], "mention_type": {}, "confidence": 3, "note": "Ecocide under the Rome Statute is international criminal justice, outside the UNODC lenses."}
```

B13 (2012)
> The drug cartels have infiltrated police forces and town halls along the border, buying the silence of officials and murdering those who refuse. No democracy can survive if organized crime captures its institutions.

```json
{"frag_id": "ex-boundary-13", "lenses": ["drugs", "organized_crime", "corruption"], "mention_type": {"drugs": "substantive", "organized_crime": "substantive", "corruption": "substantive"}, "confidence": 2, "note": "'Drug cartels' is a drug mention; infiltration of the police and town halls is the main clause, so corruption applies."}
```

## 6. Recurring false positives

| Wording | Why it is not the lens |
|---|---|
| "corruption of values", "corrupting influence" | moral sense |
| "alternative development model", "an alternative for the development of the third world" | economic ideology (rare) |
| "cartels" (oil, commodity, producer cartels) | economic sense |
| "generic drugs", "access to drugs" (medicines), "drug-resistant" | pharmaceuticals |
| "balance of terror", "nuclear terror", "reign of terror" of a war | deterrence or war |
| "State terrorism" as an epithet for military action | label `peace` if armed conflict is discussed |
| "hostage to", "held hostage by" | metaphor |
| "release of all hostages" in a ceasefire demand | `peace`, not `terrorism`, unless a sentence is about the taking of hostages itself (5.2) |
| "terrorist methods", "terrorize" said of criminal groups | `organized_crime`, not `terrorism`, unless the acts are called terrorism |
| a State's designation on a national list of "State sponsors of terrorism", its removal from the list | sanctions or relations between States: `terrorism` only if terrorism itself is discussed; an accusation that a State supports terrorists, or its denial, is `terrorism` (4.6) |
| "since 11 September", "the world after 9/11" | a date or period: no `terrorism` (4.6) |
| "extremism", "extremists" as an ideology, a political position or an insult | no `terrorism` without violence against people (4.6) |
| "radicalization" in a political or social sense | no `terrorism` without violence (4.6) |
| "drug abuse and illicit trafficking", "the scourge of drug abuse", "reduce supply and demand" | `drugs`, not `prevention_treatment` |
| "eliminate all forms of violence against women" as a gender-equality goal | no lens without a criminal-justice element |
| "crime", "crimes" said of aggression, apartheid, colonialism, genocide or war, or of a government or an army | atrocity or invective: not `criminal_justice` (crime in general is, 5.2) |
| "lasting peace", "the cause of peace", "the maintenance of international peace and security" as a purpose | general invocation: no label, or `list` in an enumeration (4.10) |
| "international crime", "gangs", "extortion" before about 1990 | usually aggression, apartheid or political invective, not `organized_crime` |
| "territorial integrity", "integrity" in general | not `corruption` |
| "returnees" (refugees), "servitude" (colonial or political), "value chains" (trade), "bombing" (aerial war before 1990) | not the crime lenses |
| "economic slavery", "debt slavery", the historical slave trade | metaphor or history |
| "piracy" of software or intellectual property | not organized crime unless framed as such |
| the arms race, arms transfers between States, "proliferation" of weapons not called illicit | `peace`, not `organized_crime` (4.4) |
| UNODC and its work on crime, corruption or terrorism | not `drugs` unless its drug work is meant (4.1) |
| IUU fishing named only as a threat to fish stocks, livelihoods or sovereignty | fisheries management: not `environmental_crime` (4.8) |
| "prisoners" of war, demands to release political prisoners | human rights or conflict; their treatment in custody is `criminal_justice` (4.9) |
| "justice", "rule of law", "impunity" for atrocity crimes | outside `criminal_justice` |
| "peace-loving", "peaceful uses", "peace and prosperity" | ceremonial or technical |
| "war on drugs", "war on crime", "war zone" for crime | not `peace` |
| "ecocide" as climate rhetoric or as a Rome Statute crime | no lens; `environmental_crime` only as an offence in national criminal law |

## 7. Eras and vocabulary

The corpus spans eight decades; vocabulary for the same topic changes. The `era_terms` lists in the
YAML are cues for recognition, not automatic triggers.

- **1946-1969.** Mandate topics are rare. Drugs are almost absent (a few late-1940s mentions of narcotic drugs). Trafficking in persons appears only occasionally, as "traffic in women and children" or "white slave traffic" (1949 Convention). Criminal justice is essentially absent. "Forced labour" in this period usually refers to State or colonial labour systems (not `trafficking_smuggling`), and "prisoners" usually means prisoners of war or political prisoners. "Terrorism" is mostly an accusation. Apply the single rule in 4.6: "acts of terrorism" by an adversary's army, police or colonial administration are an epithet (`peace` if the conflict is discussed), while terrorists described as such ("we arrested terrorists who had infiltrated our territory") and explicit rebuttals of the label for liberation fighters are `terrorism`. "Bombing" in this period almost always means aerial bombing in war (`peace`).
- **1970-1989.** "Hijacking", "air piracy" and "taking of hostages" (the 1979 Hostages Convention) are the core of `terrorism`, together with the General Assembly debate on "international terrorism" and its causes; hostages in wars follow 5.2. Drugs appear as "drug abuse", "illicit traffic", "narcotics", "UNFDAC", "crop substitution" and, from the mid-1980s, "narco-terrorism" and the 1988 Convention. "Drug abuse" here is usually the generic name of the drug problem, often in the doublet "drug abuse and illicit trafficking": `drugs` only, unless a prevention or treatment response is described (5.2). "International crime", "gangs" and "extortion" usually refer to aggression, apartheid or political opponents, not to organized crime. Corruption appears mostly as denunciation of "administrative corruption" under former regimes and of bribes paid by foreign corporations or Powers; label it when bribery or misuse of office is described, not when "corruption" is moral. The Crime Congresses on "the prevention of crime and the treatment of offenders" are `criminal_justice`, and so are torture, ill-treatment and deaths of detainees and prison conditions, political prisoners included; demands to free "political prisoners" (frequent in the 1980s) are not (4.9). Attacks on diplomats and the seizure of embassies are `terrorism` by their kind (the 1973 Convention on Internationally Protected Persons, 4.6). From 1988 the export and "dumping of toxic wastes" into developing countries is `environmental_crime` even without the word "illegal"; proposals by States to dump nuclear waste at sea (a Pacific concern from 1979 to the mid-1990s) are not (5.2). "Cartels" usually means commodity or oil cartels.
- **1990-1999.** "Narco-trafficking", "drug control", "UNDCP", the 1990 and 1998 special sessions, "demand reduction" (`prevention_treatment` only when the policy has content; the supply-and-demand formula is `drugs`). "Transnational organized crime" and "money laundering" emerge, often in lists of "new threats". Corruption becomes a governance theme. Small arms become a disarmament topic (`peace`); their illicit trade is also `organized_crime`, whoever receives them (4.4).
- **2000-2014.** The Palermo Convention (2000) and UNCAC (2003). After 2001, counter-terrorism dominates: resolution 1373, "financing of terrorism", the Global Counter-Terrorism Strategy. "Human trafficking" and "trafficking in persons" become frequent. Modern maritime piracy (from 2008). Conflict diamonds and the Kimberley Process (`environmental_crime`, with `peace` for the war they finance, 4.8). IUU fishing (`environmental_crime` only when treated as crime, 4.8) and wildlife poaching grow.
- **2015-2026.** "Violent extremism" and "foreign terrorist fighters"; "cybercrime"; "migrant smuggling" and "modern slavery"; "illicit financial flows" (SDG 16.4); the 2016 special session on drugs and debates on drug policy reform; "access to justice" (SDG 16.3), "citizen security" and "femicide" ("violence against women" is frequent but counts for `criminal_justice` only with a criminal-justice element, 5.2); "hostages" in ceasefire demands (`peace`, 5.2); from 2020 synthetic drugs and fentanyl, scam compounds, the 2021 special session against corruption, the Convention against Cybercrime (2024) and illegal mining.

## 8. Translation and text artefacts

Many speeches were delivered in other languages and appear in English through United Nations
translation or, for 2025-2026, as transcripts of the English interpretation. Label the meaning, not
the spelling.

**Calques from Spanish, French and Portuguese.**

| Wording in the fragment | Meaning | Lens |
|---|---|---|
| narcotraffic, narco-trafficking, narcotics traffic, microtrafficking | drug trafficking (retail dealing for micro-) | `drugs` |
| stupefacients, psychoactive substances, drug consumption | narcotic drugs, drug use | `drugs`; `prevention_treatment` only when a response to drug use is described (5.2) |
| illicit crops, substitution of crops | drug crops, crop substitution | `drugs` / `alternative_development` |
| organized delinquency (from "delincuencia organizada") | organized crime | `organized_crime` |
| delinquency (from "delincuencia") | crime in general | `criminal_justice` (5.2) |
| sicarios, hired assassins, extortion rackets | organized crime | `organized_crime` |
| trata, trafficking of persons, traffic in persons | trafficking in persons | `trafficking_smuggling` |
| traffic of migrants, illicit traffic of migrants | migrant smuggling | `trafficking_smuggling` |
| asset laundering, laundering of assets | money laundering | `corruption` |
| extinction of ownership / of dominion | non-conviction-based asset forfeiture | `corruption` |
| citizen security, public security, citizen coexistence | crime prevention and public safety | `criminal_justice` |
| persons deprived of liberty, social readaptation, resocialization | prisoners, rehabilitation of offenders | `criminal_justice` |
| attempt, attentat (from "atentado", "attentat") | attack, often a terrorist attack | `terrorism` if so described |

**Older typescripts and OCR (mainly 1946-2014).** Paragraph numbers ("142."), meeting references
("[277th meeting]"), page and job numbers, "modem" for "modern", "¬" for a hyphen, and words split
by hyphenation may remain. Ignore them.

**2024 PDFs.** Some texts lost ligatures: "Naons" (Nations), "elecon" (election), "ci:zens"
(citizens). Read through them.

**2025-2026 transcripts.** Text comes from speech recognition of the English interpretation: no
paragraphs, weak punctuation, lower-case proper nouns, occasional "uh", repeated phrases, and
misheard terms (for example "narco trafficking", "counter terrorism", "you know DC" for UNODC).
Residual procedural sentences by the presiding officer ("The Assembly will hear an address by ...")
carry no lens. Apply the same rules; lower confidence to 2 only when a misrecognition makes the topic
genuinely uncertain.

## 9. Output format

Return one JSON object per fragment, one per line (JSON Lines), with exactly these fields:

| Field | Type | Content |
|---|---|---|
| `frag_id` | string | the fragment id as received |
| `lenses` | list of strings | lens ids that apply, in the display order of section 2; `[]` if none |
| `mention_type` | object | one entry per id in `lenses`, value `"substantive"` or `"list"`; `{}` if none |
| `confidence` | integer 1-3 | section 3.5 |
| `note` | string | one short sentence; `""` if nothing to add |

Example:

    {"frag_id": "PER_45_1990_p012", "lenses": ["drugs", "alternative_development", "organized_crime"], "mention_type": {"drugs": "substantive", "alternative_development": "substantive", "organized_crime": "list"}, "confidence": 2, "note": "Crime listed among threats; substitution discussed at length."}

Checklist before returning a record:

1. Every id in `lenses` exists in section 2 and appears once, in display order.
2. `mention_type` has exactly the same ids as `lenses`.
3. If `prevention_treatment` or `alternative_development` is present, `drugs` is present with an equal or stronger mention type (`expand_labels` in `pipeline/lenses.py` applies this).
4. No lens was assigned from a metaphor, a formula, a name, or a referent outside the fragment.
5. Every `peace` rests on a concrete matter of peace and security (4.10), and every crime lens on a named crime or criminal group or, for `criminal_justice`, on crime in general, crime prevention, the justice system, police or detention, or crime rates (5.2).
6. Whenever `confidence` is below 3, `note` says why.
