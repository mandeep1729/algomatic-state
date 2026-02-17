"""Seed default App User and benchmark strategies.

Inserts:
- App user account (external_user_id='app') as system/template owner
- 6 benchmark trading strategies owned by the app user

Uses ON CONFLICT DO NOTHING for idempotency.

Revision ID: 031
Revises: 030
Create Date: 2026-02-16
"""

from alembic import op

# revision identifiers
revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None

# ---------------------------------------------------------------------------
# App User
# ---------------------------------------------------------------------------
APP_USER_INSERT = """\
INSERT INTO user_accounts (external_user_id, name, email, google_id, auth_provider, is_active)
VALUES ('app', 'App User', 'app@pyrsquare.com', 'na', 'na', true)
ON CONFLICT (external_user_id) DO NOTHING;
"""

# ---------------------------------------------------------------------------
# Benchmark Strategies — owned by the app user (account_id from subquery)
# ---------------------------------------------------------------------------
# Each INSERT uses a subquery for account_id so it works regardless of the
# actual auto-assigned ID.  The unique constraint (account_id, name) provides
# the ON CONFLICT target.
# ---------------------------------------------------------------------------

STRATEGY_TEMPLATE = """\
INSERT INTO strategies
    (account_id, name, description, direction, timeframes,
     entry_criteria, exit_criteria, max_risk_pct, min_risk_reward,
     is_active, risk_profile, implied_strategy_family)
VALUES (
    (SELECT id FROM user_accounts WHERE external_user_id = 'app'),
    '{name}',
    '{description}',
    'both',
    '{timeframes}'::jsonb,
    '{entry_criteria}',
    '{exit_criteria}',
    {max_risk_pct},
    1.5,
    true,
    '{risk_profile}'::jsonb,
    '{family}'
)
ON CONFLICT ON CONSTRAINT uq_strategy_account_name DO NOTHING;
"""

# Escape single quotes for SQL by doubling them
def _esc(text: str) -> str:
    return text.replace("'", "''")


STRATEGIES = [
    {
        "name": "Momentum: Multi-Timeframe Momentum Trend-Follow",
        "description": (
            "A vanilla trend-following momentum strategy that buys strength and "
            "sells weakness using a higher-timeframe trend filter and a lower-timeframe trigger."
        ),
        "timeframes": '["1Day"]',
        "entry_criteria": (
            "Long:\\n"
            "- Price > SMA_200 (trend filter)\\n"
            "- SMA_50 > SMA_200 (trend confirmation)\\n"
            "- RSI_14 crosses above 50 after being below 50 in the last 10 bars\\n"
            "- Optional: Close above prior day''s high to confirm resumption\\n"
            "\\n"
            "Short:\\n"
            "- Price < SMA_200 (trend filter)\\n"
            "- SMA_50 < SMA_200 (trend confirmation)\\n"
            "- RSI_14 crosses below 50 after being above 50 in the last 10 bars\\n"
            "- Optional: Close below prior day''s low to confirm resumption"
        ),
        "exit_criteria": (
            "Long:\\n"
            "- Stop-loss: 2.0 * ATR_14 below entry (initial)\\n"
            "- Trailing stop: 2.0 * ATR_14 below highest close since entry\\n"
            "- Trend exit: close below SMA_50 OR RSI_14 drops below 45\\n"
            "\\n"
            "Short:\\n"
            "- Stop-loss: 2.0 * ATR_14 above entry (initial)\\n"
            "- Trailing stop: 2.0 * ATR_14 above lowest close since entry\\n"
            "- Trend exit: close above SMA_50 OR RSI_14 rises above 55"
        ),
        "max_risk_pct": 1.0,
        "risk_profile": '{"tags": ["trend", "momentum", "atr-stop", "daily"]}',
        "family": "momentum",
    },
    {
        "name": "Pattern: Bull Flag / Bear Flag Continuation",
        "description": (
            "A classical continuation-pattern strategy that enters after a sharp impulse "
            "move and a tight consolidation (flag), then breaks out in the direction of the impulse."
        ),
        "timeframes": '["15Min", "1Hour", "1Day"]',
        "entry_criteria": (
            "Long:\\n"
            "- Impulse leg: price rises >= 3% (daily) or >= 1.0 * ATR (intraday) within 1-5 bars\\n"
            "- Flag: 3-12 bars of consolidation; max retracement <= 50% of impulse\\n"
            "- Volume contracts during flag vs impulse average\\n"
            "- Entry: buy stop above flag high with breakout volume > 1.2x flag average\\n"
            "\\n"
            "Short:\\n"
            "- Impulse leg: price drops >= 3% (daily) or >= 1.0 * ATR (intraday) within 1-5 bars\\n"
            "- Flag: 3-12 bars consolidation; max retracement <= 50% of impulse\\n"
            "- Volume contracts during flag\\n"
            "- Entry: sell stop below flag low with breakout volume > 1.2x flag average"
        ),
        "exit_criteria": (
            "Long:\\n"
            "- Stop-loss: below flag low OR 1.5 * ATR below entry\\n"
            "- Target: measured move = impulse height added to breakout level\\n"
            "- Fail exit: close back inside flag for 2 bars\\n"
            "\\n"
            "Short:\\n"
            "- Stop-loss: above flag high OR 1.5 * ATR above entry\\n"
            "- Target: measured move = impulse height subtracted from breakout\\n"
            "- Fail exit: close back inside flag for 2 bars"
        ),
        "max_risk_pct": 1.0,
        "risk_profile": '{"tags": ["pattern", "continuation", "flags", "breakout-confirmation"]}',
        "family": "breakout",
    },
    {
        "name": "Breakout: 20-Day Donchian Channel Breakout",
        "description": (
            "A classic breakout system that enters when price exceeds recent highs/lows, "
            "using Donchian channels with volatility-scaled stops."
        ),
        "timeframes": '["1Day"]',
        "entry_criteria": (
            "Long:\\n"
            "- Today''s high > prior 20-day highest high (exclude current bar)\\n"
            "- Optional: Close above breakout level to reduce false breaks\\n"
            "\\n"
            "Short:\\n"
            "- Today''s low < prior 20-day lowest low (exclude current bar)\\n"
            "- Optional: Close below breakdown level"
        ),
        "exit_criteria": (
            "Long:\\n"
            "- Initial stop: entry - 2.0 * ATR_20\\n"
            "- Trailing exit: close < prior 10-day lowest low\\n"
            "- Time stop (optional): exit if no new 20-day high within 15 bars\\n"
            "\\n"
            "Short:\\n"
            "- Initial stop: entry + 2.0 * ATR_20\\n"
            "- Trailing exit: close > prior 10-day highest high\\n"
            "- Time stop (optional): exit if no new 20-day low within 15 bars"
        ),
        "max_risk_pct": 0.75,
        "risk_profile": '{"tags": ["breakout", "donchian", "trend-following", "daily"]}',
        "family": "breakout",
    },
    {
        "name": "Mean-Reversion: Bollinger Band Reversion to Mean",
        "description": (
            "A simple mean-reversion strategy that fades short-term extremes "
            "using Bollinger Bands and exits near the midline/mean."
        ),
        "timeframes": '["1Hour", "1Day"]',
        "entry_criteria": (
            "Long:\\n"
            "- Regime filter: Close within +/-10% of SMA_200, SMA_200 slope flat over last 20 bars\\n"
            "- Close < Lower Bollinger Band (20,2)\\n"
            "- Optional: next bar closes higher (bullish reversal)\\n"
            "\\n"
            "Short:\\n"
            "- Regime filter: Close within +/-10% of SMA_200, SMA_200 slope flat\\n"
            "- Close > Upper Bollinger Band (20,2)\\n"
            "- Optional: next bar closes lower"
        ),
        "exit_criteria": (
            "Long:\\n"
            "- Primary exit: close >= Bollinger midline (SMA_20)\\n"
            "- Stop-loss: entry - 1.5 * ATR_14 OR close below lower band for 2 bars\\n"
            "- Time stop: exit after 7 bars if midline not reached\\n"
            "\\n"
            "Short:\\n"
            "- Primary exit: close <= Bollinger midline\\n"
            "- Stop-loss: entry + 1.5 * ATR_14 OR close above upper band for 2 bars\\n"
            "- Time stop: exit after 7 bars"
        ),
        "max_risk_pct": 0.75,
        "risk_profile": '{"tags": ["mean-reversion", "bollinger", "range-regime"]}',
        "family": "mean_reversion",
    },
    {
        "name": "Volume Flow: OBV + Price Structure Breakout",
        "description": (
            "A benchmark volume-flow strategy that requires volume accumulation/distribution "
            "(OBV) to lead price, then enters on a simple structure break."
        ),
        "timeframes": '["1Hour", "1Day"]',
        "entry_criteria": (
            "Long:\\n"
            "- OBV above OBV_SMA_20 and making a 20-bar high (volume flow leading)\\n"
            "- Price breaks above 20-bar pivot high (or 20-bar highest close)\\n"
            "- Breakout bar volume > 1.2x 20-bar average volume\\n"
            "\\n"
            "Short:\\n"
            "- OBV below OBV_SMA_20 and making a 20-bar low\\n"
            "- Price breaks below 20-bar pivot low (or 20-bar lowest close)\\n"
            "- Breakdown bar volume > 1.2x 20-bar average volume"
        ),
        "exit_criteria": (
            "Long:\\n"
            "- Stop-loss: 1.8 * ATR_14 below entry\\n"
            "- Exit if OBV crosses below OBV_SMA_20 (volume support fades)\\n"
            "- Or trailing stop: 2.0 * ATR_14 below highest close\\n"
            "\\n"
            "Short:\\n"
            "- Stop-loss: 1.8 * ATR_14 above entry\\n"
            "- Exit if OBV crosses above OBV_SMA_20\\n"
            "- Or trailing stop: 2.0 * ATR_14 above lowest close"
        ),
        "max_risk_pct": 0.5,
        "risk_profile": '{"tags": ["volume", "obv", "breakout", "confirmation"]}',
        "family": "breakout",
    },
    {
        "name": "Regime: Regime-Switch Trend vs Range Playbook",
        "description": (
            "A benchmark regime strategy that classifies the market into trend or range "
            "using simple volatility and trend-strength proxies, then applies the "
            "corresponding baseline strategy."
        ),
        "timeframes": '["1Day"]',
        "entry_criteria": (
            "Trend regime:\\n"
            "- If ADX_14 >= 20 and Close > SMA_200: allow only long breakout/momentum entries\\n"
            "- If ADX_14 >= 20 and Close < SMA_200: allow only short breakout/momentum entries\\n"
            "\\n"
            "Range regime:\\n"
            "- If ADX_14 < 20: allow only mean-reversion entries at Bollinger extremes"
        ),
        "exit_criteria": (
            "Global:\\n"
            "- Regime change exit: if regime flips (trend->range or range->trend), flatten at close\\n"
            "- Otherwise use the exits defined by the active sub-strategy"
        ),
        "max_risk_pct": 0.5,
        "risk_profile": '{"tags": ["regime", "adx", "router", "trend-vs-range"]}',
        "family": "trend",
    },
]


def upgrade() -> None:
    # Insert app user
    op.execute(APP_USER_INSERT)

    # Insert benchmark strategies
    for s in STRATEGIES:
        sql = STRATEGY_TEMPLATE.format(
            name=_esc(s["name"]),
            description=_esc(s["description"]),
            timeframes=s["timeframes"],
            entry_criteria=s["entry_criteria"],
            exit_criteria=s["exit_criteria"],
            max_risk_pct=s["max_risk_pct"],
            risk_profile=s["risk_profile"],
            family=s["family"],
        )
        op.execute(sql)


def downgrade() -> None:
    # Delete strategies owned by the app user
    op.execute("""\
        DELETE FROM strategies
        WHERE account_id = (SELECT id FROM user_accounts WHERE external_user_id = 'app');
    """)
    # Delete the app user
    op.execute("DELETE FROM user_accounts WHERE external_user_id = 'app';")
