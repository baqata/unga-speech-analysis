"""Shared paths and constants for the pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Sources (read-only)
CORPUS_TXT = ROOT / "dataverse_files" / "TXT"
SPEAKERS_XLSX = ROOT / "dataverse_files" / "Speakers_by_session.xlsx"
PROVISIONAL = ROOT / "data" / "provisional"
# Sessions split from the UN verbatim records by pipeline.records; each replaces the corpus folder of that session.
OFFICIAL = ROOT / "data" / "official"
AUDIO = ROOT / "data" / "audio"

# Committed reference data
META = ROOT / "data" / "meta"
COUNTRIES = META / "countries.csv"  # written by pipeline.meta
HISTORICAL_NAMES = META / "historical_names.csv"  # written by pipeline.meta
GROUPS = META / "groups.csv"  # written by pipeline.meta
# Countries filed under a newer code than the source files use. Nauru restored its name Naoero at the
# 81st session (2026) and its code changed from NRU to NRO; file names and speech ids keep the source code.
CODE_RENAMES = {"NRU": "NRO"}
LENSES = ROOT / "data" / "lenses"
GOLD = ROOT / "data" / "gold"

# Generated, not committed
INTERIM = ROOT / "data" / "interim"
FRAGMENTS = INTERIM / "fragments.parquet"
SPEECHES = INTERIM / "speeches.parquet"
QC = INTERIM / "qc"
LOGS = INTERIM / "logs"

# Embeddings
MODEL_ID = "microsoft/harrier-oss-v1-0.6b"
MODEL_SLUG = "harrier-oss-v1-0.6b"
EMB_DIR = INTERIM / "emb" / MODEL_SLUG

# Static site (GitHub Pages)
SITE = ROOT / "site"
SITE_DATA = SITE / "data"
