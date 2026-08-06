"""Baseline moderation scorers."""

from abc import ABC, abstractmethod
from pathlib import Path

from youth_escalate_bench.schemas.inference import InferenceRequest, ModelOutput


class ModerationScorer(ABC):
    name: str

    @abstractmethod
    def predict(self, request: InferenceRequest) -> ModelOutput:
        """Score a single causal-prefix inference request."""


def load_lexicon(path: Path | str) -> list[str]:
    path = Path(path)
    terms: list[str] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            term = line.strip().lower()
            if term and not term.startswith("#"):
                terms.append(term)
    return terms


class LexiconScorer(ModerationScorer):
    name = "lexicon_raw"

    def __init__(self, lexicon: list[str]) -> None:
        self._lexicon = lexicon

    def predict(self, request: InferenceRequest) -> ModelOutput:
        text = request.causal_prefix()[-1].text.lower()
        hits = sum(1 for term in self._lexicon if term in text)
        prob = min(1.0, hits / 3.0)
        return _score_to_output(prob)


class NormalizedLexiconScorer(ModerationScorer):
    name = "lexicon_normalized"

    def __init__(self, lexicon: list[str]) -> None:
        self._lexicon = lexicon

    def predict(self, request: InferenceRequest) -> ModelOutput:
        import re

        text = request.causal_prefix()[-1].text.lower()
        normalized = re.sub(r"[^a-z0-9\s]", "", text)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        hits = sum(1 for term in self._lexicon if term in normalized)
        prob = min(1.0, hits / 3.0)
        return _score_to_output(prob)


class CharNgramTfidfScorer(ModerationScorer):
    """Lightweight char n-gram TF-IDF + logistic-style linear scorer."""

    name = "char_ngram_tfidf"

    def __init__(self, lexicon: list[str], ngram_range: tuple[int, int] = (3, 5)) -> None:
        self._lexicon = lexicon
        self._ngram_range = ngram_range
        # Positive weights for toxic n-grams derived from lexicon terms
        self._weights: dict[str, float] = {}
        for term in lexicon:
            for n in range(ngram_range[0], ngram_range[1] + 1):
                for i in range(max(1, len(term) - n + 1)):
                    ng = term[i : i + n]
                    if len(ng) >= ngram_range[0]:
                        self._weights[ng] = self._weights.get(ng, 0.0) + 1.0

    def _ngrams(self, text: str) -> set[str]:
        normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
        normalized = " ".join(normalized.split())
        result: set[str] = set()
        for n in range(self._ngram_range[0], self._ngram_range[1] + 1):
            for i in range(max(0, len(normalized) - n + 1)):
                result.add(normalized[i : i + n])
        return result

    def predict(self, request: InferenceRequest) -> ModelOutput:
        text = request.causal_prefix()[-1].text
        grams = self._ngrams(text)
        score = sum(self._weights.get(g, 0.0) for g in grams)
        prob = min(1.0, score / 5.0)
        return _score_to_output(prob)


class ContextLexiconScorer(ModerationScorer):
    """Lexicon over full causal prefix (context-aware baseline)."""

    name = "lexicon_full_context"

    def __init__(self, lexicon: list[str]) -> None:
        self._lexicon = lexicon

    def predict(self, request: InferenceRequest) -> ModelOutput:
        combined = " ".join(t.text for t in request.causal_prefix()).lower()
        hits = sum(1 for term in self._lexicon if term in combined)
        prob = min(1.0, hits / 3.0)
        return _score_to_output(prob)


def _score_to_output(prob: float) -> ModelOutput:
    from youth_escalate_bench.schemas.taxonomy import SEVERITY_LEVELS

    if prob < 0.25:
        sev = {s: 0.0 for s in SEVERITY_LEVELS}
        sev["benign"] = 1.0
    elif prob < 0.5:
        sev = {s: 0.0 for s in SEVERITY_LEVELS}
        sev["coarse_monitor"] = 1.0
    elif prob < 0.75:
        sev = {s: 0.0 for s in SEVERITY_LEVELS}
        sev["actionable"] = 1.0
    else:
        sev = {s: 0.0 for s in SEVERITY_LEVELS}
        sev["urgent"] = 1.0

    return ModelOutput(
        harm_probability=prob,
        severity_probabilities=sev,
        target_type={"individual_peer": prob * 0.5},
        escalation_state={"stable": 1.0 - prob, "escalating": prob},
    )


def build_default_scorers(lexicon_path: Path | str) -> dict[str, ModerationScorer]:
    lexicon = load_lexicon(lexicon_path)
    scorers: list[ModerationScorer] = [
        LexiconScorer(lexicon),
        NormalizedLexiconScorer(lexicon),
        CharNgramTfidfScorer(lexicon),
        ContextLexiconScorer(lexicon),
    ]
    return {s.name: s for s in scorers}
