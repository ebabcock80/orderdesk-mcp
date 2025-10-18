# Load Testing Guide

Complete guide for load testing the OrderDesk MCP Server.

---

## Overview

Load testing validates that the server can handle expected production workloads. This guide covers:
- k6 load tests
- Stress testing
- Performance benchmarks
- Bottleneck identification

---

## Quick Start

### Install k6

**macOS:**
```bash
brew install k6
```

**Linux:**
```bash
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 \
  --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | \
  sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6
```

**Windows:**
```powershell
choco install k6
```

**Docker:**
```bash
# Run tests via Docker (no installation needed)
docker run --rm -i grafana/k6 run - <scripts/load-testing/k6-basic-load.js
```

---

## Load Tests

### Basic Load Test

**Purpose:** Validate normal production load

**Profile:**
- 10-20 concurrent users
- 9-minute duration
- Realistic usage patterns

**Run:**
```bash
./scripts/load-testing/run-load-test.sh basic
```

**Thresholds:**
- 95% of requests < 2s
- Error rate < 1%
- Health checks always passing

---

### Stress Test

**Purpose:** Find breaking point and validate graceful degradation

**Profile:**
- Ramp from 0 → 150 users
- 26-minute duration
- High concurrent load

**Run:**
```bash
./scripts/load-testing/run-load-test.sh stress
```

**Thresholds:**
- 95% of requests < 3s (under stress)
- 99% of requests < 5s
- Error rate < 5% (some degradation OK)

---

## Test Scenarios

### Scenario 1: Read-Heavy Workload (40%)

Simulates typical usage where users mostly read data:
- List stores
- List orders
- Get order details
- List products

**Expected Performance:**
- High cache hit rate (60-70%)
- Fast response times (<100ms cached)
- Low database load

---

### Scenario 2: MCP Tool Calls (30%)

Tests MCP protocol overhead:
- initialize
- tools/list
- prompts/list
- resources/list
- Tool execution

**Expected Performance:**
- Protocol overhead minimal
- Similar to direct API calls
- No connection issues

---

### Scenario 3: Monitoring (20%)

Health checks and metrics scraping:
- /health
- /health/ready
- /health/live
- /health/detailed
- /metrics

**Expected Performance:**
- Always fast (<20ms)
- No impact on main operations
- Consistent response times

---

### Scenario 4: Authentication (10%)

Tests authentication system:
- Valid authentication
- Invalid key handling
- Rate limiting
- Session management

**Expected Performance:**
- Auth failures handled gracefully
- No 500 errors
- Rate limits enforced
- Quick rejection of invalid keys

---

## Interpreting Results

### k6 Output

```
scenarios: (100.00%) 1 scenario, 150 max VUs, 26m30s max duration
✓ http_req_duration..........: avg=245ms  min=12ms  med=89ms   max=4.2s   p(90)=456ms p(95)=892ms
✓ http_req_failed............: 0.23%  ✓ 45    ✗ 19234
✓ iterations.................: 19279  12.3/s
```

**Good indicators:**
- ✅ p(95) < 2s
- ✅ Error rate < 1%
- ✅ High throughput (requests/sec)
- ✅ Check marks on thresholds

**Warning signs:**
- ⚠️ p(95) > 3s
- ⚠️ Error rate > 5%
- ⚠️ Declining throughput
- ⚠️ X marks on thresholds

---

## Performance Targets

### By Percentile

| Metric | p50 | p95 | p99 | Max |
|--------|-----|-----|-----|-----|
| **Cached Requests** | <20ms | <50ms | <100ms | <500ms |
| **Uncached Requests** | <500ms | <2s | <5s | <10s |
| **Health Checks** | <10ms | <20ms | <50ms | <100ms |
| **MCP Protocol** | <30ms | <100ms | <200ms | <1s |

### By Load Level

| Concurrent Users | Target RPS | p95 Latency | Error Rate |
|------------------|------------|-------------|------------|
| **10** | 20-30 | <100ms | <0.1% |
| **50** | 80-120 | <500ms | <0.5% |
| **100** | 150-200 | <1s | <1% |
| **150** | 200-250 | <2s | <5% |

---

## Bottleneck Analysis

### Common Bottlenecks

**1. OrderDesk API Latency**
- **Symptom:** High latency on uncached requests
- **Solution:** Increase cache TTL, add cache warming
- **Current:** 500-2000ms (external, cannot optimize)

**2. Database Locks**
- **Symptom:** Slow write operations
- **Solution:** Use WAL mode (already enabled), run VACUUM
- **Current:** Not a bottleneck

**3. Memory Pressure**
- **Symptom:** High memory usage, slow responses
- **Solution:** Use Redis cache, scale horizontally
- **Current:** Memory usage optimal

**4. CPU Saturation**
- **Symptom:** High CPU, degraded performance
- **Solution:** Scale horizontally, optimize hot paths
- **Current:** CPU usage low

---

## Load Testing Checklist

### Before Testing
- [ ] Server is healthy (`curl http://localhost:8080/health`)
- [ ] Test environment matches production (staging recommended)
- [ ] Monitoring enabled (Prometheus + Grafana)
- [ ] Baseline metrics recorded
- [ ] Database backed up
- [ ] Team notified (if testing production)

### During Testing
- [ ] Monitor metrics in real-time
- [ ] Watch for error spikes
- [ ] Check memory usage
- [ ] Check CPU usage
- [ ] Monitor database performance
- [ ] Check cache hit rates

### After Testing
- [ ] Review k6 summary statistics
- [ ] Analyze failure patterns
- [ ] Check for memory leaks
- [ ] Review error logs
- [ ] Compare with baseline
- [ ] Document findings

---

## Running Tests

### Basic Load Test

```bash
# Start server
docker-compose up -d

# Run test
./scripts/load-testing/run-load-test.sh basic

# View results
cat scripts/load-testing/results/basic-load-*-summary.json | jq
```

**Duration:** ~9 minutes  
**Max Users:** 20  
**Recommended For:** Pre-production validation

---

### Stress Test

```bash
# Use staging environment (don't stress production!)
export BASE_URL=https://staging.yourdomain.com
export MASTER_KEY=your-staging-master-key

# Run test
./scripts/load-testing/run-load-test.sh stress

# Monitor in another terminal
watch -n 1 'curl -s http://localhost:8080/health/detailed | jq ".checks.memory,.checks.disk"'
```

**Duration:** ~26 minutes  
**Max Users:** 150  
**Recommended For:** Capacity planning

---

## Custom Load Tests

### Create Custom Test

```javascript
// scripts/load-testing/k6-custom.js
import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 50,           // 50 virtual users
  duration: '5m',    // Run for 5 minutes
};

export default function () {
  const res = http.get('http://localhost:8080/health');
  check(res, { 'status 200': (r) => r.status === 200 });
}
```

**Run:**
```bash
k6 run scripts/load-testing/k6-custom.js
```

---

## Continuous Load Testing

### Integrate with CI/CD

```yaml
# .github/workflows/load-test.yml
name: Load Test

on:
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Start server
        run: docker-compose up -d
      
      - name: Install k6
        run: |
          sudo gpg -k
          # ... (k6 installation)
      
      - name: Run load test
        run: ./scripts/load-testing/run-load-test.sh basic
      
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: load-test-results
          path: scripts/load-testing/results/
```

---

## Analyzing Results

### View Summary

```bash
# Pretty print summary
cat scripts/load-testing/results/basic-load-*-summary.json | jq '.metrics'
```

### Key Metrics to Review

**1. Request Duration:**
```json
{
  "http_req_duration": {
    "avg": 245.5,
    "min": 12.3,
    "med": 89.7,
    "max": 4201.2,
    "p(90)": 456.8,
    "p(95)": 892.3
  }
}
```

**Target:** p(95) < 2000ms

**2. Error Rate:**
```json
{
  "http_req_failed": {
    "passes": 19234,
    "fails": 45,
    "value": 0.0023  // 0.23%
  }
}
```

**Target:** < 1%

**3. Throughput:**
```json
{
  "iterations": {
    "count": 19279,
    "rate": 32.13  // per second
  }
}
```

**Target:** Depends on expected load

---

## Troubleshooting

### "Test failed: thresholds not met"

**Check which threshold failed:**
```bash
# View detailed results
cat results/LATEST-summary.json | jq '.metrics | to_entries[] | select(.value.thresholds != null)'
```

**Common causes:**
- Server under-provisioned
- Database needs VACUUM
- Cache disabled or misconfigured
- Network latency

### "Connection refused errors"

```bash
# Verify server is running
docker-compose ps

# Check if port is exposed
curl http://localhost:8080/health

# Check firewall (if remote)
telnet staging.yourdomain.com 8080
```

### "High error rate during test"

```bash
# Check server logs during test
docker-compose logs -f mcp

# Look for:
# - Authentication failures
# - Rate limit hits
# - Database errors
# - Out of memory errors
```

---

## Recommendations

### Development
- Run basic load test before each release
- Ensure no regressions in performance
- Target: All thresholds passing

### Staging
- Run stress test weekly
- Test with production-like data
- Identify breaking points
- Plan capacity accordingly

### Production
- Run load tests on staging only (never production!)
- Monitor production metrics continuously
- Set up alerts for performance degradation
- Review load test results monthly

---

## Links

- [PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md) - Optimization guide
- [PRODUCTION-RUNBOOK.md](PRODUCTION-RUNBOOK.md) - Operations guide
- [k6 Documentation](https://k6.io/docs/) - Official k6 docs

