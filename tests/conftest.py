import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bot.demo import synthetic  # noqa: E402


@pytest.fixture
def cfg():
    """config.yaml com os parâmetros que os testes de unidade assumem (dados sintéticos em 1h/4h)."""
    c = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    c["timeframes"] = {"entry": "1h", "trend": "4h"}
    c["risk"].update({"exit_mode": "parcial", "trend_exit": True, "min_reward_risk": 1.5})
    c["strategy"]["btc_filter"] = False
    return c


@pytest.fixture
def synth():
    return lambda n, tf, drift, seed=1, start=100.0: synthetic(n, tf, drift, seed, start, 1_600_000_000_000)
