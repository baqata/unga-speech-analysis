"""Country and group metadata for the dashboard.

Writes three reference tables to data/meta/ (see data/meta/SOURCES.md):
- countries.csv: one row per corpus code and per current UN member state.
- historical_names.csv: names used at other times by entities filed under a code.
- groups.csv: office, bloc and region memberships in long format.

Run with: uv run python -m pipeline.meta
"""
import csv
import gettext
import json
import re

import pycountry

from pipeline.config import CODE_RENAMES, COUNTRIES, CORPUS_TXT, GROUPS, HISTORICAL_NAMES, META

SPEECH_FILE = re.compile(r"^([A-Z]{2,4})_\d{2}_\d{4}\.txt$")
M49_SOURCE = META / "m49_source.csv"
WORLD_ATLAS = META / "world-atlas-countries-110m.json"

COUNTRY_FIELDS = [
    "iso3", "name_en", "name_es", "iso_numeric", "map_iso_numeric",
    "map_extra_features", "point_lat", "point_lon",
    "m49_region_en", "m49_region_es", "m49_subregion_en", "m49_subregion_es",
    "un_member", "is_observer",
]
HISTORICAL_FIELDS = ["iso3", "from_year", "to_year", "name_en", "name_es"]
GROUP_FIELDS = ["group_id", "group_type", "name_es", "name_en", "iso3"]

# The 193 current UN member states.
UN_MEMBERS = set("""
AFG ALB DZA AND AGO ATG ARG ARM AUS AUT AZE BHS BHR BGD BRB BLR BEL BLZ BEN BTN
BOL BIH BWA BRA BRN BGR BFA BDI CPV KHM CMR CAN CAF TCD CHL CHN COL COM COG CRI
CIV HRV CUB CYP CZE PRK COD DNK DJI DMA DOM ECU EGY SLV GNQ ERI EST SWZ ETH FJI
FIN FRA GAB GMB GEO DEU GHA GRC GRD GTM GIN GNB GUY HTI HND HUN ISL IND IDN IRN
IRQ IRL ISR ITA JAM JPN JOR KAZ KEN KIR KWT KGZ LAO LVA LBN LSO LBR LBY LIE LTU
LUX MDG MWI MYS MDV MLI MLT MHL MRT MUS MEX FSM MCO MNG MNE MAR MOZ MMR NAM NRO
NPL NLD NZL NIC NER NGA MKD NOR OMN PAK PLW PAN PNG PRY PER PHL POL PRT QAT KOR
MDA ROU RUS RWA KNA LCA VCT WSM SMR STP SAU SEN SRB SYC SLE SGP SVK SVN SLB SOM
ZAF SSD ESP LKA SDN SUR SWE CHE SYR TJK THA TLS TGO TON TTO TUN TUR TKM TUV UGA
UKR ARE GBR TZA USA URY UZB VUT VEN VNM YEM ZMB ZWE
""".split())

# Non-member observers that speak in the General Debate.
OBSERVERS = {"VAT", "PSE", "EU"}

# Corpus codes that are not current ISO 3166-1 countries. M49 placement is
# the one their territory had (or has) in the M49 standard; the EU has none.
NON_ISO_ENTITIES = {
    "CSK": ("Czechoslovakia", "Checoslovaquia", "Europe", "Eastern Europe"),
    "DDR": ("East Germany", "Alemania Oriental", "Europe", "Eastern Europe"),
    "YMD": ("South Yemen", "Yemen del Sur", "Asia", "Western Asia"),
    "YUG": ("Yugoslavia", "Yugoslavia", "Europe", "Southern Europe"),
    "EU": ("European Union", "Unión Europea", "", ""),
}

# Short, commonly used names where pycountry's differ.
NAME_EN = {
    "BRN": "Brunei",
    "COD": "DR Congo",
    "FSM": "Micronesia",
    "NRO": "Naoero",
    "PSE": "Palestine",
    "RUS": "Russia",
    "VAT": "Holy See",
}
NAME_ES = {
    "BFA": "Burkina Faso",
    "BRN": "Brunéi",
    "CIV": "Costa de Marfil",
    "COD": "RD del Congo",
    "COM": "Comoras",
    "DZA": "Argelia",
    "FSM": "Micronesia",
    "MDV": "Maldivas",
    "MMR": "Myanmar",
    "NER": "Níger",
    "NRO": "Naoero",
    "PSE": "Palestina",
    "QAT": "Qatar",
    "ROU": "Rumania",
    "RUS": "Rusia",
    "SAU": "Arabia Saudita",
    "SUR": "Surinam",
    "TUN": "Túnez",
    "VAT": "Santa Sede",
}

# World-atlas features drawn apart from a member state that UN practice treats
# as part of that state (see SOURCES.md). Values are feature names, since the
# first three features have no id in the atlas.
MAP_EXTRA_FEATURES = {
    "CYP": "N. Cyprus",
    "SOM": "Somaliland",
    "SRB": "Kosovo",
    "CHN": "Taiwan",
}

# Capital-city coordinates (lat, lon) for states without 110m geometry, so
# the map can draw them as points.
MAP_POINTS = {
    "AND": (42.51, 1.52),     # Andorra la Vella
    "ATG": (17.13, -61.85),   # St. John's
    "BHR": (26.23, 50.59),    # Manama
    "BRB": (13.10, -59.61),   # Bridgetown
    "COM": (-11.72, 43.25),   # Moroni
    "CPV": (14.93, -23.51),   # Praia
    "DMA": (15.30, -61.39),   # Roseau
    "FSM": (6.91, 158.16),    # Palikir
    "GRD": (12.06, -61.75),   # St. George's
    "KIR": (1.33, 172.98),    # South Tarawa
    "KNA": (17.30, -62.72),   # Basseterre
    "LCA": (14.01, -60.99),   # Castries
    "LIE": (47.14, 9.52),     # Vaduz
    "MCO": (43.74, 7.42),     # Monaco
    "MDV": (4.18, 73.51),     # Malé
    "MHL": (7.09, 171.38),    # Majuro
    "MLT": (35.90, 14.51),    # Valletta
    "MUS": (-20.16, 57.50),   # Port Louis
    "NRO": (-0.55, 166.92),   # Yaren
    "PLW": (7.50, 134.62),    # Ngerulmud
    "SGP": (1.29, 103.85),    # Singapore
    "SMR": (43.94, 12.46),    # San Marino
    "STP": (0.34, 6.73),      # São Tomé
    "SYC": (-4.62, 55.45),    # Victoria
    "TON": (-21.14, -175.20), # Nuku'alofa
    "TUV": (-8.52, 179.20),   # Funafuti
    "VAT": (41.90, 12.45),    # Vatican City
    "VCT": (13.16, -61.22),   # Kingstown
    "WSM": (-13.85, -171.75), # Apia
}

# Spanish names of M49 regions and sub-regions (UNSD Spanish version).
REGION_ES = {
    "Africa": "África",
    "Americas": "Américas",
    "Asia": "Asia",
    "Europe": "Europa",
    "Oceania": "Oceanía",
}
SUBREGION_ES = {
    "Northern Africa": "África septentrional",
    "Sub-Saharan Africa": "África subsahariana",
    "Latin America and the Caribbean": "América Latina y el Caribe",
    "Northern America": "América septentrional",
    "Central Asia": "Asia central",
    "Eastern Asia": "Asia oriental",
    "South-eastern Asia": "Asia sudoriental",
    "Southern Asia": "Asia meridional",
    "Western Asia": "Asia occidental",
    "Eastern Europe": "Europa oriental",
    "Northern Europe": "Europa septentrional",
    "Southern Europe": "Europa meridional",
    "Western Europe": "Europa occidental",
    "Australia and New Zealand": "Australia y Nueva Zelandia",
    "Melanesia": "Melanesia",
    "Micronesia": "Micronesia",
    "Polynesia": "Polinesia",
}

# Names used by an entity filed under a code, by General Debate year
# (inclusive). Outside these ranges the countries.csv name applies.
HISTORICAL = [
    ("BEN", 1960, 1975, "Dahomey", "Dahomey"),
    ("BFA", 1960, 1983, "Upper Volta", "Alto Volta"),
    ("BLR", 1946, 1990, "Byelorussian SSR", "RSS de Bielorrusia"),
    ("CAF", 1977, 1978, "Central African Empire", "Imperio Centroafricano"),
    ("CHN", 1946, 1971, "Republic of China", "República de China"),
    ("COD", 1960, 1963, "Congo (Léopoldville)", "Congo (Léopoldville)"),
    ("COD", 1972, 1996, "Zaire", "Zaire"),
    ("CSK", 1946, 1992, "Czechoslovakia", "Checoslovaquia"),
    ("DDR", 1973, 1990, "East Germany (GDR)", "Alemania Oriental (RDA)"),
    ("DEU", 1973, 1990, "West Germany (FRG)", "Alemania Occidental (RFA)"),
    ("EGY", 1958, 1970, "United Arab Republic", "República Árabe Unida"),
    ("KHM", 1971, 1974, "Khmer Republic", "República Jemer"),
    ("KHM", 1976, 1989, "Democratic Kampuchea", "Kampuchea Democrática"),
    ("LKA", 1955, 1971, "Ceylon", "Ceilán"),
    ("MKD", 1993, 2018, "Macedonia (FYROM)", "Macedonia (ERYM)"),
    ("MMR", 1948, 1988, "Burma", "Birmania"),
    ("MYS", 1957, 1962, "Malaya", "Malaya"),
    ("NRO", 2000, 2025, "Nauru", "Nauru"),
    ("RUS", 1946, 1991, "USSR", "URSS"),
    ("SWZ", 1968, 2017, "Swaziland", "Suazilandia"),
    ("THA", 1946, 1948, "Siam", "Siam"),
    ("TZA", 1961, 1963, "Tanganyika", "Tanganica"),
    ("UKR", 1946, 1990, "Ukrainian SSR", "RSS de Ucrania"),
    ("WSM", 1976, 1996, "Western Samoa", "Samoa Occidental"),
    ("YEM", 1947, 1989, "North Yemen", "Yemen del Norte"),
    ("YMD", 1967, 1989, "South Yemen", "Yemen del Sur"),
    ("YUG", 1946, 1962, "Yugoslavia (FPRY)", "Yugoslavia (RFPY)"),
    ("YUG", 1963, 1991, "Yugoslavia (SFRY)", "Yugoslavia (RFSY)"),
    ("YUG", 2000, 2002, "Yugoslavia (FRY)", "Yugoslavia (RFY)"),
    ("YUG", 2003, 2005, "Serbia and Montenegro", "Serbia y Montenegro"),
]

# Groups with a fixed, current composition applied to all years. Region
# groups list M49 regions or sub-regions instead of members.
GROUP_DEFS = [
    ("ROCOL", "office", "Región Andina y Cono Sur (ROCOL)",
     "Andean Region and Southern Cone (ROCOL)",
     {"members": "ARG BOL CHL COL ECU PRY PER URY"}),
    ("ALC", "region", "América Latina y el Caribe",
     "Latin America and the Caribbean",
     {"subregions": ["Latin America and the Caribbean"]}),
    ("UE", "bloc", "Unión Europea (UE-27)", "European Union (EU-27)",
     {"members": "AUT BEL BGR HRV CYP CZE DNK EST FIN FRA DEU GRC HUN IRL "
                 "ITA LVA LTU LUX MLT NLD POL PRT ROU SVK SVN ESP SWE"}),
    ("BRICS", "bloc", "BRICS", "BRICS",
     {"members": "BRA RUS IND CHN ZAF EGY ETH IRN ARE IDN"}),
    ("G7", "bloc", "G7", "G7",
     {"members": "CAN FRA DEU ITA JPN GBR USA"}),
    ("AFR", "region", "África", "Africa", {"regions": ["Africa"]}),
    ("ASP", "region", "Asia-Pacífico", "Asia-Pacific",
     {"regions": ["Asia", "Oceania"]}),
]


def corpus_codes():
    """Country codes of the corpus file names, under their current code (CODE_RENAMES)."""
    return {
        CODE_RENAMES.get(match.group(1), match.group(1))
        for path in CORPUS_TXT.glob("*/*.txt")
        if (match := SPEECH_FILE.match(path.name))
    }


def atlas_features():
    """(id, name) of each world-atlas country feature; id is None for some."""
    atlas = json.loads(WORLD_ATLAS.read_text(encoding="utf-8"))
    return [(g.get("id"), g["properties"]["name"])
            for g in atlas["objects"]["countries"]["geometries"]]


def atlas_ids():
    """Feature ids (ISO 3166 numeric strings) in the world-atlas geometry."""
    return {id_ for id_, _ in atlas_features() if id_}


def build_countries(codes):
    with open(M49_SOURCE, encoding="utf-8", newline="") as f:
        m49 = {row["alpha-3"]: row for row in csv.DictReader(f)}
    spanish = gettext.translation("iso3166-1", pycountry.LOCALES_DIR, languages=["es"])
    map_ids = atlas_ids()
    source_code = {new: old for old, new in CODE_RENAMES.items()}  # the code pycountry and M49 still use

    rows = []
    for code in sorted(codes | UN_MEMBERS):
        if code in NON_ISO_ENTITIES:
            name_en, name_es, region, subregion = NON_ISO_ENTITIES[code]
            historic = pycountry.historic_countries.get(alpha_3=code)
            iso_numeric = historic.numeric if historic else ""
            map_numeric = ""
        else:
            source = source_code.get(code, code)
            country = pycountry.countries.get(alpha_3=source)
            short = getattr(country, "common_name", None) or country.name
            name_en = NAME_EN.get(code, short)
            name_es = NAME_ES.get(code, spanish.gettext(short))
            region = m49[source]["region"]
            subregion = m49[source]["sub-region"]
            iso_numeric = m49[source]["country-code"]
            map_numeric = iso_numeric if iso_numeric in map_ids else ""
        lat, lon = MAP_POINTS.get(code, ("", ""))
        rows.append({
            "iso3": code,
            "name_en": name_en,
            "name_es": name_es,
            "iso_numeric": iso_numeric,
            "map_iso_numeric": map_numeric,
            "map_extra_features": MAP_EXTRA_FEATURES.get(code, ""),
            "point_lat": lat,
            "point_lon": lon,
            "m49_region_en": region,
            "m49_region_es": REGION_ES.get(region, ""),
            "m49_subregion_en": subregion,
            "m49_subregion_es": SUBREGION_ES.get(subregion, ""),
            "un_member": str(code in UN_MEMBERS).lower(),
            "is_observer": str(code in OBSERVERS).lower(),
        })
    return rows


def build_historical():
    return [dict(zip(HISTORICAL_FIELDS, row)) for row in HISTORICAL]


def build_groups(countries):
    rows = []
    for group_id, group_type, name_es, name_en, rule in GROUP_DEFS:
        if "members" in rule:
            members = rule["members"].split()
        else:
            members = [
                c["iso3"] for c in countries
                if c["m49_region_en"] in rule.get("regions", [])
                or c["m49_subregion_en"] in rule.get("subregions", [])
            ]
        for code in sorted(members):
            rows.append({"group_id": group_id, "group_type": group_type,
                         "name_es": name_es, "name_en": name_en, "iso3": code})
    return rows


def build():
    """All tables as {path: (fields, rows)}."""
    countries = build_countries(corpus_codes())
    return {
        COUNTRIES: (COUNTRY_FIELDS, countries),
        HISTORICAL_NAMES: (HISTORICAL_FIELDS, build_historical()),
        GROUPS: (GROUP_FIELDS, build_groups(countries)),
    }


def write_csv(path, fields, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    for path, (fields, rows) in build().items():
        write_csv(path, fields, rows)
        print(f"{path.relative_to(META.parent.parent)}: {len(rows)} rows")


if __name__ == "__main__":
    main()
