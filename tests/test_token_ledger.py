"""TokenLedger: contabilidad por usuario, coste estimado y bloqueo anti-abuso."""
from datetime import datetime, timedelta, timezone

from src.token_ledger import TokenLedger, TokenUsage, estimate_cost_usd

T0 = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


class _Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


def _ledger(tmp_path, owner=999, **kw):
    clock = _Clock()
    return TokenLedger(str(tmp_path / "u.db"), owner_id=owner, clock=clock, **kw), clock


def test_cost_estimate_haiku_rates():
    # 1M entrada = 0.10, 1M salida = 0.50, lectura cache 0.1x, escritura cache 1.25x
    assert estimate_cost_usd(TokenUsage(1_000_000, 0, 0, 0)) == 0.10
    assert estimate_cost_usd(TokenUsage(0, 1_000_000, 0, 0)) == 0.50
    assert round(estimate_cost_usd(TokenUsage(0, 0, 1_000_000, 0)), 6) == 0.01
    assert round(estimate_cost_usd(TokenUsage(0, 0, 0, 1_000_000)), 6) == 0.125


def test_hourly_limit_blocks_and_expires_after_24h(tmp_path):
    led, clock = _ledger(tmp_path)
    led.record(1, TokenUsage(150_000, 10_000, 0, 0), "m", "text")
    assert led.evaluate(1) is False and not led.is_blocked(1)
    led.record(1, TokenUsage(50_000, 5_000, 0, 0), "m", "text")  # 215k en 1 h
    assert led.evaluate(1) is True  # recien bloqueado
    assert led.is_blocked(1)
    assert led.evaluate(1) is False  # solo avisa una vez
    clock.now = T0 + timedelta(hours=23)
    assert led.is_blocked(1)
    clock.now = T0 + timedelta(hours=25)
    assert not led.is_blocked(1)


def test_daily_limit_counts_across_hours(tmp_path):
    led, clock = _ledger(tmp_path)
    for i in range(6):  # 6 x 190k repartidos cada 2 h: nunca >200k/h, pero >1M/24h
        clock.now = T0 + timedelta(hours=2 * i)
        led.record(2, TokenUsage(190_000, 0, 0, 0), "m", "text")
    assert led.evaluate(2) is True


def test_old_usage_does_not_count(tmp_path):
    led, clock = _ledger(tmp_path)
    led.record(3, TokenUsage(190_000, 0, 0, 0), "m", "text")
    clock.now = T0 + timedelta(hours=2)
    led.record(3, TokenUsage(190_000, 0, 0, 0), "m", "text")
    assert led.evaluate(3) is False


def test_owner_counted_but_never_blocked(tmp_path):
    led, _ = _ledger(tmp_path, owner=999)
    led.record(999, TokenUsage(900_000, 0, 0, 0), "m", "text")
    assert led.evaluate(999) is False and not led.is_blocked(999)
    assert led.report("day")[0].total_tokens == 900_000


def test_unblock(tmp_path):
    led, _ = _ledger(tmp_path)
    led.record(4, TokenUsage(300_000, 0, 0, 0), "m", "text")
    led.evaluate(4)
    assert led.unblock(4) is True and not led.is_blocked(4)
    assert led.unblock(4) is False


def test_report_today_and_month_by_user(tmp_path):
    led, clock = _ledger(tmp_path)
    led.record(1, TokenUsage(1000, 100, 0, 0), "m", "text")
    led.record(2, TokenUsage(500, 50, 0, 0), "m", "photo")
    clock.now = T0 - timedelta(days=3)  # mismo mes, no hoy
    led.record(1, TokenUsage(2000, 0, 0, 0), "m", "text")
    clock.now = T0
    today = {r.user_id: r for r in led.report("day")}
    month = {r.user_id: r for r in led.report("month")}
    assert today[1].total_tokens == 1100 and today[2].total_tokens == 550
    assert month[1].total_tokens == 3100
    assert month[1].cost_usd > today[1].cost_usd


def test_persists_across_instances(tmp_path):
    led, _ = _ledger(tmp_path)
    led.record(1, TokenUsage(10, 1, 0, 0), "m", "text")
    led2 = TokenLedger(str(tmp_path / "u.db"), owner_id=0, clock=lambda: T0)
    assert led2.report("day")[0].total_tokens == 11
