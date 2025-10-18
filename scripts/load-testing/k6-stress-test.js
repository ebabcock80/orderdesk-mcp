import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const toolCalls = new Counter('mcp_tool_calls');
const authFailures = new Counter('auth_failures');
const cacheHits = new Trend('cache_response_time');

// Configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';
const MASTER_KEY = __ENV.MASTER_KEY || 'dev-admin-master-key-change-in-production-VNS09qKDdt';

// Stress test configuration
export const options = {
  stages: [
    { duration: '2m', target: 50 },    // Ramp to 50 users
    { duration: '5m', target: 50 },    // Hold at 50 users
    { duration: '2m', target: 100 },   // Ramp to 100 users
    { duration: '5m', target: 100 },   // Hold at 100 users
    { duration: '2m', target: 150 },   // Ramp to 150 users (stress)
    { duration: '5m', target: 150 },   // Hold at 150 users
    { duration: '3m', target: 0 },     // Ramp down
  ],
  thresholds: {
    'http_req_duration': ['p(95)<3000', 'p(99)<5000'],
    'http_req_failed': ['rate<0.05'],  // Less than 5% errors under stress
    'errors': ['rate<0.05'],
  },
};

// Simulate different user behaviors
export default function () {
  const scenario = Math.random();
  
  if (scenario < 0.4) {
    // 40% - Read operations (most common)
    testReadOperations();
  } else if (scenario < 0.7) {
    // 30% - MCP tool calls
    testMCPToolCalls();
  } else if (scenario < 0.9) {
    // 20% - Health checks and metrics
    testMonitoring();
  } else {
    // 10% - Authentication and session
    testAuthentication();
  }
  
  sleep(Math.random() * 3 + 1);  // Random sleep 1-4 seconds
}

function testReadOperations() {
  // Simulate reading orders/products
  const response = http.post(
    `${BASE_URL}/mcp?token=${MASTER_KEY}`,
    JSON.stringify({
      jsonrpc: '2.0',
      id: Math.floor(Math.random() * 10000),
      method: 'tools/call',
      params: {
        name: 'stores_list',
        arguments: {}
      }
    }),
    { headers: { 'Content-Type': 'application/json' } }
  );
  
  const success = check(response, {
    'read operation status 200': (r) => r.status === 200,
  });
  
  errorRate.add(!success);
  toolCalls.add(1);
}

function testMCPToolCalls() {
  // Test MCP protocol overhead
  const methods = ['initialize', 'tools/list', 'prompts/list', 'resources/list'];
  const method = methods[Math.floor(Math.random() * methods.length)];
  
  const response = http.post(
    `${BASE_URL}/mcp?token=${MASTER_KEY}`,
    JSON.stringify({
      jsonrpc: '2.0',
      id: Math.floor(Math.random() * 10000),
      method: method,
      params: {}
    }),
    { headers: { 'Content-Type': 'application/json' } }
  );
  
  const success = check(response, {
    'mcp call status 200': (r) => r.status === 200,
  });
  
  errorRate.add(!success);
  toolCalls.add(1);
}

function testMonitoring() {
  // Health checks and metrics
  const endpoints = ['/health', '/health/ready', '/health/live', '/metrics'];
  const endpoint = endpoints[Math.floor(Math.random() * endpoints.length)];
  
  const response = http.get(`${BASE_URL}${endpoint}`);
  
  check(response, {
    'monitoring endpoint status 200': (r) => r.status === 200,
  });
}

function testAuthentication() {
  // Test authentication with invalid key (should fail gracefully)
  const response = http.post(
    `${BASE_URL}/mcp?token=invalid-key-${Math.random()}`,
    JSON.stringify({
      jsonrpc: '2.0',
      id: 1,
      method: 'tools/list',
      params: {}
    }),
    { headers: { 'Content-Type': 'application/json' } }
  );
  
  const isAuthFailure = response.status === 401 || response.status === 403 || 
                        (response.status === 200 && response.json('error') !== undefined);
  
  if (isAuthFailure) {
    authFailures.add(1);
  }
  
  check(response, {
    'auth failure handled gracefully': (r) => r.status < 500,  // No 500 errors
  });
}

export function setup() {
  console.log(`🚀 Starting stress test against ${BASE_URL}`);
  console.log(`Target: 150 concurrent users`);
  console.log(`Duration: ~26 minutes`);
  
  // Warm up server
  console.log('Warming up server...');
  http.get(`${BASE_URL}/health`);
  
  console.log('✅ Ready to start stress test');
  return { startTime: new Date() };
}

export function teardown(data) {
  const endTime = new Date();
  const duration = (endTime - data.startTime) / 1000 / 60;
  console.log(`✅ Stress test completed in ${duration.toFixed(1)} minutes`);
}

