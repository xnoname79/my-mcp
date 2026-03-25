Remember always fetch all tools from subscribed MCP server before starting the chat.

This project is a **SOURCE|TARGET** for sync-bridge MCP server.

## sync-bridge MCP Server Rules (MANDATORY)

### Role: SOURCE (API provider — e.g. BE, API server)
After EVERY code change that affects an API (new endpoint, updated request/response, changed behavior):
1. Call `add_api_requirement` or `update_api_requirement` to sync the change with target.
2. Include in description: request format, response format, and status ([NEW], [UPDATED], [DONE]).
3. At the end of a task, call `list_api_requirements` to verify all specs are up to date.
4. When target marks items as done, do NOT revert their status.

### Role: TARGET (API consumer — e.g. FE, client, external service)
When needing a new API or changes to an existing API:
1. Call `add_api_requirement` with endpoint, method, and detailed description of what is needed.
2. Include in description: expected request/response format, which component will use it.
3. Call `get_pending_requirements` to check if source has completed any pending requests.
4. When integration is done for a spec, call `update_api_requirement` to set status to "done".

This is a BLOCKING requirement — do not consider an API task complete until specs are synced.
