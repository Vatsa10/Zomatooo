// server.js - Enhanced Food Ordering System
import express from 'express';
import cors from 'cors';
import { GoogleGenerativeAI } from '@google/generative-ai';
import axios from 'axios';
import dotenv from 'dotenv';

dotenv.config();

const app = express();

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('public')); // Serve static files

// Configuration
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const ZOMATO_MCP_URL = process.env.ZOMATO_MCP_URL || 'https://mcp-server.zomato.com/mcp';
const PORT = process.env.PORT || 3000;

if (!GEMINI_API_KEY) {
  console.error('❌ GEMINI_API_KEY is not set in environment variables');
  process.exit(1);
}

// Initialize Gemini
const genAI = new GoogleGenerativeAI(GEMINI_API_KEY);

// Store user sessions
const sessions = new Map();

// Logging middleware
app.use((req, res, next) => {
  console.log(`${new Date().toISOString()} - ${req.method} ${req.path}`);
  next();
});

// MCP Client for Zomato
class ZomatoMCPClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
  }

  async callTool(toolName, args) {
    try {
      console.log(`📡 Calling Zomato MCP: ${toolName}`, args);
      const response = await axios.post(
        this.baseUrl,
        {
          jsonrpc: '2.0',
          id: Date.now(),
          method: 'tools/call',
          params: {
            name: toolName,
            arguments: args
          }
        },
        {
          timeout: 10000,
          headers: {
            'Content-Type': 'application/json'
          }
        }
      );

      if (response.data.error) {
        throw new Error(response.data.error.message || 'MCP Server error');
      }

      return response.data.result;
    } catch (error) {
      if (error.response) {
        console.error(`❌ MCP Error: ${error.response.status} - ${error.response.data?.error?.message || error.message}`);
        throw new Error(`Zomato API error: ${error.response.data?.error?.message || error.message}`);
      } else if (error.request) {
        console.error('❌ No response from Zomato MCP Server');
        throw new Error('Cannot connect to Zomato service. Please try again later.');
      } else {
        console.error(`❌ Error: ${error.message}`);
        throw error;
      }
    }
  }

  async listTools() {
    const response = await axios.post(this.baseUrl, {
      jsonrpc: '2.0',
      id: Date.now(),
      method: 'tools/list'
    });
    return response.data.result.tools;
  }

  // Wrapper methods for each tool
  async searchRestaurants(location, cuisine = null, priceRange = null) {
    return await this.callTool('search_restaurants', {
      location,
      ...(cuisine && { cuisine }),
      ...(priceRange && { price_range: priceRange })
    });
  }

  async getMenu(restaurantId) {
    return await this.callTool('get_menu', {
      restaurant_id: restaurantId
    });
  }

  async addToCart(sessionId, restaurantId, itemId, quantity, customizations = null) {
    return await this.callTool('add_to_cart', {
      session_id: sessionId,
      restaurant_id: restaurantId,
      item_id: itemId,
      quantity,
      ...(customizations && { customizations })
    });
  }

  async viewCart(sessionId) {
    return await this.callTool('view_cart', {
      session_id: sessionId
    });
  }

  async placeOrder(sessionId, deliveryAddress, paymentMethod) {
    return await this.callTool('place_order', {
      session_id: sessionId,
      delivery_address: deliveryAddress,
      payment_method: paymentMethod
    });
  }

  async trackOrder(orderId) {
    return await this.callTool('track_order', {
      order_id: orderId
    });
  }
}

const zomatoClient = new ZomatoMCPClient(ZOMATO_MCP_URL);

// Gemini function declarations
const tools = [
  {
    functionDeclarations: [
      {
        name: 'search_restaurants',
        description: 'Search for restaurants based on location, cuisine type, and price range. Returns a list of restaurants with details like name, address, rating, and cuisine type.',
        parameters: {
          type: 'object',
          properties: {
            location: {
              type: 'string',
              description: 'The location to search for restaurants (e.g., "Mumbai", "Bangalore", "Delhi")'
            },
            cuisine: {
              type: 'string',
              description: 'Type of cuisine (e.g., "Italian", "Indian", "Chinese", "Mexican")'
            },
            priceRange: {
              type: 'string',
              description: 'Price range filter',
              enum: ['budget', 'mid-range', 'premium']
            }
          },
          required: ['location']
        }
      },
      {
        name: 'get_menu',
        description: 'Get the complete menu of a specific restaurant including item names, descriptions, prices, and categories.',
        parameters: {
          type: 'object',
          properties: {
            restaurantId: {
              type: 'string',
              description: 'The unique ID of the restaurant'
            }
          },
          required: ['restaurantId']
        }
      },
      {
        name: 'add_to_cart',
        description: 'Add a menu item to the shopping cart with specified quantity and optional customizations.',
        parameters: {
          type: 'object',
          properties: {
            restaurantId: {
              type: 'string',
              description: 'The restaurant ID'
            },
            itemId: {
              type: 'string',
              description: 'The menu item ID to add'
            },
            quantity: {
              type: 'number',
              description: 'Number of items to add (must be positive integer)'
            },
            customizations: {
              type: 'string',
              description: 'Special requests or customizations (e.g., "extra cheese", "no onions", "spicy")'
            }
          },
          required: ['restaurantId', 'itemId', 'quantity']
        }
      },
      {
        name: 'view_cart',
        description: 'View all items currently in the shopping cart with quantities, prices, and total amount.',
        parameters: {
          type: 'object',
          properties: {}
        }
      },
      {
        name: 'place_order',
        description: 'Place an order with delivery address and payment method. Confirms the order and provides order ID for tracking.',
        parameters: {
          type: 'object',
          properties: {
            deliveryAddress: {
              type: 'string',
              description: 'Complete delivery address including street, city, and postal code'
            },
            paymentMethod: {
              type: 'string',
              description: 'Payment method for the order',
              enum: ['cash', 'card', 'upi']
            }
          },
          required: ['deliveryAddress', 'paymentMethod']
        }
      },
      {
        name: 'track_order',
        description: 'Track the current status of an order using the order ID. Shows order status, estimated delivery time, and delivery person details if available.',
        parameters: {
          type: 'object',
          properties: {
            orderId: {
              type: 'string',
              description: 'The unique order ID to track'
            }
          },
          required: ['orderId']
        }
      }
    ]
  }
];

// Handle function calls
async function handleFunctionCall(functionName, args, sessionId) {
  console.log(`🔧 Executing function: ${functionName}`);
  
  try {
    switch (functionName) {
      case 'search_restaurants':
        return await zomatoClient.searchRestaurants(
          args.location,
          args.cuisine,
          args.priceRange
        );
      
      case 'get_menu':
        return await zomatoClient.getMenu(args.restaurantId);
      
      case 'add_to_cart':
        return await zomatoClient.addToCart(
          sessionId,
          args.restaurantId,
          args.itemId,
          args.quantity,
          args.customizations
        );
      
      case 'view_cart':
        return await zomatoClient.viewCart(sessionId);
      
      case 'place_order':
        return await zomatoClient.placeOrder(
          sessionId,
          args.deliveryAddress,
          args.paymentMethod
        );
      
      case 'track_order':
        return await zomatoClient.trackOrder(args.orderId);
      
      default:
        throw new Error(`Unknown function: ${functionName}`);
    }
  } catch (error) {
    console.error(`❌ Function execution error: ${error.message}`);
    return {
      error: true,
      message: error.message
    };
  }
}

// Main chat endpoint
app.post('/chat', async (req, res) => {
  try {
    const { message, sessionId = `session_${Date.now()}`, userId } = req.body;

    if (!message || typeof message !== 'string') {
      return res.status(400).json({ error: 'Valid message is required' });
    }

    // Initialize session
    if (!sessions.has(sessionId)) {
      sessions.set(sessionId, {
        history: [],
        context: {},
        userId,
        createdAt: new Date()
      });
      console.log(`📝 New session created: ${sessionId}`);
    }

    const session = sessions.get(sessionId);

    // System instruction
    const systemInstruction = `You are a friendly and helpful food ordering assistant for Zomato. 

Your capabilities:
- Search for restaurants by location, cuisine, and price range
- Show detailed menus with prices
- Help users add items to their cart
- Process orders with delivery details
- Track order status

Guidelines:
- Be conversational and friendly
- Ask clarifying questions when needed (e.g., location, preferences)
- Suggest popular dishes or restaurants when appropriate
- Format restaurant and menu information clearly
- Guide users through the ordering process step by step
- Always confirm before placing orders
- Provide order IDs for tracking

When presenting information:
- Use bullet points for lists
- Show prices clearly
- Highlight ratings and reviews
- Mention delivery times if available

Always prioritize user satisfaction and make ordering easy!`;

    // Initialize Gemini model
    const model = genAI.getGenerativeModel({
      model: 'gemini-2.0-flash',
      systemInstruction,
      tools
    });

    // Start chat
    const chat = model.startChat({
      history: session.history
    });

    console.log(`💬 User message: ${message}`);

    // Send message
    let result = await chat.sendMessage(message);
    let response = result.response;

    // Handle function calls in a loop
    let functionCallCount = 0;
    const maxFunctionCalls = 10; // Prevent infinite loops

    while (response.functionCalls && response.functionCalls.length > 0 && functionCallCount < maxFunctionCalls) {
      const functionCall = response.functionCalls[0];
      const functionName = functionCall.name;
      const args = functionCall.args;

      console.log(`🔄 Function call #${functionCallCount + 1}: ${functionName}`);

      // Execute function
      const functionResult = await handleFunctionCall(functionName, args, sessionId);

      // Send result back to Gemini
      result = await chat.sendMessage([
        {
          functionResponse: {
            name: functionName,
            response: { result: functionResult }
          }
        }
      ]);

      response = result.response;
      functionCallCount++;
    }

    if (functionCallCount >= maxFunctionCalls) {
      console.warn('⚠️ Maximum function call limit reached');
    }

    // Get final response
    const finalResponse = response.text();
    console.log(`🤖 Assistant response: ${finalResponse.substring(0, 100)}...`);

    // Update history (keep last 20 messages)
    session.history.push(
      { role: 'user', parts: [{ text: message }] },
      { role: 'model', parts: [{ text: finalResponse }] }
    );

    if (session.history.length > 40) { // 20 exchanges = 40 messages
      session.history = session.history.slice(-40);
    }

    res.json({
      response: finalResponse,
      sessionId,
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error('❌ Chat error:', error);
    res.status(500).json({
      error: 'An error occurred processing your request',
      details: error.message,
      suggestion: 'Please try again or rephrase your question'
    });
  }
});

// Session management endpoints
app.get('/session/:sessionId', (req, res) => {
  const { sessionId } = req.params;
  const session = sessions.get(sessionId);
  
  if (!session) {
    return res.status(404).json({ error: 'Session not found' });
  }

  res.json({
    sessionId,
    messageCount: session.history.length / 2,
    createdAt: session.context.createdAt,
    userId: session.userId
  });
});

app.delete('/session/:sessionId', (req, res) => {
  const { sessionId } = req.params;
  
  if (sessions.delete(sessionId)) {
    res.json({ message: 'Session cleared successfully', sessionId });
  } else {
    res.status(404).json({ error: 'Session not found' });
  }
});

app.get('/sessions', (req, res) => {
  const activeSessions = Array.from(sessions.entries()).map(([id, session]) => ({
    sessionId: id,
    messageCount: session.history.length / 2,
    createdAt: session.createdAt,
    userId: session.userId
  }));

  res.json({
    count: activeSessions.length,
    sessions: activeSessions
  });
});

// Health check
app.get('/health', async (req, res) => {
  try {
    // Test Zomato MCP connection
    await axios.post(ZOMATO_MCP_URL, {
      jsonrpc: '2.0',
      id: 1,
      method: 'tools/list'
    }, { timeout: 5000 });

    res.json({
      status: 'healthy',
      timestamp: new Date().toISOString(),
      services: {
        zomato: 'connected',
        gemini: GEMINI_API_KEY ? 'configured' : 'not configured'
      },
      activeSessions: sessions.size
    });
  } catch (error) {
    res.status(503).json({
      status: 'unhealthy',
      timestamp: new Date().toISOString(),
      error: error.message
    });
  }
});

// Error handling
app.use((err, req, res, next) => {
  console.error('❌ Unhandled error:', err);
  res.status(500).json({
    error: 'Internal server error',
    message: err.message
  });
});

// Start server
app.listen(PORT, () => {
  console.log('🍕 ========================================');
  console.log(`🚀 Food Ordering Server is running!`);
  console.log(`📡 Port: ${PORT}`);
  console.log(`🔗 Zomato MCP: ${ZOMATO_MCP_URL}`);
  console.log(`🤖 Gemini API: ${GEMINI_API_KEY ? 'Configured ✅' : 'Not configured ❌'}`);
  console.log('🍕 ========================================');
  console.log(`\n💡 Try these endpoints:`);
  console.log(`   - POST http://localhost:${PORT}/chat`);
  console.log(`   - GET  http://localhost:${PORT}/health`);
  console.log(`   - GET  http://localhost:${PORT}/sessions\n`);
});

export default app;