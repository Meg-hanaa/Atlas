"""Pytest configuration."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Disable JWT auth in API tests; use fixed test user UUID.
os.environ.setdefault("ATLAS_AUTH_DISABLED", "1")

TEST_USER_ID = "00000000-0000-0000-0000-000000000001"
