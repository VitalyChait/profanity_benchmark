# YouthEscalateBench Data Lifecycle & Corpus Report

**Benchmark Version:** `0.1.2`  
**Report Generated:** `2026-08-28 18:34:45 UTC`  
**Governance & Safety Status:** 🟢 All Data Stages Validated & Governance Gate Passed

---

## 1. Executive Data Summary

| Pipeline Stage | Process Description | Key Artifact / Metric | Status |
| :--- | :--- | :--- | :---: |
| **1. Source Audit** | Governance & License Verification | `25` Approved Sources (100% compliant) | 🟢 PASSED |
| **2. Ingestion** | Multi-Format Ingestion to Parquet | `103,400` Ingested Conversations | 🟢 PASSED |
| **3. Redaction** | PII Detection & Safe Harbor Scrubbing | `66,261` PII Entities Sanitized | 🟢 PASSED |
| **4. Threading** | DAG Topology & Temporal Ordering | `0` Causal Violations (100% Valid DAG) | 🟢 PASSED |
| **5. Sampling** | Quota Sampling & MinHash Dedup | `49` Exact Dupes, `1577779` Near-Dupes Pruned | 🟢 PASSED |
| **6. Adjudication** | Consensus Adjudication & Gold Freeze | `6120` Gold Labels Frozen | 🟢 PASSED |
| **7. Splitting** | Zero-Leakage Split (Train/Dev/Test) | Train: `2,502` | Dev: `1,251` | Test: `1,251` | 🟢 PASSED |

---

## 2. Source Governance & Legal Audit

- **Gate Status:** `PASSED`
- **Coverage:** `100.0%` of evaluated corpora audited with legal sign-off.
- **Audited Academic & Curated Corpora:**
  - `wikiconv_wikidetox`
  - `contextual_abuse_dataset`
  - `convotox`
  - `gametox`
  - `minorbench`
  - `davidson`
  - `wildchat`
  - `lmsys_chat_1m`
  - `personachat`
  - `generic`
  - `flat_joiner`
  - `conversations_gone_awry_wikipedia`
  - `conversations_gone_awry_cmv`
  - `lmsys_toxic_chat_train`
  - `lmsys_toxic_chat_test`
  - `davidson_hate_speech`
  - `dynabench_hate_speech`
  - `hatexplain`
  - `tweeteval_offensive`
  - `tweeteval_hate`
  - `profanity_en_lexicon`
  - `google_profanity_words`
  - `dsojevic_profanity_list`
  - `hurtlex_en`
  - `hatecheck_lexicon`

- **Regulatory Compliance Framework:**
  - **COPPA (Children's Online Privacy Protection Act, 15 U.S.C. §§ 6501–6506):** Strict de-identification of all underage user attributes.
  - **GDPR-K (General Data Protection Regulation Art. 8):** De-identification and pseudonymization protocols verified.
  - **UK Age Appropriate Design Code (AADC):** Privacy-by-default safeguards adhered to.
  - **IRB Ethics Protocol:** Exemption/approval guidelines documented in [`docs/irb_ethics_package.md`](https://github.com/VitalyChait/profanity_benchmark/blob/master/docs/irb_ethics_package.md).

---

## 3. Ingestion & Preprocessing

- **Total Multi-Turn Dialogues:** `103,400`
- **Canonical Storage Format:** Columnar Apache Parquet with Snappy compression and strict Pydantic schemas.
- **Platform Style Coverage:** Group Chat, Direct Messaging (DM), Forum Threads, and Social Feeds.

---

## 4. Privacy & PII Redaction

- **Total Conversations Audited:** `103,400`
- **Total PII Hits Neutralized:** `66,261`
- **Redacted Entity Classes:** Direct identifiers (email addresses, phone numbers, IP addresses, full legal names, social handles).
- **Replacement Standard:** Safe Harbor placeholder tokens (e.g. `[EMAIL]`, `[PHONE]`, `[USERNAME]`).

---

## 5. Thread Topology & Causal Validity

- **Causal Inconsistencies Detected:** `0`
- **Reconstruction Engine:** Turn-level directed acyclic graph (DAG) reconstruction.
- **Temporal Monotonicity:** Every conversational turn strictly references prior historical turns with non-decreasing timestamps.

---

## 6. Deduplication & Quota Sampling

- **Exact Duplicate Groups Pruned:** `49`
- **MinHash LSH Near-Duplicate Clusters Identified:** `1577779` (Jaccard similarity threshold >= 0.8)
- **Sampling Tier Allocations:**

| Tier | Available Pool | Target Quota | Selected | Gap |
| :--- | :---: | :---: | :---: | :---: |
| **Fixture** | 4 | 100 | **4** | 96 |
| **Functional** | 20 | 2,000 | **20** | 1,980 |
| **Live** | 0 | 1,000 | **0** | 1,000 |
| **Organic** | 103,396 | 4,000 | **4,000** | 0 |
| **Staged** | 0 | 2,000 | **0** | 2,000 |
| **Synthetic** | 980 | 3,000 | **980** | 2,020 |

---

## 7. Consensus Adjudication & Gold Label Freeze

- **Input Turn Annotations:** `6120`
- **Gold Frozen Labels:** `6120`
- **Freeze Timestamp:** `2026-08-27T17:59:49.327858+00:00`
- **Correction Policy:** `issue_correction_manifest_for_label_changes`
- **Manifest Path:** [`reports/data/gold_freeze_manifest.yaml`](data/gold_freeze_manifest.yaml)

---

## 8. Zero-Leakage Data Partitioning

- **Train Partition:** `2,502` conversations (50.0%)
- **Dev Partition:** `1,251` conversations (25.0%)
- **Test Partition:** `1,251` conversations (25.0%)
- **Leakage Prevention:** Group-split on `conversation_id` and disjoint speaker IDs guarantees zero turn or speaker contamination across train/dev/test.

---

## 9. Exported Stage Artifacts

- **Source Audit:** [`reports/data/audit_report.yaml`](data/audit_report.yaml)
- **PII Audit:** [`reports/data/pii_report.yaml`](data/pii_report.yaml)
- **Topology Report:** [`reports/data/topology_report.yaml`](data/topology_report.yaml)
- **Quota Report:** [`reports/data/quota_report.yaml`](data/quota_report.yaml)
- **Gold Manifest:** [`reports/data/gold_freeze_manifest.yaml`](data/gold_freeze_manifest.yaml)
- **Onset Dynamics:** [`reports/data/onset_metrics.yaml`](data/onset_metrics.yaml)
