"""Faust streams app: consumes raw-weather, runs the offline model, publishes predictions.

Run with:  faust -A src.streams_app worker -l info
"""
from pathlib import Path

import faust
import joblib

from src.data_loader import FEATURE_ORDER

MODEL_PATH = Path(__file__).resolve().parents[1] / "model.joblib"

model = joblib.load(MODEL_PATH)

app = faust.App(
    "weather-ml",
    broker="kafka://localhost:9092",
    value_serializer="json",
    store="memory://",
)

raw_topic = app.topic("raw-weather")
pred_topic = app.topic("predictions")


@app.agent(raw_topic)
async def predict(stream):
    async for event in stream:
        x = [[event[f] for f in FEATURE_ORDER]]
        yhat = float(model.predict(x)[0])
        delta = yhat - float(event["temp"])
        out = {
            **event,
            "pred_next_hour_temp": yhat,
            "pred_delta": delta,
            "pred_direction": 1 if delta > 0 else 0,
        }
        await pred_topic.send(value=out)
        print(f"[streams] ts={event['ts']} temp={event['temp']:.2f} -> pred={yhat:.2f}")
