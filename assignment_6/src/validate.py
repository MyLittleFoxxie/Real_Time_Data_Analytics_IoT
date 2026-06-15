"""Offline ground-truth validation of the Spark alert output.

Recomputes the 2-minute tumbling averages and the "two consecutive windows
> 100 bpm" clinical alerts directly in pandas, from the *same* readings CSV and
the *same* synthesized timestamp scheme the producer uses (src/config). Because
both sides are deterministic, the expected alert set should match the alerts
Spark wrote to alerts/clinical_alerts.csv exactly.

Run (after the Spark job + producer have finished):  python -m src.validate
"""
from __future__ import annotations

import sys

import pandas as pd

from src import config

TS_FMT = "%Y-%m-%dT%H:%M:%S"


def build_stream_frame() -> pd.DataFrame:
    """Reconstruct every (patient, event_time, heart_rate) the producer emits."""
    readings = pd.read_csv(config.READINGS_CSV)
    by_patient = {pid: g["heart_rate"].tolist() for pid, g in readings.groupby("patient_id")}
    patients = sorted(by_patient)
    n_ticks = min(config.MAX_TICKS, min(len(v) for v in by_patient.values()))

    records = []
    for tick in range(n_ticks):
        et = config.event_time_for_tick(tick)
        for p in patients:
            records.append((p, et, by_patient[p][tick]))
    # flush sentinel (identical to the producer) — below threshold, never alerts
    flush_et = config.flush_event_time(n_ticks)
    for p in patients:
        records.append((p, flush_et, config.SENTINEL_HR))

    return pd.DataFrame(records, columns=["patient_id", "event_time", "heart_rate"])


def expected_alerts() -> set[tuple[int, str, str]]:
    df = build_stream_frame()
    df["window_start"] = df["event_time"].apply(config.window_start_for)

    win = (
        df.groupby(["patient_id", "window_start"], as_index=False)["heart_rate"]
        .mean()
        .rename(columns={"heart_rate": "avg_hr"})
        .sort_values(["patient_id", "window_start"])
    )

    step = pd.Timedelta(seconds=config.WINDOW_SECONDS)
    alerts: set[tuple[int, str, str]] = set()
    last_breach: dict[int, pd.Timestamp] = {}
    for row in win.itertuples(index=False):
        if row.avg_hr > config.HR_THRESHOLD:
            prev = last_breach.get(row.patient_id)
            if prev is not None and (row.window_start - prev) == step:
                alerts.add(
                    (
                        int(row.patient_id),
                        prev.strftime(TS_FMT),
                        row.window_start.strftime(TS_FMT),
                    )
                )
            last_breach[row.patient_id] = row.window_start
    return alerts


def spark_alerts() -> set[tuple[int, str, str]]:
    path = config.ALERTS_DIR / "clinical_alerts.csv"
    if not path.exists():
        print(f"[validate] Spark alert file not found: {path}")
        print("[validate] Run the Spark job (docker compose up) and the producer first.")
        sys.exit(2)
    df = pd.read_csv(path)
    out: set[tuple[int, str, str]] = set()
    for r in df.itertuples(index=False):
        out.add(
            (
                int(r.patient_id),
                pd.to_datetime(r.prev_window_start).strftime(TS_FMT),
                pd.to_datetime(r.curr_window_start).strftime(TS_FMT),
            )
        )
    return out


def main() -> None:
    expected = expected_alerts()
    actual = spark_alerts()

    missing = expected - actual    # expected but Spark didn't fire
    extra = actual - expected      # Spark fired but not expected

    print(f"[validate] expected alerts (pandas ground truth): {len(expected)}")
    print(f"[validate] actual alerts (Spark output):          {len(actual)}")
    print(f"[validate] matched: {len(expected & actual)} | missing: {len(missing)} | extra: {len(extra)}")

    for label, s in (("MISSING (expected, not in Spark)", missing), ("EXTRA (Spark, not expected)", extra)):
        for pid, prev, curr in sorted(s)[:10]:
            print(f"  {label}: patient {pid} {prev} -> {curr}")

    if not missing and not extra and expected:
        print("\n[validate] PASS — Spark alerts exactly match the independent ground truth.")
        sys.exit(0)
    if not expected:
        print("\n[validate] WARNING — ground truth produced no alerts; check the data/config.")
        sys.exit(1)
    print("\n[validate] FAIL — see differences above.")
    sys.exit(1)


if __name__ == "__main__":
    main()
