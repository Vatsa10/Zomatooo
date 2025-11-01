import asyncio
import os
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import google.generativeai as genai  # Gemini import

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
            
            # Now create model with tools bound (re-init after fetching schemas)
            print("Binding Zomato tools to Gemini model...")
            model = genai.GenerativeModel(
                model_name=MODEL_NAME,
                tools=function_declarations,  # Bind here in constructor
                generation_config=generation_config
            )
            print("Model ready with tools!\n")
            
            messages = []  # Conversation history (Gemini uses chat format)
            print("Food ordering chatbot ready! Type your query (e.g., 'Order pizza in Bangalore') or 'quit' to exit.")
            
            while True:
                user_input = input("\nYou: ").strip()
                if user_input.lower() == 'quit':
                    break
                
                messages.append({"role": "user", "parts": [user_input]})
                
                # Generate with Gemini (handles tool calls automatically if needed)
                response = model.generate_content(messages)
                
                # Handle response (text or function call)
                final_response = ""
                if response.parts:
                    for part in response.parts:
                        if hasattr(part, 'text') and part.text:
                            final_response += part.text
                        elif hasattr(part, 'function_call') and part.function_call:
                            # Execute tool via MCP
                            tool_call = part.function_call
                            tool_result = await session.call_tool(
                                name=tool_call.name,
                                arguments=tool_call.args
                            )
                            # Append tool result to messages for follow-up
                            messages.append({
                                "role": "model",
                                "parts": [{"function_response": {
                                    "name": tool_call.name,
                                    "response": {"result": tool_result.content[0].text if tool_result.content else "Tool executed successfully."}
                                }}]
                            })
                            # Re-generate with tool result
                            follow_up = model.generate_content(messages)
                            if follow_up.parts:
                                for f_part in follow_up.parts:
                                    if hasattr(f_part, 'text') and f_part.text:
                                        final_response += f_part.text
                            break  # Single tool call per turn for simplicity
                
                # Append assistant response to history
                messages.append({"role": "model", "parts": [final_response]})
                print(f"Gemini: {final_response}")

if __name__ == "__main__":
    asyncio.run(main())