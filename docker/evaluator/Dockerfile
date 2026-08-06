# Evaluator container for private /predict submissions
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY configs/profanity_lexicon.txt ./configs/profanity_lexicon.txt

RUN pip install --no-cache-dir .

# Network disabled at runtime by orchestrator; no external deps at runtime
EXPOSE 8080
CMD ["yeb", "serve", "--host", "0.0.0.0", "--port", "8080"]
