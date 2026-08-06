"""Private benchmark evaluator HTTP server (/predict interface)."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from youth_escalate_bench.baselines.scorers import ModerationScorer, build_default_scorers
from youth_escalate_bench.schemas.inference import InferenceRequest, ModelOutput


class PredictHandler(BaseHTTPRequestHandler):
    scorer: ModerationScorer | None = None
    lexicon_path: Path = Path("configs/profanity_lexicon.txt")

    def do_POST(self) -> None:
        if self.path != "/predict":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            request = InferenceRequest.model_validate(data)
            scorer = self.scorer or build_default_scorers(self.lexicon_path)["lexicon_raw"]
            output = scorer.predict(request)
            response = output.model_dump()
            payload = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:
            abstain = ModelOutput.create_abstention_output()
            payload = json.dumps({"error": str(e), "output": abstain.model_dump()}).encode("utf-8")
            self.send_response(422)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress request text logging (private benchmark policy)
        return


def serve(host: str = "127.0.0.1", port: int = 8080, lexicon_path: Path | None = None) -> None:
    if lexicon_path:
        PredictHandler.lexicon_path = lexicon_path
    server = ThreadingHTTPServer((host, port), PredictHandler)
    print(f"YouthEscalateBench evaluator listening on http://{host}:{port}/predict")
    server.serve_forever()
