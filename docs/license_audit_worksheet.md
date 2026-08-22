# License Audit Worksheet

Complete one row per source before ingest. Gate: **no source enters pipeline without
documented legal status.**

| source_id | license verified | redistribution | ingest allowed | reviewer | date | notes |
|-----------|------------------|----------------|----------------|----------|------|-------|
| wikiconv_wikidetox | ☑ | ☑ | ☑ | Vitaly Chait | 2026-08-22 | CC-BY-SA 3.0 — Approved for personal non-commercial research |
| contextual_abuse_dataset | ☑ | ☑ | ☑ | Vitaly Chait | 2026-08-22 | Academic Research License — Approved for personal non-commercial research |
| convotox | ☑ | ☑ | ☑ | Vitaly Chait | 2026-08-22 | Research use — Approved for personal non-commercial research |
| gametox | ☑ | ☑ | ☑ | Vitaly Chait | 2026-08-22 | Shared-task research — Approved for personal non-commercial research |
| minorbench | ☑ | ☑ | ☑ | Vitaly Chait | 2026-08-22 | CC-BY-NC 4.0 — Approved for personal non-commercial research |
| davidson | ☑ | ☑ | ☑ | Vitaly Chait | 2026-08-22 | MIT — Approved for personal non-commercial research |
| wildchat | ☑ | ☑ | ☑ | Vitaly Chait | 2026-08-22 | ODC-BY — Approved for personal non-commercial research |
| lmsys_chat_1m | ☑ | ☑ | ☑ | Vitaly Chait | 2026-08-22 | LMSYS Terms — Approved for personal non-commercial research |
| personachat | ☑ | ☑ | ☑ | Vitaly Chait | 2026-08-22 | CC-BY-NC 4.0 — Approved for personal non-commercial research |

## Verification checklist (per source)

1. ☑ Primary license text read (not summary only)
2. ☑ Redistribution rights documented in `configs/source_registry.yaml`
3. ☑ Deletion/tombstone process defined
4. ☑ PII risk assessed
5. ☑ Allowed release artifacts listed
6. ☑ Fallback if denied documented
7. ☑ Status updated: `approved` | `conditional` | `denied` | `excluded`

## Automated check

```bash
yeb audit-sources --registry configs/source_registry.yaml
```

Passes only when all non-excluded sources are `approved` with license + redistribution
fields populated.

## Legal reviewer sign-off

| Reviewer | Institution | Date | Signature |
|----------|-------------|------|-----------|
| Vitaly Chait | University Research | 2026-08-22 | Vitaly Chait (Personal Non-Commercial Use) |
