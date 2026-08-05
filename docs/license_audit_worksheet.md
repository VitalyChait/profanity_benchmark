# License Audit Worksheet

Complete one row per source before ingest. Gate: **no source enters pipeline without
documented legal status.**

| source_id | license verified | redistribution | ingest allowed | reviewer | date | notes |
|-----------|------------------|----------------|----------------|----------|------|-------|
| wikiconv_wikidetox | ☐ | ☐ | ☐ | | | CC-BY-SA — verify per release |
| contextual_abuse_dataset | ☐ | ☐ | ☐ | | | Check paper/repo license |
| convotox | ☐ | ☐ | ☐ | | | Written approval required |
| gametox | ☐ | ☐ | ☐ | | | Shared-task access |
| minorbench | ☐ | ☐ taxonomy only | ☐ | | | Not conversation backbone |
| davidson | ☐ | ☐ optional | ☐ | | | Flat tweets only |
| wildchat | ☑ excluded | ☑ denied | ☐ | | | Toxic convs removed |
| lmsys_chat_1m | ☑ excluded | ☑ denied | ☐ | | | Transfer prohibited |
| personachat | ☐ | ☐ scaffold | ☐ | | | Safe scaffold only |

## Verification checklist (per source)

1. ☐ Primary license text read (not summary only)
2. ☐ Redistribution rights documented in `configs/source_registry.yaml`
3. ☐ Deletion/tombstone process defined
4. ☐ PII risk assessed
5. ☐ Allowed release artifacts listed
6. ☐ Fallback if denied documented
7. ☐ Status updated: `approved` | `conditional` | `denied` | `excluded`

## Automated check

```bash
yeb audit-sources --registry configs/source_registry.yaml
```

Passes only when all non-excluded sources are `approved` with license + redistribution
fields populated.

## Legal reviewer sign-off

| Reviewer | Institution | Date | Signature |
|----------|-------------|------|-----------|
| | | | |
