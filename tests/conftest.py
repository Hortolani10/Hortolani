import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def cfg():
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def synthetic(n: int, tf_ms: int, drift: float, seed: int = 1, start: float = 100.0) -> pd.DataFrame:
    """Passeio aleatório com tendência + ondas (gera pullbacks)."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    rets = drift + 0.004 * np.sin(t / 9) + rng.normal(0, 0.006, n)
    close = start * np.exp(np.cumsum(rets))
    open_ = np.r_[start, close[:-1]]
    spread = np.abs(rng.normal(0, 0.004, n)) * close
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    vol = rng.uniform(50, 150, n) * (1 + 2 * (close > open_))
    ts = 1_600_000_000_000 + t * tf_ms
    return pd.DataFrame({"ts": ts, "open": open_, "high": high, "low": low, "close": close, "volume": vol})


@pytest.fixture
def synth():
    return synthetic
