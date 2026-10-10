# Meridian Usage Connector

Use the Meridian MCP tools when the user asks about Meridian AI assistant usage, cost, top users, or capability status.

Do not infer access. The MCP server enforces role scope, group visibility, and capability state. If a tool returns `permission_denied`, explain the denial without revealing protected group data.

Useful examples:

- "Show my team's AI usage for last_7_days."
- "Who are the top users in my group for 2026-W38?"
- "Is code-execution enabled for my group?"
- "Disable web-search for clinical-operations" only when the caller has capability write access.
