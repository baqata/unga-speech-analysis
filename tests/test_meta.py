"""Checks on the committed country and group metadata (pipeline.meta)."""
import csv
from collections import Counter, defaultdict

import pytest

from pipeline import meta
from pipeline.config import CORPUS_TXT, COUNTRIES, GROUPS, HISTORICAL_NAMES

needs_corpus = pytest.mark.skipif(not CORPUS_TXT.exists(), reason="corpus not available")


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


countries = read(COUNTRIES)
historical = read(HISTORICAL_NAMES)
groups = read(GROUPS)
by_code = {row["iso3"]: row for row in countries}


def members(group_id):
    return {row["iso3"] for row in groups if row["group_id"] == group_id}


@needs_corpus
def test_every_corpus_code_has_exactly_one_row():
    counts = Counter(row["iso3"] for row in countries)
    codes = meta.corpus_codes()
    assert len(codes) == 200
    assert {code: counts[code] for code in codes if counts[code] != 1} == {}


@needs_corpus
def test_committed_tables_match_the_code():
    for path, (fields, rows) in meta.build().items():
        assert read(path) == [{f: str(row[f]) for f in fields} for row in rows], path.name


def test_codes_are_unique_and_un_members_present():
    assert len(by_code) == len(countries)
    assert len(meta.UN_MEMBERS) == 193
    assert {c for c, row in by_code.items() if row["un_member"] == "true"} == meta.UN_MEMBERS
    assert {c for c, row in by_code.items() if row["is_observer"] == "true"} == {"VAT", "PSE", "EU"}


@pytest.mark.parametrize("column", ["name_en", "name_es"])
def test_names_are_unique_and_present(column):
    names = [row[column] for row in countries]
    assert all(names)
    assert [n for n, k in Counter(names).items() if k > 1] == []


def test_group_sizes():
    assert members("ROCOL") == {"ARG", "BOL", "CHL", "COL", "ECU", "PRY", "PER", "URY"}
    assert len(members("UE")) == 27
    assert members("BRICS") == {"BRA", "RUS", "IND", "CHN", "ZAF", "EGY", "ETH", "IRN", "ARE", "IDN"}
    assert members("G7") == {"CAN", "FRA", "DEU", "ITA", "JPN", "GBR", "USA"}
    assert len(members("ALC")) == 33
    assert len(members("AFR")) == 54


def test_group_members_are_known_and_historical_codes_placed():
    assert {row["iso3"] for row in groups} <= set(by_code)
    assert {row["group_type"] for row in groups} <= {"office", "bloc", "region"}
    grouped = {row["iso3"] for row in groups}
    assert not {"CSK", "DDR", "YUG", "EU"} & grouped
    assert "YMD" in members("ASP")


def test_map_ids_exist_in_world_atlas():
    atlas = meta.atlas_ids()
    used = {row["map_iso_numeric"] for row in countries if row["map_iso_numeric"]}
    assert used <= atlas
    for code in ["CSK", "DDR", "YUG", "YMD", "EU"]:
        assert by_code[code]["map_iso_numeric"] == ""
    assert all(len(row["iso_numeric"]) in (0, 3) for row in countries)


def test_every_atlas_feature_is_assigned_or_documented():
    names = {name for _, name in meta.atlas_features()}
    extra = {row["map_extra_features"] for row in countries if row["map_extra_features"]}
    assert extra <= names
    by_id = {row["map_iso_numeric"] for row in countries if row["map_iso_numeric"]}
    left = {name for id_, name in meta.atlas_features() if id_ not in by_id} - extra
    # Territories drawn in neutral grey; their labels are listed in SOURCES.md.
    assert left == {"W. Sahara", "Falkland Is.", "Greenland", "Fr. S. Antarctic Lands",
                    "Puerto Rico", "New Caledonia", "Antarctica"}


def test_points_for_states_without_geometry():
    no_shape = {row["iso3"] for row in countries if row["map_iso_numeric"] == ""}
    with_point = {row["iso3"] for row in countries if row["point_lat"]}
    assert with_point == no_shape - {"CSK", "DDR", "YMD", "YUG", "EU"}
    assert len(with_point) == 29
    for code in with_point:
        lat, lon = float(by_code[code]["point_lat"]), float(by_code[code]["point_lon"])
        assert -90 <= lat <= 90 and -180 <= lon <= 180, code


def test_historical_ranges_do_not_overlap():
    ranges = defaultdict(list)
    for row in historical:
        assert row["iso3"] in by_code
        assert row["name_en"] and row["name_es"]
        start, end = int(row["from_year"]), int(row["to_year"])
        assert 1946 <= start <= end
        ranges[row["iso3"]].append((start, end))
    for code, spans in ranges.items():
        spans.sort()
        for (_, prev_end), (next_start, _) in zip(spans, spans[1:]):
            assert next_start > prev_end, code


def test_naoero_is_filed_under_its_current_code():
    assert "NRU" not in by_code
    row = by_code["NRO"]
    assert (row["name_en"], row["name_es"], row["iso_numeric"]) == ("Naoero", "Naoero", "520")
    assert [(r["from_year"], r["to_year"], r["name_en"]) for r in historical if r["iso3"] == "NRO"] == [
        ("2000", "2025", "Nauru")]
