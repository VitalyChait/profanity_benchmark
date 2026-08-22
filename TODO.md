# YouthEscalateBench — End-of-Project & Pre-Release TODOs

This file tracks critical pending actions, compliance requirements, and validation gates that must be completed prior to public release, benchmark publication (e.g., NeurIPS / ACL / EMNLP), or dataset redistribution.

---

## ⚠️ 1. Mandatory Legal & License Re-Audit (CRITICAL)

> [!IMPORTANT]
> **Source audits must be performed again prior to any public release or external redistribution.**
> 
> During early development, all datasources in [`configs/source_registry.yaml`](configs/source_registry.yaml) and [`docs/license_audit_worksheet.md`](docs/license_audit_worksheet.md) were approved under a **personal, non-commercial research use** exemption.

Before releasing datasets, artifacts, or benchmark splits publicly:
- [ ] **Re-run the complete license audit** for every ingested source:
  - **WikiConv / WikiDetox**: Verify CC-BY-SA redistribution and attribution compliance per release.
  - **Contextual Abuse Dataset (CAD)**: Verify redistribution terms and academic licensing constraints.
  - **ConvoTox**: Obtain written redistribution approval from authors before publishing Reddit tree extracts.
  - **GameTox**: Confirm whether shared-task terms permit public derived benchmark redistribution.
  - **MinorBench**: Confirm taxonomy-only vs data derivative usage.
  - **Davidson / Tweet Sources**: Verify Twitter/X Developer Agreement data redistribution policies (IDs only vs text).
  - **LMSYS-Chat-1M / WildChat**: Confirm exclusion or strict adherence to non-redistribution terms.
- [ ] Update legal reviewer sign-off table in [`docs/license_audit_worksheet.md`](docs/license_audit_worksheet.md) with institutional legal/PI approval.
- [ ] Re-run automated audit gate:
  ```bash
  yeb audit-sources --registry configs/source_registry.yaml
  ```

---

## 2. Institutional Ethics & IRB Review

- [ ] Submit [`docs/irb_ethics_package.md`](docs/irb_ethics_package.md) to the university/institutional review board.
- [ ] Convene expert taxonomy review panel (cyberbullying researcher, linguist, trust & safety specialist) to formally sign off on [`docs/annotation_guidelines_v0.1.md`](docs/annotation_guidelines_v0.1.md).
- [ ] Finalize youth advisory co-design protocol ([`docs/youth_advisory_protocol.md`](docs/youth_advisory_protocol.md)) if engaging minor panels (13–17), or fallback to 18–24 demographic.

---

## 3. Annotation & Data Quality Gates

- [ ] **Annotator Recruitment**: Onboard human annotators following the wellness protocol in [`docs/annotator_wellness_protocol.md`](docs/annotator_wellness_protocol.md).
- [ ] **Pilot Phase (500 conversations)**:
  - Run triple annotation on the pilot batch (`annotate_export` stage).
  - Confirm agreement metrics meet the target gate (Krippendorff $\alpha \ge 0.80$ on severity, $\ge 90\%$ actionable agreement) via `metrics/agreement.py`.
- [ ] **Production Adjudication**:
  - Run `yeb run --stage adjudicate` to resolve disagreements and generate frozen gold manifests.
  - Perform independent PII audit on all final text spans.

---

## 4. Preregistration & Model Evaluation

- [ ] **OSF Preregistration Freeze**:
  - Pin the exact baseline model panel, versions, decoding parameters, and checkpoint IDs in [`docs/preregistration.md`](docs/preregistration.md) *before* evaluating on hidden test splits.
- [ ] **Neural & Frontier Baselines**:
  - Implement and evaluate open guardrails (Llama-Guard 3, WildGuard).
  - Implement and evaluate frontier LLMs (GPT-4o, Claude 3.5 Sonnet, Llama 3.1 70B/8B).
  - Implement perspective / commercial moderation API baselines.
- [ ] **Causal & Onset Evaluation**:
  - Execute evaluations across all 3 context conditions (`current_turn_only`, `prev_plus_current`, `full_prefix`).
  - Compute onset lag (lag 0, 1, 2 detection recall) and algospeak robustness degradation.

---

## 5. Submission & Public Artifacts

- [ ] Generate submission tables and error analysis bundles with `yeb run --stage report`.
- [ ] Finalize NeurIPS / ACL documentation:
  - [`docs/benchmark_card.md`](docs/benchmark_card.md)
  - [`docs/datasheet.md`](docs/datasheet.md)
  - [`metadata/croissant.json`](metadata/croissant.json)
- [ ] Build and test the private `/predict` evaluator Docker container (`docker/evaluator/Dockerfile`).
