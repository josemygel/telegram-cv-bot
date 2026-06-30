# cv_mcp — MCP server for Jose Miguel's profile, contact and documents

Exposes the profile, contact details and the CV / cover-letter PDFs over the Model
Context Protocol. Reuses `src.profile` and the `cv/` document folder.

## Tools
- `get_profile()` — the full grounding profile text.
- `get_contact()` — name, email, phone, location, LinkedIn, GitHub.
- `list_documents()` — which `cv` and `cover_letter` PDFs exist, per language.
- `get_document_path(kind="cv", lang="es")` — absolute path to a PDF (`cv` | `cover_letter`).

## Run
```bash
python mcps/cv_mcp/server.py
```

## Register in Claude Desktop
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "josembot-cv": {
      "command": "python",
      "args": ["C:\\Users\\josem\\Proyectos\\telegram-voice-bot\\mcps\\cv_mcp\\server.py"]
    }
  }
}
```
