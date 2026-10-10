# Note to Team Leads

Subject: Meridian AI usage visibility is now available

Hi team leads,

You can now see your team’s Claude and Gemini assistant usage in the Meridian AI dashboard and, when enabled for your group, through the Meridian assistant connector.

What you can ask:

- “How much did my team use in the last 7 days?”
- “Show my team’s usage for 2026-W38.”
- “Who are the top users in my group this month?”
- “What did Claude and Gemini cost for my team?”
- “Which capabilities are enabled for my group?”

What you cannot see:

- Other teams’ usage, unless you are a platform admin.
- Protected details from a group you are not authorized to access.
- Data for periods outside the imported starter-kit window.

Why some requests may be denied:

- Your role may not have the required scope in the selected environment.
- You may be asking for another group’s data.
- The `usage-connector` capability may be disabled for your group.
- Capability changes may be restricted. In production, only platform admins can update controls.

How to request changes:

- Ask the platform team to enable or disable capabilities for your group.
- Include the group name, capability, reason, and whether the change is for dev, staging, or prod.
- For production changes, the platform team will verify ownership and policy before applying an override.

The goal is to give each team useful visibility into its own AI usage while keeping cross-team data and controls protected.

