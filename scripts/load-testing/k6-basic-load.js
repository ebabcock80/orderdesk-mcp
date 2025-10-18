import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');

// Configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';
const MASTER_KEY = __ENV.MASTER_KEY || 'dev-admin-master-key-change-in-production-VNS09qKDdt';

// Load test configuration
export const options = {
  stages: [
    { duration: '1m', target: 10 },   // Ramp up to 10 users over 1 minute
    { duration: '3m', target: 10 },   // Stay at 10 users for 3 minutes
    { duration: '1m', target: 20 },   // Ramp up to 20 users
    { duration: '3m', target: 20 },   // Stay at 20 users for 3 minutes
    { duration: '1m', target: 0 },    // Ramp down to 0 users
  ],
  thresholds: {
    'http_req_duration': ['p(95)<2000'],  // 95% of requests under 2s
    'http_req_failed': ['rate<0.01'],     // Less than 1% errors
    'errors': ['rate<0.01'],              // Less than 1% custom errors
  },
};

// Test data
const testStoreId = 'test-store-001';
const testApiKey = 'test-api-key-001';

export default function () {
  // Test 1: Health Check
  let response = http.get(`${BASE_URL}/health`);
  check(response, {
    'health check status 200': (r) => r.status === 200,
    'health check has ok status': (r) => r.json('status') === 'ok',
  });

  sleep(0.5);

  // Test 2: MCP Protocol - Initialize
  response = http.post(
    `${BASE_URL}/mcp?token=${MASTER_KEY}`,
    JSON.stringify({
      jsonrpc: '2.0',
      id: 1,
      method: 'initialize',
      params: {
        protocolVersion: '2024-11-05',
        capabilities: {},
        clientInfo: { name: 'k6-load-test', version: '1.0.0' }
      }
    }),
    { headers: { 'Content-Type': 'application/json' } }
  );
  
  const initSuccess = check(response, {
    'initialize status 200': (r) => r.status === 200,
    'initialize has result': (r) => r.json('result') !== undefined,
  });
  errorRate.add(!initSuccess);

  sleep(0.5);

  // Test 3: MCP Protocol - List Tools
  response = http.post(
    `${BASE_URL}/mcp?token=${MASTER_KEY}`,
    JSON.stringify({
      jsonrpc: '2.0',
      id: 2,
      method: 'tools/list',
      params: {}
    }),
    { headers: { 'Content-Type': 'application/json' } }
  );
  
  const toolsSuccess = check(response, {
    'tools/list status 200': (r) => r.status === 200,
    'tools/list has tools': (r) => r.json('result.tools') !== undefined,
    'tools/list has 11 tools': (r) => r.json('result.tools.length') >= 11,
  });
  errorRate.add(!toolsSuccess);

  sleep(0.5);

  // Test 4: MCP Protocol - Call stores_list
  response = http.post(
    `${BASE_URL}/mcp?token=${MASTER_KEY}`,
    JSON.stringify({
      jsonrpc: '2.0',
      id: 3,
      method: 'tools/call',
      params: {
        name: 'stores_list',
        arguments: {}
      }
    }),
    { headers: { 'Content-Type': 'application/json' } }
  );
  
  const storesSuccess = check(response, {
    'stores_list status 200': (r) => r.status === 200,
    'stores_list has content': (r) => r.json('result.content') !== undefined,
  });
  errorRate.add(!storesSuccess);

  sleep(1);

  // Test 5: Health Check Detailed (heavier operation)
  response = http.get(`${BASE_URL}/health/detailed`);
  check(response, {
    'detailed health status 200': (r) => r.status === 200,
    'detailed health has checks': (r) => r.json('checks') !== undefined,
  });

  sleep(2);
}

// Setup function (runs once per VU at start)
export function setup() {
  console.log(`Starting load test against ${BASE_URL}`);
  console.log(`Using master key: ${MASTER_KEY.substring(0, 10)}...`);
  
  // Verify server is healthy before starting
  const healthCheck = http.get(`${BASE_URL}/health`);
  if (healthCheck.status !== 200) {
    throw new Error(`Server not healthy: ${healthCheck.status}`);
  }
  
  console.log('✅ Server health check passed, starting load test...');
  return { startTime: new Date() };
}

// Teardown function (runs once at end)
export function teardown(data) {
  const endTime = new Date();
  const duration = (endTime - data.startTime) / 1000;
  console.log(`Load test completed in ${duration.toFixed(1)}s`);
}

