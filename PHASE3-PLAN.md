# Phase 3: Order Mutations (Create, Update, Delete) - Implementation Plan

**Date Started:** October 18, 2025  
**Status:** 🔄 IN PROGRESS  
**Estimated Duration:** ~40 hours

---

## 🎯 Phase 3 Goals

Implement safe order mutation operations with full-object update workflow.

### **Exit Criteria:**
- ✅ Full-order mutation workflow (fetch → mutate → upload)
- ✅ `orders.create` MCP tool (create new orders)
- ✅ `orders.update` MCP tool (safe merge workflow)
- ✅ `orders.delete` MCP tool (delete orders)
- ✅ Conflict resolution with retries (5 attempts with exponential backoff)
- ✅ Cache invalidation on mutations
- ✅ Comprehensive tests (>80% coverage)
- ✅ All tests passing
- ✅ Documentation updated

---

## 📋 Tasks Breakdown (10 tasks)

### **Task Group 1: Mutation Helpers (2 tasks)**

**phase3-1:** Implement full-object fetch helper
- Function: `fetch_full_order(client, order_id)`
- Purpose: Get complete order before mutation
- Returns: Full order object
- Status: 🔄 TODO

**phase3-2:** Implement safe merge helper
- Function: `merge_order_changes(original, changes)`
- Purpose: Safely merge partial updates into full object
- Strategy: Shallow merge for top-level, preserve arrays unless specified
- Status: 🔄 TODO

---

### **Task Group 2: HTTP Client Methods (3 tasks)**

**phase3-3:** Implement create_order method
- Endpoint: `POST /orders`
- Validates: Required fields
- Returns: Created order
- Status: 🔄 TODO

**phase3-4:** Implement update_order method  
- Endpoint: `PUT /orders/{order_id}`
- Strategy: Full-object upload (not partial PATCH)
- Conflict handling: Retry on 409
- Status: 🔄 TODO

**phase3-5:** Implement delete_order method
- Endpoint: `DELETE /orders/{order_id}`
- Validates: Order exists
- Returns: Deletion confirmation
- Status: 🔄 TODO

---

### **Task Group 3: MCP Tools (3 tasks)**

**phase3-6:** Create orders.create MCP tool
- Parameters: Order data (email, items, shipping, etc.)
- Validation: Required fields
- Returns: Created order
- Status: 🔄 TODO

**phase3-7:** Create orders.update MCP tool
- Parameters: order_id + partial changes
- Workflow: Fetch → Merge → Upload
- Retries: 5 attempts with exponential backoff
- Returns: Updated order
- Status: 🔄 TODO

**phase3-8:** Create orders.delete MCP tool
- Parameters: order_id
- Validation: Confirmation
- Returns: Deletion status
- Status: 🔄 TODO

---

### **Task Group 4: Cache Invalidation (1 task)**

**phase3-9:** Implement cache invalidation on mutations
- Invalidate: Single order cache on update/delete
- Invalidate: Store cache on create/update/delete
- Strategy: Selective invalidation (not full flush)
- Status: 🔄 TODO

---

### **Task Group 5: Testing (1 task)**

**phase3-10:** Write mutation tests
- test_order_mutations.py (unit tests)
- Test: Create, update, delete workflows
- Test: Conflict resolution
- Test: Cache invalidation
- Coverage: >80%
- Status: 🔄 TODO

---

## 🏗️ Implementation Order

### **Step 1: Mutation Helpers (2-3 hours)**
1. Implement fetch_full_order
2. Implement merge_order_changes

### **Step 2: HTTP Client Methods (3-4 hours)**
3. Implement create_order
4. Implement update_order with retries
5. Implement delete_order

### **Step 3: MCP Tools (4-5 hours)**
6. Create orders.create MCP tool
7. Create orders.update MCP tool
8. Create orders.delete MCP tool

### **Step 4: Cache Invalidation (2 hours)**
9. Implement selective cache invalidation

### **Step 5: Testing (4-5 hours)**
10. Write comprehensive mutation tests

### **Step 6: Validation (1 hour)**
- Run all tests
- Verify mutation workflow
- Check conflict resolution
- Update documentation

**Total Estimated:** ~17-19 hours

---

## 📁 Files to Modify

1. `mcp_server/services/orderdesk_client.py` - Add mutation methods
2. `mcp_server/routers/orders.py` - Add 3 MCP tools
3. `tests/test_order_mutations.py` - New test file
4. `docs/IMPLEMENTATION-GUIDE.md` - Update with Phase 3

---

## 🔧 Technical Specifications

### **Full-Order Update Workflow**

Per specification: **Never use PATCH, always fetch → mutate → PUT**

```python
# 1. Fetch current state
order = await client.get_order(order_id)

# 2. Merge changes
updated_order = merge_order_changes(order, changes)

# 3. Upload full object
result = await client.update_order(order_id, updated_order)
```

**Why:**
- Prevents data loss (no accidental field overwrites)
- Atomic updates (all or nothing)
- Conflict detection (409 if order changed)

### **Conflict Resolution**

```python
@retry_on_conflict(max_retries=5)
async def update_with_retry():
    order = await fetch_full_order()
    merged = merge_order_changes(order, changes)
    return await upload_order(merged)
```

**Retry Strategy:**
- Max retries: 5 (per specification Q13)
- Backoff: 0.5s, 1s, 2s, 4s, 8s
- On 409: Re-fetch and retry
- After 5 attempts: Raise ConflictError

### **Merge Strategy**

```python
def merge_order_changes(original: dict, changes: dict) -> dict:
    """
    Safely merge partial changes into full order.
    
    Rules:
    - Top-level fields: Shallow merge (changes override)
    - Arrays (order_items): Full replacement if provided
    - Nested objects: Shallow merge
    - Null values: Remove field (explicit)
    """
    merged = original.copy()
    
    for key, value in changes.items():
        if value is None:
            # Explicit null = remove field
            merged.pop(key, None)
        else:
            # Override with new value
            merged[key] = value
    
    return merged
```

---

## 📊 Success Metrics

### **Code Quality:**
- ✅ All linter checks pass
- ✅ Type checking passes
- ✅ Test coverage >80%
- ✅ All core tests passing

### **Functionality:**
- ✅ Can create orders
- ✅ Can update orders safely
- ✅ Can delete orders
- ✅ Conflict resolution works
- ✅ Cache invalidation works
- ✅ Retries handle conflicts

### **Safety:**
- ✅ No data loss on updates
- ✅ Atomic operations
- ✅ Proper error messages
- ✅ Audit logging for mutations

---

## 🚀 GitHub & Linear Updates

### **Update Frequency:**
- After mutation helpers (1 commit)
- After HTTP methods (1 commit)
- After MCP tools (1 commit)
- After tests (1 commit)

### **Commit Messages:**
- `feat(phase3): Implement mutation helpers`
- `feat(phase3): Add order mutation HTTP methods`
- `feat(phase3): Implement order mutation MCP tools`
- `feat(phase3): Add mutation tests and cache invalidation`

---

## ⚠️ Known Challenges

### **Challenge 1: Conflict Resolution**
- **Issue:** Multiple agents updating same order
- **Solution:** Full-object workflow + 5 retries with backoff

### **Challenge 2: Cache Invalidation**
- **Issue:** Stale cache after mutations
- **Solution:** Selective invalidation (single order + list)

### **Challenge 3: Required Fields**
- **Issue:** OrderDesk has many required fields for create
- **Solution:** Comprehensive validation with helpful error messages

---

## 🎯 Ready to Start!

**Next Action:** Begin with phase3-1 (Implement full-object fetch helper)

**Estimated Completion:** October 18, 2025 (same day, ~4-5 hours remaining)

---

