# Zomato Food Ordering Chatbot

A conversational AI chatbot that helps users discover restaurants, browse menus, and place food orders through natural language conversations.

## Features

- 🍽️ **Restaurant Discovery** - Find restaurants based on cuisine, location, or dish name
- 📝 **Menu Browsing** - View restaurant menus with prices and descriptions
- 🛒 **Smart Cart** - Add/remove items, update quantities, and view cart summary
- 🎤 **Voice Input** - Support for voice commands (browser permission required)
- 🔊 **Voice Output** - Text-to-speech responses for a more interactive experience
- 💳 **Order Management** - Place orders and track order status

## Prerequisites

- Python 3.8+
- pip (Python package manager)
- Google Gemini API key (for natural language understanding)
- Zomato MCP Server access

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd zomato-mcp-chatbot
   ```

2. **Create a virtual environment (recommended)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory with your API keys:
   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

5. **Start the development server**
   ```bash
   uvicorn main:app --reload
   ```

6. **Access the chatbot**
   Open your browser and navigate to: `http://localhost:8000`

## Usage

1. **Search for restaurants**
   - "Find me pizza places near me"
   - "Show me Indian restaurants in Bangalore"
   - "I'm craving sushi, any good places nearby?"

2. **View menu items**
   - "Show me the menu for [restaurant name]"
   - "What are the vegetarian options?"
   - "Do you have any desserts?"

3. **Manage your cart**
   - "Add 2 Margherita pizzas to my cart"
   - "Show me my cart"
   - "Remove the garlic bread from my order"
   - "Update my order to 3 pizzas"

4. **Place an order**
   - "I want to place an order"
   - "Deliver to 123 Main St, Apt 4B"
   - "I'll pay with credit card"

5. **Check order status**
   - "Where's my order?"
   - "What's the status of my delivery?"

## Project Structure

```
zomato-mcp-chatbot/
├── main.py            # FastAPI application and route handlers
├── requirements.txt   # Python dependencies
├── static/            # Static files (CSS, JS, audio)
│   ├── css/
│   └── js/
├── templates/         # HTML templates
│   └── index.html     # Chat interface
└── .env              # Environment variables
```

## API Endpoints

- `GET /` - Serve the chat interface
- `POST /api/chat` - Process user messages and return bot responses
- `POST /api/order` - Place a new order
- `GET /api/order/{order_id}` - Get order status
- `GET /api/restaurants` - Search for restaurants
- `GET /api/menu/{restaurant_id}` - Get restaurant menu

## Voice Commands

The chatbot supports voice input through the browser's Web Speech API. Click the microphone button and speak naturally to:
- Search for restaurants
- Add items to cart
- Place orders
- Ask questions about the menu

## Troubleshooting

- **Voice input not working**: Ensure your browser has microphone permissions enabled for this site
- **API errors**: Verify your API keys are correctly set in the `.env` file
- **Installation issues**: Make sure you're using Python 3.8+ and all dependencies are installed

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Zomato for the MCP server and API
- Google Gemini for natural language understanding
- FastAPI for the backend framework
- Tailwind CSS for styling
