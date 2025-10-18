# Bare Metal Deployment Guide

Complete guide for deploying OrderDesk MCP Server on bare metal or VPS without Docker/Kubernetes.

---

## Overview

This guide covers deploying directly on:
- Linux servers (Ubuntu, Debian, RHEL, CentOS)
- VPS (DigitalOcean, Linode, Vultr)
- Bare metal servers
- Systemd service management

---

## Prerequisites

- Linux server (Ubuntu 22.04+ recommended)
- Python 3.12+
- SQLite 3.35+
- nginx (for reverse proxy)
- systemd (for service management)
- sudo access

---

## Quick Start

### 1. Install Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y \
  python3.12 \
  python3.12-venv \
  python3-pip \
  sqlite3 \
  nginx \
  certbot \
  python3-certbot-nginx
```

**RHEL/CentOS:**
```bash
sudo dnf install -y \
  python3.12 \
  python3-pip \
  sqlite \
  nginx \
  certbot \
  python3-certbot-nginx
```

### 2. Create Service User

```bash
# Create dedicated user
sudo useradd -r -s /bin/false -d /opt/orderdesk orderdesk

# Create application directory
sudo mkdir -p /opt/orderdesk
sudo chown orderdesk:orderdesk /opt/orderdesk
```

### 3. Install Application

```bash
# Clone repository
cd /opt/orderdesk
sudo -u orderdesk git clone https://github.com/ebabcock80/orderdesk-mcp.git app
cd app

# Create virtual environment
sudo -u orderdesk python3.12 -m venv venv

# Install dependencies
sudo -u orderdesk venv/bin/pip install --upgrade pip
sudo -u orderdesk venv/bin/pip install -e .[webui]
```

### 4. Configure Environment

```bash
# Copy environment template
sudo -u orderdesk cp config/environments/production.env .env

# Generate secrets
MCP_KMS_KEY=$(openssl rand -base64 32)
ADMIN_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
JWT_KEY=$(openssl rand -base64 48)
CSRF_KEY=$(openssl rand -base64 32)

# Update .env file
sudo -u orderdesk nano .env
# Set all CHANGE_ME values with generated secrets
# Set PUBLIC_URL to your domain
```

### 5. Create Systemd Service

```bash
# Create service file
sudo tee /etc/systemd/system/orderdesk-mcp.service << 'EOF'
[Unit]
Description=OrderDesk MCP Server
After=network.target
Wants=redis.service

[Service]
Type=simple
User=orderdesk
Group=orderdesk
WorkingDirectory=/opt/orderdesk/app
EnvironmentFile=/opt/orderdesk/app/.env

ExecStart=/opt/orderdesk/app/venv/bin/uvicorn \
  mcp_server.main:app \
  --host 0.0.0.0 \
  --port 8080 \
  --workers 2 \
  --loop uvloop \
  --log-config logging.json

ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=orderdesk-mcp

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/orderdesk/app/data

# Resource limits
MemoryMax=512M
CPUQuota=100%

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable orderdesk-mcp

# Start service
sudo systemctl start orderdesk-mcp

# Check status
sudo systemctl status orderdesk-mcp
```

### 6. Configure nginx

```bash
# Create nginx site configuration
sudo tee /etc/nginx/sites-available/orderdesk-mcp << 'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name yourdomain.com www.yourdomain.com;

    # Let's Encrypt ACME challenge
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Redirect to HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL certificates (managed by certbot)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Proxy to application
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # MCP endpoint (longer timeout)
    location /mcp {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 75s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    # Health check (no auth required)
    location /health {
        proxy_pass http://127.0.0.1:8080;
        access_log off;
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/orderdesk-mcp /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### 7. Get SSL Certificate

```bash
# Stop nginx temporarily
sudo systemctl stop nginx

# Get certificate
sudo certbot certonly --standalone \
  -d yourdomain.com \
  -d www.yourdomain.com \
  --agree-tos \
  --email admin@yourdomain.com

# Start nginx
sudo systemctl start nginx

# Test auto-renewal
sudo certbot renew --dry-run
```

### 8. Verify Deployment

```bash
# Check service status
sudo systemctl status orderdesk-mcp

# Check logs
sudo journalctl -u orderdesk-mcp -f

# Test health endpoint
curl https://yourdomain.com/health

# Test MCP endpoint
curl -X POST "https://yourdomain.com/mcp?token=YOUR_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

---

## Redis Installation (Optional)

### Install Redis

```bash
# Ubuntu/Debian
sudo apt-get install -y redis-server

# RHEL/CentOS
sudo dnf install -y redis

# Configure Redis
sudo tee /etc/redis/redis.conf << 'EOF'
bind 127.0.0.1
port 6379
maxmemory 512mb
maxmemory-policy allkeys-lru
appendonly yes
EOF

# Start Redis
sudo systemctl enable redis
sudo systemctl start redis

# Update .env
echo "CACHE_BACKEND=redis" | sudo -u orderdesk tee -a /opt/orderdesk/app/.env
echo "REDIS_URL=redis://127.0.0.1:6379/0" | sudo -u orderdesk tee -a /opt/orderdesk/app/.env

# Restart application
sudo systemctl restart orderdesk-mcp
```

---

## Monitoring

### Journal Logs

```bash
# View logs
sudo journalctl -u orderdesk-mcp -f

# View logs from last hour
sudo journalctl -u orderdesk-mcp --since "1 hour ago"

# View error logs only
sudo journalctl -u orderdesk-mcp -p err -f
```

### Metrics

```bash
# View Prometheus metrics
curl http://localhost:8080/metrics

# Parse specific metric
curl -s http://localhost:8080/metrics | grep http_requests_total
```

### Log Rotation

```bash
# Configure systemd journal size
sudo mkdir -p /etc/systemd/journald.conf.d/
sudo tee /etc/systemd/journald.conf.d/size-limit.conf << 'EOF'
[Journal]
SystemMaxUse=500M
SystemMaxFileSize=100M
EOF

sudo systemctl restart systemd-journald
```

---

## Automated Backups

### Setup Cron Job

```bash
# Create backup directory
sudo mkdir -p /opt/orderdesk/backups
sudo chown orderdesk:orderdesk /opt/orderdesk/backups

# Add to crontab
sudo -u orderdesk crontab -e

# Add this line:
0 2 * * * cd /opt/orderdesk/app && ./scripts/backup/automated-backup.sh >> /opt/orderdesk/logs/backup.log 2>&1
```

---

## Updates

### Update Application

```bash
# 1. Backup database
cd /opt/orderdesk/app
sudo -u orderdesk ./scripts/backup/backup.sh --compress

# 2. Pull latest code
sudo -u orderdesk git pull origin main

# 3. Update dependencies
sudo -u orderdesk venv/bin/pip install -e .[webui]

# 4. Apply migrations (if any)
sudo -u orderdesk ./scripts/migrations/migrate.sh --list
sudo -u orderdesk ./scripts/migrations/migrate.sh --apply XXX

# 5. Restart service
sudo systemctl restart orderdesk-mcp

# 6. Verify
curl https://yourdomain.com/health
sudo journalctl -u orderdesk-mcp -n 50
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs
sudo journalctl -u orderdesk-mcp -n 100 --no-pager

# Check if port is in use
sudo netstat -tlnp | grep 8080

# Check permissions
ls -la /opt/orderdesk/app/data/

# Test manually
sudo -u orderdesk /opt/orderdesk/app/venv/bin/uvicorn mcp_server.main:app --host 0.0.0.0 --port 8080
```

### Database Locked

```bash
# Check for other processes
sudo lsof /opt/orderdesk/app/data/app.db

# Kill if necessary
sudo kill -9 PID

# Restart service
sudo systemctl restart orderdesk-mcp
```

### Out of Memory

```bash
# Check memory usage
free -h
ps aux | grep uvicorn

# Increase swap
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## Security Hardening

### Firewall

```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# Firewalld (RHEL/CentOS)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### Fail2Ban

```bash
# Install
sudo apt-get install -y fail2ban

# Configure for nginx
sudo tee /etc/fail2ban/jail.d/nginx.conf << 'EOF'
[nginx-limit-req]
enabled = true
filter = nginx-limit-req
logpath = /var/log/nginx/error.log
maxretry = 5
bantime = 3600
EOF

sudo systemctl restart fail2ban
```

---

## Performance Tuning

### System Limits

```bash
# Increase file descriptors
sudo tee /etc/security/limits.d/orderdesk.conf << 'EOF'
orderdesk soft nofile 65536
orderdesk hard nofile 65536
EOF

# Reboot or re-login for changes to take effect
```

### Python/Uvicorn

```bash
# Tune workers based on CPU cores
WORKERS=$(($(nproc) * 2 + 1))

# Update systemd service
sudo sed -i "s/--workers 2/--workers $WORKERS/" /etc/systemd/system/orderdesk-mcp.service
sudo systemctl daemon-reload
sudo systemctl restart orderdesk-mcp
```

---

## Maintenance

### Log Rotation

```bash
# Create logrotate config
sudo tee /etc/logrotate.d/orderdesk-mcp << 'EOF'
/opt/orderdesk/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 orderdesk orderdesk
    sharedscripts
    postrotate
        systemctl reload orderdesk-mcp > /dev/null 2>&1 || true
    endscript
}
EOF
```

### Database Vacuum

```bash
# Monthly cron job
sudo -u orderdesk crontab -e

# Add:
0 3 1 * * cd /opt/orderdesk/app && ./scripts/performance/vacuum_db.sh >> /opt/orderdesk/logs/vacuum.log 2>&1
```

---

## Monitoring

### Systemd Journal

```bash
# View logs
sudo journalctl -u orderdesk-mcp -f

# Export logs
sudo journalctl -u orderdesk-mcp --since today > orderdesk.log
```

### Prometheus Node Exporter

```bash
# Install
wget https://github.com/prometheus/node_exporter/releases/download/v1.7.0/node_exporter-1.7.0.linux-amd64.tar.gz
tar xvf node_exporter-1.7.0.linux-amd64.tar.gz
sudo cp node_exporter-1.7.0.linux-amd64/node_exporter /usr/local/bin/

# Create service
sudo tee /etc/systemd/system/node-exporter.service << 'EOF'
[Unit]
Description=Prometheus Node Exporter
After=network.target

[Service]
User=nobody
ExecStart=/usr/local/bin/node_exporter
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Start
sudo systemctl enable node-exporter
sudo systemctl start node-exporter
```

---

## High Availability

### Multi-Server Setup

**Requirements:**
- Load balancer (HAProxy, nginx)
- Shared database (NFS or PostgreSQL)
- Shared cache (Redis Cluster)

**Not recommended with SQLite** - use PostgreSQL for HA.

---

## Links

- [DEPLOYMENT-DOCKER.md](DEPLOYMENT-DOCKER.md) - Docker deployment
- [DEPLOYMENT-KUBERNETES.md](DEPLOYMENT-KUBERNETES.md) - Kubernetes deployment
- [PRODUCTION-RUNBOOK.md](PRODUCTION-RUNBOOK.md) - Operations guide

