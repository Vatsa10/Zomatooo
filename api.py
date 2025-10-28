from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
import os, requests, json

app = FastAPI()

CLIENT_ID = "your_zomato_client_id"
CLIENT_SECRET = "your_zomato_client_secret"
REDIRECT_URI = "http://localhost:8001/auth/callback"
TOKEN_FILE = "token.json"

class ChatRequest(BaseModel):
    message: str

def get_access_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return json.load(f).get("access_token")
    return None

@app.get("/")
async def root():
    return {"status": "Zomato MCP Server running"}

@app.get("/auth/start")
async def start_auth():
    auth_url = (
        f"https://developers.zomato.com/oauth/authorize"
        f"?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code"
    )
    return RedirectResponse(url=auth_url)

@app.get("/auth/callback")
async def auth_callback(code: str):
    token_url = "https://developers.zomato.com/oauth/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }
    response = requests.post(token_url, data=data)
    token_data = response.json()
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f)
    return JSONResponse({"message": "Authorization successful!", "token": token_data})

@app.post("/chat")
async def chat(request: ChatRequest):
    query = request.message
    token = get_access_token()

    if not token:
        return JSONResponse({
            "auth": {
                "type": "oauth",
                "auth_url": f"http://localhost:8001/auth/start",
                "redirect_uri": REDIRECT_URI
            },
            "message": "Please authenticate with Zomato first."
        })

    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(
        "https://developers.zomato.com/api/v2.1/search",
        headers=headers,
        params={"q": query, "entity_type": "city"}
    )

    if resp.status_code != 200:
        return {"error": "Failed to fetch from Zomato", "details": resp.text}

    return resp.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
