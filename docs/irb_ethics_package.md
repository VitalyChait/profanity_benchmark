# IRB / Ethics Submission Package Draft

**Project:** YouthEscalateBench — Dynamic Multi-Turn Youth-Safeguarding Benchmark  
**Version:** 0.1.2 draft  
**Status:** For institutional review — not yet submitted

## 1. Study summary

We will construct and release a research benchmark for evaluating whether automated
moderation systems can detect harmful peer-to-peer interactions as they emerge across
multi-turn conversations. The benchmark evaluates **detection**, not automated
punishment or youth-facing chatbot responses.

## 2. Human subjects activities

| Activity | Population | Risk level |
|----------|------------|------------|
| Adult annotation of harmful text | 18+ trained annotators | Moderate content exposure |
| Adult-staged peer dialogue | Adults 18–24 | Moderate — scripted scenarios |
| Youth advisory co-design | 13–17 with guardian consent | Low — sanitized scenarios only |
| Public dataset ingestion | No direct contact | Minimal — licensed public text |

Youth advisors **do not** produce abuse, assign moderation labels, or review severe
sexual content.

## 3. Recruitment and consent

- **Adult annotators:** employment contract, informed consent, wellness briefing.
- **Staged dialogue actors (18–24):** consent + scenario briefing; no minor recruitment
  for harmful content authorship.
- **Youth advisors (13–17):** guardian consent + youth assent; IRB-approved protocol
  for sanitized material review only.

**Fallback:** If youth IRB is unavailable, use 18–24 advisors and narrow claims to
"youth-oriented communication settings."

## 4. Data handling

- No scraping of private Discord, Roblox, school, or minor-only spaces.
- Two-pass PII detection + human review before any release.
- Exact timestamps, contact info, and recoverable identifiers removed.
- Tombstone deletion propagated on source removal.
- Private test labels access-controlled; aggregate metrics only in public reports.

## 5. Annotator protections

- Informed warnings before exposure.
- Paid breaks, exposure limits, opt-out without penalty.
- Wellness resources and reassignment options.
- No performance pressure tied to model agreement.

## 6. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Annotator distress | Wellness protocol, exposure limits |
| PII leakage | Two-pass redaction + independent audit |
| Benchmark misuse for surveillance | Responsible-AI documentation, license tiers |
| Misrepresenting youth authorship | Explicit source-tier provenance |

## 7. Benefits

Improved early detection of cyberbullying and coded harm in peer chat; reproducible
evaluation for researchers and trust-and-safety practitioners.

## 8. Documents to attach at submission

- [ ] Threat model (`docs/threat_model.md`)
- [ ] Annotation guidelines (`docs/annotation_guidelines_v0.1.md`)
- [ ] Source registry (`configs/source_registry.yaml`)
- [ ] License audit worksheet (`docs/license_audit_worksheet.md`)
- [ ] Youth advisor protocol (draft when IRB requests)
- [ ] Data retention and deletion policy

## 9. Determination requested

Expedited or full board review for:

1. Adult annotation of licensed/staged harmful peer text.
2. Optional youth advisory panel (sanitized materials only).
