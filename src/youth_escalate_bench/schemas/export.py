"""Export JSON Schema for benchmark contracts."""

import json
from pathlib import Path

from youth_escalate_bench.schemas.conversation import ConversationRecord
from youth_escalate_bench.schemas.inference import InferenceRequest, ModelOutput
from youth_escalate_bench.schemas.labels import AnnotationRecord


def export_all(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    schemas = {
        "inference_request": InferenceRequest.model_json_schema(),
        "model_output": ModelOutput.model_json_schema(),
        "annotation_record": AnnotationRecord.model_json_schema(),
        "conversation_record": ConversationRecord.model_json_schema(),
    }
    paths: list[Path] = []
    for name, schema in schemas.items():
        path = output_dir / f"{name}.schema.json"
        path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
        paths.append(path)
    return paths
