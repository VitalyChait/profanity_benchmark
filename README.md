# YouthEscalateBench

Dynamic multi-turn youth safety moderation benchmark for causal cyberbullying and escalation detection. Includes a 12-stage pipeline, 14 audited research datasets & lexicons (79k+ turns, 2,508 unified profanity terms), 12 evaluated LLMs/baselines across 3 context conditions, automated difficulty ranking, autonomous agentic discovery, real-time interactive service dashboard, and 100% test pass rate (119/119).

## Quick Start
```bash
pip install -e ".[dev]"
python main.py --all --extended-report
```

## Running as a Service & Interactive Dashboard
Start the private `/predict` evaluator server and open the live analysis dashboard:
```bash
yeb serve --host 127.0.0.1 --port 8080
```
Open **`http://localhost:8080/dashboard`** in your browser to interactively analyze:
- 📊 **Visual Analytics**: 300 DPI multi-panel heatmaps, context trajectories, and leaderboards.
- 🔍 **Failure Case Inspector**: Search and filter false positives vs. false negatives with full dialogue context.
- 🎯 **Hard-Sample Ranking**: Top difficult conversational turns and word vulnerability index.
- ⚡ **Live Prediction Playground**: Interactively test moderation queries against live `/predict`.

## Useful CLI Commands
- `yeb serve`: Launch evaluator microservice and web dashboard (`/dashboard`).
- `yeb difficulty-ranking`: View hardest conversational turns and word vulnerability index.
- `yeb profanity-check <term>`: Inspect severity (Level 1–4) and categories for any slang or term.
- `yeb lexicon-stats`: Display breakdown across 2,508 terms and contributing sources.
- `yeb urban-dict <term>`: Query colloquial definitions from Urban Dictionary API.
- `yeb agent-discover`: Run autonomous agentic discovery loop to scout and verify new slang.
- `yeb audit-pii`: Spot-check sample conversations for residual PII entities.
- `yeb create-snapshot`: Package quarterly release archives with Croissant metadata and SHA256.

See **[README_extended.md](README_extended.md)** for full documentation, metrics, and architecture.
