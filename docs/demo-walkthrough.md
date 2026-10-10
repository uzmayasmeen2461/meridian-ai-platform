# Meridian AI Demo Walkthrough and Transcript Template

Use this script for a recorded demo or as the transcript submission artifact.

## Setup

```bash
python3 -m pip install -e "backend[test]"
python3 -m app.cli bootstrap --db-url sqlite:///backend/meridian.db --starter-kit starter-kit
```

Start the backend:

```bash
MERIDIAN_DATABASE_URL=sqlite:///backend/meridian.db \
MERIDIAN_ENV=prod \
MERIDIAN_STARTER_KIT="$(pwd)/starter-kit" \
uvicorn app.main:app --app-dir backend --reload
```

Start the frontend:

```bash
cd frontend
npm install
npm run dev
```

## Demo Script

### 1. Ingestion and Health

Show:

```bash
python3 -m app.cli bootstrap --db-url sqlite:///backend/meridian.db --starter-kit starter-kit
curl http://127.0.0.1:8000/health
```

Say:

> The bootstrap command creates the SQLite schema and deterministically ingests the immutable starter-kit data. Rerunning it is idempotent.

### 2. Dashboard

Open the Vite URL.

Show:

- identity selector
- environment chip
- group selector
- period selector
- summary cards
- token and USD charts
- top users table
- capability controls

Say:

> The dashboard uses only FastAPI responses. Usage totals are SQL aggregations from normalized usage facts; it does not recompute from raw files in the UI.

### 3. Permissions

Select a platform admin:

```text
Chloe Dubois / user_533B58E6F66C98ACB833527A
```

Show that the admin can view all groups and update capabilities.

Select a team lead:

```text
Priya Nair / user_E7691888F28227066DD2FB86
```

Show that production restricts the team lead to their own group and prevents capability writes.

Say:

> Authorization is enforced by backend services, not by the frontend. Denied responses return a structured `permission_denied` shape and no protected usage data.

### 4. MCP Tool Discovery

Run:

```bash
PYTHONPATH=backend \
MERIDIAN_DATABASE_URL=sqlite:///backend/meridian.db \
MERIDIAN_ENV=prod \
MERIDIAN_STARTER_KIT="$(pwd)/starter-kit" \
MERIDIAN_MCP_USER_ID=user_533B58E6F66C98ACB833527A \
python3 -m app.mcp_server
```

Use an MCP client to list tools. Expected tools:

```text
usage_summary
top_users
capability_status
set_capability
```

Say:

> The MCP server starts as a configured local user. This is appropriate for this controlled local demonstration, not production multi-user authentication.

### 5. MCP Allowed Read

Call:

```json
{
  "tool": "usage_summary",
  "arguments": {
    "group": "clinical-operations",
    "period": "last_7_days"
  }
}
```

Expected result includes Claude and Gemini platform totals plus combined totals.

### 6. MCP Denied Cross-Group Read

Restart MCP as Priya Nair:

```bash
MERIDIAN_MCP_USER_ID=user_E7691888F28227066DD2FB86
```

Call:

```json
{
  "tool": "usage_summary",
  "arguments": {
    "group": "finance",
    "period": "last_7_days"
  }
}
```

Expected result:

```json
{
  "error": "permission_denied",
  "reason": "Caller may not access the requested group.",
  "required_scope": "usage:read"
}
```

### 7. MCP Denied Write

As Priya Nair in production, call:

```json
{
  "tool": "set_capability",
  "arguments": {
    "group": "clinical-operations",
    "capability": "web-search",
    "enabled": false
  }
}
```

Expected result:

```json
{
  "error": "permission_denied",
  "reason": "Caller role is not allowed for this operation.",
  "required_scope": "capabilities:write"
}
```

### 8. Provisioning

Run:

```bash
python3 -m app.cli provision \
  --actor-user-id user_533B58E6F66C98ACB833527A \
  --db-url sqlite:///backend/meridian.db \
  --starter-kit starter-kit \
  --output-dir provisioning/rendered
```

Show generated:

```text
provisioning/rendered/dev/permissions.manifest.json
provisioning/rendered/dev/host-registration.json
provisioning/rendered/staging/...
provisioning/rendered/prod/...
```

Say:

> Provisioning is generated from environment YAML and current capability state. It is deterministic and safe to rerun.

## Transcript Template

Use this section to paste exact terminal and MCP client output from the final recording.

```text
[00:00] Bootstrap command:
[paste command and output]

[00:30] Dashboard:
[describe selected identity, group, period, and totals shown]

[01:30] Admin capability update:
[describe action and API result]

[02:00] MCP tool discovery:
[paste tool list]

[02:30] MCP allowed read:
[paste usage_summary result]

[03:00] MCP denied cross-group read:
[paste permission_denied result]

[03:30] MCP denied write:
[paste permission_denied result]

[04:00] Provisioning:
[paste provision command and generated file list]
```

