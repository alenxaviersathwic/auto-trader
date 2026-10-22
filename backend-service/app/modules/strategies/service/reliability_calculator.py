from decimal import Decimal
from typing import List, Optional


class ReliabilityCalculator:
    """Computes reliability flags for strategy performance snapshots."""

    DRAWDOWN_PLACEHOLDERS = {Decimal("450.00"), Decimal("450.0"), Decimal("450")}

    def compute_flags(
        self,
        total_trades: int,
        win_rate_pct: Decimal,
        net_pnl: Decimal,
        profit_factor: Decimal,
        max_drawdown: Decimal,
        min_trades: int = 30,
    ) -> List[str]:
        flags: List[str] = []

        # 1. LOW_SAMPLE
        if total_trades < min_trades:
            flags.append("LOW_SAMPLE")

        # 2. PERFECT_RECORD_TINY_SAMPLE
        if Decimal(win_rate_pct) >= Decimal("99.99") and total_trades < 5:
            flags.append("PERFECT_RECORD_TINY_SAMPLE")

        # 3. PF_PNL_INCONSISTENT
        # profit factor below 1.0 with positive PnL OR profit factor above 1.0 with negative PnL
        pf = Decimal(profit_factor)
        pnl = Decimal(net_pnl)
        if (pf < Decimal("1.0") and pnl > Decimal("0.0")) or (pf > Decimal("1.0") and pnl < Decimal("0.0")):
            flags.append("PF_PNL_INCONSISTENT")

        # 4. DRAWDOWN_PLACEHOLDER
        dd = Decimal(max_drawdown)
        if any(abs(dd - p) < Decimal("0.01") for p in self.DRAWDOWN_PLACEHOLDERS):
            flags.append("DRAWDOWN_PLACEHOLDER")

        return flags
