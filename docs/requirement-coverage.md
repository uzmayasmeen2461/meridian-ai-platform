# Meridian AI Requirement Coverage

Assignment ID: `Fullstack-ClaudeGemini-UsageConnector-v1`

## Part A: Usage and Admin Service

| Requirement | Status | Evidence |
| --- | --- | --- |
| Ingest Claude and Gemini exports into one model | Complete | `backend/app/ingest`, `backend/app/domain/models.py`, ingestion tests |
| Attribute usage to users and groups through directory | Complete | Directory ingestion and attribution tests in `backend/tests/test_ingestion.py` |
| Reconcile Claude usage and cost without double-counting | Complete | Claude cost reconciliation tests, one normalized usage fact grain |
| Map Gemini billing SKUs to input/output tokens | Complete | Gemini SKU pairing and total token tests |
| Expose API for usage/cost by platform, group, week, and top users | Complete | FastAPI routes under `/api/usage/*`, API tests |
| Expose capability controls, persisted | Complete | `/api/capabilities`, `CapabilityOverride`, API and authorization tests |
| Enforce authorization server-side | Complete | `AuthorizationService`, API tests across dev/staging/prod |
| Provide minimal admin page | Complete | React dashboard in `frontend/` |
| Test mapping backend-first | Complete | Backend test suite covers mapping, totals, idempotency, authorization |

## Part B: Assistant Connector

| Requirement | Status | Evidence |
| --- | --- | --- |
| MCP server over Part A service | Complete | `backend/app/mcp_server.py` |
| Four required tools only | Complete | `usage_summary`, `top_users`, `capability_status`, `set_capability`; tested in `test_mcp_server.py` |
| Scoped identity at server startup | Complete for local demo | Uses `MERIDIAN_MCP_USER_ID`; documented as non-production auth |
| Team leads see own group only | Complete | MCP and authorization tests |
| Platform admins see every group | Complete | API, MCP, provisioning tests |
| `set_capability` requires admin/write scope | Complete | YAML-driven tests across environments |
| Structured denial with no partial protected data | Complete | API and MCP denial tests |
| Honor per-group capability controls | Complete | `usage-connector` gate tested for MCP operations |
| Register/distribute on Claude Desktop | Complete as local package template | `packaging/claude-desktop/manifest.json` and instructions |
| Register/distribute on Gemini CLI | Complete as local extension template | `packaging/gemini-cli/meridian-usage/gemini-extension.json` |
| Recording or transcript | Prepared | `docs/demo-walkthrough.md` |
| Automated provisioning for dev/staging/prod | Complete | `python -m app.cli provision ...`, tests, CI workflow |
| Team-lead note | Prepared | `docs/team-lead-note.md` |

## Submission Readiness

| Item | Status |
| --- | --- |
| GitHub repo code | Ready after excluding local generated artifacts |
| README | Complete |
| Transcript template | Complete |
| Team-lead note | Complete |
| CI workflow | Complete |
| Known limitations documented | Complete |

