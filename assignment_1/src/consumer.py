"""Reads the predictions topic and prints one formatted line per message."""
import json

from confluent_kafka import Consumer

BOOTSTRAP = "localhost:9092"
TOPIC = "predictions"
GROUP_ID = "predictions-printer"


def main() -> None:
    consumer = Consumer(
        {
            "bootstrap.servers": BOOTSTRAP,
            "group.id": GROUP_ID,
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
        }
    )
    consumer.subscribe([TOPIC])
    print(f"[consumer] subscribed to '{TOPIC}'. Waiting for predictions...")

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"[consumer] error: {msg.error()}")
                continue
            try:
                rec = json.loads(msg.value().decode("utf-8"))
            except Exception as exc:
                print(f"[consumer] bad payload: {exc}")
                continue

            ts = rec.get("ts", "?")
            temp = rec.get("temp")
            pred = rec.get("pred_next_hour_temp")
            delta = rec.get("pred_delta", 0.0)
            arrow = "UP" if rec.get("pred_direction") == 1 else "DOWN"
            print(
                f"[{ts}] temp={temp:5.2f}C  ->  next_hour={pred:5.2f}C  "
                f"(delta={delta:+.2f}, {arrow})"
            )
    except KeyboardInterrupt:
        print("\n[consumer] stopping.")
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
