# projects_mcp — MCP server for Jose Miguel's projects

Exposes the structured project data (`profile/projects.yaml`) over the Model Context
Protocol so **any** MCP client (Claude Desktop, IDEs, the bot) can query it. It reuses
`src.projects.ProjectsRepository`, so there is one source of truth.

## Tools
- `list_projects()` — id, name, role, status of every project.
- `get_project(project_id, lang="es")` — full detail (scope/envergadura, participation, stack, summary, url).
- `get_project_field(project_id, field, lang="es")` — one field: `scope` | `participation` | `summary` | `stack`.
- `search_projects(query)` — substring match over name/summary/stack.

## Run
```bash
python mcps/projects_mcp/server.py
```

## Register in Claude Desktop
Add to `claude_desktop_config.json` (replace the path with the absolute path to
**your own** clone of this repo):
```json
{
  "mcpServers": {
    "josembot-projects": {
      "command": "python",
      "args": ["<path-to-your-clone>/mcps/projects_mcp/server.py"]
    }
  }
}
```

## Security
This server runs over **stdio** (the client launches it as a local subprocess) — there is no
network listener and no auth needed. If you ever adapt it to run over HTTP/SSE instead, add
authentication first: an unauthenticated network MCP server would let anyone on the network
query your project data.
