// mockZomatoService.js - Mock Zomato Service for Testing
// Use this until OAuth is properly configured

export class MockZomatoService {
  constructor() {
    this.restaurants = this.generateMockRestaurants();
    this.carts = new Map();
    this.orders = new Map();
  }

  generateMockRestaurants() {
    return {
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
        },
        {
          id: 'rest_003',
          name: 'Jassi De Parathe',
          cuisine: 'North Indian, Punjabi',
          rating: 4.6,
          priceRange: 'budget',
          location: 'Sayajigunj, Vadodara',
          deliveryTime: '20-25 mins',
          image: '🥘'
        },
        {
          id: 'rest_004',
          name: 'The Barbeque Nation',
          cuisine: 'BBQ, North Indian',
          rating: 4.4,
          priceRange: 'premium',
          location: 'Alkapuri, Vadodara',
          deliveryTime: '35-40 mins',
          image: '🍖'
        }
      ],
      mumbai: [
        {
          id: 'rest_101',
          name: 'Pizza Express',
          cuisine: 'Italian, Pizza',
          rating: 4.2,
          priceRange: 'mid-range',
          location: 'Bandra, Mumbai',
          deliveryTime: '30-35 mins',
          image: '🍕'
        },
        {
          id: 'rest_102',
          name: 'Pasta Lovers',
          cuisine: 'Italian',
          rating: 4.5,
          priceRange: 'mid-range',
          location: 'Andheri, Mumbai',
          deliveryTime: '25-30 mins',
          image: '🍝'
        }
      ],
      delhi: [
        {
          id: 'rest_201',
          name: 'Biryani Blues',
          cuisine: 'Biryani, Indian',
          rating: 4.7,
          priceRange: 'budget',
          location: 'Connaught Place, Delhi',
          deliveryTime: '30-35 mins',
          image: '🍚'
        }
      ]
    };
  }

  getMenus() {
    return {
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
                description: 'Traditional Gujarati breakfast with crispy sev and spicy usal',
                price: 80,
                veg: true,
                rating: 4.6
              },
              {
                id: 'item_002',
                name: 'Dabeli',
                description: 'Famous Gujarati street food with peanuts and pomegranate',
                price: 40,
                veg: true,
                rating: 4.5
              },
              {
                id: 'item_003',
                name: 'Khaman Dhokla',
                description: 'Steamed savory cake made from gram flour',
                price: 60,
                veg: true,
                rating: 4.4
              }
            ]
          },
          {
            name: 'Main Course',
            items: [
              {
                id: 'item_004',
                name: 'Gujarati Thali',
                description: 'Complete meal with dal, kadhi, vegetables, roti, rice',
                price: 200,
                veg: true,
                rating: 4.7
              },
              {
                id: 'item_005',
                name: 'Undhiyu',
                description: 'Mixed vegetable curry - Gujarati specialty',
                price: 150,
                veg: true,
                rating: 4.5
              }
            ]
          }
        ]
      },
      'rest_002': {
        restaurantId: 'rest_002',
        restaurantName: 'Mandap Restaurant',
        categories: [
          {
            name: 'North Indian',
            items: [
              {
                id: 'item_101',
                name: 'Butter Chicken',
                description: 'Creamy tomato-based chicken curry',
                price: 280,
                veg: false,
                rating: 4.6
              },
              {
                id: 'item_102',
                name: 'Paneer Butter Masala',
                description: 'Cottage cheese in rich creamy gravy',
                price: 220,
                veg: true,
                rating: 4.5
              }
            ]
          }
        ]
      },
      'rest_003': {
        restaurantId: 'rest_003',
        restaurantName: 'Jassi De Parathe',
        categories: [
          {
            name: 'Parathas',
            items: [
              {
                id: 'item_201',
                name: 'Aloo Paratha',
                description: 'Stuffed with spiced potato filling',
                price: 60,
                veg: true,
                rating: 4.7
              },
              {
                id: 'item_202',
                name: 'Paneer Paratha',
                description: 'Stuffed with cottage cheese',
                price: 80,
                veg: true,
                rating: 4.6
              },
              {
                id: 'item_203',
                name: 'Mix Veg Paratha',
                description: 'Stuffed with mixed vegetables',
                price: 70,
                veg: true,
                rating: 4.5
              }
            ]
          }
        ]
      },
      'rest_101': {
        restaurantId: 'rest_101',
        restaurantName: 'Pizza Express',
        categories: [
          {
            name: 'Pizzas',
            items: [
              {
                id: 'item_301',
                name: 'Margherita Pizza',
                description: 'Classic pizza with mozzarella and basil',
                price: 299,
                veg: true,
                rating: 4.4
              },
              {
                id: 'item_302',
                name: 'Pepperoni Pizza',
                description: 'Loaded with pepperoni and cheese',
                price: 399,
                veg: false,
                rating: 4.5
              }
            ]
          }
        ]
      }
    };
  }

  // Search restaurants
  async searchRestaurants(location, cuisine = null, priceRange = null) {
    console.log('🔍 Mock Search:', { location, cuisine, priceRange });
    
    const locationKey = location.toLowerCase().replace(/\s+/g, '');
    let restaurants = this.restaurants[locationKey] || this.restaurants.vadodara;

    // Filter by cuisine
    if (cuisine) {
      const cuisineLower = cuisine.toLowerCase();
      restaurants = restaurants.filter(r => 
        r.cuisine.toLowerCase().includes(cuisineLower)
      );
    }

    // Filter by price range
    if (priceRange) {
      restaurants = restaurants.filter(r => r.priceRange === priceRange);
    }

    return {
      success: true,
      location,
      count: restaurants.length,
      restaurants
    };
  }

  // Get menu
  async getMenu(restaurantId) {
    console.log('📋 Mock Get Menu:', restaurantId);
    
    const menus = this.getMenus();
    const menu = menus[restaurantId];

    if (!menu) {
      return {
        success: false,
        error: 'Restaurant not found'
      };
    }

    return {
      success: true,
      menu
    };
  }

  // Add to cart
  async addToCart(sessionId, restaurantId, itemId, quantity, customizations = null) {
    console.log('🛒 Mock Add to Cart:', { sessionId, restaurantId, itemId, quantity });

    if (!this.carts.has(sessionId)) {
      this.carts.set(sessionId, {
        restaurantId,
        items: [],
        total: 0
      });
    }

    const cart = this.carts.get(sessionId);

    // Find item details
    const menus = this.getMenus();
    const menu = menus[restaurantId];
    
    if (!menu) {
      return {
        success: false,
        error: 'Restaurant not found'
      };
    }

    let foundItem = null;
    for (const category of menu.categories) {
      const item = category.items.find(i => i.id === itemId);
      if (item) {
        foundItem = item;
        break;
      }
    }

    if (!foundItem) {
      return {
        success: false,
        error: 'Item not found'
      };
    }

    // Add item to cart
    const cartItem = {
      itemId,
      name: foundItem.name,
      price: foundItem.price,
      quantity,
      customizations,
      subtotal: foundItem.price * quantity
    };

    cart.items.push(cartItem);
    cart.total = cart.items.reduce((sum, item) => sum + item.subtotal, 0);

    return {
      success: true,
      message: `Added ${quantity}x ${foundItem.name} to cart`,
      cart
    };
  }

  // View cart
  async viewCart(sessionId) {
    console.log('👀 Mock View Cart:', sessionId);

    const cart = this.carts.get(sessionId);

    if (!cart || cart.items.length === 0) {
      return {
        success: true,
        message: 'Your cart is empty',
        cart: {
          items: [],
          total: 0
        }
      };
    }

    return {
      success: true,
      cart
    };
  }

  // Place order
  async placeOrder(sessionId, deliveryAddress, paymentMethod) {
    console.log('📦 Mock Place Order:', { sessionId, deliveryAddress, paymentMethod });

    const cart = this.carts.get(sessionId);

    if (!cart || cart.items.length === 0) {
      return {
        success: false,
        error: 'Cart is empty'
      };
    }

    const orderId = `ORD${Date.now()}`;
    const order = {
      orderId,
      items: cart.items,
      total: cart.total,
      deliveryAddress,
      paymentMethod,
      status: 'confirmed',
      estimatedDelivery: '30-35 mins',
      placedAt: new Date().toISOString()
    };

    this.orders.set(orderId, order);
    this.carts.delete(sessionId); // Clear cart

    return {
      success: true,
      message: 'Order placed successfully!',
      order
    };
  }

  // Track order
  async trackOrder(orderId) {
    console.log('📍 Mock Track Order:', orderId);

    const order = this.orders.get(orderId);

    if (!order) {
      return {
        success: false,
        error: 'Order not found'
      };
    }

    // Simulate order progression
    const statuses = ['confirmed', 'preparing', 'out_for_delivery', 'delivered'];
    const currentStatusIndex = statuses.indexOf(order.status);
    
    if (currentStatusIndex < statuses.length - 1) {
      order.status = statuses[currentStatusIndex + 1];
    }

    return {
      success: true,
      order: {
        orderId: order.orderId,
        status: order.status,
        estimatedDelivery: order.estimatedDelivery,
        deliveryAddress: order.deliveryAddress,
        total: order.total
      }
    };
  }
}

export default MockZomatoService;