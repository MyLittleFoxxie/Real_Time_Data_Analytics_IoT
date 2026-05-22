# ENGR 5785G — Assignment 1

## Real-Time Streaming with Apache Kafka

---

## Overview

Build a small real-time streaming application using Apache Kafka. Your app will read rows from a public dataset, stream them through Kafka as live events, apply a simple machine learning prediction (e.g., linear regression) using the Streams API, and publish results to an output topic. The goal is to show a complete, running pipeline from raw data to live ML inference.

---

## Step 1: Choose Your Language & Streams Library

The stream processing component must use a dedicated Streams API. Pick one of the following options:

| Option A: Python + Faust                                                                                                                                                                                       | Option B: Java or Scala + Kafka Streams                                                                                                                                                               |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Library:** `faust-streaming` (`pip install faust-streaming`) — Faust is the Python equivalent of Kafka Streams. It gives you agents, topics as streams, and stateful tables using the same conceptual model. | **Library:** Kafka Streams (Apache native) — the official JVM streams library. Use `StreamsBuilder` to define a topology: source → filter/map → sink. Maven/Gradle: `kafka-streams` + `weka` / `dl4j` |
| `pip install faust-streaming scikit-learn`                                                                                                                                                                     | `KStream<> raw = builder.stream("raw-data");`                                                                                                                                                         |
| Faust app → `@app.agent(raw_topic)` → run ML model → send to `predictions_topic`                                                                                                                               | `raw.mapValues(record -> predict(record)).to("predictions");`                                                                                                                                         |

---

## Step 2: Pick a Dataset

Choose one of the datasets below, or propose your own:

| #   | Dataset                   | Source                                      | ML Task                       |
| --- | ------------------------- | ------------------------------------------- | ----------------------------- |
| A   | TIHM: Dementia Monitoring | nature.com/articles/s41597-023-02519-y      | Detect agitation in PWD       |
| B   | Air Quality (UCI)         | archive.ics.uci.edu/dataset/360             | Predict CO concentration      |
| C   | Credit Card Fraud         | kaggle.com/datasets/mlg-ulb/creditcardfraud | Flag fraudulent transactions  |
| D   | Bike Sharing (UCI)        | archive.ics.uci.edu/dataset/275             | Predict hourly rental count   |
| E   | Weather: Oshawa/Toronto   | climate.weather.gc.ca                       | Predict next-hour temperature |

Train your ML model **offline** on the full dataset before the demo. During the demo, replay rows one by one as live Kafka events at ~1 row/second.

---

## Step 3: What to Build

Your application must have **three components** running concurrently:

| Producer                                                                                                        | Streams Processor                                                                                                                                                           | Output Consumer                                                                                                           |
| --------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Reads rows from your dataset and publishes each one as a JSON message to the `raw-data` topic at ~1 row/second. | Uses Faust (Python) or Kafka Streams (Java/Scala) to consume `raw-data`, run the pre-trained ML model on each record, and produce a new message to the `predictions` topic. | A simple consumer that reads from `predictions` and prints each result to the console in a readable format as it arrives. |

---

## Step 4: ML Model

The ML component does not need to be sophisticated. A logistic regression, decision tree, or random forest is perfectly appropriate. Train it offline, save the model file (`.pkl`, `.joblib`, or equivalent), and load it inside your Streams processor.

---

## Deliverables

| Item              | Description                                                                                            | Points  |
| ----------------- | ------------------------------------------------------------------------------------------------------ | ------- |
| Working pipeline  | All three components run together; predictions appear in real time                                     | 35      |
| Streams API usage | Processor correctly uses Faust agents or Kafka Streams topology — not a plain consumer loop            | 20      |
| ML model          | Trained offline, loaded in processor, prediction in every output message; README reports accuracy + F1 | 20      |
| README.md         | Dataset chosen, setup steps, how to run each component, which Streams library used, model performance  | 15      |
| Video demo        | 2–3 min recording showing all three terminals running simultaneously with predictions printing live    | 10      |
| **TOTAL**         |                                                                                                        | **100** |

---

## Submission

Push everything to a **public GitHub repository** and submit the link on the course portal. Your repo must contain:

- All source code (producer, streams processor, output consumer)
- The trained model file (`.pkl`, `.joblib`, or equivalent)
- Dependency file: `requirements.txt` (Python) or `pom.xml` / `build.gradle` (Java/Scala)
- `README.md` as described above
- A link to your video demo (YouTube unlisted, Google Drive, or OneDrive)

---

## Tips

- **Faust (Python):** Run `faust -A app worker -l info` to start the Streams processor. Faust handles the consumer loop internally — you just define agents.
- **Kafka Streams (Java):** Build a `StreamsBuilder` topology once and call `streams.start()`. It runs continuously in its own threads.
- Train your model in a separate notebook first. Once you are happy with accuracy, export it and import it in the processor with a single `load()` call.
- Test the producer alone first and confirm messages appear in the Confluent Cloud topic viewer before starting the processor.
- **For the video:** Open three terminals side-by-side (producer, streams processor, output consumer). Start them in order and let it run for 60–90 seconds.
- **For the video:** Open three terminals side-by-side (producer, streams processor, output consumer). Start them in order and let it run for 60–90 seconds.
