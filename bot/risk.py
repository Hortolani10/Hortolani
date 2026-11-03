"""Gestão de risco: tamanho de posição e travas de proteção do capital."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


def position_size(equity: float, entry: float, stop: float, cfg: dict) -> float:
    """Quantidade a comprar para que, se o stop for atingido, a perda seja
    ~risk_per_trade do capital (incluindo taxas), limitada a max_position_pct."""
    r, f = cfg["risk"], cfg["fees"]
    per_unit_loss = (entry - stop) + entry * (f["taker"] * 2 + f["slippage"])
    if per_unit_loss <= 0 or entry <= 0:
        return 0.0
    qty_risk = equity * r["risk_per_trade"] / per_unit_loss
    qty_cap = equity * r["max_position_pct"] / entry
    return max(0.0, min(qty_risk, qty_cap))


@dataclass
class RiskGuard:
    """Travas: perda diária máxima e pausa após sequência de stops."""
    cfg: dict
    day: str = ""
    day_start_equity: float = 0.0
    consecutive_losses: int = 0
    paused_until: str | None = None
    history: list = field(default_factory=list)

    def new_bar(self, now: datetime, equity: float) -> None:
        d = now.strftime("%Y-%m-%d")
        if d != self.day:
            self.day, self.day_start_equity = d, equity

    def register_close(self, pnl: float, now: datetime) -> None:
        self.history.append(pnl)
        if pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.cfg["risk"]["max_consecutive_losses"]:
                until = now + timedelta(hours=self.cfg["risk"]["cooldown_hours"])
                self.paused_until = until.isoformat()
                self.consecutive_losses = 0
        else:
            self.consecutive_losses = 0

    def can_open(self, now: datetime, equity: float) -> tuple[bool, str]:
        if self.paused_until:
            until = datetime.fromisoformat(self.paused_until)
            if now < until:
                return False, f"pausado após sequência de stops até {until:%Y-%m-%d %H:%M}"
            self.paused_until = None
        if self.day_start_equity > 0:
            dd = 1 - equity / self.day_start_equity
            if dd >= self.cfg["risk"]["max_daily_loss"]:
                return False, f"perda diária de {dd:.2%} atingiu o limite"
        return True, ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k not in ("cfg", "history")}

    def load(self, d: dict) -> None:
        for k, v in d.items():
            setattr(self, k, v)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
