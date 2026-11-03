import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bot.demo import synthetic  # noqa: E402


@pytest.fixture
def cfg():
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


@pytest.fixture
def synth():
    return lambda n, tf, drift, seed=1, start=100.0: synthetic(n, tf, drift, seed, start, 1_600_000_000_000)
