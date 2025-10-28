from fastapi import FastAPI, Request
import httpx

app = FastAPI()

ZOMATO_MCP_URL = "https://mcp-server.zomato.com/mcp"

@app.post("/mcp")
async def proxy_mcp(request: Request):
    try:
        body = await request.json()
        async with httpx.AsyncClient() as client:
            response = await client.post(ZOMATO_MCP_URL, json=body)
        return response.json()
    except Exception as e:
        return {"error": str(e)}
