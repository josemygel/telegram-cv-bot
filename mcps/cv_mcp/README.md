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
Add to `claude_desktop_config.json` (replace the path with the absolute path to
**your own** clone of this repo):
```json
{
  "mcpServers": {
    "josembot-cv": {
      "command": "python",
      "args": ["<path-to-your-clone>/mcps/cv_mcp/server.py"]
    }
  }
}
```

## Security
This server runs over **stdio** (the client launches it as a local subprocess) — there is no
network listener and no auth needed. If you ever adapt it to run over HTTP/SSE instead, add
authentication first: an unauthenticated network MCP server would let anyone on the network
read your profile, contact details and CV documents.
