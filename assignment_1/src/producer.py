"""Replays the latest monthly weather CSV to the `raw-weather` Kafka topic at ~1 msg/sec."""
import json
import time

from confluent_kafka import Producer

from src.data_loader import load_latest

BOOTSTRAP = "localhost:9092"
TOPIC = "raw-weather"
RATE_SECONDS = 1.0


def delivery_report(err, msg):
    if err is not None:
        print(f"[producer] delivery failed: {err}")


def main() -> None:
    df = load_latest()
    producer = Producer({"bootstrap.servers": BOOTSTRAP})
    print(f"[producer] streaming {len(df)} rows to topic '{TOPIC}' at 1/sec...")

    for _, row in df.iterrows():
        payload = {
            "ts": row["ts"].isoformat(),
            "hour": int(row["hour"]),
            "temp": float(row["temp"]),
            "dew_point": float(row["dew_point"]),
            "humidity": float(row["humidity"]),
            "pressure": float(row["pressure"]),
        }
        producer.produce(TOPIC, value=json.dumps(payload).encode("utf-8"), callback=delivery_report)
        producer.poll(0)
        print(f"[producer] sent ts={payload['ts']} temp={payload['temp']:.2f}")
        time.sleep(RATE_SECONDS)

    producer.flush()
    print("[producer] done.")


if __name__ == "__main__":
    main()
