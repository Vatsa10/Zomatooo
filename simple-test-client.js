// test-client.js - Simple test client for the food ordering system
import axios from 'axios';

const API_URL = 'http://localhost:3000';
const sessionId = `test_${Date.now()}`;

async function chat(message) {
  try {
    console.log(`\n${'='.repeat(60)}`);
    console.log(`👤 You: ${message}`);
    console.log('⏳ Processing...');
    
    const response = await axios.post(`${API_URL}/chat`, {
      message,
      sessionId
    });

    console.log(`\n🤖 Assistant: ${response.data.response}`);
    console.log(`\n📊 Stats:`);
    console.log(`   - Tools used: ${response.data.toolsUsed}`);
    console.log(`   - Processing time: ${response.data.processingTime}`);
    console.log(`   - Session: ${response.data.sessionId}`);
    console.log('='.repeat(60));
    
    return response.data;
  } catch (error) {
    console.error(`\n❌ Error: ${error.response?.data?.error || error.message}`);
    if (error.response?.data?.details) {
      console.error(`   Details: ${error.response.data.details}`);
    }
    return null;
  }
}

async function checkHealth() {
  try {
    const response = await axios.get(`${API_URL}/health`);
    console.log('\n✅ Server Health Check:');
    console.log(`   Status: ${response.data.status}`);
    console.log(`   Mode: ${response.data.mode}`);
    console.log(`   Tools: ${response.data.tools.length} available`);
    console.log(`   Tools: ${response.data.tools.join(', ')}`);
    return true;
  } catch (error) {
    console.error('\n❌ Server not responding');
    console.error('   Please make sure the server is running with: node gemini-food-ordering.js');
    return false;
  }
}

async function listTools() {
  try {
    const response = await axios.get(`${API_URL}/tools`);
    console.log('\n📋 Available Tools:');
    response.data.tools.forEach((tool, i) => {
      console.log(`\n${i + 1}. ${tool.name}`);
      console.log(`   ${tool.description}`);
      console.log(`   Required params: ${tool.parameters.required?.join(', ') || 'none'}`);
    });
  } catch (error) {
    console.error('❌ Could not list tools:', error.message);
  }
}

async function runTests() {
  console.log('🍕 Food Ordering System - Test Client');
  console.log('=====================================\n');

  // Check if server is running
  const isHealthy = await checkHealth();
  if (!isHealthy) {
    return;
  }

  // List available tools
  await listTools();

  console.log('\n\n🧪 Starting conversation tests...\n');
  await new Promise(resolve => setTimeout(resolve, 1000));

  // Test 1: Search restaurants
  await chat('Find Gujarati restaurants in Vadodara');
  await new Promise(resolve => setTimeout(resolve, 2000));

  // Test 2: Get menu
  await chat('Show me the menu for Sev Usal House');
  await new Promise(resolve => setTimeout(resolve, 2000));

  // Test 3: Add to cart
  await chat('Add 2 Sev Usal to my cart');
  await new Promise(resolve => setTimeout(resolve, 2000));

  // Test 4: View cart
  await chat('What\'s in my cart?');
  await new Promise(resolve => setTimeout(resolve, 2000));

  // Test 5: Simple query
  await chat('What can you help me with?');

  console.log('\n\n✅ Test completed!\n');
}

// Check command line arguments
const args = process.argv.slice(2);

if (args.length > 0) {
  // Single message mode
  const message = args.join(' ');
  (async () => {
    const isHealthy = await checkHealth();
    if (isHealthy) {
      await chat(message);
    }
  })();
} else {
  // Run full test suite
  runTests().catch(error => {
    console.error('Test failed:', error.message);
    process.exit(1);
  });
}