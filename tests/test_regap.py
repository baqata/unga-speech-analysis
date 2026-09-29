import pytest

from pipeline.regap import filler, find_gaps, looping, merge, splice_text


def seg(start, end, text, recovered=False):
    s = {"start": start, "end": end, "text": text}
    if recovered:
        s["recovered"] = True
    return s


def test_gaps_are_the_long_stretches_between_segments():
    segs = [seg(5.0, 7.0, "a"), seg(10.0, 12.0, "b"), seg(30.0, 40.0, "c")]
    assert find_gaps(segs) == [(12.0, 30.0)]


def test_a_stretched_segment_ends_where_its_words_can_have_ended():
    segs = [seg(17.0, 22.0, "invite him to address the Assembly."), seg(30.0, 60.0, "Thank you."),
            seg(60.0, 67.0, "make the mountains disappear")]
    assert find_gaps(segs) == [(22.0, 30.0), (33.0, 60.0)]
    assert find_gaps(segs, min_gap=10.0) == [(33.0, 60.0)]
    assert [filler(s) for s in segs] == [False, True, False]
    out, _ = merge(segs, [seg(33.5, 59.0, "Switzerland is a country of mountains.", True)])
    assert [s["end"] for s in out] == [22.0, 33.5, 59.0, 67.0]


def test_merge_inserts_in_time_order_and_trims_words_the_neighbours_hold():
    segs = [seg(0.0, 5.0, "Paraguay reaches a different conclusion."), seg(30.0, 35.0, "Since we cannot.")]
    found = [seg(5.0, 6.0, "conclusion.", True),
             seg(6.0, 9.0, "different conclusion. The United Nations remains indispensable.", True),
             seg(9.0, 30.0, "Manuel Gondra: since", True)]
    out, added = merge(segs, found)
    assert [s["text"] for s in out] == ["Paraguay reaches a different conclusion.",
                                        "The United Nations remains indispensable.", "Manuel Gondra:",
                                        "Since we cannot."]
    assert len(added) == 2


def test_merge_skips_the_pre_roll_heard_again_with_other_spellings():
    segs = [seg(0.0, 6.0, "We must effect healing through repartory justice, for it is the right thing to do."),
            seg(11.0, 15.0, "As a result, in July of this year.")]
    found = [seg(6.0, 7.0, "through a partry justice, for it is the right thing to do.", True)]
    assert merge(segs, found) == (segs, [])


def test_splice_keeps_the_text_spelling_and_adds_the_recovered_words():
    first = seg(0.0, 5.0, "heads of state,")
    added = seg(6.0, 9.0, "Thank you.", True)
    segs = [first, added, seg(30.0, 35.0, "we meet")]
    assert splice_text("Heads of State, we meet", segs, [added]) == "Heads of State, Thank you. we meet"
    with pytest.raises(ValueError):
        splice_text("Heads of State, we meet today", segs, [added])


def test_a_second_pass_adds_only_its_own_segments():
    earlier = seg(6.0, 7.0, "Thank you.", True)  # recovered by a first pass, already in the text
    added = seg(40.0, 42.0, "Switzerland is a country of mountains.", True)
    segs = [seg(0.0, 5.0, "invite him."), earlier, added, seg(60.0, 62.0, "Thank you.")]
    assert splice_text("invite him. Thank you. Thank you.", segs, [added]) == \
        "invite him. Thank you. Switzerland is a country of mountains. Thank you."


def test_a_segment_an_earlier_pass_recovered_keeps_its_identity_when_shortened():
    segs = [seg(0.0, 5.0, "invite him."), seg(60.0, 62.0, "We meet.")]
    segs, first = merge(segs, [seg(9.0, 50.0, "Thank you.", True)])  # first pass: a stretched recovery
    segs, second = merge(segs, [seg(40.0, 50.0, "Switzerland is a country of mountains.", True)])
    assert [s["end"] for s in segs] == [5.0, 40.0, 50.0, 62.0]
    assert splice_text("invite him. Thank you. We meet.", segs, second) == \
        "invite him. Thank you. Switzerland is a country of mountains. We meet."


def test_a_repetition_loop_is_not_speech():
    assert looping("I'ts, I do, " + "I go, " * 72)
    assert not looping("Mr. President, Mr. Secretary-General, Excellencies, it is a special honor to address this "
                       "assembly on behalf of Hungary. I speak here to the nations of the world.")
    assert not looping("Thank you.")
