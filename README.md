```markdown
# MCP Candidate Portal Server

This FastAPI-based MCP server exposes tools for candidate search based on experience, location, and department.

## Setup
```bash
docker-compose up --build
```

## Endpoints
- `POST /register/context`: Register a tool context node.
- `GET /register/context/{node_id}`: Retrieve a registered node.
- `POST /tools/candidate/search`: Search for candidates.
- `GET /health`: Health check.

## Integration with ChatMCP
1. Configure ChatMCP client to point to `http://<server>:3000`.
2. Use the `/register/context` endpoint to register tool definitions on startup.
3. Call `/tools/candidate/search` from ChatMCP when user invokes candidate search intent.
4. Parse and display results in ChatMCP chat interface.