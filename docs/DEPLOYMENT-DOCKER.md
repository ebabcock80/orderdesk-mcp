# Docker Deployment Guide

**Production-ready Docker deployment for OrderDesk MCP Server**

---

## 📋 **Table of Contents**

1. [Quick Start](#quick-start)
2. [Single-Server Deployment](#single-server-deployment)
3. [Multi-Instance with Load Balancer](#multi-instance-with-load-balancer)
4. [SSL/TLS Configuration](#ssltls-configuration)
5. [Database & Caching](#database--caching)
6. [Monitoring & Logging](#monitoring--logging)
7. [Backup & Recovery](#backup--recovery)
8. [Troubleshooting](#troubleshooting)

---

## 🚀 **Quick Start**

### **Prerequisites**

- Docker 20.10+
- Docker Compose 2.0+
- 2GB RAM minimum
- 10GB disk space

### **1. Clone & Configure**

```bash
git clone https://github.com/ebabcock80/orderdesk-mcp.git
cd orderdesk-mcp

# Copy production environment file
cp .env.production.example .env

# Edit .env and change ALL secrets
nano .env
```

### **2. Start Services**

```bash
# Production deployment
docker-compose -f docker-compose.production.yml up -d

# Check status
docker-compose -f docker-compose.production.yml ps

# View logs
docker-compose -f docker-compose.production.yml logs -f mcp
```

### **3. Verify Deployment**

```bash
# Health check
curl http://localhost:8000/health/ready

# Metrics
curl http://localhost:8000/metrics
```

---

## 🏢 **Single-Server Deployment**

### **Architecture**

```
Internet → nginx (reverse proxy) → MCP Server
                                 ↓
                           PostgreSQL + Redis
```

### **docker-compose.production.yml**

See [`docker-compose.production.yml`](../docker-compose.production.yml) in the repository root.

**Key features:**
- nginx reverse proxy with SSL/TLS
- PostgreSQL database with persistence
- Redis cache with persistence
- Prometheus metrics collection
- Automatic health checks
- Volume mounts for data persistence

### **Starting Production Stack**

```bash
# Start all services
docker-compose -f docker-compose.production.yml up -d

# Scale MCP instances (multi-instance)
docker-compose -f docker-compose.production.yml up -d --scale mcp=3

# Stop all services
docker-compose -f docker-compose.production.yml down

# Stop and remove volumes (DANGEROUS - deletes data)
docker-compose -f docker-compose.production.yml down -v
```

---

## ⚖️ **Multi-Instance with Load Balancer**

### **Architecture**

```
Internet → nginx (load balancer)
            ├→ MCP Instance 1
            ├→ MCP Instance 2
            └→ MCP Instance 3
               ↓
         PostgreSQL + Redis
```

### **Scaling**

```bash
# Scale to 3 instances
docker-compose -f docker-compose.production.yml up -d --scale mcp=3

# Check instances
docker-compose -f docker-compose.production.yml ps mcp

# View logs from all instances
docker-compose -f docker-compose.production.yml logs -f mcp
```

### **Load Balancing Strategy**

nginx configuration (in `docker-compose.production.yml`):
- **Algorithm:** Least connections
- **Health Checks:** Every 5 seconds
- **Failover:** Automatic (unhealthy instances excluded)
- **Session Affinity:** Not required (stateless)

---

## 🔒 **SSL/TLS Configuration**

### **Option 1: Let's Encrypt (Recommended)**

Use Traefik or Certbot for automatic SSL:

```bash
# Install certbot
sudo apt-get install certbot

# Get certificate
sudo certbot certonly --standalone -d yourdomain.com

# Configure nginx (see nginx.conf.example)
# Certificates will be at:
# /etc/letsencrypt/live/yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/yourdomain.com/privkey.pem
```

### **Option 2: Self-Signed (Development/Testing)**

```bash
# Generate self-signed certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/privkey.pem \
  -out nginx/ssl/fullchain.pem \
  -subj "/CN=yourdomain.com"
```

### **Option 3: Cloudflare (Easiest)**

1. Point your domain to Cloudflare
2. Enable "Full (strict)" SSL mode
3. No SSL configuration needed on server
4. Cloudflare handles SSL termination

### **nginx SSL Configuration**

Add to `docker-compose.production.yml`:

```yaml
nginx:
  volumes:
    - ./nginx/ssl:/etc/nginx/ssl:ro
    - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
```

nginx.conf snippet:

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://mcp:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 💾 **Database & Caching**

### **PostgreSQL Configuration**

```yaml
postgres:
  image: postgres:16-alpine
  environment:
    POSTGRES_DB: orderdesk_production
    POSTGRES_USER: orderdesk
    POSTGRES_PASSWORD: ${DATABASE_PASSWORD}
  volumes:
    - postgres_data:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U orderdesk"]
    interval: 10s
    timeout: 5s
    retries: 5
```

**Connection string:**
```
DATABASE_URL=postgresql://orderdesk:${DATABASE_PASSWORD}@postgres:5432/orderdesk_production
```

### **Redis Configuration**

```yaml
redis:
  image: redis:7-alpine
  command: redis-server --requirepass ${REDIS_PASSWORD} --appendonly yes
  volumes:
    - redis_data:/data
  healthcheck:
    test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
    interval: 10s
    timeout: 3s
    retries: 5
```

**Connection string:**
```
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
```

### **Database Backups**

Automated daily backups:

```bash
# Add to crontab
0 2 * * * docker exec orderdesk-postgres pg_dump -U orderdesk orderdesk_production | gzip > /backups/db-$(date +\%Y\%m\%d).sql.gz

# Retain last 30 days
find /backups -name "db-*.sql.gz" -mtime +30 -delete
```

Manual backup:

```bash
# Backup
docker exec orderdesk-postgres pg_dump -U orderdesk orderdesk_production > backup.sql

# Restore
cat backup.sql | docker exec -i orderdesk-postgres psql -U orderdesk orderdesk_production
```

---

## 📊 **Monitoring & Logging**

### **Prometheus Metrics**

Metrics available at `http://localhost:8000/metrics`:

- HTTP request latency and throughput
- MCP tool execution times
- Cache hit/miss rates
- Database query performance
- Error rates by type
- OrderDesk API latency

### **Grafana Dashboard**

```bash
# Add Grafana to docker-compose.yml
grafana:
  image: grafana/grafana:latest
  ports:
    - "3000:3000"
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
  volumes:
    - grafana_data:/var/lib/grafana
    - ./monitoring/grafana-dashboard.json:/etc/grafana/provisioning/dashboards/orderdesk.json
```

Access Grafana at `http://localhost:3000`

### **Log Aggregation**

Logs are JSON-structured and sent to stdout:

```bash
# View live logs
docker-compose logs -f mcp

# Search logs (requires jq)
docker-compose logs mcp | jq 'select(.level == "error")'

# Export logs
docker-compose logs mcp > logs/mcp-$(date +%Y%m%d).log
```

**ELK Stack Integration:**

```yaml
# Add to docker-compose.yml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
    labels: "service=orderdesk-mcp"
```

---

## 🔄 **Backup & Recovery**

### **Backup Strategy**

**What to backup:**
1. PostgreSQL database (`postgres_data` volume)
2. Application configuration (`.env` file)
3. SSL certificates (`nginx/ssl/` directory)
4. Redis data (optional, cache can be rebuilt)

**Backup script:**

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/orderdesk-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Database
docker exec orderdesk-postgres pg_dump -U orderdesk orderdesk_production | gzip > "$BACKUP_DIR/database.sql.gz"

# Configuration
cp .env "$BACKUP_DIR/env"

# SSL certificates
cp -r nginx/ssl "$BACKUP_DIR/ssl"

# Create tarball
tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"
rm -rf "$BACKUP_DIR"

echo "Backup created: $BACKUP_DIR.tar.gz"
```

### **Disaster Recovery**

**Scenario: Complete server failure**

```bash
# 1. Install Docker on new server
curl -fsSL https://get.docker.com | sh

# 2. Clone repository
git clone https://github.com/ebabcock80/orderdesk-mcp.git
cd orderdesk-mcp

# 3. Restore configuration
tar -xzf backup-YYYYMMDD.tar.gz
cp backup-YYYYMMDD/env .env
cp -r backup-YYYYMMDD/ssl nginx/

# 4. Start services
docker-compose -f docker-compose.production.yml up -d postgres redis

# 5. Restore database
gunzip -c backup-YYYYMMDD/database.sql.gz | docker exec -i orderdesk-postgres psql -U orderdesk orderdesk_production

# 6. Start application
docker-compose -f docker-compose.production.yml up -d mcp nginx

# 7. Verify
curl https://yourdomain.com/health/ready
```

**Recovery Time Objective (RTO):** < 30 minutes  
**Recovery Point Objective (RPO):** < 24 hours (daily backups)

---

## 🐛 **Troubleshooting**

### **Container Won't Start**

```bash
# Check logs
docker-compose logs mcp

# Check environment variables
docker-compose config

# Verify secrets
grep -v '^#' .env | grep 'CHANGE-ME'  # Should return nothing

# Test database connection
docker exec orderdesk-postgres psql -U orderdesk -d orderdesk_production -c "SELECT 1;"
```

### **Health Check Failing**

```bash
# Detailed health check
curl http://localhost:8000/health/detailed | jq

# Check database
docker exec orderdesk-postgres pg_isready

# Check Redis
docker exec orderdesk-redis redis-cli ping
```

### **High Memory Usage**

```bash
# Check container stats
docker stats

# Restart with memory limit
docker-compose -f docker-compose.production.yml up -d --scale mcp=2 \
  --memory="512m" --memory-swap="1g"
```

### **Slow Performance**

```bash
# Check cache hit rate
curl http://localhost:8000/metrics | grep cache_operations

# Check database query times
curl http://localhost:8000/metrics | grep db_query_duration

# Check OrderDesk API latency
curl http://localhost:8000/metrics | grep orderdesk_api_duration
```

### **Database Connection Errors**

```bash
# Check connection string
docker-compose exec mcp env | grep DATABASE_URL

# Test from container
docker-compose exec mcp python -c "
from mcp_server.models.database import get_engine
engine = get_engine()
with engine.connect() as conn:
    print('Connected:', conn.execute('SELECT 1').fetchone())
"
```

---

## 📚 **Additional Resources**

- [Production Runbook](./PRODUCTION-RUNBOOK.md)
- [Security Audit](./SECURITY-AUDIT.md)
- [Performance Benchmarks](./PERFORMANCE-BENCHMARKS.md)
- [Kubernetes Deployment](./DEPLOYMENT-KUBERNETES.md)

---

## ✅ **Production Checklist**

Before going live:

- [ ] All secrets changed in `.env`
- [ ] SSL/TLS certificates configured
- [ ] Database backups automated
- [ ] Monitoring dashboards set up
- [ ] Alert rules configured
- [ ] Firewall rules applied
- [ ] DDoS protection enabled
- [ ] Load testing completed
- [ ] Disaster recovery tested
- [ ] Runbook documented

---

**Need help?** Open an issue on [GitHub](https://github.com/ebabcock80/orderdesk-mcp/issues)

