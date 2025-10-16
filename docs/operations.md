# OrderDesk MCP Operations Guide

This document provides detailed information about the order mutation workflow, caching behavior, and webhook processing.

## Full Order Update Workflow

OrderDesk requires complete order objects for all updates. This server implements a robust fetch → mutate → update workflow with concurrency safety.

### Workflow Steps

1. **Fetch Current Order**
   ```python
   order = await client.get_order(store_id, order_id)
   ```

2. **Apply Mutations**
   ```python
   modified = mutator(copy.deepcopy(order))
   ```

3. **Update Order**
   ```python
   updated = await client.update_order(store_id, order_id, modified)
   ```

4. **Handle Conflicts**
   - If concurrent update detected, retry with exponential backoff
   - Maximum 3 retry attempts
   - Each retry fetches fresh order data

### Concurrency Safety

The system handles concurrent updates through:

- **Conditional Headers**: Uses `If-Unmodified-Since` when available
- **Retry Logic**: Automatic retry on conflict detection
- **Fresh Data**: Always fetches latest order before mutation
- **Exponential Backoff**: 100ms, 200ms, 300ms delays between retries

### Example Mutation

```python
def mutator(order: Dict[str, Any]) -> Dict[str, Any]:
    """Move order to different folder and add note."""
    # Update folder
    order["folder_id"] = 456
    
    # Add note
    if "notes" not in order:
        order["notes"] = []
    order["notes"].append({
        "note": "Moved to processing folder",
        "type": "system",
        "date_added": "2024-01-01 00:00:00"
    })
    
    return order

# Apply mutation
result = await mutate_order_full(client, store_id, order_id, mutator)
```

## Caching System

### Cache Backends

#### Memory Cache
- **Pros**: Fastest access, no I/O
- **Cons**: Lost on restart, single instance only
- **Use Case**: Development, single instance deployments

#### SQLite Cache
- **Pros**: Persistent, no external dependencies
- **Cons**: File I/O overhead, single instance only
- **Use Case**: Small deployments, development

#### Redis Cache
- **Pros**: Distributed, persistent, fast
- **Cons**: External dependency, network overhead
- **Use Case**: Production, multiple instances

### Cache Keys

Cache keys follow the pattern:
```
{tenant_id}:{store_id}:{endpoint}:{query_hash}
```

Examples:
- `tenant-123:store-456:orders:abc123`
- `tenant-123:store-456:inventory/789:def456`

### TTL Configuration

| Endpoint | TTL | Reason |
|----------|-----|--------|
| Orders | 15s | Frequently changing |
| Products | 60s | Moderate changes |
| Customers | 5m | Rarely changing |
| Store Settings | 1h | Very stable |

### Cache Invalidation

Cache is automatically invalidated on:

- **Order Updates**: All order-related caches for the store
- **Product Updates**: All inventory caches for the store
- **Store Changes**: All caches for the store
- **Tenant Changes**: All caches for the tenant

### Manual Invalidation

```python
# Invalidate all caches for a store
await cache_manager.invalidate_store(tenant_id, store_id)

# Invalidate all caches for a tenant
await cache_manager.invalidate_tenant(tenant_id)
```

## Webhook Processing

### Webhook Flow

1. **Receive Webhook**
   - Validate signature (if configured)
   - Parse JSON payload
   - Extract event ID

2. **Deduplication**
   - Check if event already processed
   - Store event in database
   - Return duplicate status if found

3. **Processing**
   - Mark event as processed
   - Update relevant caches
   - Trigger external systems (future)

### Webhook Security

#### Signature Validation
```python
# Generate signature
signature = hmac.new(
    webhook_secret.encode("utf-8"),
    request_body,
    hashlib.sha256
).hexdigest()

# Verify signature
if not hmac.compare_digest(received_signature, expected_signature):
    raise HTTPException(401, "Invalid signature")
```

#### Event Deduplication
```python
# Check for existing event
existing = db.query(WebhookEvent).filter(
    WebhookEvent.event_id == event_id
).first()

if existing:
    return {"status": "duplicate"}
```

### Webhook Configuration

Set `WEBHOOK_SECRET` in environment for signature validation:

```bash
WEBHOOK_SECRET=your-webhook-secret-here
```

OrderDesk webhook URL:
```
https://your-domain.com/webhooks/orderdesk
```

## Error Handling

### Error Response Format

```json
{
  "error": {
    "code": "OD_API_429",
    "message": "OrderDesk API rate limit exceeded",
    "details": {
      "retry_after": 8
    },
    "request_id": "abc-123-def"
  }
}
```

### Error Codes

| Code | Description | Action |
|------|-------------|--------|
| `AUTH_REQUIRED` | Missing/invalid auth | Check Authorization header |
| `STORE_NOT_FOUND` | Store doesn't exist | Verify store ID |
| `OD_API_429` | Rate limited | Wait and retry |
| `OD_API_5XX` | Server error | Retry with backoff |
| `CONCURRENT_UPDATE` | Order modified | Retry mutation |
| `INVALID_MUTATION` | Bad mutation ops | Check operation format |

### Retry Logic

#### OrderDesk API Calls
- **429 Rate Limit**: Wait for `X-Retry-After` seconds
- **5XX Server Error**: Exponential backoff (250ms → 1s → 2s)
- **Network Error**: Exponential backoff with jitter
- **Max Retries**: 3 attempts

#### Order Mutations
- **Concurrent Update**: Retry with fresh data
- **Backoff**: 100ms, 200ms, 300ms
- **Max Retries**: 3 attempts

## Performance Optimization

### Caching Strategy

1. **Read-Heavy Workloads**: Use Redis with longer TTLs
2. **Write-Heavy Workloads**: Use memory cache with shorter TTLs
3. **Mixed Workloads**: Use SQLite with moderate TTLs

### Database Optimization

1. **Indexes**: Automatic on tenant_id, store_id, event_id
2. **Connection Pooling**: Built-in SQLAlchemy pooling
3. **Query Optimization**: Use specific field selection

### Memory Management

1. **Connection Cleanup**: Automatic httpx client cleanup
2. **Cache Limits**: Memory cache with TTL expiration
3. **Log Rotation**: Structured logs with size limits

## Monitoring and Observability

### Metrics

Prometheus metrics available at `/metrics`:

- `http_requests_total`: Request count by method/endpoint/status
- `http_request_duration_seconds`: Request duration histogram
- `cache_hits_total`: Cache hit count
- `cache_misses_total`: Cache miss count

### Logging

Structured JSON logs include:

```json
{
  "ts": "2024-01-01T00:00:00Z",
  "level": "info",
  "msg": "orderdesk_api_request",
  "tenant_id": "tenant-123",
  "store_id": "store-456",
  "method": "GET",
  "endpoint": "orders/789",
  "status_code": 200,
  "duration_ms": 150,
  "request_id": "abc-123",
  "client_ip": "192.168.1.1"
}
```

### Health Checks

Health endpoint at `/health` returns:
```json
{
  "status": "ok"
}
```

Use for:
- Load balancer health checks
- Container health checks
- Monitoring system probes

## Best Practices

### Order Mutations

1. **Always use the mutation workflow** for order updates
2. **Test mutations** with small changes first
3. **Handle retries** in your client code
4. **Validate data** before sending to OrderDesk

### Caching

1. **Choose appropriate TTL** based on data volatility
2. **Monitor cache hit rates** for optimization
3. **Use Redis** for multi-instance deployments
4. **Invalidate caches** after writes

### Security

1. **Rotate master keys** periodically
2. **Use HTTPS** in production
3. **Validate webhook signatures** if using webhooks
4. **Monitor audit logs** for suspicious activity

### Performance

1. **Use pagination** for large result sets
2. **Batch operations** when possible
3. **Monitor response times** and optimize slow endpoints
4. **Use appropriate cache backends** for your use case
