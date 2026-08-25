# YouthEscalateBench Evaluator Container Manual

This directory contains the containerization specification (`Dockerfile`) for the **YouthEscalateBench Private Evaluator & Real-Time Moderation Service**.

---

## 📌 What is this Dockerfile Used For?

The `Dockerfile` packages YouthEscalateBench into a lightweight, hermetic, and reproducible container exposing a standardized **HTTP `POST /predict`** interface on port `8080`.

### Core Use Cases

| Use Case | Description | Why Docker is Essential |
| :--- | :--- | :--- |
| **1. Private Benchmark Submission & Grading** | Automated evaluation of participant models in competitive benchmarks (e.g., NeurIPS, ACL, Kaggle-style challenges). | Ensures models run in identical environments without dependency conflicts or host contamination. |
| **2. Zero-Leakage Air-Gapped Evaluation** | Evaluating models on hidden/unseen test splits with complete network isolation (`--network none`). | Guarantees participant models cannot exfiltrate hidden benchmark test data or make unauthorized external API calls. |
| **3. Production Real-Time Moderation Microservice** | Deploying chat safety moderation in gaming chats, youth forums, or messaging platforms as a standalone microservice. | Plug-and-play deployment onto Kubernetes, AWS ECS, Google Cloud Run, or Docker Compose. |
| **4. Reproducible Baseline Benchmarking** | Running lexical, subword TF-IDF, and rule-based safeguard baselines locally with zero environment drift. | Avoids Python version mismatches and OS-specific dependency issues. |

---

## 🚀 Quickstart & Example Workflow

### 1. Build the Evaluator Container

Execute the build command from the **repository root**:

```bash
docker build -t youth-escalate-evaluator -f docker/evaluator/Dockerfile .
```

---

### 2. Run the Container

#### Standard Local Execution:
```bash
docker run --rm -p 8080:8080 --name yeb-service youth-escalate-evaluator
```

#### Air-Gapped Zero-Leakage Mode (Network Disabled):
```bash
docker run --rm -p 8080:8080 --network none --name yeb-service youth-escalate-evaluator
```
> **Note:** In `--network none` mode, no external connections are permitted. All models rely strictly on local weights and rule sets.

---

### 3. Example Inference Request & Response

#### Example `curl` Request

Send a causal prefix conversation turn to `http://localhost:8080/predict`:

```bash
curl -X POST http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{
    "benchmark_version": "0.1.0",
    "conversation_id": "conv_gaming_042",
    "current_turn_id": "turn_3",
    "platform_style": "gaming_chat",
    "language_mode": "english",
    "task": "current_harm",
    "turns": [
      {
        "turn_id": "turn_1",
        "speaker_id": "player_alpha",
        "role": "user",
        "text": "Nice shot!",
        "relative_time": "0s"
      },
      {
        "turn_id": "turn_2",
        "speaker_id": "player_beta",
        "role": "user",
        "text": "Thanks, let us push mid lane.",
        "relative_time": "+15s"
      },
      {
        "turn_id": "turn_3",
        "speaker_id": "player_gamma",
        "role": "user",
        "text": "you are absolute trash uninstall this game now",
        "relative_time": "+22s"
      }
    ]
  }'
```

#### Example Output Response (JSON)

```json
{
  "harm_probability": 0.95,
  "harm_types": {
    "harassment_bullying": 0.92,
    "hate_speech": 0.05,
    "sexual_explicit": 0.0,
    "threats_violence": 0.08,
    "self_harm": 0.0
  },
  "severity_probabilities": {
    "benign": 0.05,
    "low": 0.15,
    "medium": 0.60,
    "high": 0.20
  },
  "target_type": {
    "individual": 0.95,
    "group": 0.05,
    "unspecified": 0.0
  },
  "escalation_state": {
    "escalating": 0.88,
    "stable": 0.10,
    "deescalating": 0.02
  },
  "forecast_next_two_turns": 0.75,
  "evidence_turn_ids": ["turn_3"],
  "abstain": false
}
```

---

### 4. Python Client Example

```python
import requests

url = "http://localhost:8080/predict"
payload = {
    "benchmark_version": "0.1.0",
    "conversation_id": "conv_chat_101",
    "current_turn_id": "t2",
    "platform_style": "group_chat",
    "language_mode": "english",
    "task": "current_harm",
    "turns": [
        {"turn_id": "t1", "speaker_id": "user_a", "role": "user", "text": "Are you joining the game tonight?", "relative_time": "0s"},
        {"turn_id": "t2", "speaker_id": "user_b", "role": "user", "text": "Yeah, see you there!", "relative_time": "+5s"}
    ]
}

response = requests.post(url, json=payload)
data = response.json()

print(f"Status: {response.status_code}")
print(f"Harm Probability: {data['harm_probability']}")
print(f"Severity Breakdown: {data['severity_probabilities']}")
```

---

## 🔒 Security & Benchmark Integrity Rules

1. **Causal Prefix Guarantee**: The request schema enforces that `current_turn_id` is the final turn in `turns`. Future turns are strictly disallowed to prevent lookahead data leakage.
2. **No Text Logging**: The server suppresses text request logging to preserve user privacy and comply with child safety governance frameworks (COPPA / GDPR-K).
3. **Graceful Abstention**: In case of malformed data or inference exceptions, the server returns HTTP `422` with a standardized `ModelOutput.create_abstention_output()`.
