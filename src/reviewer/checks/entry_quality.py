"""Entry Quality & Timing Critique — behavioral check for execution quality.

Evaluates execution quality at the moment of entry per ENTRY_QUALITY.md.
Does NOT predict direction — answers whether the entry was at value or
extension, whether momentum was expanding or exhausting, and whether
the entry was likely disciplined or emotional.

Sub-checks:
  EQ000: Composite entry quality score + classification
  EQ001: VWAP Extension penalty
  EQ002: Value Area check (inside/outside)
  EQ003: Moving Average Distance penalty
  EQ004: Breakout Extension penalty
  EQ005: Momentum Exhaustion penalty
  EQ006: Volume Climax penalty
  EQ007: Divergence penalty
  EQ008: Volatility Decay penalty

All sub-checks use check_type="entry_quality", check_phase="at_entry".
"""

import logging
from typing import Any, Optional

from src.reviewer.checks.base import BaseChecker, CheckResult
from src.trade.intent import TradeIntent

logger = logging.getLogger(__name__)

CHECK_TYPE = "entry_quality"
CHECK_PHASE = "at_entry"

# Score boundaries for classification
_CLASSIFICATIONS = [
    (80, "High-Quality Timing"),
    (60, "Acceptable Entry"),
    (40, "Late / Extended"),
    (0, "Emotional / FOMO"),
]


def _classify(score: float) -> str:
    """Map a 0-100 score to a human-readable label."""
    for threshold, label in _CLASSIFICATIONS:
        if score >= threshold:
            return label
    return "Emotional / FOMO"


def _severity_for_score(score: float) -> str:
    """Determine severity based on composite score."""
    if score >= 80:
        return "info"
    if score >= 60:
        return "info"
    if score >= 40:
        return "warn"
    return "critical"


class EntryQualityChecker(BaseChecker):
    """Evaluates execution quality at trade entry.

    Requires indicator_snapshot and optionally baseline_stats
    passed via **kwargs from CheckRunner.
    """

    CHECK_NAME = "entry_quality"

    def run(
        self,
        fill: Any,
        intent: Optional[TradeIntent],
        atr: Optional[float],
        account_balance: Optional[float],
        **kwargs,
    ) -> list[CheckResult]:
        """Run all entry quality sub-checks.

        Args:
            fill: TradeFill model instance
            intent: TradeIntent domain object (may be None)
            atr: ATR value for the symbol/timeframe
            account_balance: Trader's account balance
            **kwargs:
                indicator_snapshot: dict of indicator values at entry bar
                baseline_stats: dict of trader baseline stats (optional)

        Returns:
            List of CheckResult (one per sub-check + composite EQ000)
        """
        snapshot = kwargs.get("indicator_snapshot")
        if not snapshot:
            logger.debug(
                "No indicator_snapshot for fill_id=%s, skipping entry quality checks",
                getattr(fill, "id", "?"),
            )
            return []

        entry_price = getattr(fill, "price", None)
        if entry_price is None:
            logger.debug("No price on fill, skipping entry quality checks")
            return []

        results: list[CheckResult] = []
        penalties: dict[str, float] = {}
        flags: dict[str, bool] = {}

        # Run each sub-check and collect penalties
        results.append(self._check_vwap_extension(entry_price, snapshot, atr, penalties, flags))
        results.append(self._check_value_area(entry_price, snapshot, flags))
        results.append(self._check_ma_distance(entry_price, snapshot, atr, penalties, flags))
        results.append(self._check_breakout_extension(entry_price, snapshot, atr, penalties, flags))
        results.append(self._check_momentum_exhaustion(snapshot, penalties, flags))
        results.append(self._check_volume_climax(snapshot, penalties, flags))
        results.append(self._check_divergence(snapshot, penalties, flags))
        results.append(self._check_volatility_decay(snapshot, penalties, flags))

        # Compute composite score
        total_penalty = sum(penalties.values())
        score = max(0.0, min(100.0, 100.0 - total_penalty))
        label = _classify(score)
        severity = _severity_for_score(score)

        composite_details = {
            "entry_quality_score": round(score, 1),
            "label": label,
            "flags": flags,
            "penalties": {k: round(v, 2) for k, v in penalties.items()},
            "total_penalty": round(total_penalty, 2),
            "indicators_used": {
                k: round(v, 4) if isinstance(v, float) else v
                for k, v in snapshot.items()
                if k in (
                    "vwap", "sma_20", "sma_200", "atr_14", "rsi_14",
                    "stoch_k", "macd_hist", "rv_15", "rv_60",
                    "volume_sma_20", "breakout_20", "dist_vwap_60",
                )
            },
        }

        passed = score >= 60
        nudge = f"Entry quality: {score:.0f}/100 — {label}."
        if not passed:
            nudge += " Consider waiting for better entry conditions."

        composite = CheckResult(
            check_type=CHECK_TYPE,
            code="EQ000",
            severity=severity,
            passed=passed,
            nudge_text=nudge,
            check_phase=CHECK_PHASE,
            details=composite_details,
        )
        results.insert(0, composite)

        logger.info(
            "Entry quality checks complete for fill_id=%s: score=%.1f label='%s' (%d sub-checks)",
            getattr(fill, "id", "?"), score, label, len(results) - 1,
        )
        return results

    # ------------------------------------------------------------------
    # EQ001 — VWAP Extension
    # ------------------------------------------------------------------

    def _check_vwap_extension(
        self,
        entry_price: float,
        snapshot: dict,
        atr: Optional[float],
        penalties: dict,
        flags: dict,
    ) -> CheckResult:
        """Penalty = abs(dist_vwap) * 20."""
        vwap = snapshot.get("vwap")
        effective_atr = atr or snapshot.get("atr_14")

        if vwap is None or effective_atr is None or effective_atr <= 0:
            flags["extended_from_vwap"] = False
            return CheckResult(
                check_type=CHECK_TYPE, code="EQ001", severity="info",
                passed=True, check_phase=CHECK_PHASE,
                nudge_text="VWAP extension check skipped (missing data).",
                details={"reason": "missing_data"},
            )

        dist_vwap = (entry_price - vwap) / effective_atr
        penalty = abs(dist_vwap) * 20
        penalties["vwap_extension"] = penalty

        extended = abs(dist_vwap) > 0.5
        flags["extended_from_vwap"] = extended

        if not extended:
            return CheckResult(
                check_type=CHECK_TYPE, code="EQ001", severity="info",
                passed=True, check_phase=CHECK_PHASE,
                nudge_text=f"Entry is {dist_vwap:.2f} ATR from VWAP — within normal range.",
                details={"dist_vwap": round(dist_vwap, 4), "penalty": round(penalty, 2)},
            )

        return CheckResult(
            check_type=CHECK_TYPE, code="EQ001", severity="warn",
            passed=False, check_phase=CHECK_PHASE,
            nudge_text=f"Entry is {abs(dist_vwap):.2f} ATR away from VWAP — extended.",
            details={"dist_vwap": round(dist_vwap, 4), "penalty": round(penalty, 2)},
        )

    # ------------------------------------------------------------------
    # EQ002 — Value Area
    # ------------------------------------------------------------------

    def _check_value_area(
        self,
        entry_price: float,
        snapshot: dict,
        flags: dict,
    ) -> CheckResult:
        """inside_value = abs(entry - vwap) <= vwap_std."""
        vwap = snapshot.get("vwap")
        vwap_std = snapshot.get("stddev_20")  # use 20-bar price stddev as proxy

        if vwap is None or vwap_std is None or vwap_std <= 0:
            flags["inside_value"] = False
            return CheckResult(
                check_type=CHECK_TYPE, code="EQ002", severity="info",
                passed=True, check_phase=CHECK_PHASE,
                nudge_text="Value area check skipped (missing VWAP std data).",
                details={"reason": "missing_data"},
            )

        inside = abs(entry_price - vwap) <= vwap_std
        flags["inside_value"] = inside

        if inside:
            return CheckResult(
                check_type=CHECK_TYPE, code="EQ002", severity="info",
                passed=True, check_phase=CHECK_PHASE,
                nudge_text="Entry is inside the value area (within 1 std of VWAP).",
                details={"distance_from_vwap": round(abs(entry_price - vwap), 4), "vwap_std": round(vwap_std, 4)},
            )

        return CheckResult(
            check_type=CHECK_TYPE, code="EQ002", severity="info",
            passed=False, check_phase=CHECK_PHASE,
            nudge_text="Entry is outside the value area — above 1 std from VWAP.",
            details={"distance_from_vwap": round(abs(entry_price - vwap), 4), "vwap_std": round(vwap_std, 4)},
        )

    # ------------------------------------------------------------------
    # EQ003 — MA Distance
    # ------------------------------------------------------------------

    def _check_ma_distance(
        self,
        entry_price: float,
        snapshot: dict,
        atr: Optional[float],
        penalties: dict,
        flags: dict,
    ) -> CheckResult:
        """penalty = max(0, abs(dist_ma20) - 1.5) * 10."""
        sma_20 = snapshot.get("sma_20")
        effective_atr = atr or snapshot.get("atr_14")

        if sma_20 is None or effective_atr is None or effective_atr <= 0:
            flags["stretched_from_ma"] = False
            return CheckResult(
                check_type=CHECK_TYPE, code="EQ003", severity="info",
                passed=True, check_phase=CHECK_PHASE,
                nudge_text="MA distance check skipped (missing data).",
                details={"reason": "missing_data"},
            )

        dist_ma20 = (entry_price - sma_20) / effective_atr
        penalty = max(0, abs(dist_ma20) - 1.5) * 10
        penalties["ma_distance"] = penalty

        stretched = abs(dist_ma20) > 1.5
        flags["stretched_from_ma"] = stretched

        if not stretched:
            return CheckResult(
                check_type=CHECK_TYPE, code="EQ003", severity="info",
                passed=True, check_phase=CHECK_PHASE,
                nudge_text=f"Entry is {dist_ma20:.2f} ATR from SMA20 — within range.",
                details={"dist_ma20": round(dist_ma20, 4), "penalty": round(penalty, 2)},
            )

        return CheckResult(
            check_type=CHECK_TYPE, code="EQ003", severity="warn",
            passed=False, check_phase=CHECK_PHASE,
            nudge_text=f"Entry is {abs(dist_ma20):.2f} ATR from SMA20 — stretched.",
            details={"dist_ma20": round(dist_ma20, 4), "penalty": round(penalty, 2)},
        )

    # ------------------------------------------------------------------
    # EQ004 — Breakout Extension
    # ------------------------------------------------------------------

    def _check_breakout_extension(
        self,
        entry_price: float,
        snapshot: dict,
        atr: Optional[float],
        penalties: dict,
        flags: dict,
    ) -> CheckResult:
        """penalty = max(0, breakout_extension - 0.5) * 15."""
        breakout_level = snapshot.get("donchian_high_20")
        effective_atr = atr or snapshot.get("atr_14")

        if breakout_level is None or effective_atr is None or effective_atr <= 0:
            flags["late_breakout"] = False
            return CheckResult(
                check_type=CHECK_TYPE, code="EQ004", severity="info",
                passed=True, check_phase=CHECK_PHASE,
                nudge_text="Breakout extension check skipped (missing data).",
                details={"reason": "missing_data"},
            )

        breakout_ext = (entry_price - breakout_level) / effective_atr
        penalty = max(0, breakout_ext - 0.5) * 15
        penalties["breakout_extension"] = penalty

        late = breakout_ext > 0.5
        flags["late_breakout"] = late

        if not late:
            return CheckResult(
                check_type=CHECK_TYPE, code="EQ004", severity="info",
                passed=True, check_phase=CHECK_PHASE,
                nudge_text=f"Breakout extension {breakout_ext:.2f} ATR — early/timely.",
                details={"breakout_extension": round(breakout_ext, 4), "penalty": round(penalty, 2)},
            )

        return CheckResult(
            check_type=CHECK_TYPE, code="EQ004", severity="warn",
            passed=False, check_phase=CHECK_PHASE,
            nudge_text=f"Breakout extension {breakout_ext:.2f} ATR — late entry.",
            details={"breakout_extension": round(breakout_ext, 4), "penalty": round(penalty, 2)},
        )

    # ------------------------------------------------------------------
    # EQ005 — Momentum Exhaustion
    # ------------------------------------------------------------------

    def _check_momentum_exhaustion(
        self,
        snapshot: dict,
        penalties: dict,
        flags: dict,
    ) -> CheckResult:
        """exhaustion count * 10. Triggers: RSI>75, stoch_k>85, MACD declining."""
        exhaustion = 0
        triggers = []

        rsi = snapshot.get("rsi_14")
        if rsi is not None and rsi > 75:
            exhaustion += 1
            triggers.append(f"RSI={rsi:.1f}>75")

        stoch_k = snapshot.get("stoch_k")
        if stoch_k is not None and stoch_k > 85:
            exhaustion += 1
            triggers.append(f"StochK={stoch_k:.1f}>85")

        macd_hist = snapshot.get("macd_hist")
        macd_hist_prev = snapshot.get("macd_hist_prev")
        if macd_hist is not None and macd_hist_prev is not None:
            if macd_hist < macd_hist_prev:
                exhaustion += 1
                triggers.append("MACD declining")

        penalty = exhaustion * 10
        penalties["momentum_exhaustion"] = penalty

        exhausted = exhaustion >= 2
        flags["momentum_exhaustion"] = exhausted

        if not exhausted:
            return CheckResult(
                check_type=CHECK_TYPE, code="EQ005", severity="info",
                passed=True, check_phase=CHECK_PHASE,
                nudge_text="Momentum is not exhausted.",
                details={"exhaustion_count": exhaustion, "triggers": triggers, "penalty": penalty},
            )

        return CheckResult(
            check_type=CHECK_TYPE, code="EQ005", severity="warn",
            passed=False, check_phase=CHECK_PHASE,
            nudge_text=f"Momentum exhaustion detected ({', '.join(triggers)}).",
            details={"exhaustion_count": exhaustion, "triggers": triggers, "penalty": penalty},
        )

    # ------------------------------------------------------------------
    # EQ006 — Volume Climax
    # ------------------------------------------------------------------

    def _check_volume_climax(
        self,
        snapshot: dict,
        penalties: dict,
        flags: dict,
    ) -> CheckResult:
        """rel_vol > 2.5 → 10 penalty."""
        volume = snapshot.get("volume")
        avg_volume = snapshot.get("volume_sma_20")

        if volume is None or avg_volume is None or avg_volume <= 0:
            flags["volume_climax"] = False
            return CheckResult(
                check_type=CHECK_TYPE, code="EQ006", severity="info",
                passed=True, check_phase=CHECK_PHASE,
                nudge_text="Volume climax check skipped (missing data).",
                details={"reason": "missing_data"},
            )

        rel_vol = volume / avg_volume
        climax = rel_vol > 2.5
        penalty = 10.0 if climax else 0.0
        penalties["volume_climax"] = penalty

        flags["volume_climax"] = climax

        if not climax:
            return CheckResult(
                check_type=CHECK_TYPE, code="EQ006", severity="info",
                passed=True, check_phase=CHECK_PHASE,
                nudge_text=f"Relative volume {rel_vol:.1f}x — normal.",
                details={"rel_vol": round(rel_vol, 2), "penalty": penalty},
            )

        return CheckResult(
            check_type=CHECK_TYPE, code="EQ006", severity="warn",
            passed=False, check_phase=CHECK_PHASE,
            nudge_text=f"Volume climax: {rel_vol:.1f}x average — potential blow-off.",
            details={"rel_vol": round(rel_vol, 2), "penalty": penalty},
        )

    # ------------------------------------------------------------------
    # EQ007 — Divergence
    # ------------------------------------------------------------------

    def _check_divergence(
        self,
        snapshot: dict,
        penalties: dict,
        flags: dict,
    ) -> CheckResult:
        """Price higher high + RSI lower high → 20 penalty."""
        price_hh = snapshot.get("price_higher_high")
        rsi_lh = snapshot.get("rsi_lower_high")

        if price_hh is None or rsi_lh is None:
            flags["bearish_divergence"] = False
            return CheckResult(
                check_type=CHECK_TYPE, code="EQ007", severity="info",
                passed=True, check_phase=CHECK_PHASE,
                nudge_text="Divergence check skipped (missing data).",
                details={"reason": "missing_data"},
            )

        divergent = bool(price_hh) and bool(rsi_lh)
        penalty = 20.0 if divergent else 0.0
        penalties["divergence"] = penalty

        flags["bearish_divergence"] = divergent

        if not divergent:
            return CheckResult(
                check_type=CHECK_TYPE, code="EQ007", severity="info",
                passed=True, check_phase=CHECK_PHASE,
                nudge_text="No bearish divergence detected.",
                details={"penalty": penalty},
            )

        return CheckResult(
            check_type=CHECK_TYPE, code="EQ007", severity="critical",
            passed=False, check_phase=CHECK_PHASE,
            nudge_text="Bearish divergence: price making higher high but RSI making lower high.",
            details={"penalty": penalty},
        )

    # ------------------------------------------------------------------
    # EQ008 — Volatility Decay
    # ------------------------------------------------------------------

    def _check_volatility_decay(
        self,
        snapshot: dict,
        penalties: dict,
        flags: dict,
    ) -> CheckResult:
        """rv_15 < rv_60 * 0.6 → 15 penalty."""
        rv_15 = snapshot.get("rv_15")
        rv_60 = snapshot.get("rv_60")

        if rv_15 is None or rv_60 is None or rv_60 <= 0:
            flags["volatility_decay"] = False
            return CheckResult(
                check_type=CHECK_TYPE, code="EQ008", severity="info",
                passed=True, check_phase=CHECK_PHASE,
                nudge_text="Volatility decay check skipped (missing data).",
                details={"reason": "missing_data"},
            )

        decaying = rv_15 < rv_60 * 0.6
        penalty = 15.0 if decaying else 0.0
        penalties["volatility_decay"] = penalty

        flags["volatility_decay"] = decaying

        if not decaying:
            return CheckResult(
                check_type=CHECK_TYPE, code="EQ008", severity="info",
                passed=True, check_phase=CHECK_PHASE,
                nudge_text=f"Volatility stable: rv_15={rv_15:.4f} vs rv_60={rv_60:.4f}.",
                details={"rv_15": round(rv_15, 6), "rv_60": round(rv_60, 6), "penalty": penalty},
            )

        return CheckResult(
            check_type=CHECK_TYPE, code="EQ008", severity="warn",
            passed=False, check_phase=CHECK_PHASE,
            nudge_text=f"Volatility decaying: rv_15={rv_15:.4f} is < 60% of rv_60={rv_60:.4f}.",
            details={"rv_15": round(rv_15, 6), "rv_60": round(rv_60, 6), "penalty": penalty},
        )
