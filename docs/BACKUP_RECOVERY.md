# Backup and Recovery Guide

Complete guide for backing up and restoring the OrderDesk MCP Server database.

---

## Overview

The OrderDesk MCP Server uses SQLite for data storage. This guide covers:
- Manual backups
- Automated backups
- Restore procedures
- Disaster recovery
- Cloud backup integration

---

## Quick Start

### Manual Backup (Local)
```bash
./scripts/backup/backup.sh
```

### Manual Backup (Docker)
```bash
./scripts/backup/backup.sh --docker --compress
```

### Restore from Backup
```bash
./scripts/backup/restore.sh backups/orderdesk-mcp-20251018_120000.db
```

### Setup Automated Backups
```bash
./scripts/backup/automated-backup.sh --setup-cron
```

---

## Backup Scripts

### Location: `scripts/backup/`

| Script | Purpose |
|--------|---------|
| `backup.sh` | Manual backup with optional compression |
| `restore.sh` | Database restore with verification |
| `automated-backup.sh` | Automated backup with cloud upload |

---

## Manual Backup

### Basic Backup

**Local (non-Docker):**
```bash
./scripts/backup/backup.sh
```

**Docker deployment:**
```bash
./scripts/backup/backup.sh --docker
```

**Output:**
```
✅ Backup created: ./backups/orderdesk-mcp-20251018_120000.db (2.5M)
```

### Compressed Backup

```bash
./scripts/backup/backup.sh --compress
```

**Output:**
```
✅ Backup created: ./backups/orderdesk-mcp-20251018_120000.db
✅ Backup compressed: ./backups/orderdesk-mcp-20251018_120000.db.gz (512K)
```

**Compression Ratio:** Typically 60-80% size reduction

### Docker Backup

```bash
./scripts/backup/backup.sh --docker --compress
```

**Features:**
- Online backup (no downtime)
- Uses SQLite `.backup` command (atomic)
- No table locking
- Consistent snapshot

---

## Automated Backups

### Setup Cron Job

```bash
./scripts/backup/automated-backup.sh --setup-cron
```

**Installs cron job:**
```
0 2 * * * /path/to/scripts/backup/automated-backup.sh
```

**Schedule:** Daily at 2:00 AM

### Custom Schedule

```bash
# Edit crontab
crontab -e

# Every 6 hours
0 */6 * * * /path/to/scripts/backup/automated-backup.sh

# Twice daily (2 AM and 2 PM)
0 2,14 * * * /path/to/scripts/backup/automated-backup.sh

# Weekly (Sunday at 3 AM)
0 3 * * 0 /path/to/scripts/backup/automated-backup.sh
```

### Configuration

```bash
# Environment variables
export BACKUP_DIR=./backups
export RETENTION_DAYS=30
export DOCKER=true
export COMPRESS=true

# Optional cloud upload
export ENABLE_CLOUD_UPLOAD=true
export S3_BUCKET=my-orderdesk-backups
```

### Logs

```bash
# View backup logs
tail -f logs/backup.log

# Check recent backups
ls -lht backups/ | head -10
```

---

## Database Restore

### Preview Restore (Dry Run)

```bash
./scripts/backup/restore.sh --dry-run backups/orderdesk-mcp-20251018_120000.db
```

**Output:**
```
Backup Information:
Tables: 7
Tenants: 3
Stores: 5

✅ Dry Run Complete (No Changes Made)
```

### Restore Local Database

```bash
./scripts/backup/restore.sh backups/orderdesk-mcp-20251018_120000.db
```

**Steps:**
1. Verifies backup integrity
2. Creates pre-restore backup
3. Confirms with user
4. Restores database
5. Verifies restored data

### Restore Docker Database

```bash
./scripts/backup/restore.sh --docker backups/orderdesk-mcp-20251018_120000.db.gz
```

**Steps:**
1. Decompresses if needed
2. Stops Docker container
3. Creates pre-restore backup
4. Restores database
5. Restarts container
6. Verifies restored data

---

## Cloud Backup Integration

### AWS S3

**Setup:**
```bash
# Install AWS CLI
brew install awscli  # macOS
# or: pip install awscli

# Configure credentials
aws configure

# Set bucket name
export S3_BUCKET=my-orderdesk-backups
export ENABLE_CLOUD_UPLOAD=true
```

**Run backup:**
```bash
./scripts/backup/automated-backup.sh
```

**Verify upload:**
```bash
aws s3 ls s3://my-orderdesk-backups/backups/
```

### Google Cloud Storage

**Setup:**
```bash
# Install gcloud SDK
brew install --cask google-cloud-sdk  # macOS

# Authenticate
gcloud auth login

# Set bucket name
export GCS_BUCKET=my-orderdesk-backups
export ENABLE_CLOUD_UPLOAD=true
```

**Run backup:**
```bash
./scripts/backup/automated-backup.sh
```

**Verify upload:**
```bash
gsutil ls gs://my-orderdesk-backups/backups/
```

---

## Disaster Recovery

### Scenario 1: Database Corruption

**Symptoms:**
- SQLite errors in logs
- Application won't start
- Health check fails

**Recovery:**
```bash
# 1. Find latest good backup
ls -lt backups/

# 2. Restore
./scripts/backup/restore.sh --docker backups/orderdesk-mcp-LATEST.db.gz

# 3. Verify
docker-compose logs mcp
curl http://localhost:8080/health
```

### Scenario 2: Accidental Data Deletion

**Symptoms:**
- User deleted important data
- Store removed by mistake

**Recovery:**
```bash
# 1. Stop the server immediately
docker-compose stop mcp

# 2. Find backup before deletion
ls -lt backups/  # Check timestamps

# 3. Restore
./scripts/backup/restore.sh --docker backups/orderdesk-mcp-BEFORE_DELETE.db

# 4. Start server
docker-compose start mcp

# 5. Verify data is restored
# Login to WebUI and check
```

### Scenario 3: Server Failure / Migration

**Recovery:**
```bash
# On new server:

# 1. Clone repository
git clone https://github.com/ebabcock80/orderdesk-mcp.git
cd orderdesk-mcp

# 2. Copy environment config
cp config/environments/production.env .env
# Update all secrets

# 3. Download latest backup from cloud
aws s3 cp s3://my-orderdesk-backups/backups/LATEST.db.gz backups/

# 4. Restore backup
./scripts/backup/restore.sh --docker backups/LATEST.db.gz

# 5. Start server
docker-compose -f docker-compose.production.yml up -d

# 6. Verify
curl https://yourdomain.com/health/ready
```

---

## Backup Verification

### Verify Backup Integrity

```bash
# SQLite integrity check
sqlite3 backups/orderdesk-mcp-20251018_120000.db "PRAGMA integrity_check;"

# Should output: ok
```

### Test Restore

```bash
# 1. Create test directory
mkdir -p test-restore

# 2. Restore to test location
export DATA_DIR=./test-restore
./scripts/backup/restore.sh backups/BACKUP.db

# 3. Verify data
sqlite3 test-restore/app.db "SELECT count(*) FROM tenants;"
sqlite3 test-restore/app.db "SELECT count(*) FROM stores;"

# 4. Cleanup
rm -rf test-restore
```

---

## Backup Best Practices

### Frequency

| Environment | Frequency | Retention |
|-------------|-----------|-----------|
| **Development** | Daily | 7 days |
| **Staging** | Every 6 hours | 14 days |
| **Production** | Hourly | 30 days |

### 3-2-1 Backup Rule

✅ **3** Copies of data:
- 1 active database
- 1 local backup
- 1 cloud backup

✅ **2** Different media types:
- Local disk (SSD/HDD)
- Cloud storage (S3/GCS)

✅ **1** Offsite copy:
- Cloud backup in different region

### Backup Checklist

**Daily:**
- [ ] Automated backup runs successfully
- [ ] Backup files created in `backups/`
- [ ] Cloud upload succeeds (if enabled)
- [ ] Old backups cleaned up per retention policy

**Weekly:**
- [ ] Test backup integrity
- [ ] Verify backup sizes are reasonable
- [ ] Check backup logs for errors
- [ ] Test restore procedure (dry-run)

**Monthly:**
- [ ] Full restore test to staging
- [ ] Review backup retention policy
- [ ] Check cloud storage costs
- [ ] Update backup procedures if needed

---

## Storage Requirements

### Backup Size Estimates

| Data | Uncompressed | Compressed (.gz) |
|------|--------------|------------------|
| **Empty database** | ~20KB | ~4KB |
| **10 tenants, 50 stores** | ~500KB | ~100KB |
| **100 tenants, 500 stores** | ~5MB | ~1MB |
| **1000 tenants, 5000 stores** | ~50MB | ~10MB |

**With audit logs (90 days):**
- Add ~10MB per 10,000 operations

### Retention Calculations

**Example: 100 tenants, daily backups, 30-day retention**
- Compressed backup: ~1MB
- Daily for 30 days: ~30MB total
- Storage cost: ~$0.01/month (S3)

**Recommendation:** Compress all automated backups

---

## Cloud Storage Setup

### AWS S3 Lifecycle Policy

```json
{
  "Rules": [
    {
      "Id": "ArchiveOldBackups",
      "Status": "Enabled",
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "GLACIER"
        }
      ],
      "Expiration": {
        "Days": 90
      }
    }
  ]
}
```

**Apply:**
```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket my-orderdesk-backups \
  --lifecycle-configuration file://lifecycle.json
```

### Google Cloud Storage Lifecycle

```json
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
        "condition": {"age": 30}
      },
      {
        "action": {"type": "Delete"},
        "condition": {"age": 90}
      }
    ]
  }
}
```

**Apply:**
```bash
gsutil lifecycle set lifecycle.json gs://my-orderdesk-backups
```

---

## Monitoring Backups

### Check Backup Status

```bash
# View recent backups
ls -lht backups/ | head -5

# Check backup logs
tail -f logs/backup.log

# Verify latest backup
sqlite3 backups/$(ls -t backups/*.db | head -1) "PRAGMA integrity_check;"
```

### Backup Alerts

**Cron failure notification:**
```bash
# Add to crontab
MAILTO=admin@yourdomain.com
0 2 * * * /path/to/scripts/backup/automated-backup.sh
```

**Monitoring script:**
```bash
#!/bin/bash
# Check if backup ran in last 24 hours
LATEST=$(find backups/ -name "*.db*" -mtime -1 | wc -l)
if [ "$LATEST" -eq 0 ]; then
    echo "ALERT: No backup created in last 24 hours!"
    # Send alert
fi
```

---

## Recovery Testing

### Monthly Recovery Test

```bash
# 1. Create test environment
docker-compose -f docker-compose.staging.yml down
rm -rf test-data/
mkdir test-data/

# 2. Restore latest backup
export DATA_DIR=./test-data
./scripts/backup/restore.sh backups/LATEST.db.gz

# 3. Start server with test data
export DATA_DIR=./test-data
docker-compose -f docker-compose.staging.yml up -d

# 4. Verify
curl http://localhost:8080/health/detailed
# Login to WebUI and verify data

# 5. Cleanup
docker-compose -f docker-compose.staging.yml down
rm -rf test-data/
```

### Recovery Time Objective (RTO)

| Scenario | Target RTO | Actual |
|----------|------------|--------|
| Database corruption | < 15 minutes | ~5-10 minutes |
| Accidental deletion | < 30 minutes | ~15-20 minutes |
| Server failure | < 1 hour | ~30-45 minutes |
| Complete disaster | < 4 hours | ~2-3 hours |

**RTO depends on:**
- Backup size
- Network speed (for cloud download)
- Server provisioning time

---

## Troubleshooting

### "Backup failed: database is locked"

SQLite's `.backup` command handles locks automatically. If you see this error:

```bash
# Wait for active operations to complete
# Or use the Docker backup method (more robust)
./scripts/backup/backup.sh --docker
```

### "Restore failed: container not found"

```bash
# Check container name
docker ps -a | grep orderdesk

# Update CONTAINER_NAME
export CONTAINER_NAME=your-actual-container-name
./scripts/backup/restore.sh --docker BACKUP.db
```

### "Corrupt backup file"

```bash
# Verify integrity
sqlite3 BACKUP.db "PRAGMA integrity_check;"

# If corrupt, use previous backup
ls -lt backups/  # Find older backup
./scripts/backup/restore.sh backups/OLDER_BACKUP.db
```

### "Out of disk space"

```bash
# Check disk space
df -h

# Clean up old backups manually
rm backups/orderdesk-mcp-2024*.db.gz

# Or reduce retention period
export RETENTION_DAYS=7
./scripts/backup/automated-backup.sh
```

---

## What Gets Backed Up

### Database Tables
- ✅ `tenants` - All user accounts
- ✅ `stores` - OrderDesk store registrations (with encrypted API keys)
- ✅ `audit_log` - Complete audit trail
- ✅ `sessions` - Active user sessions
- ✅ `magic_links` - Email verification tokens
- ✅ `webhook_events` - Webhook history
- ✅ `master_key_metadata` - Key management data

### What's NOT Backed Up
- ❌ Application code (in Git)
- ❌ Configuration files (in Git)
- ❌ Docker images (rebuild from Dockerfile)
- ❌ Logs (separate log management)

---

## Production Backup Strategy

### Recommended Setup

```bash
# 1. Setup automated daily backups
./scripts/backup/automated-backup.sh --setup-cron

# 2. Configure cloud upload
export ENABLE_CLOUD_UPLOAD=true
export S3_BUCKET=my-orderdesk-backups

# 3. Test backup
./scripts/backup/automated-backup.sh --test

# 4. Verify cloud upload
aws s3 ls s3://my-orderdesk-backups/backups/

# 5. Setup monitoring
# Add to your monitoring system to check:
# - Backup file created in last 24 hours
# - Backup size is reasonable (not 0 bytes)
# - Cloud upload succeeded
```

### Backup Rotation

**Local Backups:**
- Hourly: Keep for 48 hours
- Daily: Keep for 30 days
- Weekly: Keep for 90 days
- Monthly: Keep for 1 year

**Cloud Backups:**
- All backups uploaded
- Lifecycle policy moves to cold storage after 30 days
- Automatically deleted after 90 days

---

## Links

- [README.md](../README.md) - Main documentation
- [PRODUCTION-RUNBOOK.md](PRODUCTION-RUNBOOK.md) - Operations guide
- [ENVIRONMENT_CONFIGURATION.md](ENVIRONMENT_CONFIGURATION.md) - Environment setup
- [DEPLOYMENT-DOCKER.md](DEPLOYMENT-DOCKER.md) - Docker deployment

