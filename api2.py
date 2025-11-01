import asyncio
import os
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import google.generativeai as genai  # Gemini import

async def main():
    # Load API key
    load_dotenv()
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise ValueError("Set GEMINI_API_KEY in .env file")

    # Configure Gemini
    genai.configure(api_key=GEMINI_API_KEY)
    MODEL_NAME = "gemini-2.0-flash-exp"    # Initialize the model with tools
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        generation_config={
            "temperature": 0.2,
            "max_output_tokens": 2048,
        },
        tools=[]  # We'll add tools after getting them from MCP
    )

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
            tools = await session.list_tools()
            tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in tools.tools])
            print(f"Connected to Zomato MCP. Available tools:\n{tool_descriptions}\n")
            
            # Prepare tools information for Gemini
            tools_info = []
            for tool in tools.tools:
                # Create tool description for Gemini
                tool_info = f"{tool.name}: {tool.description}"
                if hasattr(tool, 'inputSchema'):
                    if hasattr(tool.inputSchema, 'get'):
                        props = tool.inputSchema.get("properties", {})
                        if props:
                            tool_info += "\nParameters:"
                            for param, details in props.items():
                                param_type = details.get('type', 'string')
                                desc = details.get('description', 'No description')
                                tool_info += f"\n- {param} ({param_type}): {desc}"
                tools_info.append(tool_info)
            
            # Create system message with tools information
            tools_info_text = "\n\n".join(tools_info)
            system_message = f"""You are a helpful food ordering assistant. Here are the available tools:
            
            {tools_info_text}
            
            When the user makes a request:
            1. First, check if you need to use any tools to fulfill the request
            2. If a tool is needed, describe what you would do with it
            3. If the user asks to order food, you'll need their address and payment method
            4. For any location-specific queries, use the get_saved_addresses_for_user tool first
            """
            
            messages = []  # Conversation history (Gemini uses chat format)
            print("Food ordering chatbot ready! Type your query (e.g., 'Order pizza in Bangalore') or 'quit' to exit.")
            
            while True:
                user_input = input("\nYou: ").strip()
                if user_input.lower() == 'quit':
                    break
                
                messages.append({"role": "user", "parts": [user_input]})
                
                # Prepare the conversation history for Gemini
                conversation = []
                
                # Add system message if this is the first message
                if len(messages) == 1:  # Only user's first message
                    conversation.append({"role": "user", "parts": [system_message]})
                    conversation.append({"role": "model", "parts": ["I understand. I'm ready to help with your food order."]})
                
                # Add user's message
                conversation.append({"role": "user", "parts": [messages[-1]["parts"][0]]})
                
                try:
                    # Call Gemini model
                    response = model.generate_content(
                        conversation,
                        generation_config={
                            "max_output_tokens": 2048,
                            "temperature": 0.2,
                        }
                    )
                    
                    # Extract the response text
                    if response and hasattr(response, 'text'):
                        final_response = response.text
                        
                        # Add tool usage instructions if relevant
                        if any(tool.name in final_response.lower() for tool in tools.tools):
                            final_response += "\n\n[Note: To use this feature, please provide the required information and I'll help you use the appropriate tool.]"
                    else:
                        final_response = "I'm sorry, I couldn't generate a response. Please try again."
                    
                except Exception as e:
                    final_response = f"Error: {str(e)}\n\nPlease try again or rephrase your request."
                
                # Append assistant response to history
                messages.append({"role": "model", "parts": [final_response]})
                print(f"Gemini: {final_response}")

if __name__ == "__main__":
    asyncio.run(main())