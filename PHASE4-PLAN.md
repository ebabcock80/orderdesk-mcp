# Phase 4: Product Operations - Implementation Plan

**Date Started:** October 18, 2025  
**Status:** 🔄 IN PROGRESS  
**Estimated Duration:** ~15 hours

---

## 🎯 Phase 4 Goals

Implement product catalog operations with caching and search capabilities.

### **Exit Criteria:**
- ✅ HTTP client product methods (get, list)
- ✅ `products.get` MCP tool (fetch single product)
- ✅ `products.list` MCP tool (with pagination and search)
- ✅ Product caching (60-second TTL per spec)
- ✅ Search functionality
- ✅ Comprehensive tests (>80% coverage)
- ✅ All tests passing
- ✅ Documentation updated
- ✅ GitHub and Linear updated

---

## 📋 Tasks Breakdown (8 tasks)

### **Task Group 1: HTTP Client Methods (2 tasks)**

**phase4-1:** Implement get_product method
- Endpoint: `GET /inventory/{product_id}`
- Returns: Single product object
- Error handling: 404, 401, 500
- Status: 🔄 TODO

**phase4-2:** Implement list_products method  
- Endpoint: `GET /inventory`
- Query params: limit, offset, search
- Returns: Array of products with metadata
- Status: 🔄 TODO

---

### **Task Group 2: MCP Tools (2 tasks)**

**phase4-3:** Create products.get MCP tool
- Parameters: product_id, store_identifier?
- Caching: 60-second TTL
- Returns: Product details
- Status: 🔄 TODO

**phase4-4:** Create products.list MCP tool
- Parameters: limit, offset, search?, store_identifier?
- Pagination: Similar to orders.list
- Returns: Products array + pagination
- Status: 🔄 TODO

---

### **Task Group 3: Caching (1 task)**

**phase4-5:** Implement product caching
- TTL: 60 seconds (per spec - longer than orders)
- Cache key: tenant:store:products/{id}
- Invalidation: On product updates (Phase 5+ if needed)
- Status: 🔄 TODO

---

### **Task Group 4: Testing (2 tasks)**

**phase4-6:** Write unit tests
- test_products_client.py (client methods)
- test_products_mcp.py (MCP tools)
- Coverage: >80%
- Status: 🔄 TODO

**phase4-7:** Write integration tests (optional)
- test_products_integration.py (real API)
- Env-gated: ORDERDESK_TEST_ENABLED
- Status: 🔄 TODO

---

### **Task Group 5: Documentation (1 task)**

**phase4-8:** Update documentation
- docs/IMPLEMENTATION-GUIDE.md - Add Phase 4
- PHASE4-COMPLETE.md - Create summary
- Update Linear and GitHub
- Status: 🔄 TODO

---

## 🏗️ Implementation Order

### **Step 1: HTTP Client Methods (2-3 hours)**
1. Implement get_product
2. Implement list_products with search

### **Step 2: MCP Tools (2-3 hours)**
3. Create products.get MCP tool
4. Create products.list MCP tool

### **Step 3: Caching (1 hour)**
5. Integrate product caching (60s TTL)

### **Step 4: Testing (3-4 hours)**
6. Write unit tests
7. Write integration tests

### **Step 5: Documentation (1-2 hours)**
8. Update all documentation

**Total Estimated:** ~10-15 hours

---

## 📁 Files to Modify

1. `mcp_server/services/orderdesk_client.py` - Add product methods
2. `mcp_server/routers/products.py` - Add 2 MCP tools
3. `mcp_server/main.py` - Uncomment products router
4. `tests/test_products_client.py` - New test file
5. `tests/test_products_mcp.py` - New test file
6. `docs/IMPLEMENTATION-GUIDE.md` - Update with Phase 4

---

## 🔧 Technical Specifications

### **OrderDesk Product API:**

**Get Product:**
```
GET /api/v2/inventory/{product_id}?store_id={id}&api_key={key}
```

**List Products:**
```
GET /api/v2/inventory?store_id={id}&api_key={key}&limit=50&offset=0&search=query
```

### **Product Object Structure:**
```json
{
  "id": "product-123",
  "name": "Premium Widget",
  "price": 49.99,
  "sku": "WIDGET-001",
  "quantity": 100,
  "weight": 1.5,
  "category": "Electronics",
  "description": "High-quality widget",
  "created": "2025-01-01T00:00:00Z",
  "modified": "2025-10-18T00:00:00Z"
}
```

### **Caching Strategy:**
- **TTL:** 60 seconds (4x longer than orders)
- **Reason:** Products change less frequently
- **Cache Key:** `tenant:{id}:store:{id}:products/{product_id}`
- **Invalidation:** Manual or TTL expiry

---

## 📊 Success Metrics

### **Code Quality:**
- ✅ All linter checks pass
- ✅ Type checking passes
- ✅ Test coverage >80%
- ✅ All new tests passing

### **Functionality:**
- ✅ Can fetch single product
- ✅ Can list products with pagination
- ✅ Search works correctly
- ✅ Caching reduces API calls
- ✅ Proper error messages

---

## 🚀 GitHub & Linear Updates

### **Update Frequency:**
- After HTTP client methods (1 commit)
- After MCP tools (1 commit)
- After tests (1 commit)
- After documentation (1 commit)

### **Linear Updates:**
- Update project description after each commit
- Track progress (tasks completed)

---

## 🎯 Ready to Start!

**Next Action:** Begin with phase4-1 (Implement get_product method)

**Using Context7 for:** OrderDesk API documentation, httpx best practices

---

