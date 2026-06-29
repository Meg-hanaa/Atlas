"""Tests for dedup/merge before retain."""

import sqlite3

import pytest

from config import DB_PATH
from memory.dedup import _connect, prepare_chunk_for_retain
from tests.conftest import TEST_USER_ID

UID = TEST_USER_ID


@pytest.fixture(autouse=True)
def clean_chunk_index():
    _connect()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM chunk_index")
    conn.commit()
    conn.close()
    yield


def test_first_chunk_is_retain():
    chunk = {
        "subject": "ml-notes",
        "source": "youtube:a",
        "content": "Neural networks learn hierarchical representations.",
    }
    _, action = prepare_chunk_for_retain(chunk, UID)
    assert action == "retain"


def test_similar_chunk_merges_sources():
    c1 = {
        "subject": "ml-notes",
        "source": "youtube:a",
        "content": "Convolutional neural networks use filters to detect spatial features in images.",
    }
    c2 = {
        "subject": "ml-notes",
        "source": "pdf:b",
        "content": "CNNs apply convolutional filters to find spatial patterns in image data.",
    }
    prepare_chunk_for_retain(c1, UID)
    merged, action = prepare_chunk_for_retain(c2, UID)
    assert action == "merge"
    assert "youtube:a" in merged["merged_sources"]
    assert "pdf:b" in merged["merged_sources"]


def test_unrelated_chunk_stays_retain():
    prepare_chunk_for_retain(
        {
            "subject": "ml-notes",
            "source": "youtube:a",
            "content": "Convolutional neural networks use filters.",
        },
        UID,
    )
    _, action = prepare_chunk_for_retain(
        {
            "subject": "ml-notes",
            "source": "photo:c",
            "content": "Gradient descent iteratively minimizes the loss.",
        },
        UID,
    )
    assert action == "retain"
