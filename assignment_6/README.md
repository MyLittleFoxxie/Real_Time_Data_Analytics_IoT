# Module 6 Assignment — Real-Time Stream Processing (Spark Structured Streaming)

Repository for Ontario Tech course **ENGR 5785G — Real-Time Data Analytics IoT**.

Student: Vitor Brandao Raposo

Student ID: 101011969

Date: 06/2026

---

## Scenario B — Hospital Patient Monitoring (IoMT)

> Detect **sustained** abnormal heart rates, not single spikes, across ICU patient streams.

| Requirement (from the assignment PDF) | This implementation |
| --- | --- |
| Window: **tumbling 2 min** | `window("event_time", "2 minutes")` |
| Compute **average heart rate per patient per window** | `groupBy(window, patient_id).agg(avg("heart_rate"))` |
| Flag patients **exceeding 100 bpm in two consecutive windows** | per-patient consecutive-breach tracking in `foreachBatch` |
| Alert: **clinical alert with patient ID** | `*** CLINICAL ALERT *** patient N ...` in the console + `alerts/clinical_alerts.csv` |
| `readStream` with a **watched directory** | `spark.readStream.json("stream_input/")` |
| **Window aggregation with `withWatermark`** | `withWatermark("event_time", "4 minutes")` |
| **Alert condition as a filtered output stream** | `avg_hr > 100` filter, surfaced as the alert stream |

Spark runs **inside Docker** (no local Java/winutils needed), matching the repo's
"infrastructure is Docker-managed" convention.

---

## Quick Start (Windows)

```powershell
# from assignment_6/, with the repo-root virtual environment active
..\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt        # host-side: pandas + openpyxl (one-time prep & validation only)

# 1. Build the streamable dataset from the Kaggle xlsx (one-time)
python -m src.prepare_data                # -> iomt_data/icu_readings.csv

# 2. Start the Spark Structured Streaming job (waits for files)
docker compose up -d
docker compose logs -f spark              # watch this window — screenshot the CLINICAL ALERT lines here

# 3. In a second terminal, feed the stream
python -m src.producer                    # writes timestamped JSON ticks into stream_input/

# 4. Validate the results against an independent ground truth
python -m src.validate                    # -> PASS when Spark's alerts match exactly

# 5. Tear down
docker compose down
```

Expected `validate` output:

```text
[validate] expected alerts (pandas ground truth): 167
[validate] actual alerts (Spark output):          167
[validate] matched: 167 | missing: 0 | extra: 0
[validate] PASS — Spark alerts exactly match the independent ground truth.
```

---

## What the Spark console shows (screenshot target)

```text
[spark] watching /app/stream_input | window=2 minutes watermark=4 minutes threshold=100 bpm

===== batch 4: 30 finalized window(s) =====
  patient  1 | window 00:02:00-00:04:00 | avg HR 103.75 bpm  <-- HIGH
  patient  2 | window 00:02:00-00:04:00 | avg HR 106.50 bpm  <-- HIGH
  ...
  *** CLINICAL ALERT *** patient 8: avg HR > 100 bpm in two consecutive windows (00:22-00:24), latest avg 105.0 bpm
  *** CLINICAL ALERT *** patient 12: avg HR > 100 bpm in two consecutive windows (00:24-00:26), latest avg 106.8 bpm
```

Each batch prints every finalized 2-minute window average (with a `<-- HIGH` marker
when it breaches 100 bpm); a `CLINICAL ALERT` line fires only when a patient
breaches in **two adjacent** windows.

---

## Repository Structure

```text
assignment_6/
├── StreamProcessing_Assignment.pdf   ← Assignment spec
├── docker-compose.yml                ← Spark job runner (apache spark:3.5.3, local mode)
├── requirements.txt                  ← host deps: pandas, openpyxl (prep + validation only)
├── iomt_data/
│   ├── patients_data_with_alerts.xlsx ← Kaggle source (gitignored, not submitted)
│   └── icu_readings.csv               ← produced by prepare_data.py (gitignored)
├── src/
│   ├── config.py                     ← shared constants + the canonical event-time scheme
│   ├── prepare_data.py               ← xlsx → streamable CSV (round-robin onto ICU pool)
│   ├── producer.py                   ← writes timestamped JSON ticks into stream_input/
│   ├── streaming_job.py              ← the Spark Structured Streaming job
│   └── validate.py                   ← pandas ground truth vs. Spark alerts
├── stream_input/                     ← watched directory (gitignored, runtime)
├── checkpoints/  stream_window_out/  ← Spark state/output (gitignored, runtime)
├── alerts/clinical_alerts.csv        ← fired alerts (gitignored, runtime)
└── README.md                         ← this file
```

---

## Dataset

Source: **IoMT Health Monitoring** (Kaggle) — `patients_data_with_alerts.xlsx`,
50,000 rows. Columns used: `Patient Number`, `Heart Rate (bpm)`
(mean ≈ 104.5 bpm; 54.6% of readings exceed 100 bpm).

The raw dataset is **cross-sectional**: each of the 50,000 rows is a *distinct*
patient with a single reading and **no timestamp**. Scenario B's
"two consecutive windows per patient" only has meaning if patients recur over
time, so `prepare_data.py` remaps every reading **round-robin onto a pool of 30
ICU patients** (`config.POOL_SIZE`), and `producer.py` replays them while
**synthesizing an event timestamp** for each reading (`config.event_time_for_tick`):
30 seconds of event-time per tick, four ticks per 2-minute window. This is the
allowed "simulate streaming" approach from the assignment.

> **Submission rule:** the Kaggle `*.xlsx` and the derived `icu_readings.csv` are
> **gitignored** and must not be submitted. `prepare_data.py` regenerates the CSV.

---

## Written Explanation

### Why a tumbling window?

Scenario B asks for the **average heart rate per patient per window** and an alert
on **two consecutive windows**. A **tumbling** (fixed, non-overlapping) 2-minute
window gives each patient exactly **one** average per 2-minute interval, so
"two consecutive windows" maps cleanly to two **adjacent, disjoint** intervals
(`start₂ == start₁ + 2 min`). A sliding window would reuse the same readings
across overlapping windows, double-counting samples and making "consecutive"
ambiguous — inflating false alerts for what is meant to be a *sustained* signal.
Tumbling is also exactly what the scenario prescribes.

### Where the pipeline requires state

1. **Windowed-aggregation state (Spark-managed, checkpointed).** Spark keeps a
   running `avg(heart_rate)` for every `(patient_id, 2-min window)` key in its
   state store, holding each partial aggregate until the **watermark**
   (`event_time − 4 min`) passes the window's end, at which point append mode
   emits the window's final average exactly once and evicts its state. The
   watermark is what bounds this state so it cannot grow without limit.

2. **Consecutive-breach state (application-level).** Detecting *two consecutive*
   breaching windows requires remembering, per patient, the start time of its
   most recent breaching window — information that spans windows and micro-batches
   and is therefore not expressible by a single windowed aggregation. The
   `foreachBatch` handler in [src/streaming_job.py](src/streaming_job.py) keeps a
   `patient_id → last_breaching_window_start` dictionary and fires the clinical
   alert when the current breaching window is adjacent to the stored one.

---

## How results are validated

[src/validate.py](src/validate.py) recomputes the 2-minute tumbling averages and
the consecutive-breach alerts **independently in pandas**, from the *same*
`icu_readings.csv` and the *same* deterministic timestamp scheme the producer
uses (`src/config.py`). It then compares its alert set to what Spark wrote to
`alerts/clinical_alerts.csv`. Because both paths are deterministic, the match is
**exact** (167 alerts, 0 missing, 0 extra). To finalize the last windows, the
producer emits one far-future below-threshold "flush" tick that advances the
watermark — both the producer and the validator emit it identically, so they stay
in agreement.

---

## Submission Checklist

- [x] Spark Structured Streaming job code (`src/streaming_job.py`) on GitHub
- [x] README with exact run steps (this file)
- [x] `readStream` from a watched directory
- [x] Window aggregation with `withWatermark`
- [x] Alert condition as a filtered output stream (`avg_hr > 100`)
- [x] Tumbling 2-min window, average HR per patient, two-consecutive-window alert
- [x] Written explanation (window choice + where state is required)
- [ ] Screenshot of the `CLINICAL ALERT` output firing in the Spark console
      (run step 2–3, capture `docker compose logs -f spark`)
- [x] Source dataset and derived CSV gitignored (not submitted)
```
