# Production Runbook

**Operational procedures for OrderDesk MCP Server**

---

## 🎯 **Quick Reference**

| **Task** | **Command** | **Expected Time** |
|----------|-------------|-------------------|
| Deploy | `docker-compose -f docker-compose.production.yml up -d` | 2 minutes |
| Scale | `docker-compose -f docker-compose.production.yml up -d --scale mcp=3` | 30 seconds |
| Restart | `docker-compose -f docker-compose.production.yml restart mcp` | 10 seconds |
| Backup | `./scripts/backup.sh` | 5 minutes |
| Restore | `./scripts/restore.sh backup-YYYYMMDD.tar.gz` | 10 minutes |
| View Logs | `docker-compose -f docker-compose.production.yml logs -f mcp` | Real-time |
| Health Check | `curl https://yourdomain.com/health/ready` | Instant |

---

## 📚 **Table of Contents**

1. [Emergency Contacts](#emergency-contacts)
2. [Common Operations](#common-operations)
3. [Incident Response](#incident-response)
4. [Monitoring & Alerts](#monitoring--alerts)
5. [Rollback Procedures](#rollback-procedures)
6. [Performance Tuning](#performance-tuning)

---

## 🚨 **Emergency Contacts**

**On-Call Rotation:**
- Primary: [Your Name] - [Phone/Slack]
- Secondary: [Backup Person] - [Phone/Slack]
- Escalation: [Manager] - [Phone/Slack]

**External Vendors:**
- OrderDesk Support: support@orderdesk.com
- Database Provider: [Contact]
- Hosting Provider: [Contact]

**Useful Links:**
- Status Page: https://status.yourdomain.com
- Grafana: https://monitoring.yourdomain.com
- GitHub: https://github.com/ebabcock80/orderdesk-mcp
- Documentation: https://github.com/ebabcock80/orderdesk-mcp/tree/main/docs

---

## ⚙️ **Common Operations**

### **1. Deployment**

**Standard Deployment:**
```bash
# 1. Backup current state
./scripts/backup.sh

# 2. Pull latest code
git pull origin main

# 3. Build new image
docker-compose -f docker-compose.production.yml build mcp

# 4. Rolling restart (zero downtime)
docker-compose -f docker-compose.production.yml up -d mcp

# 5. Verify health
curl https://yourdomain.com/health/ready

# 6. Monitor logs for 5 minutes
docker-compose -f docker-compose.production.yml logs -f --tail=100 mcp
```

**Expected Duration:** 5-10 minutes

---

### **2. Scaling**

**Scale Up (Horizontal):**
```bash
# Scale to 3 instances
docker-compose -f docker-compose.production.yml up -d --scale mcp=3

# Verify all instances healthy
docker-compose -f docker-compose.production.yml ps mcp

# Check load distribution
curl https://yourdomain.com/metrics | grep http_requests_total
```

**Scale Down:**
```bash
# Scale to 1 instance
docker-compose -f docker-compose.production.yml up -d --scale mcp=1
```

---

### **3. Restart Services**

**Restart Application Only:**
```bash
docker-compose -f docker-compose.production.yml restart mcp
```

**Restart All Services:**
```bash
docker-compose -f docker-compose.production.yml restart
```

**Hard Restart (Rebuild):**
```bash
docker-compose -f docker-compose.production.yml down
docker-compose -f docker-compose.production.yml up -d --build
```

---

### **4. View Logs**

**Live Logs:**
```bash
# All services
docker-compose -f docker-compose.production.yml logs -f

# MCP only
docker-compose -f docker-compose.production.yml logs -f mcp

# Last 100 lines
docker-compose -f docker-compose.production.yml logs --tail=100 mcp
```

**Search Logs:**
```bash
# Find errors
docker-compose logs mcp | grep -i error

# Find specific request
docker-compose logs mcp | grep "request_id=abc123"

# JSON parsing (requires jq)
docker-compose logs mcp | jq 'select(.level == "error")'
```

---

### **5. Database Operations**

**Backup:**
```bash
docker exec orderdesk-postgres pg_dump -U orderdesk orderdesk_production > backup.sql
gzip backup.sql
```

**Restore:**
```bash
gunzip backup.sql.gz
cat backup.sql | docker exec -i orderdesk-postgres psql -U orderdesk orderdesk_production
```

**Check Database Size:**
```bash
docker exec orderdesk-postgres psql -U orderdesk -d orderdesk_production -c \
  "SELECT pg_size_pretty(pg_database_size('orderdesk_production'));"
```

**Vacuum (Maintenance):**
```bash
docker exec orderdesk-postgres psql -U orderdesk -d orderdesk_production -c "VACUUM ANALYZE;"
```

---

### **6. Cache Operations**

**Clear Cache:**
```bash
docker exec orderdesk-redis redis-cli -a "${REDIS_PASSWORD}" FLUSHALL
```

**Check Cache Stats:**
```bash
docker exec orderdesk-redis redis-cli -a "${REDIS_PASSWORD}" INFO stats
```

**Monitor Cache:**
```bash
docker exec orderdesk-redis redis-cli -a "${REDIS_PASSWORD}" MONITOR
```

---

## 🔥 **Incident Response**

### **Severity Levels**

| **Level** | **Description** | **Response Time** | **Examples** |
|-----------|-----------------|-------------------|--------------|
| P0 (Critical) | Service down | 15 minutes | Complete outage, data loss |
| P1 (High) | Major degradation | 1 hour | 50%+ errors, slow responses |
| P2 (Medium) | Minor degradation | 4 hours | Intermittent errors |
| P3 (Low) | Cosmetic issues | 1 business day | UI glitches, typos |

---

### **P0: Service Down**

**Symptoms:**
- All health checks failing
- 5xx errors on all requests
- Unable to connect to service

**Response:**
1. **Alert the team** (Slack/PagerDuty)
2. **Check infrastructure:**
   ```bash
   docker-compose ps
   curl http://localhost/health/ready
   ```
3. **Check logs:**
   ```bash
   docker-compose logs --tail=200 mcp
   ```
4. **Common fixes:**
   - Database connection: Restart postgres
   - Redis connection: Restart redis
   - Application crash: Restart mcp
5. **If still down, rollback:**
   ```bash
   git checkout <previous-commit>
   docker-compose up -d --build mcp
   ```
6. **Post-incident:** Create incident report, update runbook

---

### **P1: High Error Rate**

**Symptoms:**
- Error rate > 5%
- Response time p95 > 2 seconds
- Intermittent 5xx errors

**Response:**
1. **Check metrics:**
   ```bash
   curl http://localhost/metrics | grep errors_total
   curl http://localhost/metrics | grep http_request_duration
   ```
2. **Identify error type:**
   ```bash
   docker-compose logs mcp | jq 'select(.level == "error")' | head -50
   ```
3. **Common causes:**
   - OrderDesk API down: Check OrderDesk status
   - Database slow: Check query times, run VACUUM
   - Memory leak: Restart application
   - Rate limiting: Increase limits or scale up
4. **Scale if needed:**
   ```bash
   docker-compose up -d --scale mcp=3
   ```

---

### **P2: Cache Issues**

**Symptoms:**
- Low cache hit rate (<50%)
- Slow response times
- High OrderDesk API usage

**Response:**
1. **Check cache health:**
   ```bash
   curl http://localhost/health/detailed | jq '.checks.cache'
   ```
2. **Check cache metrics:**
   ```bash
   curl http://localhost/metrics | grep cache
   ```
3. **Restart Redis if unhealthy:**
   ```bash
   docker-compose restart redis
   ```
4. **Verify cache backend in .env:**
   ```bash
   grep CACHE_BACKEND .env
   ```

---

## 📊 **Monitoring & Alerts**

### **Key Metrics to Monitor**

| **Metric** | **Threshold** | **Alert** |
|------------|---------------|-----------|
| Error rate | > 1% | Warning |
| Error rate | > 5% | Critical |
| Response time p95 | > 2s | Warning |
| Response time p95 | > 5s | Critical |
| Cache hit rate | < 50% | Warning |
| Disk space | > 80% | Warning |
| Disk space | > 90% | Critical |
| Memory usage | > 80% | Warning |
| CPU usage | > 80% | Warning |

### **Health Check Monitoring**

**Set up external monitoring (UptimeRobot, Pingdom, etc):**
- URL: https://yourdomain.com/health/ready
- Interval: 1 minute
- Timeout: 10 seconds
- Alert on: 3 consecutive failures

### **Log Monitoring**

**Set up alerts for:**
- ERROR level logs
- CRITICAL level logs
- Specific error codes (AUTH_FAILED, ORDERDESK_ERROR, etc.)

---

## ⏮️ **Rollback Procedures**

### **Application Rollback**

```bash
# 1. Identify previous working version
git log --oneline -10

# 2. Checkout previous version
git checkout <commit-hash>

# 3. Rebuild and restart
docker-compose -f docker-compose.production.yml up -d --build mcp

# 4. Verify health
curl https://yourdomain.com/health/ready

# 5. Monitor for 10 minutes
docker-compose logs -f --tail=100 mcp
```

**Expected Duration:** 5 minutes

### **Database Rollback**

```bash
# 1. Stop application
docker-compose stop mcp

# 2. Restore from backup
cat backup-YYYYMMDD.sql | docker exec -i orderdesk-postgres psql -U orderdesk orderdesk_production

# 3. Restart application
docker-compose start mcp

# 4. Verify
curl https://yourdomain.com/health/ready
```

**Expected Duration:** 10-30 minutes (depending on database size)

---

## 🚀 **Performance Tuning**

### **Database Optimization**

```sql
-- Find slow queries
SELECT query, mean_exec_time, calls 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;

-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan 
FROM pg_stat_user_indexes 
WHERE idx_scan = 0;

-- Vacuum and analyze
VACUUM ANALYZE;
```

### **Cache Optimization**

**Adjust TTLs in `.env`:**
```bash
CACHE_TTL_ORDERS=15      # Increase if orders change infrequently
CACHE_TTL_PRODUCTS=60    # Increase for stable catalog
CACHE_TTL_CUSTOMERS=300  # Increase if customer data stable
```

**Monitor cache effectiveness:**
```bash
curl http://localhost/metrics | grep cache_operations_total
```

### **Application Tuning**

**Increase worker count (in Dockerfile):**
```dockerfile
CMD ["uvicorn", "mcp_server.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**Adjust resource limits (in docker-compose.production.yml):**
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 1G
```

---

## 📝 **Maintenance Schedule**

| **Task** | **Frequency** | **Duration** |
|----------|---------------|--------------|
| Database backup | Daily | 5 minutes |
| Log rotation | Daily | 1 minute |
| Database vacuum | Weekly | 10 minutes |
| Security updates | Monthly | 30 minutes |
| Certificate renewal | Every 90 days | 5 minutes |
| Load testing | Quarterly | 2 hours |

---

## ✅ **Pre-Deployment Checklist**

- [ ] All tests passing on CI
- [ ] Backup created
- [ ] Change window communicated
- [ ] Rollback plan ready
- [ ] Monitoring alerts active
- [ ] Team notified
- [ ] Post-deployment verification plan

---

## 📞 **Support**

**Need help?**
- Documentation: https://github.com/ebabcock80/orderdesk-mcp/tree/main/docs
- Issues: https://github.com/ebabcock80/orderdesk-mcp/issues
- Email: support@yourdomain.com

