"""Unit tests for the cleaning rules (pipeline.clean).

Examples are modelled on real UNGDC v14 files; each test names the rule it
covers and checks both the replacement and its counter.
"""
from collections import Counter

from pipeline import clean
from pipeline.clean import Vocab


def vocab_of(**freqs) -> Vocab:
    """Vocab from keyword counts; "_" stands for a hyphen."""
    return Vocab(Counter({w.replace("_", "-"): n for w, n in freqs.items()}))


# ---------------------------------------------------------------------------
# normalise
# ---------------------------------------------------------------------------

def test_bom_is_removed():
    c = Counter()
    assert clean.normalise("\ufeffMr. President,", c) == "Mr. President,"
    assert c["bom"] == 1


def test_crlf_and_cr_only_line_endings():
    c = Counter()
    assert clean.normalise("One.\r\nTwo.\r\n", c) == "One.\nTwo.\n"
    assert c["crlf"] == 2 and c["cr_only"] == 0
    c = Counter()
    assert clean.normalise("One.\rTwo.\r", c) == "One.\nTwo.\n"
    assert c["cr_only"] == 2 and c["crlf"] == 0


def test_unicode_spaces_and_invisible_characters():
    c = Counter()
    text = "United\u00a0Nations\u202fCharter \u200bpeace\u00adkeeping"
    assert clean.normalise(text, c) == "United Nations Charter peacekeeping"
    assert c["unicode_space"] == 2 and c["invisible_char"] == 2


def test_ligature_characters_are_expanded():
    c = Counter()
    assert clean.normalise("the \ufb01rst e\ufb00ort", c) == "the first effort"
    assert c["ligature_char"] == 2


def test_mojibake_map_and_possessive():
    c = Counter()
    raw = "the Organizationâ€™s role â€” and CÃ´te dâ€™Ivoire; the Peopleâs Republic"
    assert clean.normalise(raw, c) == ("the Organization’s role — and Côte d’Ivoire; "
                                       "the People’s Republic")
    assert c["mojibake"] == 5


# ---------------------------------------------------------------------------
# strip_editorial
# ---------------------------------------------------------------------------

def test_bracketed_references_are_removed_and_other_brackets_kept():
    c = Counter()
    text = ("As I said at the time [1234th meeting], the report [A/8701/Add.1, para. 3] "
            "and the Organization of African Unity [OAU] agree [ibid.].")
    assert clean.strip_editorial(text, c) == (
        "As I said at the time, the report and the Organization of African Unity [OAU] agree.")
    assert c["bracket_ref"] == 3


def test_damaged_bracket_references():
    c = Counter()
    text = ("as he told us [877th meeting) that peace, the report [A/8492J. It was "
            "stated [A/36731 at the time\nand then [see resolution 2625 (XXV)\nnext")
    out = clean.strip_editorial(text, c)
    assert out == ("as he told us that peace, the report. It was stated at the time\n"
                   "and then\nnext")
    assert c["bracket_ref"] == 4


def test_speaker_note_is_removed():
    c = Counter()
    text = "Thank you. [The speaker continued in French.] We believe"
    assert clean.strip_editorial(text, c) == "Thank you. We believe"


def test_see_and_document_references():
    c = Counter()
    text = ("the Agenda (see resolution 70/1) and the Declaration (resolution 2625 (XXV)), "
            "as noted (A/70/PV.5, p. 3) and (S/2015/1), also (see A/73/PV.6).")
    assert clean.strip_editorial(text, c) == (
        "the Agenda and the Declaration, as noted and, also.")
    assert c["see_ref"] == 2 and c["doc_ref"] == 3


def test_ordinary_parentheses_are_kept():
    c = Counter()
    text = "the least developed countries (LDCs) and the year (1945) matter"
    assert clean.strip_editorial(text, c) == text


def test_see_reference_with_damaged_closer_and_record_note():
    c = Counter()
    text = ("economic relations (see 1215th meeting, para. 106]. The situation in Syria has "
            "deteriorated to such an extent that This record contains the text of speeches "
            "delivered in English and of the interpretation of speeches delivered in the other "
            "languages. Corrections should be submitted to the original languages only. "
            "Corrections will be issued after the end of the session in a consolidated "
            "corrigendum. humanitarian organizations are unable to cope.")
    assert clean.strip_editorial(text, c) == (
        "economic relations. The situation in Syria has deteriorated to such an extent that "
        "humanitarian organizations are unable to cope.")
    # The damaged "(see ... meeting ...]" is caught by the meeting-reference rule.
    assert c["bracket_ref"] == 1 and c["record_note"] == 1


def test_spoke_in_notes():
    c = Counter()
    text = "Mr. President, (spoke in French) Nous sommes ici. (spoke in English) We are here."
    assert clean.strip_editorial(text, c) == "Mr. President, Nous sommes ici. We are here."
    assert c["spoke_in"] == 2


def test_applause_notes_but_not_the_word():
    c = Counter()
    text = "Long live Africa! (Applause) [Laughter] Thank you. APPLAUSE. The applause of the people"
    assert clean.strip_editorial(text, c) == (
        "Long live Africa! Thank you. The applause of the people")
    assert c["applause"] == 3


# ---------------------------------------------------------------------------
# strip_markdown
# ---------------------------------------------------------------------------

def test_markdown_emphasis():
    c = Counter()
    text = "**Mr. President**, the *Pact for the Future* and 3 * 4 ** remain"
    assert clean.strip_markdown(text, c) == "Mr. President, the Pact for the Future and 3 * 4  remain"
    assert c["markdown"] == 3


# ---------------------------------------------------------------------------
# Vocabulary and hyphenation decisions
# ---------------------------------------------------------------------------

def test_vocab_splits_line_end_hyphens_before_counting():
    v = Vocab()
    v.add("economic develop-\nment and self-determination; develop¬\nment")
    assert v.freq("development") == 0
    assert v.freq("develop") == 2 and v.freq("ment") == 2
    assert v.freq("self-determination") == 1


def test_closed_or_hyphenated():
    v = vocab_of(development=10, develop_ment=0, self_determination=5, selfdetermination=1,
                 secretarygeneral=50)
    assert v.closed_or_hyphenated("develop", "ment") == ("development", True)
    assert v.closed_or_hyphenated("self", "determination") == ("self-determination", False)
    # A capitalised right part is a proper compound: the hyphen stays.
    assert v.closed_or_hyphenated("Secretary", "General") == ("Secretary-General", False)
    # Unknown in both forms: keep the hyphen.
    assert v.closed_or_hyphenated("post", "conflict") == ("post-conflict", False)
    assert v.decisions[("develop-ment", "development")] == 1


# ---------------------------------------------------------------------------
# fix_ocr
# ---------------------------------------------------------------------------

def test_modem_is_corrected_only_as_an_adjective():
    c = Counter()
    text = "the modem world, Modem technology, a modem, and modem connections"
    out = clean.fix_ocr(text, "XXX_50_1995", 1995, Vocab(), c)
    assert out == "the modern world, Modern technology, a modern, and modem connections"
    assert c["modem"] == 3


def test_not_sign_used_as_hyphen():
    c = Counter()
    v = vocab_of(international=20, self_determination=5)
    text = "develop¬\nment of inter¬national law and self¬determination and a ¬ b"
    out = clean.fix_ocr(text, "XXX_47_1992", 1992, v, c)
    assert out == "develop-\nment of international law and self-determination and a - b"
    assert c["not_sign"] == 4


def test_one_for_i_before_a_verb():
    c = Counter()
    text = "60. 1 should like to recall, and 1 believe that paragraph 1 should be amended."
    out = clean.fix_ocr(text, "XXX_25_1970", 1970, Vocab(), c)
    assert out == "60. I should like to recall, and I believe that paragraph 1 should be amended."
    assert c["one_for_i"] == 2
    # Only in the OCR era.
    c = Counter()
    assert clean.fix_ocr(text, "XXX_50_1995", 1995, Vocab(), c) == text
    assert c["one_for_i"] == 0


def test_disfluencies():
    c = Counter()
    text = "Uh, the world is, um, changing. We need an umbrella for the humble."
    out = clean.fix_ocr(text, "XXX_80_2025", 2025, Vocab(), c)
    assert out == "the world is, changing. We need an umbrella for the humble."
    assert c["disfluency"] == 2


def test_ligature_loss_only_in_targeted_files():
    v = Vocab(Counter({"nations": 100, "citizens": 40, "better": 50, "justice": 60,
                       "setting": 20, "election": 30, "united": 100, "the": 500, "and": 500,
                       "of": 500, "our": 100, "for": 100}))
    text = "United Na5ons and our ci:zens, be>er jus=ce for the se‘ng of the elecon."
    c = Counter()
    out = clean.fix_ocr(text, "KNA_79_2024", 2024, v, c)
    assert out == "United Nations and our citizens, better justice for the setting of the election."
    assert c["ligature_loss"] == 6
    assert clean.fix_ocr(text, "KEN_79_2024", 2024, v, Counter()) == text


def test_ligature_loss_missing_letters_irn():
    v = Vocab(Counter({"nations": 100, "international": 40, "united": 100, "the": 500,
                       "and": 500, "law": 50}))
    c = Counter()
    out = clean.fix_ocr("the United Naons and internaonal law", "IRN_79_2024", 2024, v, c)
    assert out == "the United Nations and international law"
    assert c["ligature_loss"] == 2


# ---------------------------------------------------------------------------
# strip_presiding (2025 and provisional transcripts)
# ---------------------------------------------------------------------------

SPEECH = ("When we took office, the country was in ruins. We had to confront our problems "
          "with honesty. May God bless all peoples of the world.")


def test_presiding_intro_and_closing_are_removed():
    text = ("The Assembly will now hear an address by His Excellency Juan Perez, President of "
            "the Republic. I request protocol to escort His Excellency and invite him to "
            "address the Assembly. " + SPEECH + " On behalf of the Assembly, I wish to thank "
            "the President of the Republic. Thank you.")
    c, removed = Counter(), []
    out = clean.strip_presiding(text, c, removed)
    assert out == SPEECH
    assert c["presiding_intro"] == 1 and c["presiding_closing"] == 1
    assert [kind for kind, _ in removed] == ["intro", "closing"]


def test_presiding_intro_cut_at_salutation_inside_the_sentence():
    # The transcript runs the introduction into the speaker's first words (MYS 2025).
    text = ("Now, I give the floor to His Excellency, Mr. Ahmad Rahman, Minister of Foreign "
            "Affairs of Malaysia Bismillahirrahmanirrahim, Madam President, Your Excellencies, "
            "May I begin by congratulating the President. " + SPEECH)
    out = clean.strip_presiding(text, Counter())
    assert out.startswith("Bismillahirrahmanirrahim, Madam President, Your Excellencies, May I")
    assert out.endswith(SPEECH)


def test_presiding_intro_after_other_sentences_and_caption():
    text = ("Thank you. The next speaker is the Foreign Minister. I now give the floor to his "
            "excellency Ivan Petrov, Minister for Foreign Affairs. FOREIGN MINISTER PETROV, "
            "MINISTER FOR FOREIGN AFFAIRS Madam President, ladies and gentlemen, " + SPEECH)
    c = Counter()
    out = clean.strip_presiding(text, c)
    assert out == "Madam President, ladies and gentlemen, " + SPEECH
    assert c["transcript_caption"] == 1


def test_presiding_closing_followed_by_junk():
    text = SPEECH + " I thank the Prime Minister of Tuvalu. Okay, here we go."
    assert clean.strip_presiding(text, Counter()) == SPEECH


def test_presiding_invitation_with_long_title():
    text = ("I now invite Her Excellency Maria Lopez Rosero, Minister for Foreign Affairs and "
            "Human Mobility of Ecuador to address the assembly. Madam President, " + SPEECH)
    c = Counter()
    assert clean.strip_presiding(text, c) == "Madam President, " + SPEECH
    assert c["presiding_intro"] == 1


def test_short_transcript_is_not_cut_by_the_next_introduction():
    text = (SPEECH + " Thank you very much. On behalf of the Assembly, I wish to thank the Vice "
            "President of the Republic. The Assembly will hear an address by his ex-")
    c = Counter()
    assert clean.strip_presiding(text, c) == SPEECH + " Thank you very much."
    assert c["presiding_intro"] == 0


def test_speech_without_presiding_text_is_unchanged():
    c = Counter()
    assert clean.strip_presiding(SPEECH, c) == SPEECH
    assert c["presiding_intro"] == 0 and c["presiding_closing"] == 0


# ---------------------------------------------------------------------------
# split_lines
# ---------------------------------------------------------------------------

def texts(lines):
    return [ln.text for ln in lines]


def test_page_furniture_is_dropped():
    raw = ("The first paragraph ends here.\n\x0c15-29432\t3/24\n12\n"
           "A/70/PV.13\t28/09/2015\n* * *\nThe second paragraph.\n"
           "15-29432 3/24 The third line after an inline header.")
    c = Counter()
    lines = clean.split_lines(raw, 2015, c)
    assert texts(lines) == ["The first paragraph ends here.", "The second paragraph.",
                            "The third line after an inline header."]
    assert c["form_feed"] == 1 and c["page_number"] == 1 and c["page_header"] == 3
    assert c["separator"] == 1
    assert lines[1].gap == "sep" and lines[2].gap == "page"


def test_paragraph_numbers_in_the_ocr_era():
    raw = ("77.\t In Japan we believe.\n78. The next paragraph began in 1945. 79. Inline "
           "paragraph.\n. Disarmament is next.\n63.\t31.\tA doubled number.")
    c = Counter()
    lines = clean.split_lines(raw, 1970, c)
    assert texts(lines) == ["In Japan we believe.", "The next paragraph began in 1945.",
                            "Inline paragraph.", "Disarmament is next.", "A doubled number."]
    assert [ln.numbered for ln in lines] == [True, True, True, False, True]
    assert c["para_number"] == 5 and c["stray_punct"] == 1


def test_numbers_that_are_not_paragraph_numbers_are_kept():
    raw = "We adopted resolutions 1514 and\n12. In the year after, we met again."
    lines = clean.split_lines(raw, 1970, Counter())
    assert texts(lines) == ["We adopted resolutions 1514 and", "12. In the year after, we met again."]


def test_paragraph_numbers_on_their_own_line_and_after_stray_punctuation():
    raw = ("107.\nMr. President, let me first congratulate you.\nIt is worth noting.\n"
           ". 108. To give each Government a seat.\n, 109. Apart from that, we agree.\n"
           "We refer to resolution\n242.\n")
    c = Counter()
    lines = clean.split_lines(raw, 1978, c)
    assert texts(lines) == ["Mr. President, let me first congratulate you.", "It is worth noting.",
                            "To give each Government a seat.", "Apart from that, we agree.",
                            "We refer to resolution", "242."]
    assert [ln.numbered for ln in lines] == [True, False, True, True, False, False]
    assert c["para_number"] == 3 and c["stray_punct"] == 2


def test_verbatim_record_headers_with_barcode_and_corrigendum():
    raw = ("First line of the speech ends here.\n17-29597 (E) 1729597 general elections.\n"
           "A/PV.1943 and Corr.l\n363 A/PV.2371\nThe treaties are under way. » A/PV.1942 and Corr.l")
    c = Counter()
    lines = clean.split_lines(raw, 1971, c)
    assert texts(lines) == ["First line of the speech ends here.", "general elections.",
                            "The treaties are under way."]
    assert c["page_header"] == 4


def test_paragraph_numbers_after_1991_need_a_paragraph_start():
    raw = "12. The Charter is clear.\nWe met in\n2. The text goes on.\n42. 50 years later, less."
    lines = clean.split_lines(raw, 2000, Counter())
    assert texts(lines) == ["The Charter is clear.", "We met in", "2. The text goes on.",
                            "50 years later, less."]


def test_markdown_headings_bullets_and_trailing_separators():
    raw = ("## 1. Peace and security\nOur priorities are:\n- first, peace;\n- second, trade.\n"
           "End of section. * * *\nNew section - with a dash inside.")
    c = Counter()
    lines = clean.split_lines(raw, 2024, c)
    assert texts(lines) == ["Peace and security", "Our priorities are:", "first, peace;",
                            "second, trade.", "End of section.",
                            "New section - with a dash inside."]
    assert lines[0].heading and lines[2].bullet and lines[3].bullet
    assert lines[5].gap == "sep"


# ---------------------------------------------------------------------------
# Repeated n-gram loops
# ---------------------------------------------------------------------------

def test_whisper_loop_is_collapsed():
    text = "Our position is clear: " + "the people of Kashmir " * 17 + "deserve justice."
    c, removed = Counter(), []
    out = clean.collapse_loops(text, c, removed)
    assert out == "Our position is clear: the people of Kashmir deserve justice."
    assert c["ngram_loop"] == 1 and c["ngram_loop_words"] == 64
    assert removed[0][0] == "17 x 4-gram"


def test_long_passage_repeated_twice_is_collapsed():
    passage = ("we call on all States to respect the sovereignty and territorial integrity of "
               "every nation and to settle their disputes by peaceful means ")
    text = "Finally, " + passage + passage + "Thank you."
    out = clean.collapse_loops(text, Counter())
    assert out == "Finally, " + passage + "Thank you."


def test_short_repetitions_and_punctuation_are_kept():
    for text in ("Never again, never again. We must act now for the future of all.",
                 "He said . . . . . . . . . and then the meeting went on as before.",
                 "Peace, peace, peace. That is what our people want from this Assembly."):
        assert clean.collapse_loops(text, Counter()) == text


def test_loops_never_span_paragraphs():
    paragraphs = ["We will act.", "We will act.", "We will act.", "We will act.",
                  "We will act and we will succeed together."]
    assert clean.collapse_loops_all(paragraphs, Counter()) == paragraphs


# ---------------------------------------------------------------------------
# Review fixes: mojibake, editorial debris, other speakers, presiding, lines
# ---------------------------------------------------------------------------

def test_mojibake_apostrophes_and_accented_i():
    c = Counter()
    raw = "UNITAâs leader, CÃ´te dâIvoire and Mr. RodrÃ\xadguez; Côte d�Ivoire �peace�"
    assert clean.normalise(raw, c) == (
        "UNITA’s leader, Côte d’Ivoire and Mr. Rodríguez; Côte d’Ivoire \"peace\"")
    assert c["mojibake"] >= 6


def test_mojibake_rule_keeps_ordinary_a_circumflex():
    text = "the château and the pâté, Mâcon"
    assert clean.normalise(text, Counter()) == text


def test_meeting_references_with_damaged_openers():
    c = Counter()
    text = ("as he said (868th meeting] and f680th meeting] and {751st meeting} "
            "and 1873rd meeting] and (144th meeting), para. 3.")
    assert clean.strip_editorial(text, c) == "as he said and and and and, para. 3."
    assert c["bracket_ref"] == 5


def test_damaged_references_without_the_word_or_with_a_damaged_opener():
    c = Counter()
    text = ("the resolution [377 (V)} and the proposals [DC/10, DC/12, DC/15). Also "
            "[item 93J and [A]33/241], the Declaration /resolution 2621 (XXV)], the report "
            "fA/9001/Add.l], the Strategy {resolution 35/118] and and/or 5 [OAU].")
    assert clean.strip_editorial(text, c) == (
        "the resolution and the proposals. Also and, the Declaration, the report, "
        "the Strategy and and/or 5 [OAU].")
    assert c["bracket_ref"] == 7


def test_damaged_bracket_does_not_eat_prose():
    # A "[" with no closer only takes the typed reference body (GBR 1970, YUG 1956).
    text = "as stated [A/8001, para. 12 in the report of the Secretary-General on the work"
    assert clean.strip_editorial(text, Counter()) == (
        "as stated in the report of the Secretary-General on the work")


def test_official_records_citations_footnotes_and_watermark():
    c = Counter()
    text = ("he said, \"peace is indivisible\" (Official Records of the General Assembly, "
            "Twenty-fifth Session, Plenary Meetings (A/PV.1880), para. 5). We agree.\n"
            "2 See Official Records of the Security Council, Twenty-sixth Year, 1606th meeting.\n"
            "The next line. Digitized by Dag Hammarskjöld Library\n6/ Official Records of the "
            "Security Council. Sixteenth Year.\nOfficial Records of the Security Council, "
            "Fifteenth Year.\nThe end, as quoted (Official Records\nof the General Assembly, "
            "Fiftieth Session, Plenary Meetings, 1st meeting, p. 6).")
    assert clean.strip_editorial(text, c) == (
        "he said, \"peace is indivisible\". We agree.\nThe next line.\nThe end, as quoted.")
    # The inner "(A/PV.1880)" goes first as a document reference, then the citation.
    assert c["doc_ref"] == 3 and c["footnote"] == 3 and c["watermark"] == 1


def test_other_speakers_are_cut_and_own_labels_dropped():
    text = ("Mr. KHALIL (Honduras) (interpretation from Spanish): We come in peace.\n"
            "Our region needs development.\n"
            "The PRESIDENT: I thank the Minister for Foreign Affairs of Honduras.\n"
            "Mr. OGATA (Japan): The Japanese delegation wishes to speak.\n"
            "Mr. KHALIL (Honduras): Let me add one final word.\n")
    c, removed = Counter(), []
    out = clean.strip_other_speakers(text, {"Honduras"}, c, removed)
    assert out == ("We come in peace.\nOur region needs development.\n"
                   "Let me add one final word.\n")
    assert c["speaker_label"] == 2 and c["other_speaker"] == 2
    assert [kind for kind, _ in removed] == ["other_speaker", "other_speaker"]


def test_delegation_labels_are_kept_without_country_names():
    text = "We come in peace. " * 20 + "\nMr. OGATA (Japan): The delegation of Japan agrees.\n"
    assert clean.strip_other_speakers(text, (), Counter()) == text


def test_presiding_closings_in_several_forms():
    for closing in ("I thank His Excellency, Minister for Foreign Affairs of Austria.",
                    "On behalf of the General Assembly, thank you.",
                    "I thank the Federal Councillor of the Swiss Confederation.",
                    "We have heard the last speaker in the general debate for this meeting."):
        text = SPEECH + " " + closing
        c = Counter()
        assert clean.strip_presiding(text, c) == SPEECH, closing
        assert c["presiding_closing"] >= 1


def test_speaker_thanks_are_not_a_presiding_closing():
    for thanks in ("I thank the people of Japan for their hospitality.",
                   "I thank the President of the General Assembly.",
                   "Thank you."):
        text = SPEECH + " " + thanks
        assert clean.strip_presiding(text, Counter()) == text, thanks


def test_presiding_intro_hall_order_and_repeated_name_and_title():
    text = ("The Assembly will now hear an address by His Excellency Isaac Herzog, President "
            "of the State of Israel. Please, order in the hall. Isaac Herzog, President of the "
            "State of Israel. Mr. President, " + SPEECH)
    c, removed = Counter(), []
    assert clean.strip_presiding(text, c, removed) == "Mr. President, " + SPEECH
    assert [kind for kind, _ in removed] == ["intro", "name"]


def test_repeated_name_needs_an_introduction():
    text = "Taye Atske Selassie, President of Ethiopia. Mr. President, " + SPEECH
    assert clean.strip_presiding(text, Counter()) == text


def test_hon_caption_run_is_removed():
    text = ("I now give the floor to the Minister of Foreign Affairs of the Lao People's "
            "Democratic Republic. Hon Albert CHAN Wai-yip Hon Philip MONG YANG Madam President, "
            + SPEECH)
    c = Counter()
    assert clean.strip_presiding(text, c) == "Madam President, " + SPEECH
    assert c["transcript_caption"] == 1


def test_running_heads_of_1993_to_1996_are_dropped():
    raw = ("guide this session to the successful\nForty-eighth session - 11 October l993 7\n"
           "conclusion of its work.\n8 General Assembly - Forty-eighth session\n"
           "The conflict goes on.\nGeneral Assembly 22nd plenary meeting\n"
           "Fiftieth session 13 October 1995\nWe hope for peace.")
    c = Counter()
    lines = clean.split_lines(raw, 1995, c)
    assert texts(lines) == ["guide this session to the successful", "conclusion of its work.",
                            "The conflict goes on.", "We hope for peace."]
    assert c["page_header"] == 4


def test_bullets_on_continuation_lines_are_not_bullets():
    raw = ("Our country has made progress in\n• education, health and\n• infrastructure, and "
           "we will\n• continue on this path.\nOur priorities are:\n• peace;\n• development.")
    lines = clean.split_lines(raw, 2024, Counter())
    assert texts(lines)[1:4] == ["education, health and", "infrastructure, and we will",
                                 "continue on this path."]
    assert not any(ln.bullet for ln in lines)


def test_real_bullets_survive_a_continuation():
    raw = ("Our country has made progress in\n• education.\nOur priorities are:\n"
           "• peace;\n• development.")
    lines = clean.split_lines(raw, 2024, Counter())
    assert [ln.bullet for ln in lines] == [False, False, False, True, True]


def test_deliberate_repetition_is_kept_when_long_loops_are_off():
    passage = ("we call on all States to respect the sovereignty and territorial integrity of "
               "every nation and to settle their disputes by peaceful means ")
    text = "Finally, " + passage + passage + "Thank you."
    assert clean.collapse_loops(text, Counter(), long_loops=False) == text
    text = "I repeat: we will never accept it. I repeat: we will never accept it."
    assert clean.collapse_loops(text, Counter()) == text


def test_prefix_hyphen_before_a_digit_loses_its_space():
    c = Counter()
    text = "the post- 2015 agenda, the mid- 1970s, resolution ES- 7/2; the fifth century- 1,200"
    assert clean.fix_ocr(text, "XXX_68_2013", 2013, Vocab(), c) == (
        "the post-2015 agenda, the mid-1970s, resolution ES-7/2; the fifth century- 1,200")
    assert c["prefix_digit"] == 3
