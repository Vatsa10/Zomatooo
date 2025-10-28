from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Dict, List, Optional
import httpx
import asyncio
import edge_tts
import os
import json
import uuid
from datetime import datetime

app = FastAPI(title="Zomato Food Ordering Chatbot")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Configuration
ZOMATO_PROXY_URL = "http://localhost:8001/mcp"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# In-memory storage for demo (replace with database in production)
user_sessions = {}  # Store user sessions
user_carts = {}      # Store user carts

# Models
class UserMessage(BaseModel):
    message: str
    session_id: Optional[str] = None

class CartItem(BaseModel):
    restaurant_id: str
    restaurant_name: str
    item_id: str
    item_name: str
    quantity: int
    price: float

class OrderRequest(BaseModel):
    session_id: str
    delivery_address: str
    payment_method: str

# Helper: Call Gemini for Intent Classification
# -------------------------
async def call_gemini(user_input: str, context: str = "") -> dict:
    """
    Call Gemini model to understand user intent and extract relevant information
    """
    prompt = f"""
    You are a food ordering assistant. Analyze the user's message and respond in JSON format.
    
    User message: '{user_input}'
    
    Context: {context}
    
    Respond with a JSON object containing:
    - intent: One of ["search_restaurants", "view_menu", "add_to_cart", "view_cart", "place_order", "track_order"]
    - query: Food item or restaurant name (if searching)
    - location: Delivery location (default to 'Vadodara' if not specified)
    - restaurant_id: If mentioned or relevant
    - item_id: If adding to cart
    - quantity: Number of items (default 1)
    - delivery_address: If provided
    - payment_method: If provided
    
    Example responses:
    {{"intent": "search_restaurants", "query": "pizza", "location": "Vadodara"}}
    {{"intent": "add_to_cart", "restaurant_id": "123", "item_id": "456", "quantity": 2}}
    """
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
                params={"key": GEMINI_API_KEY},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=20,
            )
            data = resp.json()
            text_output = data["candidates"][0]["content"]["parts"][0]["text"]
            # Clean the response to ensure it's valid JSON
            text_output = text_output.strip('`').replace('json\n', '').replace('\n', '')
            return json.loads(text_output)
    except Exception as e:
        print(f"Error calling Gemini: {str(e)}")
        return {"intent": "search_restaurants", "query": user_input, "location": "Vadodara"}

async def call_zomato_proxy(query: str, location: str):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                ZOMATO_PROXY_URL,
                json={
                    "action": "restaurant_discovery",
                    "query": query,
                    "location": location
                },
                timeout=20,
            )
            return resp.json()
    except Exception as e:
        return {"error": str(e)}

# Cart Management
# -------------------------
def get_or_create_cart(session_id: str) -> dict:
    """Get existing cart or create a new one"""
    if session_id not in user_carts:
        user_carts[session_id] = {
            "items": [],
            "restaurant_id": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
    return user_carts[session_id]

def add_to_cart(session_id: str, item: dict):
    """Add item to cart"""
    cart = get_or_create_cart(session_id)
    
    # If cart is not empty and trying to add from different restaurant
    if cart["restaurant_id"] and cart["restaurant_id"] != item["restaurant_id"]:
        return False, "Cannot add items from different restaurants. Please clear your cart first."
    
    # Update cart restaurant if empty
    if not cart["restaurant_id"]:
        cart["restaurant_id"] = item["restaurant_id"]
        cart["restaurant_name"] = item["restaurant_name"]
    
    # Check if item already in cart
    for cart_item in cart["items"]:
        if cart_item["item_id"] == item["item_id"]:
            cart_item["quantity"] += item["quantity"]
            cart["updated_at"] = datetime.now().isoformat()
            return True, "Item quantity updated in cart"
    
    # Add new item to cart
    cart["items"].append(item)
    cart["updated_at"] = datetime.now().isoformat()
    return True, "Item added to cart"

def get_cart_summary(session_id: str) -> dict:
    """Get cart summary"""
    if session_id not in user_carts or not user_carts[session_id]["items"]:
        return {"item_count": 0, "total": 0, "items": []}
    
    cart = user_carts[session_id]
    total = sum(item["price"] * item["quantity"] for item in cart["items"])
    
    return {
        "restaurant_name": cart.get("restaurant_name", ""),
        "item_count": len(cart["items"]),
        "total": total,
        "items": cart["items"]
    }

def clear_cart(session_id: str):
    """Clear the cart"""
    if session_id in user_carts:
        user_carts[session_id] = {
            "items": [],
            "restaurant_id": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
    return True

# Helper: Generate text-to-speech
# -------------------------
async def speak_text(text: str):
    """Convert text to speech using edge-tts"""
    try:
        output_file = f"static/voice_{uuid.uuid4()}.mp3"
        communicate = edge_tts.Communicate(text, "en-IN-NeerjaNeural")
        os.makedirs("static", exist_ok=True)
        await communicate.save(output_file)
        return output_file
    except Exception as e:
        print(f"Error in text-to-speech: {str(e)}")
        return None

@app.post("/chat")
async def chat(req: Request):
    """
    Main entry for your voice chatbot.
    Expects: {"message": "Find pizza near me"}
    Returns: JSON + voice file path
    """
    data = await req.json()
    user_message = data.get("message", "")

    # Step 1️⃣ Parse intent via Gemini
    gemini_response = await call_gemini(user_message)
    print("Gemini output:", gemini_response)

    # Step 2️⃣ Extract query & location safely
    try:
        import json
        parsed = json.loads(gemini_response)
        query = parsed.get("query", user_message)
        location = parsed.get("location", "Vadodara")
    except:
        query, location = user_message, "Vadodara"

    # Step 3️⃣ Get restaurant data from Zomato MCP proxy
    zomato_data = await call_zomato_proxy(query, location)

    # Step 4️⃣ Generate a nice spoken summary
    summary = ""
    if "result" in zomato_data and isinstance(zomato_data["result"], dict):
        restaurants = zomato_data["result"].get("restaurants", [])
        if restaurants:
            top = restaurants[:3]
            names = [r.get("name", "Unknown") for r in top]
            summary = f"Here are some top {query} places in {location}: " + ", ".join(names)
        else:
            summary = f"Sorry, I couldn't find any {query} places in {location}."
    else:
        summary = "Sorry, something went wrong while fetching restaurants."

    # Step 5️⃣ Speak it aloud
    await speak_text(summary)

    return JSONResponse({
        "query": query,
        "location": location,
        "summary": summary,
        "zomato_data": zomato_data,
        "voice_file": "voice_reply.mp3"
    })
