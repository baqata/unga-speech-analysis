"""pipeline.records: verbatim-record pages -> general-debate statements."""
from pipeline import records

PAGE1 = """               United Nations                                                   A/79/PV.7
               General Assembly                                          Official Records
               Seventy-ninth session

               7th plenary meeting
               Tuesday, 24 September 2024, 9 a.m.
               New York

President:     Mr. Yang . . . . . . . . . . . . . . . . . . . . . . . . . . . . (Cameroon)

                     The meeting was called to order at 9.05 a.m.

               Agenda item 8
               General debate

               Address by Mr. Test Person, President of the Republic of Türkiye
                   The President: The Assembly will now hear an address by the President of the
               Republic of Türkiye.
                     Mr. Test Person, President of the Republic of Türkiye, was escorted into the
                     General Assembly Hall.
                   President Person (spoke in Turkish; English interpretation provided by the
               delegation): The first paragraph runs over two lines and speaks of self-
               determination at the seventy -ninth session.
                   The second paragraph mentions Grenad a and runs on to the next page, where
               it ends after the page furniture and

               This record contains the text of speeches delivered in English and of the translation of speeches
               delivered in other languages. Corrections should be submitted to the original languages only.
               Document System of the United Nations (http://documents.un.org).

24-27317 (E)
*2427317*                                                              Accessible document      Please recycle
"""

PAGE2 = """A/79/PV.7                                                                     24/12/2024

            a language note.
            (spoke in English)
                The third paragraph is short.
                The President: On behalf of the General Assembly, I wish to thank the President
            of the Republic of Türkiye for the statement he has just made.
                Mr. Test Person, President of the Republic of Türkiye, was escorted from the
                General Assembly Hall.
                The President: I now give the floor to His Excellency Mr. Dos, Minister for
            Foreign Affairs of Norway.
                Mr. Dos (Norway): Norway speaks here, on one line and
            then on a second line.
                Mr. Kim (Democratic People’s Republic of Korea) (spoke in Korean; interpretation
            provided by the delegation) Allow me, as the record prints no colon, to speak.

2/64                                                                         24-27317
"""

PAGE3 = """24-27317                                                                          3/64
A/79/PV.7                                                                     24/12/2024

                The President: Several representatives have asked to speak in exercise of the
            right of reply. I remind members that statements are limited to 10 minutes and
            should be made by delegations from their seats.
                Mr. Tres (Islamic Republic of Iran): This is a reply and must not be kept as
            the country's statement.
                The meeting rose at 1 p.m.
"""

VOCAB = {"grenada": 1000, "grenad": 0, "a": 100_000}


def parse(pages=(PAGE1, PAGE2, PAGE3)):
    warnings = []
    out = records.parse_record(list(pages), "A/79/PV.7", warnings, VOCAB)
    return out, warnings


def test_statements_keep_speech_text_only():
    out, warnings = parse()
    assert [(s["iso3"], s["who"]) for s in out] == [
        ("TUR", "President Person"), ("NOR", "Mr. Dos"), ("PRK", "Mr. Kim")]
    tur = out[0]["paragraphs"]
    assert tur == [
        "The first paragraph runs over two lines and speaks of self-determination at the "
        "seventy-ninth session.",
        "The second paragraph mentions Grenada and runs on to the next page, where it ends after "
        "the page furniture and a language note.",
        "The third paragraph is short."]
    assert out[1]["paragraphs"] == ["Norway speaks here, on one line and then on a second line."]
    assert out[2]["paragraphs"] == ["Allow me, as the record prints no colon, to speak."]
    assert out[0]["joins"] == ["Grenad a -> Grenada"]
    assert warnings == []


def test_other_items_and_long_presider_turns():
    other = PAGE1.replace("Agenda item 8\n               General debate",
                          "Agenda item 127\n               Report of the Secretary-General")
    out, _ = parse((other, PAGE2, PAGE3))
    assert out == []  # nothing is taken outside the general debate
    long = PAGE2.replace("I wish to thank the President",
                         "I wish to thank the President " + "and " * 260)
    _, warnings = parse((PAGE1, long, PAGE3))
    assert len(warnings) == 1 and "The President speaks" in warnings[0]


def test_iso3_of_un_names():
    assert records.iso3_of("Mr. Lazarus McCarthy Chakwera, President of the Republic of Malawi and "
                           "Commander-in-Chief of the Malawi Defence Force") == "MWI"
    assert records.iso3_of("Mr. Félix-Antoine Tshisekedi Tshilombo, President of the Democratic "
                           "Republic of the Congo") == "COD"
    assert records.iso3_of("Mr. X, Prime Minister of Saint Vincent and the Grenadines and Minister "
                           "of Finance") == "VCT"
    assert records.iso3_of("Côte d’Ivoire") == "CIV"
    assert records.iso3_of("European Council") == "EU"
    assert records.iso3_of("Mr. David Ranibok Adeang, President and Head of State of the Republic "
                           "of Nauru") == "NRO"
