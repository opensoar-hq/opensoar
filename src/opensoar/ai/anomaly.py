"""Alert pattern anomaly detection.

The detector runs on a rolling 7-day window per
``(partner, rule_name, source_ip)`` tuple and fires three heuristics:

* ``count_spike`` — current-day count with a z-score > 3 against the trailing
  baseline.
* ``first_seen_ip`` — source IP never observed before for this
  ``(partner, rule_name)`` pair.
* ``new_severity`` — a severity level higher than anything observed before
  for this ``(partner, rule_name)`` pair.

The module exposes pure helpers (``zscore``, ``compute_anomaly_signals``) used
in unit tests, plus ``run_anomaly_detection`` which persists anomalies to the
DB and is safe to invoke from a Celery beat job or the ``Scheduler`` tick
loop.
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.models.alert import Alert
from opensoar.models.anomaly import Anomaly

logger = logging.getLogger(__name__)

# Severity ordering from lowest to highest. Unknown levels are treated as the
# lowest so an alert labelled "info" cannot mask a later "critical".
SEVERITY_ORDER: dict[str, int] = {
    "info": 0,
    "informational": 0,
    "low": 1,
    "medium": 2,
    "moderate": 2,
    "high": 3,
    "critical": 4,
}

DEFAULT_BASELINE_DAYS = 7
DEFAULT_ZSCORE_THRESHOLD = 3.0


def zscore(sample: float, *, mean: float, stdev: float) -> float:
    """Return the z-score of ``sample`` relative to ``mean`` / ``stdev``.

    When ``stdev`` is zero we fall back to two special cases:
      * If the sample matches the mean, the score is 0.
      * Otherwise, we return ``+inf`` so threshold checks still fire.
    """
    if stdev == 0.0:
        return 0.0 if sample == mean else math.inf
    return (sample - mean) / stdev


@dataclass
class AnomalySignal:
    """Pure-python anomaly record ready to be persisted or serialised."""

    kind: str
    partner: str | None
    rule_name: str | None
    source_ip: str | None
    score: float
    details: dict[str, Any] = field(default_factory=dict)

    def to_model_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "partner": self.partner,
            "rule_name": self.rule_name,
            "source_ip": self.source_ip,
            "score": float(self.score),
            "details": dict(self.details),
        }


def _key(alert: Alert) -> tuple[str | None, str | None, str | None]:
    return (alert.partner, alert.rule_name, alert.source_ip)


def _day_bucket(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def _severity_rank(severity: str | None) -> int:
    if not severity:
        return 0
    return SEVERITY_ORDER.get(severity.lower(), 0)


def _stdev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def compute_anomaly_signals(
    *,
    history: Iterable[Alert],
    current: Iterable[Alert],
    zscore_threshold: float = DEFAULT_ZSCORE_THRESHOLD,
    baseline_days: int = DEFAULT_BASELINE_DAYS,
) -> list[AnomalySignal]:
    """Compute anomaly signals from a ``history`` window and ``current`` alerts.

    Both iterables are plain ``Alert`` objects, in any order. The detector
    deduplicates signals per ``(kind, partner, rule_name, source_ip)`` so a
    burst of repeated alerts does not flood the anomaly table.
    """
    history_list = list(history)
    current_list = list(current)

    signals: list[AnomalySignal] = []
    seen: set[tuple[str, str | None, str | None, str | None]] = set()

    def _emit(signal: AnomalySignal) -> None:
        dedup_key = (
            signal.kind,
            signal.partner,
            signal.rule_name,
            signal.source_ip,
        )
        if dedup_key in seen:
            return
        seen.add(dedup_key)
        signals.append(signal)

    # ── first_seen_ip ───────────────────────────────────────────────────
    seen_ips: dict[tuple[str | None, str | None], set[str | None]] = defaultdict(set)
    for alert in history_list:
        seen_ips[(alert.partner, alert.rule_name)].add(alert.source_ip)

    for alert in current_list:
        if not alert.source_ip:
            continue
        bucket = (alert.partner, alert.rule_name)
        if alert.source_ip not in seen_ips[bucket]:
            _emit(
                AnomalySignal(
                    kind="first_seen_ip",
                    partner=alert.partner,
                    rule_name=alert.rule_name,
                    source_ip=alert.source_ip,
                    score=1.0,
                    details={"severity": alert.severity},
                )
            )
            # Record it so subsequent current alerts for the same key are
            # deduplicated by ``_emit``.
            seen_ips[bucket].add(alert.source_ip)

    # ── new_severity ────────────────────────────────────────────────────
    max_severity: dict[tuple[str | None, str | None], tuple[int, str | None]] = {}
    for alert in history_list:
        bucket = (alert.partner, alert.rule_name)
        rank = _severity_rank(alert.severity)
        current_best = max_severity.get(bucket, (-1, None))
        if rank > current_best[0]:
            max_severity[bucket] = (rank, alert.severity)

    for alert in current_list:
        bucket = (alert.partner, alert.rule_name)
        rank = _severity_rank(alert.severity)
        previous = max_severity.get(bucket)
        if previous is None:
            # A brand-new rule is covered by first_seen_ip; skip new_severity
            # to avoid double-reporting.
            max_severity[bucket] = (rank, alert.severity)
            continue
        prev_rank, prev_label = previous
        if rank > prev_rank:
            _emit(
                AnomalySignal(
                    kind="new_severity",
                    partner=alert.partner,
                    rule_name=alert.rule_name,
                    source_ip=alert.source_ip,
                    score=float(rank - prev_rank),
                    details={
                        "severity": alert.severity,
                        "previous_max": prev_label,
                    },
                )
            )
            max_severity[bucket] = (rank, alert.severity)

    # ── count_spike ─────────────────────────────────────────────────────
    # Build daily counts per (partner, rule, ip) from history.
    per_day: dict[
        tuple[str | None, str | None, str | None], dict[datetime, int]
    ] = defaultdict(lambda: defaultdict(int))
    for alert in history_list:
        per_day[_key(alert)][_day_bucket(alert.created_at)] += 1

    current_counts: dict[tuple[str | None, str | None, str | None], int] = defaultdict(int)
    for alert in current_list:
        current_counts[_key(alert)] += 1

    for key, count in current_counts.items():
        history_daily = per_day.get(key, {})
        # Only consider the baseline window days — we don't need more.
        values = [float(v) for v in history_daily.values()][-baseline_days:]
        if not values:
            # No history for this key; first_seen_ip already covers this case.
            continue
        # Pad with zeros so an otherwise-quiet baseline is not considered
        # equal to the current count.
        while len(values) < baseline_days:
            values.append(0.0)
        mean = sum(values) / len(values)
        stdev = _stdev(values)
        score = zscore(float(count), mean=mean, stdev=stdev)
        if score > zscore_threshold:
            partner, rule_name, source_ip = key
            _emit(
                AnomalySignal(
                    kind="count_spike",
                    partner=partner,
                    rule_name=rule_name,
                    source_ip=source_ip,
                    score=float(score if math.isfinite(score) else 1e6),
                    details={
                        "current_count": count,
                        "baseline_mean": mean,
                        "baseline_stdev": stdev,
                        "baseline_days": baseline_days,
                        "threshold": zscore_threshold,
                    },
                )
            )

    return signals


async def run_anomaly_detection(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    baseline_days: int = DEFAULT_BASELINE_DAYS,
    zscore_threshold: float = DEFAULT_ZSCORE_THRESHOLD,
) -> int:
    """Run detection against the DB and persist any new anomalies.

    Returns the number of anomaly rows inserted.

    The method is idempotent within a detection day: if an anomaly with the
    same ``(kind, partner, rule_name, source_ip)`` has already been persisted
    in the last 24 hours it is not duplicated.
    """
    now = now or datetime.now(timezone.utc)
    window_start = now - timedelta(days=baseline_days)
    current_start = _day_bucket(now)

    stmt = select(Alert).where(Alert.created_at >= window_start)
    alerts: list[Alert] = list((await session.execute(stmt)).scalars().all())

    current: list[Alert] = []
    history: list[Alert] = []
    for alert in alerts:
        created = alert.created_at
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created and created >= current_start:
            current.append(alert)
        else:
            history.append(alert)

    signals = compute_anomaly_signals(
        history=history,
        current=current,
        zscore_threshold=zscore_threshold,
        baseline_days=baseline_days,
    )

    if not signals:
        return 0

    # Dedupe against anomalies already stored in the current detection day so
    # repeated runs are idempotent.
    existing = (
        await session.execute(
            select(
                Anomaly.kind,
                Anomaly.partner,
                Anomaly.rule_name,
                Anomaly.source_ip,
            ).where(Anomaly.created_at >= current_start)
        )
    ).all()
    seen: set[tuple[str, str | None, str | None, str | None]] = {
        (row.kind, row.partner, row.rule_name, row.source_ip) for row in existing
    }

    inserted = 0
    for signal in signals:
        key = (signal.kind, signal.partner, signal.rule_name, signal.source_ip)
        if key in seen:
            continue
        session.add(Anomaly(**signal.to_model_payload()))
        seen.add(key)
        inserted += 1

    if inserted:
        await session.commit()
        logger.info("anomaly detection: persisted %d new signal(s)", inserted)

    return inserted
