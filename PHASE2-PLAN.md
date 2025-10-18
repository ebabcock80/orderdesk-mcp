# Phase 2: Order Read Path & Pagination - Implementation Plan

**Date Started:** October 18, 2025  
**Status:** 🔄 IN PROGRESS  
**Estimated Duration:** ~35 hours

---

## 🎯 Phase 2 Goals

Implement read-only OrderDesk API integration with proper HTTP client, pagination, and caching.

### **Exit Criteria:**
- ✅ HTTP client with retries (exponential backoff for 429/5xx)
- ✅ `orders.get` MCP tool (fetch single order)
- ✅ `orders.list` MCP tool (with pagination)
- ✅ Read-through caching (15-second TTL for orders)
- ✅ Comprehensive tests (>80% coverage)
- ✅ Integration tests (optional, env-gated)
- ✅ All tests passing
- ✅ Documentation updated

---

## 📋 Tasks Breakdown (12 tasks)

### **Task Group 1: HTTP Client (4 tasks)**

**phase2-1:** Create OrderDesk HTTP client base class
- File: `mcp_server/services/orderdesk_client.py` (new)
- Implement: httpx.AsyncClient with base configuration
- Features: Base URL, timeout, headers
- Status: 🔄 TODO

**phase2-2:** Add retry logic with exponential backoff
- Add: Retry decorator with exponential backoff
- Retries: 3 for 429/5xx errors
- Backoff: 1s, 2s, 4s with jitter
- Status: 🔄 TODO

**phase2-3:** Add error handling and logging
- OrderDeskAPIError exception class
- HTTP status code mapping
- Structured logging with correlation IDs
- Status: 🔄 TODO

**phase2-4:** Add authentication (store credentials)
- Integrate with StoreService for credential decryption
- Add store_id + api_key authentication
- Status: 🔄 TODO

---

### **Task Group 2: Order Operations (3 tasks)**

**phase2-5:** Implement orders.get method
- Endpoint: `GET /orders/{order_id}`
- Response: Single order object
- Error handling: 404, 401, 500
- Status: 🔄 TODO

**phase2-6:** Implement orders.list method
- Endpoint: `GET /orders`
- Query params: limit, offset, folder_id, status
- Response: Array of orders with metadata
- Status: 🔄 TODO

**phase2-7:** Add pagination controls
- Limit: 1-100 (default 50)
- Offset: 0+ (default 0)
- Return: total_count, has_more metadata
- Status: 🔄 TODO

---

### **Task Group 3: MCP Tools (2 tasks)**

**phase2-8:** Create orders.get MCP tool
- Pydantic schema with order_id parameter
- Call orderdesk_client.get_order()
- Return formatted response
- Status: 🔄 TODO

**phase2-9:** Create orders.list MCP tool
- Pydantic schema with pagination params
- Call orderdesk_client.list_orders()
- Return paginated response
- Status: 🔄 TODO

---

### **Task Group 4: Caching (1 task)**

**phase2-10:** Implement read-through caching
- Cache key: `tenant:{tenant_id}:store:{store_id}:orders:{order_id}`
- TTL: 15 seconds (per spec)
- Backend: Memory (default) or Redis
- Invalidation: On mutation (Phase 3+)
- Status: 🔄 TODO

---

### **Task Group 5: Tests (2 tasks)**

**phase2-11:** Write unit tests
- test_orderdesk_client.py (HTTP client tests)
- test_orders_tools.py (MCP tool tests)
- Mocking: httpx responses
- Coverage: >80%
- Status: 🔄 TODO

**phase2-12:** Write integration tests (optional)
- test_orders_integration.py (real OrderDesk API)
- Env-gated: ORDERDESK_TEST_ENABLED=true
- Uses: ORDERDESK_TEST_STORE_ID, ORDERDESK_TEST_API_KEY
- Status: 🔄 TODO

---

## 🏗️ Implementation Order

### **Step 1: HTTP Client Foundation (4-6 hours)**
1. Create OrderDeskClient class
2. Add retry logic
3. Add error handling
4. Add authentication

### **Step 2: Order Operations (3-4 hours)**
5. Implement orders.get
6. Implement orders.list
7. Add pagination controls

### **Step 3: MCP Tools (2-3 hours)**
8. Create orders.get MCP tool
9. Create orders.list MCP tool

### **Step 4: Caching (2-3 hours)**
10. Implement read-through caching

### **Step 5: Testing (4-6 hours)**
11. Write unit tests
12. Write integration tests

### **Step 6: Validation (2 hours)**
- Run all tests
- Verify pagination
- Check caching behavior
- Update documentation

**Total Estimated:** ~20-25 hours (conservative estimate)

---

## 📁 Files to Create

### **New Files:**
1. `mcp_server/services/orderdesk_client.py` - HTTP client
2. `tests/test_orderdesk_client.py` - Client tests
3. `tests/test_orders_tools.py` - MCP tool tests
4. `tests/test_orders_integration.py` - Integration tests (optional)

### **Files to Modify:**
5. `mcp_server/routers/orders.py` - Update MCP tools
6. `mcp_server/services/cache.py` - Enhance caching
7. `mcp_server/main.py` - Uncomment orders router
8. `docs/IMPLEMENTATION-GUIDE.md` - Add Phase 2 docs

---

## 🔧 Technical Specifications

### **HTTP Client:**
```python
class OrderDeskClient:
    base_url = "https://app.orderdesk.me/api/v2"
    timeout = httpx.Timeout(connect=15.0, read=60.0)
    max_retries = 3
    retry_statuses = [429, 500, 502, 503, 504]
```

### **Retry Logic:**
```python
@retry_with_exponential_backoff(
    max_retries=3,
    base_delay=1.0,
    max_delay=10.0,
    jitter=True
)
```

### **Pagination:**
```python
{
  "orders": [...],
  "total_count": 150,
  "limit": 50,
  "offset": 0,
  "has_more": true
}
```

### **Caching:**
```python
cache_key = f"tenant:{tenant_id}:store:{store_id}:orders:{order_id}"
ttl = 15  # seconds
```

---

## 📊 Success Metrics

### **Code Quality:**
- ✅ All linter checks pass (ruff, black)
- ✅ Type checking passes (mypy --strict)
- ✅ Test coverage >80%
- ✅ All tests passing (unit + integration)

### **Functionality:**
- ✅ Can fetch single order
- ✅ Can list orders with pagination
- ✅ Pagination controls work (limit, offset)
- ✅ Caching reduces API calls
- ✅ Retries handle temporary failures
- ✅ Error messages are helpful

### **Performance:**
- ✅ Cache hit rate >50% in normal usage
- ✅ Response time <100ms (cached)
- ✅ Response time <2s (uncached)
- ✅ Handles rate limiting gracefully

---

## 🚀 GitHub & Linear Updates

### **Update Frequency:**
- After each task group (4 commits total)
- Update Linear project description with progress
- Create Linear issues for any blockers

### **Commit Messages:**
- `feat(phase2): Implement OrderDesk HTTP client`
- `feat(phase2): Add order read operations`
- `feat(phase2): Implement MCP tools for orders`
- `feat(phase2): Add caching and tests`

---

## 📝 Documentation Updates

### **Files to Update:**
1. `docs/IMPLEMENTATION-GUIDE.md` - Add Phase 2 section
2. `IMPLEMENTATION-STATUS.md` - Update progress
3. `README.md` - Add orders.get and orders.list tools
4. `PHASE2-COMPLETE.md` - Create completion report

---

## ⚠️ Known Challenges

### **Challenge 1: OrderDesk API Rate Limiting**
- **Issue:** 120 requests/minute limit
- **Solution:** Caching + token bucket rate limiter (already implemented in Phase 1)

### **Challenge 2: Pagination Edge Cases**
- **Issue:** Last page, empty results
- **Solution:** Proper has_more flag, handle empty arrays

### **Challenge 3: Error Handling**
- **Issue:** Many possible error states (401, 404, 429, 500, etc.)
- **Solution:** Comprehensive error mapping, helpful messages

---

## 🎯 Ready to Start!

**Next Action:** Begin with phase2-1 (Create OrderDesk HTTP client base class)

**Estimated Completion:** October 20-21, 2025 (2-3 days at ~8-12 hours/day)

---

