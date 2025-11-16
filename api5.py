import asyncio
import os
import json
import re  # For simple city extraction
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import google.generativeai as genai  # Gemini import

# Pydantic Models
class Restaurant(BaseModel):
    res_id: int = Field(..., description="Unique identifier for the restaurant")
    name: str = Field(..., description="Name of the restaurant")
    rating: float = Field(..., description="Average rating of the restaurant")
    votes: int = Field(..., description="Number of votes/ratings")
    distance: float = Field(..., description="Distance from the user's location in km")
    eta: str = Field(..., description="Estimated delivery time")
    res_image: str = Field(..., description="URL of the restaurant's image")
    res_offer: Optional[str] = Field(None, description="Any active offers")
    serviceability_status: str = Field(..., description="Service availability status")

class RestaurantSearchResponse(BaseModel):
    results: List[Restaurant] = Field(..., description="List of restaurants matching the search")

# Global state
location_state = {"current_location": None, "addresses": [], "resolved": False}
cart_state = {"items": [], "restaurant_id": None}  # Simple cart tracking

def mcp_schema_to_gemini(schema):
    """Convert MCP Schema to Gemini-compatible JSON Schema dict."""
    if hasattr(schema, 'model_dump'):
        dump = schema.model_dump()
    elif hasattr(schema, 'dict'):
        dump = schema.dict()
    else:
        dump = dict(schema) if hasattr(schema, '__dict__') else {}
    
    def normalize_types(obj):
        if isinstance(obj, dict):
            return {k: normalize_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [normalize_types(item) for item in obj]
        elif isinstance(obj, str) and obj.lower() in ['object', 'string', 'number', 'integer', 'boolean', 'array', 'null']:
            return obj.upper()
        return obj
    
    normalized = normalize_types(dump)
    if 'type' not in normalized:
        normalized['type'] = 'OBJECT'
    elif isinstance(normalized['type'], str):
        normalized['type'] = normalized['type'].upper()
    
    return normalized

async def fetch_and_cache_addresses(session):
    """Auto-fetch and parse addresses as JSON."""
    try:
        addr_result = await session.call_tool(name="get_saved_addresses_for_user", arguments={})
        addresses_text = addr_result.content[0].text if addr_result.content else '{"addresses": []}'
        addresses = json.loads(addresses_text).get("addresses", [])
        print(f"Startup: Fetched {len(addresses)} addresses.")
        
        if addresses:
            location_state["addresses"] = addresses
            location_state["current_location"] = addresses[0]  # Full dict with lat/lng
            location_state["resolved"] = True
            print(f"Default location: {addresses[0].get('short_name', 'Unknown')}")
        else:
            location_state["resolved"] = False
            print("No saved addresses. Will prompt for city.")
    except (json.JSONDecodeError, Exception) as e:
        print(f"Error parsing addresses: {e}. Will prompt for city.")
        location_state["resolved"] = False

def extract_city_from_input(user_input):
    """Extract city from user message."""
    match = re.search(r'(?:in|from|near|live in)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)', user_input, re.IGNORECASE)
    if match:
        return match.group(1)
    words = user_input.split()
    if len(words) > 2 and words[-1].isalpha():
        return words[-1].capitalize()
    return None

def modify_tool_args_for_location(tool_name, args, user_query=""):
    """Inject location/keyword into tool args."""
    loc = location_state["current_location"]
    if not loc:
        return args

    # Full location dict for schema
    loc_obj = loc if isinstance(loc, dict) else {"name": loc}

    if tool_name == "get_restaurants_for_keyword":
        # Ensure keyword from query if missing
        if "keyword" not in args:
            # Extract from user_query, e.g., "pizza" or "dominos pizza"
            kw_match = re.search(r'(pizza|dominos?|order\s+\w+)', user_query, re.IGNORECASE)
            args["keyword"] = kw_match.group(1).lower() if kw_match else "pizza"  # Fallback
        # Format keyword per docs if needed
        if "dominos" in args["keyword"].lower():
            args["keyword"] = f"{args['keyword']} from dominos"
        args["user_location"] = loc_obj
    elif tool_name in ["get_all_restaurants", "get_dynamic_search_filters", "get_search_order_history"]:
        args["user_location"] = loc_obj
    return args

async def main():
    load_dotenv()
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise ValueError("Set GEMINI_API_KEY in .env file")

    genai.configure(api_key=GEMINI_API_KEY)
    MODEL_NAME = "gemini-2.0-flash-exp"
    generation_config = {"temperature": 0.7, "max_output_tokens": 1024}

    server_params = StdioServerParameters(command="npx", args=["mcp-remote", "https://mcp-server.zomato.com/mcp"])
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await fetch_and_cache_addresses(session)
            
            tools_resp = await session.list_tools()
            tools = tools_resp.tools
            print(f"Connected to Zomato MCP. Available tools:\n" + "\n".join([f"- {t.name}: {t.description}" for t in tools]) + "\n")
            
            function_declarations = []
            for tool in tools:
                try:
                    input_schema = mcp_schema_to_gemini(tool.inputSchema)
                    function_declarations.append({
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": input_schema
                    })
                    print(f"Processed tool: {tool.name} with schema type: {input_schema.get('type', 'unknown')}")
                except Exception as e:
                    print(f"Warning: Failed schema for {tool.name}: {e}. Skipping.")
                    continue
            
            if not function_declarations:
                raise ValueError("No valid tools.")
            
            system_prompt = """
            You are a Zomato food ordering assistant. Follow strictly:
            1. For searches: Use get_restaurants_for_keyword with 'keyword' (e.g., 'pizza' or 'pizza from dominos') AND 'user_location' (full dict with name/lat/lng).
            2. If no results, try broader keyword or get_all_restaurants.
            3. After search, call get_menu_items_listing(restaurant_id) to list items, then get_restaurant_menu_by_category for details.
            4. For cart: create_cart with items (restaurant_id, dish name, quantity, variant). Show summary/total before checkout.
            5. Confirm every step (address, items, total).
            6. If empty results, suggest alternatives.
            Be engaging, concise.
            """
            
            print("Binding Zomato tools to Gemini model...")
            model = genai.GenerativeModel(
                model_name=MODEL_NAME,
                tools=function_declarations,
                generation_config=generation_config,
                system_instruction=system_prompt
            )
            print("Model ready with tools!\n")
            
            messages = [{"role": "user", "parts": [system_prompt]}]
            if location_state["resolved"]:
                messages.append({"role": "model", "parts": [f"Location: {location_state['current_location'].get('short_name', 'Set')}."]})
            else:
                messages.append({"role": "model", "parts": ["No addresses. Say your city (e.g., 'in Vadodara') to start."]})
            
            print("Food ordering chatbot ready! Type your query (e.g., 'Order pizza near me') or 'quit' to exit.")
            
            while True:
                user_input = input("\nYou: ").strip()
                if user_input.lower() == 'quit':
                    break
                
                if not location_state["resolved"]:
                    city = extract_city_from_input(user_input)
                    if city:
                        # Mock resolve: Set as {"name": city} (no lat/lng; tool may geocode)
                        location_state["current_location"] = {"name": city}
                        location_state["resolved"] = True
                        print(f"Resolved to: {city}")
                        messages.append({"role": "model", "parts": [f"Location set to {city}."]})
                        continue
                
                messages.append({"role": "user", "parts": [user_input]})
                
                response = model.generate_content(messages)
                
                final_response = ""
                tool_called = False
                if response.parts:
                    for part in response.parts:
                        if hasattr(part, 'text') and part.text:
                            final_response += part.text
                        elif hasattr(part, 'function_call') and part.function_call:
                            tool_called = True
                            tool_call = part.function_call
                            modified_args = modify_tool_args_for_location(tool_call.name, dict(tool_call.args), user_input)
                            
                            try:
                                tool_result = await session.call_tool(name=tool_call.name, arguments=modified_args)
                                result_text = tool_result.content[0].text if tool_result.content else "Success."
                                
                                # Process restaurant search results
                                if tool_call.name == "get_restaurants_for_keyword":
                                    try:
                                        # Parse and validate the response using Pydantic
                                        search_data = json.loads(result_text)
                                        restaurants = RestaurantSearchResponse(**search_data)
                                        
                                        # Format the output in a structured way
                                        formatted_results = []
                                        for i, restaurant in enumerate(restaurants.results, 1):
                                            formatted_results.append(
                                                f"{i}. {restaurant.name} ({restaurant.rating}⭐, {restaurant.distance}km, {restaurant.eta})"
                                                f"\n   🏷️ {restaurant.votes} votes"
                                                f"\n   🚚 {restaurant.serviceability_status}"
                                                f"\n   🆔 ID: {restaurant.res_id}"
                                            )
                                            
                                            if restaurant.res_offer:
                                                formatted_results[-1] += f"\n   🎁 Special Offer: {restaurant.res_offer}"
                                        
                                        result_text = "\n\n".join(formatted_results) if formatted_results else "No restaurants found."
                                        print(f"Found {len(restaurants.resments)} restaurants:")
                                        print(result_text)
                                        
                                    except json.JSONDecodeError as e:
                                        print(f"Error parsing restaurant data: {e}")
                                    except Exception as e:
                                        print(f"Error processing restaurant data: {e}")
                                
                                # If search empty, append fallback suggestion
                                if "total_results\": 0" in result_text:
                                    print("No results found. Trying a broader search...")
                                    # Auto-call get_all_restaurants if search failed
                                    fallback_result = await session.call_tool(
                                        name="get_all_restaurants",
                                        arguments={"user_location": location_state["current_location"]}
                                    )
                                    if fallback_result.content:
                                        print("Here are some nearby restaurants:")
                                        print(fallback_result.content[0].text[:200] + "...")
                            except Exception as e:
                                result_text = f"Error: {str(e)}. Please check your input and try again."
                            
                            messages.append({
                                "role": "model",
                                "parts": [{"function_response": {
                                    "name": tool_call.name,
                                    "response": {"result": result_text}
                                }}]
                            })
                            follow_up = model.generate_content(messages)
                            if follow_up.parts:
                                for f_part in follow_up.parts:
                                    if hasattr(f_part, 'text') and f_part.text:
                                        final_response += f_part.text
                            break
                
                # If no tool, handle location/items
                if not tool_called:
                    if "order" in user_input.lower() and cart_state["items"]:
                        final_response += f"\nCurrent cart: {len(cart_state['items'])} items. Total: ₹{sum(item.get('price', 0) for item in cart_state['items']):.0f}. Confirm?"
                
                messages.append({"role": "model", "parts": [final_response]})
                print(f"Gemini: {final_response}")

if __name__ == "__main__":
    asyncio.run(main())