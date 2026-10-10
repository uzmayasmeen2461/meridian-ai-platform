# Claude Desktop Package

This directory is a Claude Desktop MCPB packaging template for the Meridian Usage Connector.

The current implementation is intentionally a local demonstration package: it starts the existing Python backend package over stdio and expects the backend dependencies and SQLite database to be available on the machine.

To create a `.mcpb` file after installing the MCPB CLI:

```bash
cd packaging/claude-desktop
mcpb pack
```

Install the generated `.mcpb` through Claude Desktop Settings > Extensions > Advanced settings > Install Extension. Configure the backend path, database URL, starter-kit path, environment, and simulated user ID when prompted.
# meridian-ai-platform
