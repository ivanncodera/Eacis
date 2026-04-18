"""Pytest configuration helpers for local test runs.

Ensure the repository root is on sys.path so tests importing the package
`eacis` work when pytest runs from different CWDs.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
