"""
Shared pytest setup.

Some tests use the sample files by name (for example "rubric.json"),
the same way you would on the command line from this folder. This makes
those tests work no matter which folder you run pytest from.
"""

import os
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent


@pytest.fixture(scope="session", autouse=True)
def run_from_backend_folder():
    previous = Path.cwd()
    os.chdir(BACKEND_DIR)
    yield
    os.chdir(previous)
