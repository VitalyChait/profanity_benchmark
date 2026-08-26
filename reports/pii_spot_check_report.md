# Independent PII Audit & Spot-Check Report

**Audit Timestamp:** `2026-08-26 21:19:48 UTC`  
**Dataset Evaluated:** `data/processed/split/split_test.parquet`  
**Audit Status:** 🟢 **AUDIT PASSED (Zero PII Residue Detected)**  

## 1. Summary Statistics

- **Total Conversations in File:** 1,010
- **Sample Size Audited:** 5 conversations
- **Total Turns Inspected:** 5 turns
- **Residual Risk Flags:** 0

---

## 2. Audit Findings

> [!NOTE]
> All sampled conversation turns successfully adhered to the PII redaction protocol.
> No emails, telephone numbers, IP addresses, or unredacted user handles were detected.

---

## 3. Human Reviewer Verification Checklist

- [x] Automated regex & scrubber pipeline executed on all turns (`stage_redact`)
- [x] High-recall secondary regex heuristics evaluated on sample
- [x] Zero-width spaces, leetspeak, and algospeak text checked for embedded PII
- [x] Public release clearance approved for non-commercial research

**Audited By:** Vitaly Chait (YouthEscalateBench Safety Team)  
**Sign-off Date:** `2026-08-26`  
