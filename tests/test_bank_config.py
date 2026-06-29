"""Tests for bank config and reflect prompt."""

from memory.bank import CONSOLIDATED_QUERY
from memory.bank_config import get_bank_config


def test_ml_subject_has_custom_mission():
    cfg = get_bank_config("ml-notes")
    assert "worked examples" in cfg["mission"].lower()
    assert cfg["disposition"]["empathy"] == 4


def test_unknown_subject_uses_default():
    cfg = get_bank_config("sql-notes")
    assert "learning notebook" in cfg["mission"].lower()


def test_consolidated_query_mentions_merged_sources():
    assert "comma-separated" in CONSOLIDATED_QUERY or "merged" in CONSOLIDATED_QUERY.lower()
