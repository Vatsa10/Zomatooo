// test.js - Test the Food Ordering System
import axios from 'axios';

const API_URL = 'http://localhost:3000';
const sessionId = `test_session_${Date.now()}`;

// Colors for console output
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m'
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

async function sendMessage(message) {
  try {
    log(`\n👤 User: ${message}`, 'blue');
    
    const response = await axios.post(`${API_URL}/chat`, {
      message,
      sessionId
    });

    log(`🤖 Assistant: ${response.data.response}`, 'green');
    return response.data;
  } catch (error) {
    log(`❌ Error: ${error.response?.data?.error || error.message}`, 'red');
    return null;
  }
}

async function testHealthCheck() {
  log('\n=== Health Check ===', 'magenta');
  try {
    const response = await axios.get(`${API_URL}/health`);
    log(`✅ Server is healthy`, 'green');
    log(JSON.stringify(response.data, null, 2), 'yellow');
    return true;
  } catch (error) {
    log(`❌ Health check failed: ${error.message}`, 'red');
    return false;
  }
}

async function runTests() {
  log('🍕 Starting Food Ordering System Tests', 'magenta');
  log(`📝 Session ID: ${sessionId}`, 'yellow');

  // Check if server is running
  const isHealthy = await testHealthCheck();
  if (!isHealthy) {
    log('\n❌ Server is not running. Please start the server first with: npm start', 'red');
    return;
  }

  // Wait a bit
  await new Promise(resolve => setTimeout(resolve, 1000));

  // Test 1: Restaurant Search
  log('\n\n=== Test 1: Restaurant Search ===', 'magenta');
  await sendMessage('Find me Italian restaurants in Mumbai');
  await new Promise(resolve => setTimeout(resolve, 2000));

  // Test 2: Menu Browse
  log('\n\n=== Test 2: Get Menu (you may need to adjust restaurant ID) ===', 'magenta');
  await sendMessage('Show me the menu for the first restaurant');
  await new Promise(resolve => setTimeout(resolve, 2000));

  // Test 3: Budget Search
  log('\n\n=== Test 3: Budget Restaurant Search ===', 'magenta');
  await sendMessage('Find budget-friendly Chinese restaurants near me');
  await new Promise(resolve => setTimeout(resolve, 2000));

  // Test 4: Add to Cart
  log('\n\n=== Test 4: Add to Cart ===', 'magenta');
  await sendMessage('I want to order pizza');
  await new Promise(resolve => setTimeout(resolve, 2000));

  // Test 5: View Cart
  log('\n\n=== Test 5: View Cart ===', 'magenta');
  await sendMessage('What\'s in my cart?');
  await new Promise(resolve => setTimeout(resolve, 2000));

  // Test 6: Conversational
  log('\n\n=== Test 6: Conversational Query ===', 'magenta');
  await sendMessage('What do you recommend for a vegetarian lunch?');
  await new Promise(resolve => setTimeout(resolve, 2000));

  // Test 7: Session Info
  log('\n\n=== Test 7: Session Info ===', 'magenta');
  try {
    const response = await axios.get(`${API_URL}/session/${sessionId}`);
    log('Session details:', 'green');
    log(JSON.stringify(response.data, null, 2), 'yellow');
  } catch (error) {
    log(`❌ Error getting session: ${error.message}`, 'red');
  }

  log('\n\n✅ Tests completed!', 'green');
  log('💡 Tip: You can now test the chat interface by opening index.html in your browser', 'yellow');
}

// Run tests
runTests().catch(error => {
  log(`\n❌ Test suite failed: ${error.message}`, 'red');
  process.exit(1);
});