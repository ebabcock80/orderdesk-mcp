# Kubernetes Deployment Guide

Complete guide for deploying the OrderDesk MCP Server on Kubernetes.

---

## Overview

This guide covers deploying OrderDesk MCP Server on Kubernetes with:
- Multi-replica deployment
- Redis caching
- Persistent storage
- Auto-scaling
- SSL/TLS termination
- Monitoring integration

---

## Prerequisites

- Kubernetes cluster (v1.23+)
- kubectl configured
- Helm 3 (optional, for cert-manager)
- Container registry access (Docker Hub, GCR, ECR)

---

## Quick Start

### 1. Build and Push Image

```bash
# Build image
docker build -t your-registry/orderdesk-mcp:v0.1.0 .

# Push to registry
docker push your-registry/orderdesk-mcp:v0.1.0

# Update deployment.yaml with your image
sed -i 's|orderdesk-mcp-server:latest|your-registry/orderdesk-mcp:v0.1.0|' k8s/base/deployment.yaml
```

### 2. Create Secrets

```bash
# Generate secrets
MCP_KMS_KEY=$(openssl rand -base64 32)
ADMIN_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
JWT_KEY=$(openssl rand -base64 48)
CSRF_KEY=$(openssl rand -base64 32)

# Create Kubernetes secret
kubectl create secret generic orderdesk-secrets \
  --from-literal=mcp_kms_key="$MCP_KMS_KEY" \
  --from-literal=admin_master_key="$ADMIN_KEY" \
  --from-literal=jwt_secret_key="$JWT_KEY" \
  --from-literal=csrf_secret_key="$CSRF_KEY"
```

### 3. Update ConfigMap

```bash
# Edit k8s/base/configmap.yaml
# Update public_url with your domain
kubectl apply -f k8s/base/configmap.yaml
```

### 4. Deploy

```bash
# Deploy all resources
kubectl apply -f k8s/base/

# Verify deployment
kubectl get pods -l app=orderdesk-mcp
kubectl get svc orderdesk-mcp
kubectl get ingress orderdesk-mcp
```

### 5. Verify

```bash
# Check pod status
kubectl get pods -l app=orderdesk-mcp

# Check logs
kubectl logs -l app=orderdesk-mcp --tail=50

# Test health endpoint
kubectl port-forward svc/orderdesk-mcp 8080:8080
curl http://localhost:8080/health
```

---

## Kubernetes Resources

### Base Manifests (`k8s/base/`)

| File | Purpose |
|------|---------|
| `deployment.yaml` | Main application deployment (2 replicas) |
| `service.yaml` | ClusterIP service for internal access |
| `ingress.yaml` | Ingress for external access with SSL/TLS |
| `configmap.yaml` | Non-secret configuration |
| `secrets.yaml.example` | Secret template (don't commit real secrets!) |
| `pvc.yaml` | Persistent storage for database |
| `redis-deployment.yaml` | Redis cache deployment |
| `hpa.yaml` | Horizontal Pod Autoscaler (2-10 replicas) |

---

## Deployment Configuration

### Replicas and Scaling

**Default Configuration:**
```yaml
replicas: 2  # Minimum for high availability
```

**Auto-scaling:**
```yaml
# HPA scales based on CPU/memory
minReplicas: 2
maxReplicas: 10
targetCPUUtilization: 70%
targetMemoryUtilization: 80%
```

**Manual scaling:**
```bash
kubectl scale deployment orderdesk-mcp --replicas=5
```

---

### Resource Limits

```yaml
resources:
  requests:
    memory: "256Mi"   # Guaranteed
    cpu: "250m"       # 0.25 CPU
  limits:
    memory: "512Mi"   # Maximum
    cpu: "1000m"      # 1 CPU
```

**Recommendations by load:**
- **Light (<100 users):** 256Mi/250m
- **Medium (100-500):** 512Mi/500m
- **Heavy (500-1000):** 1Gi/1000m
- **Very Heavy (1000+):** 2Gi/2000m

---

### Health Probes

**Liveness Probe:**
```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 30
```

**Purpose:** Restart unhealthy pods

**Readiness Probe:**
```yaml
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 10
```

**Purpose:** Remove unready pods from service

**Startup Probe:**
```yaml
startupProbe:
  httpGet:
    path: /health
    port: 8080
  failureThreshold: 30
  periodSeconds: 5
```

**Purpose:** Allow slow startup (up to 150s)

---

## Persistent Storage

### Database Volume

```yaml
# PersistentVolumeClaim
storage: 10Gi
accessModes:
- ReadWriteOnce
storageClassName: standard
```

**Storage Classes by Provider:**
- **AWS EKS:** `gp3` (SSD)
- **Google GKE:** `standard-rwo` (SSD)
- **Azure AKS:** `managed-premium` (SSD)
- **On-Premise:** Configure StorageClass for your provider

**Important:** SQLite requires ReadWriteOnce (RWO). For multi-replica with shared database, consider PostgreSQL instead.

---

## SSL/TLS Configuration

### Option 1: cert-manager (Recommended)

**Install cert-manager:**
```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
```

**Create ClusterIssuer:**
```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@yourdomain.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
```

**Apply:**
```bash
kubectl apply -f cluster-issuer.yaml
```

**Ingress automatically requests certificate!**

### Option 2: Manual Certificates

```bash
# Create TLS secret from existing certificates
kubectl create secret tls orderdesk-mcp-tls \
  --cert=path/to/fullchain.pem \
  --key=path/to/privkey.pem
```

---

## Redis Configuration

### Internal Redis (Included)

```bash
# Deployed automatically with base manifests
kubectl apply -f k8s/base/redis-deployment.yaml
```

**Configuration:**
- 512MB max memory
- LRU eviction policy
- Persistence enabled (AOF)
- 5GB persistent volume

### External Redis (Cloud)

**AWS ElastiCache:**
```yaml
# In configmap.yaml
redis_url: "redis://your-elasticache-endpoint:6379/0"

# Remove redis-deployment.yaml from deployment
```

**Google Cloud Memorystore:**
```yaml
redis_url: "redis://10.x.x.x:6379/0"  # Internal IP
```

**Azure Cache for Redis:**
```yaml
redis_url: "rediss://your-cache.redis.cache.windows.net:6380/0"  # Note: rediss (SSL)
```

---

## Monitoring Integration

### Prometheus

**ServiceMonitor (if using Prometheus Operator):**
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: orderdesk-mcp
spec:
  selector:
    matchLabels:
      app: orderdesk-mcp
  endpoints:
  - port: http
    path: /metrics
    interval: 30s
```

**Apply:**
```bash
kubectl apply -f k8s/servicemonitor.yaml
```

### Grafana Dashboards

Import Grafana dashboards for:
- HTTP request latency
- Cache hit rates
- Error rates
- Pod resource usage

---

## Deployment Strategies

### Rolling Update (Default)

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1        # Add 1 pod before removing old
    maxUnavailable: 0  # No downtime
```

**Deploy update:**
```bash
# Update image
kubectl set image deployment/orderdesk-mcp mcp-server=your-registry/orderdesk-mcp:v0.2.0

# Watch rollout
kubectl rollout status deployment/orderdesk-mcp
```

### Blue-Green Deployment

```bash
# 1. Deploy green version
kubectl apply -f k8s/green/

# 2. Test green
kubectl port-forward svc/orderdesk-mcp-green 8080:8080

# 3. Switch traffic (update ingress)
kubectl patch ingress orderdesk-mcp -p '{"spec":{"rules":[{"host":"yourdomain.com","http":{"paths":[{"path":"/","pathType":"Prefix","backend":{"service":{"name":"orderdesk-mcp-green"}}}]}}]}}'

# 4. Remove blue after verification
kubectl delete -f k8s/blue/
```

---

## Cloud Provider Specifics

### AWS EKS

**Storage Class:**
```yaml
storageClassName: gp3
```

**Load Balancer:**
```yaml
# Use AWS ALB Ingress Controller
annotations:
  kubernetes.io/ingress.class: alb
  alb.ingress.kubernetes.io/scheme: internet-facing
  alb.ingress.kubernetes.io/target-type: ip
```

**Secrets Manager:**
```yaml
# Use External Secrets Operator
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: orderdesk-secrets
spec:
  secretStoreRef:
    name: aws-secrets-manager
  target:
    name: orderdesk-secrets
  data:
  - secretKey: mcp_kms_key
    remoteRef:
      key: orderdesk/mcp_kms_key
```

---

### Google GKE

**Storage Class:**
```yaml
storageClassName: standard-rwo
```

**Load Balancer:**
```yaml
# GKE Ingress creates GCP Load Balancer
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  annotations:
    kubernetes.io/ingress.class: "gce"
```

**Secrets Manager:**
```yaml
# Use Google Secret Manager with External Secrets
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: gcpsm-secret-store
spec:
  provider:
    gcpsm:
      projectID: "your-project-id"
```

---

### Azure AKS

**Storage Class:**
```yaml
storageClassName: managed-premium
```

**Load Balancer:**
```yaml
annotations:
  kubernetes.io/ingress.class: azure/application-gateway
```

---

## Operations

### View Logs

```bash
# All pods
kubectl logs -l app=orderdesk-mcp --tail=100 -f

# Specific pod
kubectl logs orderdesk-mcp-xxxxx-yyyyy -f

# Previous crashed pod
kubectl logs orderdesk-mcp-xxxxx-yyyyy --previous
```

### Execute Commands in Pod

```bash
# Get shell
kubectl exec -it orderdesk-mcp-xxxxx-yyyyy -- /bin/sh

# Run backup
kubectl exec orderdesk-mcp-xxxxx-yyyyy -- sqlite3 /app/data/app.db ".backup '/app/data/backup.db'"

# Copy backup out
kubectl cp orderdesk-mcp-xxxxx-yyyyy:/app/data/backup.db ./backup.db
```

### Database Backup

```bash
# Backup script
kubectl exec -it $(kubectl get pod -l app=orderdesk-mcp -o jsonpath='{.items[0].metadata.name}') -- \
  sh -c 'sqlite3 /app/data/app.db ".backup /app/data/backup-$(date +%Y%m%d).db"'

# Copy out
kubectl cp $(kubectl get pod -l app=orderdesk-mcp -o jsonpath='{.items[0].metadata.name}'):/app/data/backup-*.db ./backups/
```

---

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl describe pod orderdesk-mcp-xxxxx-yyyyy

# Common issues:
# - ImagePullBackOff: Wrong image name or registry auth
# - CrashLoopBackOff: App crashing on startup
# - Pending: Insufficient resources or PVC not bound
```

### Database Issues

```bash
# Check PVC status
kubectl get pvc

# Check if volume is mounted
kubectl exec orderdesk-mcp-xxxxx-yyyyy -- ls -la /app/data/
```

### Redis Connection Issues

```bash
# Check Redis is running
kubectl get pods -l component=redis

# Test connection
kubectl exec orderdesk-mcp-xxxxx-yyyyy -- \
  sh -c 'apk add redis && redis-cli -h orderdesk-redis ping'
```

---

## Production Checklist

### Before Deployment
- [ ] Image built and pushed to registry
- [ ] Secrets created (unique, strong keys)
- [ ] ConfigMap updated (correct domain)
- [ ] Storage class configured
- [ ] Ingress controller installed
- [ ] cert-manager installed (if using)
- [ ] Monitoring ready (Prometheus + Grafana)

### Deployment
- [ ] Apply all manifests (`kubectl apply -f k8s/base/`)
- [ ] Verify pods running
- [ ] Check logs for errors
- [ ] Test health endpoints
- [ ] Verify database created
- [ ] Test MCP endpoint

### Post-Deployment
- [ ] Configure DNS (point to ingress)
- [ ] Verify SSL/TLS working
- [ ] Test from Claude Desktop
- [ ] Set up alerts
- [ ] Configure backups
- [ ] Monitor for 24 hours

---

## Scaling

### Manual Scaling

```bash
# Scale deployment
kubectl scale deployment orderdesk-mcp --replicas=5

# Verify
kubectl get pods -l app=orderdesk-mcp
```

### Auto-Scaling (HPA)

```bash
# Apply HPA
kubectl apply -f k8s/base/hpa.yaml

# Check HPA status
kubectl get hpa orderdesk-mcp

# Watch scaling
kubectl get hpa orderdesk-mcp --watch
```

**Triggers:**
- CPU > 70% → scale up
- Memory > 80% → scale up
- Sustained low usage → scale down (after 5 min)

---

## Updates and Rollbacks

### Rolling Update

```bash
# Update to new version
kubectl set image deployment/orderdesk-mcp \
  mcp-server=your-registry/orderdesk-mcp:v0.2.0

# Watch rollout
kubectl rollout status deployment/orderdesk-mcp

# Check history
kubectl rollout history deployment/orderdesk-mcp
```

### Rollback

```bash
# Rollback to previous version
kubectl rollout undo deployment/orderdesk-mcp

# Rollback to specific revision
kubectl rollout undo deployment/orderdesk-mcp --to-revision=3
```

---

## Backup and Recovery

### Automated Backups

**CronJob for backups:**
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: orderdesk-backup
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: your-registry/orderdesk-mcp:latest
            command:
            - /bin/sh
            - -c
            - |
              sqlite3 /app/data/app.db ".backup /app/data/backup-$(date +%Y%m%d).db"
              # Upload to S3 or GCS
            volumeMounts:
            - name: data
              mountPath: /app/data
          volumes:
          - name: data
            persistentVolumeClaim:
              claimName: orderdesk-data
          restartPolicy: OnFailure
```

---

## Security

### Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: orderdesk-mcp
spec:
  podSelector:
    matchLabels:
      app: orderdesk-mcp
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8080
  egress:
  - to:
    - podSelector:
        matchLabels:
          component: redis
    ports:
    - protocol: TCP
      port: 6379
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 443  # OrderDesk API
```

### Pod Security

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000
  seccompProfile:
    type: RuntimeDefault
```

---

## Monitoring

### Prometheus Scraping

**Service annotations:**
```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8080"
  prometheus.io/path: "/metrics"
```

**Metrics available at:** `http://orderdesk-mcp:8080/metrics`

### Grafana Dashboards

**Import dashboards for:**
1. Application performance
2. Cache effectiveness
3. Database performance
4. Error rates
5. Resource usage

---

## Cost Optimization

### Resource Optimization

```bash
# Check actual usage
kubectl top pods -l app=orderdesk-mcp

# Adjust requests/limits based on actual usage
# Recommendation: Set requests to p95 usage, limits to peak
```

### Storage Optimization

```bash
# Check PVC usage
kubectl exec orderdesk-mcp-xxxxx-yyyyy -- df -h /app/data

# Resize if needed (if StorageClass supports it)
kubectl patch pvc orderdesk-data -p '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'
```

### Autoscaling Tuning

```yaml
# Tune HPA for cost savings
minReplicas: 1  # For low-traffic periods
maxReplicas: 5  # Cap maximum
```

---

## High Availability

### Multi-Region Deployment

**Requirements:**
- Multi-region Kubernetes cluster
- External database (PostgreSQL with replication)
- External Redis (Redis Cluster or Sentinel)
- Global load balancer

**Not recommended with SQLite** - use PostgreSQL for multi-region.

### Disaster Recovery

```bash
# 1. Backup PVC regularly
kubectl exec -it orderdesk-mcp-xxxxx-yyyyy -- /app/scripts/backup/backup.sh

# 2. Store backups in S3/GCS
# 3. Document restore procedure
# 4. Test DR annually
```

---

## Links

- [DEPLOYMENT-DOCKER.md](DEPLOYMENT-DOCKER.md) - Docker deployment
- [ENVIRONMENT_CONFIGURATION.md](ENVIRONMENT_CONFIGURATION.md) - Environment config
- [BACKUP_RECOVERY.md](BACKUP_RECOVERY.md) - Backup procedures
- [PRODUCTION-RUNBOOK.md](PRODUCTION-RUNBOOK.md) - Operations guide

