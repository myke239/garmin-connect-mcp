"""Keep test scratch in the checkout, including on a clean CI checkout."""
from pathlib import Path


def pytest_configure(config):
    if config.option.basetemp == "work/pytest-tmp":
        destination=Path(__file__).resolve().parents[1]/"work"/"pytest-tmp"
        destination.parent.mkdir(parents=True,exist_ok=True)
        config.option.basetemp=str(destination)
