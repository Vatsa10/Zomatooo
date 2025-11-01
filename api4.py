#address showing properly form the zomato account

import asyncio
import os
import re  # For simple city extraction
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import google.generativeai as genai  # Gemini import

# Global state for location (shared across chat turns)
location_state = {"current_location": None, "addresses": [], "resolved": False}

def mcp_schema_to_gemini(schema):
    """Convert MCP Schema to Gemini-compatible JSON Schema dict."""
    # Extract dict representation (Pydantic-aware, no specific class check)
    if hasattr(schema, 'model_dump'):
        dump = schema.model_dump()
    elif hasattr(schema, 'dict'):
        dump = schema.dict()
    else:
        # Plain dict or other (e.g., fallback serialization)
        dump = dict(schema) if hasattr(schema, '__dict__') else {}
    
    # Recursively ensure types are uppercase for proto enum
    def normalize_types(obj):
        if isinstance(obj, dict):
            return {k: normalize_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [normalize_types(item) for item in obj]
        elif isinstance(obj, str) and obj.lower() in ['object', 'string', 'number', 'integer', 'boolean', 'array', 'null']:
            return obj.upper()  # Uppercase for Gemini proto enum (e.g., 'object' -> 'OBJECT')
        return obj
    
    normalized = normalize_types(dump)
    
    # Ensure root has "type": "OBJECT" if missing
    if 'type' not in normalized:
        normalized['type'] = 'OBJECT'
    elif isinstance(normalized['type'], str):
        normalized['type'] = normalized['type'].upper()
    
    return normalized

async def fetch_and_cache_addresses(session):
    """Auto-fetch saved addresses at startup and cache."""
    try:
        addr_result = await session.call_tool(name="get_saved_addresses_for_user", arguments={})
        addresses_text = addr_result.content[0].text if addr_result.content else "No addresses found."
        print(f"Startup: Fetched addresses - {addresses_text}")
        
        # Parse simple list (assume JSON-like or plain text; enhance if needed)
        if "No addresses" not in addresses_text and addresses_text.strip():
            # Simple split; for real JSON, use json.loads
            location_state["addresses"] = [addr.strip() for addr in addresses_text.split(",") if addr.strip()]
            if location_state["addresses"]:
                location_state["current_location"] = location_state["addresses"][0]  # Default to first
                location_state["resolved"] = True
                print(f"Default location set to: {location_state['current_location']}")
        else:
            location_state["current_location"] = None
            location_state["resolved"] = False
            print("No saved addresses found. Will prompt for city.")
    except Exception as e:
        print(f"Error fetching addresses: {e}. Will prompt for city.")
        location_state["current_location"] = None
        location_state["resolved"] = False

def extract_city_from_input(user_input):
    """Simple extraction for city from user message (e.g., 'in Vadodara')."""
    # Common patterns
    match = re.search(r'(?:in|from|near)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)', user_input, re.IGNORECASE)
    if match:
        return match.group(1)
    # Fallback to last word if city-like
    words = user_input.split()
    if len(words) > 2 and words[-1].isalpha():
        return words[-1].capitalize()
    return None

def modify_tool_args_for_location(tool_name, args):
    """Inject location into tool args (e.g., set user_location for searches)."""
    loc = location_state["current_location"]
    if not loc:
        return args  # Skip if no loc

    loc_obj = {"name": loc}  # Assume schema expects dict; fallback to str if errors

    if tool_name in ["get_all_restaurants", "get_restaurants_for_keyword", "get_dynamic_search_filters", "get_search_order_history"]:
        # Set required user_location
        args["user_location"] = loc_obj
        # Also enhance query if present
        if "query" in args and isinstance(args["query"], str):
            if "in" not in args["query"].lower():
                args["query"] = f"{args['query']} in {loc}"
    elif tool_name in ["get_order_tracking_info"]:  # If it uses ctx for location
        if "ctx" in args:
            args["ctx"] = {**args.get("ctx", {}), "location": loc_obj}
    
    return args

async def main():
    # Load API key
    load_dotenv()
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise ValueError("Set GEMINI_API_KEY in .env file")

    # Configure Gemini
    genai.configure(api_key=GEMINI_API_KEY)
    MODEL_NAME = "gemini-2.0-flash-exp"  # Or "gemini-1.5-flash" if 2.0 isn't available
    generation_config = {
        "temperature": 0.7,
        "max_output_tokens": 1024,
    }

    # MCP server params: Run mcp-remote as subprocess
    server_params = StdioServerParameters(
        command="npx",
        args=["mcp-remote", "https://mcp-server.zomato.com/mcp"]
    )
    
    # Connect to MCP server (Zomato tools)
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection (required for MCP protocol)
            await session.initialize()
            
            # Auto-fetch addresses at startup
            await fetch_and_cache_addresses(session)
            
            # List available tools (e.g., search_restaurants, add_to_cart)
            tools_resp = await session.list_tools()
            tools = tools_resp.tools
            tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
            print(f"Connected to Zomato MCP. Available tools:\n{tool_descriptions}\n")
            
            # Define Gemini function tools from MCP tools
            function_declarations = []
            for tool in tools:
                try:
                    # Convert schema safely
                    input_schema = mcp_schema_to_gemini(tool.inputSchema)
                    
                    function_declarations.append({
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": input_schema  # Now Gemini-compatible
                    })
                    print(f"Processed tool: {tool.name} with schema type: {input_schema.get('type', 'unknown')}")  # Debug
                except Exception as e:
                    print(f"Warning: Failed to process schema for {tool.name}: {e}. Skipping tool.")
                    continue  # Skip bad tools to avoid crashing
            
            if not function_declarations:
                raise ValueError("No valid tools could be processed—check MCP connection or schemas.")
            
            # System prompt for better location handling
            system_prompt = """
            You are a helpful food ordering assistant using Zomato tools. ALWAYS follow Zomato's location workflow:
            1. For any search/order, FIRST call get_saved_addresses_for_user if location unknown.
            2. If addresses exist, use the first one as user_location = {"name": "Address Name"}.
            3. If no addresses, ask ONCE for user's city (e.g., 'Vadodara'), then set user_location = {"name": "City"} and use in ALL search tools.
            4. For targeted searches, call get_restaurants_for_keyword with 'query' (formatted, e.g., 'pizza') AND required 'user_location'.
            5. For general, use get_all_restaurants with user_location.
            6. Before cart/checkout, confirm items/total.
            7. If tool fails on location, re-prompt specifically.
            Be concise, friendly, confirm steps. Cache location.
            """
            
            # Now create model with tools bound (re-init after fetching schemas)
            print("Binding Zomato tools to Gemini model...")
            model = genai.GenerativeModel(
                model_name=MODEL_NAME,
                tools=function_declarations,  # Bind here in constructor
                generation_config=generation_config,
                system_instruction=system_prompt  # Add system prompt for workflow
            )
            print("Model ready with tools!\n")
            
            messages = [{"role": "user", "parts": [system_prompt]}]  # Start with system in history
            if location_state["resolved"]:
                messages.append({"role": "model", "parts": [f"Startup: Location resolved to {location_state['current_location']}."]})
            else:
                messages.append({"role": "model", "parts": ["Startup: No saved addresses. Please tell me your city (e.g., 'I live in Vadodara') to get started."]})
            
            print("Food ordering chatbot ready! Type your query (e.g., 'Order pizza in Bangalore') or 'quit' to exit.")
            
            while True:
                user_input = input("\nYou: ").strip()
                if user_input.lower() == 'quit':
                    break
                
                # Extract and update location from user input if not resolved
                if not location_state["resolved"]:
                    city = extract_city_from_input(user_input)
                    if city:
                        location_state["current_location"] = city
                        location_state["resolved"] = True
                        print(f"Resolved location to: {city}")
                        messages.append({"role": "user", "parts": [f"Location set to {city}."]})
                        continue  # Skip generation; confirm next
                
                messages.append({"role": "user", "parts": [user_input]})
                
                # Generate with Gemini (handles tool calls automatically if needed)
                response = model.generate_content(messages)
                
                # Handle response (text or function call)
                final_response = ""
                tool_called = False
                if response.parts:
                    for part in response.parts:
                        if hasattr(part, 'text') and part.text:
                            final_response += part.text
                        elif hasattr(part, 'function_call') and part.function_call:
                            tool_called = True
                            # Modify args with location
                            tool_call = part.function_call
                            modified_args = modify_tool_args_for_location(tool_call.name, dict(tool_call.args))  # Copy to dict
                            
                            # Execute tool via MCP
                            try:
                                tool_result = await session.call_tool(
                                    name=tool_call.name,
                                    arguments=modified_args
                                )
                                result_text = tool_result.content[0].text if tool_result.content else "Tool executed successfully."
                                print(f"Tool {tool_call.name} result: {result_text[:200]}...")  # Debug truncated
                            except Exception as e:
                                result_text = f"Tool error: {str(e)}. Please confirm your location (city/address)."
                                print(f"Tool {tool_call.name} failed: {e}")
                            
                            # Append tool result to messages for follow-up
                            messages.append({
                                "role": "model",
                                "parts": [{"function_response": {
                                    "name": tool_call.name,
                                    "response": {"result": result_text}
                                }}]
                            })
                            # Re-generate with tool result
                            follow_up = model.generate_content(messages)
                            if follow_up.parts:
                                for f_part in follow_up.parts:
                                    if hasattr(f_part, 'text') and f_part.text:
                                        final_response += f_part.text
                            break  # Single tool call per turn for simplicity
                
                if not tool_called and not location_state["resolved"]:
                    final_response = "To order food, first tell me your city for delivery (e.g., 'Vadodara')."
                
                # Append assistant response to history
                messages.append({"role": "model", "parts": [final_response]})
                print(f"Gemini: {final_response}")

if __name__ == "__main__":
    asyncio.run(main())