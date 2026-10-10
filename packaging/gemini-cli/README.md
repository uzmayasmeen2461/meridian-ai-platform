# Gemini CLI Extension

This directory contains a local Gemini CLI extension for the Meridian Usage Connector.

Link it for local development:

```bash
gemini extensions link packaging/gemini-cli/meridian-usage
```

Before launching Gemini CLI, export the simulated connector identity:

```bash
export MERIDIAN_MCP_USER_ID=user_533B58E6F66C98ACB833527A
```

The extension starts the existing backend MCP server over stdio and uses the local `backend/meridian.db` database. Run the backend bootstrap command first if the database does not exist.
