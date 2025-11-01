import express from 'express';
import cors from 'cors';
import { GoogleGenerativeAI } from '@google/generative-ai';
import axios from 'axios';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());

// Configuration
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const ZOMATO_MCP_URL = 'https://mcp-server.zomato.com/mcp';
const USE_MOCK = process.env.USE_MOCK_SERVICE !== 'false';
const PORT = process.env.PORT || 3000;

if (!GEMINI_API_KEY) {
  console.error('❌ GEMINI_API_KEY is required');
  process.exit(1);
}

const genAI = new GoogleGenerativeAI(GEMINI_API_KEY);

// ============================================
// MCP-STYLE TOOL REGISTRY
// ============================================

class ToolRegistry {
  constructor() {
    this.tools = new Map();
    this.registerDefaultTools();
  }

  // Register a tool (MCP-style)
  registerTool(definition) {
    this.tools.set(definition.name, definition);
    console.log(`📝 Registered tool: ${definition.name}`);
  }

  // Get all tools for Gemini
  getGeminiTools() {
    const functionDeclarations = [];
    
    for (const [name, tool] of this.tools) {
      functionDeclarations.push({
        name: tool.name,
        description: tool.description,
        parameters: tool.inputSchema
      });
    }

    return [{ functionDeclarations }];
  }

  // Execute a tool
  async executeTool(name, args, context) {
    const tool = this.tools.get(name);
    if (!tool) {
      throw new Error(`Tool not found: ${name}`);
    }

    console.log(`🔧 Executing: ${name}`, args);
    return await tool.handler(args, context);
  }

  // Register default Zomato tools
  registerDefaultTools() {
    // Tool 1: Search Restaurants
    this.registerTool({
      name: 'search_restaurants',
      description: 'Search for restaurants based on location, cuisine, and price range. Returns list with ratings, delivery times, and addresses.',
      inputSchema: {
        type: 'object',
        properties: {
          location: {
            type: 'string',
            description: 'City or area (e.g., "Vadodara", "Mumbai")'
          },
          cuisine: {
            type: 'string',
            description: 'Cuisine type (e.g., "Gujarati", "Italian", "Chinese")'
          },
          priceRange: {
            type: 'string',
            enum: ['budget', 'mid-range', 'premium'],
            description: 'Price range filter'
          }
        },
        required: ['location']
      },
      handler: async (args, ctx) => {
        if (USE_MOCK) {
          return ctx.mockService.searchRestaurants(
            args.location, 
            args.cuisine, 
            args.priceRange
          );
        }
        return await ctx.zomatoClient.callMCP('search_restaurants', args);
      }
    });

    // Tool 2: Get Menu
    this.registerTool({
      name: 'get_menu',
      description: 'Get complete restaurant menu with items, prices, descriptions, and dietary info.',
      inputSchema: {
        type: 'object',
        properties: {
          restaurantId: {
            type: 'string',
            description: 'Restaurant ID'
          }
        },
        required: ['restaurantId']
      },
      handler: async (args, ctx) => {
        if (USE_MOCK) {
          return ctx.mockService.getMenu(args.restaurantId);
        }
        return await ctx.zomatoClient.callMCP('get_menu', {
          restaurant_id: args.restaurantId
        });
      }
    });

    // Tool 3: Add to Cart
    this.registerTool({
      name: 'add_to_cart',
      description: 'Add food item to cart with quantity and optional customizations.',
      inputSchema: {
        type: 'object',
        properties: {
          restaurantId: { type: 'string', description: 'Restaurant ID' },
          itemId: { type: 'string', description: 'Menu item ID' },
          quantity: { type: 'number', description: 'Quantity to add', minimum: 1 },
          customizations: { type: 'string', description: 'Special instructions' }
        },
        required: ['restaurantId', 'itemId', 'quantity']
      },
      handler: async (args, ctx) => {
        if (USE_MOCK) {
          return ctx.mockService.addToCart(
            ctx.sessionId,
            args.restaurantId,
            args.itemId,
            args.quantity,
            args.customizations
          );
        }
        return await ctx.zomatoClient.callMCP('add_to_cart', {
          session_id: ctx.sessionId,
          restaurant_id: args.restaurantId,
          item_id: args.itemId,
          quantity: args.quantity,
          customizations: args.customizations
        });
      }
    });

    // Tool 4: View Cart
    this.registerTool({
      name: 'view_cart',
      description: 'View all items in cart with quantities, prices, and total amount.',
      inputSchema: {
        type: 'object',
        properties: {}
      },
      handler: async (args, ctx) => {
        if (USE_MOCK) {
          return ctx.mockService.viewCart(ctx.sessionId);
        }
        return await ctx.zomatoClient.callMCP('view_cart', {
          session_id: ctx.sessionId
        });
      }
    });

    // Tool 5: Place Order
    this.registerTool({
      name: 'place_order',
      description: 'Place order with delivery address and payment method. Returns order ID.',
      inputSchema: {
        type: 'object',
        properties: {
          deliveryAddress: {
            type: 'string',
            description: 'Full delivery address'
          },
          paymentMethod: {
            type: 'string',
            enum: ['cash', 'card', 'upi'],
            description: 'Payment method'
          }
        },
        required: ['deliveryAddress', 'paymentMethod']
      },
      handler: async (args, ctx) => {
        if (USE_MOCK) {
          return ctx.mockService.placeOrder(
            ctx.sessionId,
            args.deliveryAddress,
            args.paymentMethod
          );
        }
        return await ctx.zomatoClient.callMCP('place_order', {
          session_id: ctx.sessionId,
          delivery_address: args.deliveryAddress,
          payment_method: args.paymentMethod
        });
      }
    });

    // Tool 6: Track Order
    this.registerTool({
      name: 'track_order',
      description: 'Track order status with order ID. Shows status, ETA, and delivery details.',
      inputSchema: {
        type: 'object',
        properties: {
          orderId: {
            type: 'string',
            description: 'Order ID to track'
          }
        },
        required: ['orderId']
      },
      handler: async (args, ctx) => {
        if (USE_MOCK) {
          return ctx.mockService.trackOrder(args.orderId);
        }
        return await ctx.zomatoClient.callMCP('track_order', {
          order_id: args.orderId
        });
      }
    });
  }
}

// ============================================
// ZOMATO MCP CLIENT
// ============================================

class ZomatoMCPClient {
  constructor(url) {
    this.url = url;
  }

  async callMCP(method, params) {
    try {
      const response = await axios.post(this.url, {
        jsonrpc: '2.0',
        id: Date.now(),
        method: 'tools/call',
        params: {
          name: method,
          arguments: params
        }
      }, { timeout: 10000 });

      if (response.data.error) {
        throw new Error(response.data.error.message);
      }

      return response.data.result;
    } catch (error) {
      console.error(`❌ Zomato MCP Error: ${error.message}`);
      throw error;
    }
  }
}

// ============================================
// MOCK SERVICE (FOR TESTING)
// ============================================

class MockZomatoService {
  constructor() {
    this.carts = new Map();
    this.orders = new Map();
  }

  async searchRestaurants(location, cuisine, priceRange) {
    const restaurants = {
      vadodara: [
        {
          id: 'rest_001',
          name: 'Sev Usal House',
          cuisine: 'Gujarati',
          rating: 4.5,
          priceRange: 'budget',
          location: 'Alkapuri, Vadodara',
          deliveryTime: '25-30 mins',
          image: '🍛'
        },
        {
          id: 'rest_002',
          name: 'Mandap Restaurant',
          cuisine: 'North Indian, Gujarati',
          rating: 4.3,
          priceRange: 'mid-range',
          location: 'RC Dutt Road, Vadodara',
          deliveryTime: '30-35 mins',
          image: '🍽️'
        }
      ]
    };

    const key = location.toLowerCase().replace(/\s+/g, '');
    let results = restaurants[key] || restaurants.vadodara;

    if (cuisine) {
      results = results.filter(r => 
        r.cuisine.toLowerCase().includes(cuisine.toLowerCase())
      );
    }

    if (priceRange) {
      results = results.filter(r => r.priceRange === priceRange);
    }

    return { success: true, count: results.length, restaurants: results };
  }

  async getMenu(restaurantId) {
    const menus = {
      'rest_001': {
        restaurantId: 'rest_001',
        restaurantName: 'Sev Usal House',
        categories: [
          {
            name: 'Breakfast Specials',
            items: [
              {
                id: 'item_001',
                name: 'Sev Usal',
                description: 'Traditional Gujarati breakfast',
                price: 80,
                veg: true,
                rating: 4.6
              },
              {
                id: 'item_002',
                name: 'Dabeli',
                description: 'Famous Gujarati street food',
                price: 40,
                veg: true,
                rating: 4.5
              }
            ]
          }
        ]
      }
    };

    const menu = menus[restaurantId];
    return menu ? { success: true, menu } : { success: false, error: 'Restaurant not found' };
  }

  async addToCart(sessionId, restaurantId, itemId, quantity, customizations) {
    if (!this.carts.has(sessionId)) {
      this.carts.set(sessionId, { restaurantId, items: [], total: 0 });
    }

    const cart = this.carts.get(sessionId);
    const item = { itemId, name: 'Sev Usal', price: 80, quantity, customizations };
    cart.items.push(item);
    cart.total += item.price * quantity;

    return { success: true, message: `Added ${quantity}x to cart`, cart };
  }

  async viewCart(sessionId) {
    const cart = this.carts.get(sessionId);
    return cart && cart.items.length > 0 
      ? { success: true, cart }
      : { success: true, message: 'Cart is empty', cart: { items: [], total: 0 } };
  }

  async placeOrder(sessionId, deliveryAddress, paymentMethod) {
    const cart = this.carts.get(sessionId);
    if (!cart || cart.items.length === 0) {
      return { success: false, error: 'Cart is empty' };
    }

    const orderId = `ORD${Date.now()}`;
    const order = {
      orderId,
      items: cart.items,
      total: cart.total,
      deliveryAddress,
      paymentMethod,
      status: 'confirmed',
      estimatedDelivery: '30-35 mins'
    };

    this.orders.set(orderId, order);
    this.carts.delete(sessionId);

    return { success: true, message: 'Order placed!', order };
  }

  async trackOrder(orderId) {
    const order = this.orders.get(orderId);
    return order 
      ? { success: true, order }
      : { success: false, error: 'Order not found' };
  }
}

// ============================================
// INITIALIZE SERVICES
// ============================================

const toolRegistry = new ToolRegistry();
const zomatoClient = new ZomatoMCPClient(ZOMATO_MCP_URL);
const mockService = new MockZomatoService();
const sessions = new Map();

// ============================================
// CHAT ENDPOINT
// ============================================

app.post('/chat', async (req, res) => {
  const startTime = Date.now();
  
  try {
    const { message, sessionId = `session_${Date.now()}` } = req.body;

    console.log('\n' + '='.repeat(60));
    console.log(`📨 New message from session: ${sessionId}`);
    console.log(`💬 User: ${message}`);
    console.log('='.repeat(60));

    if (!message) {
      return res.status(400).json({ error: 'Message required' });
    }

    // Initialize session
    if (!sessions.has(sessionId)) {
      sessions.set(sessionId, { history: [], createdAt: new Date() });
    }

    const session = sessions.get(sessionId);

    // System instruction
    const systemInstruction = `You are a friendly food ordering assistant for Zomato.

Help users:
- Search restaurants by location, cuisine, and price
- Browse menus and recommend dishes
- Add items to cart with customizations
- Place orders with delivery details
- Track order status

Be conversational, ask clarifying questions, and format information clearly.
Always confirm before placing orders.`;

    // Initialize Gemini with tools
    const model = genAI.getGenerativeModel({
      model: 'gemini-2.0-flash',
      systemInstruction,
      tools: toolRegistry.getGeminiTools()
    });

    const chat = model.startChat({ history: session.history });

    // Send message
    let result = await chat.sendMessage(message);
    let response = result.response;

    // Handle function calls
    let callCount = 0;
    const maxCalls = 10;

    while (response.functionCalls?.length > 0 && callCount < maxCalls) {
      const functionCall = response.functionCalls[0];
      
      console.log(`🔄 Function call: ${functionCall.name}`);
      
      // Execute tool with context
      const context = {
        sessionId,
        zomatoClient,
        mockService
      };

      const toolResult = await toolRegistry.executeTool(
        functionCall.name,
        functionCall.args,
        context
      );

      console.log(`✅ Tool result:`, JSON.stringify(toolResult).substring(0, 100));

      // Send result back to Gemini
      result = await chat.sendMessage([{
        functionResponse: {
          name: functionCall.name,
          response: { result: toolResult }
        }
      }]);

      response = result.response;
      callCount++;
    }

    // Get final text response
    let finalResponse = '';
    try {
      finalResponse = response.text();
    } catch (error) {
      console.error('⚠️ No text in response, generating fallback');
      // If no text response, create a summary
      if (callCount > 0) {
        finalResponse = 'I\'ve processed your request. Please let me know if you need any clarification or would like to proceed with your order.';
      } else {
        finalResponse = 'I\'m here to help you order food! Try asking me to search for restaurants, view menus, or place an order.';
      }
    }

    console.log(`💬 Response: ${finalResponse.substring(0, 100)}...`);

    // Update history
    session.history.push(
      { role: 'user', parts: [{ text: message }] },
      { role: 'model', parts: [{ text: finalResponse }] }
    );

    if (session.history.length > 40) {
      session.history = session.history.slice(-40);
    }

    res.json({
      response: finalResponse,
      sessionId,
      toolsUsed: callCount,
      processingTime: `${Date.now() - startTime}ms`
    });

    console.log(`⏱️  Processed in ${Date.now() - startTime}ms`);
    console.log('='.repeat(60) + '\n');

  } catch (error) {
    console.error('❌ Error:', error);
    console.error('Stack:', error.stack);
    res.status(500).json({
      error: 'Request failed',
      details: error.message
    });
  }
});

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    mode: USE_MOCK ? 'mock' : 'production',
    tools: Array.from(toolRegistry.tools.keys())
  });
});

// List available tools
app.get('/tools', (req, res) => {
  const tools = [];
  for (const [name, tool] of toolRegistry.tools) {
    tools.push({
      name: tool.name,
      description: tool.description,
      parameters: tool.inputSchema
    });
  }
  res.json({ tools });
});

// Start server
app.listen(PORT, () => {
  console.log('🍕 ========================================');
  console.log('🚀 Gemini Food Ordering System');
  console.log(`📡 Port: ${PORT}`);
  console.log(`🔧 Mode: ${USE_MOCK ? '🎭 Mock Service' : '🌐 Production'}`);
  console.log(`🤖 Gemini: ${GEMINI_API_KEY ? '✅' : '❌'}`);
  console.log(`🛠️  Tools: ${toolRegistry.tools.size} registered`);
  console.log('🍕 ========================================');
  console.log('\n💡 Endpoints:');
  console.log(`   POST /chat - Main chat endpoint`);
  console.log(`   GET  /tools - List available tools`);
  console.log(`   GET  /health - Health check\n`);
});

export default app;