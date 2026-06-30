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
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "josembot-projects": {
      "command": "python",
      "args": ["C:\\Users\\josem\\Proyectos\\telegram-voice-bot\\mcps\\projects_mcp\\server.py"]
    }
  }
}
```
