# Branching Strategy

## Overview

The OrderDesk MCP Server uses a feature branch workflow to protect the production-ready `main` branch while enabling active development.

---

## Branch Structure

### `main` Branch (Protected)
- **Status:** Production-Ready ✅
- **CI:** All tests passing (110/110)
- **Coverage:** >80%
- **Documentation:** Complete and clean
- **Purpose:** Stable, deployable code at all times

**Current State:**
- HTTP MCP endpoint functional
- Smart order merge workflow working
- All 11 MCP tools tested
- WebUI admin interface complete
- User management with optional signup
- Zero linting/type errors

**Protected From:**
- Direct commits (use PRs)
- Breaking changes
- Experimental code
- Work-in-progress features

---

### `feature/phase-7-production-hardening` Branch (Active)
- **Status:** In Development 🔄
- **Based On:** `main` (29de84f)
- **Purpose:** Phase 7 implementation
- **Tasks:** 4/19 complete (21%)

**Will Include:**
- Enhanced Prometheus metrics
- Structured health checks with dependencies
- Performance optimization
- Security audit and penetration testing
- Load testing
- Error tracking integration (Sentry)
- Deployment guides (Kubernetes, bare metal)
- Environment-specific configs
- Database migration strategy
- Backup and recovery procedures
- Monitoring dashboards (Grafana)
- Alert configuration
- Log aggregation
- Performance benchmarks
- Production checklist and runbook

**PR Requirements:**
- All tests passing
- CI checks green
- Code reviewed
- Documentation updated
- No breaking changes to API

---

## Workflow

### For New Features

1. **Create Feature Branch:**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/your-feature-name
   ```

2. **Develop & Test:**
   ```bash
   # Make changes
   git add .
   git commit -m "feat: your feature"
   
   # Run tests
   pytest tests/
   ./test_mcp_endpoints.sh
   ```

3. **Push & Create PR:**
   ```bash
   git push -u origin feature/your-feature-name
   # Create PR on GitHub
   ```

4. **Merge to Main:**
   - After PR approval
   - All CI checks passing
   - Code reviewed

---

### For Bug Fixes

1. **Create Hotfix Branch:**
   ```bash
   git checkout main
   git checkout -b hotfix/bug-description
   ```

2. **Fix & Test:**
   ```bash
   # Fix the bug
   git commit -m "fix: bug description"
   
   # Verify fix
   pytest tests/
   ```

3. **Fast-Track to Main:**
   - Create PR
   - Quick review
   - Merge immediately if critical

---

## Branch Protection Rules (Recommended)

### For `main` Branch:

1. **Require PR Reviews:**
   - At least 1 approval required
   - Cannot push directly to main

2. **Require Status Checks:**
   - Lint & Format Check must pass
   - Type Check must pass
   - Unit Tests must pass
   - Docker Build must pass

3. **No Force Push:**
   - Preserve history
   - Traceable changes

4. **Linear Integration:**
   - PR title must reference Linear issue
   - Format: `feat(scope): description (EBA-XX)`

---

## Current Branches

### Active Branches

| Branch | Purpose | Status | Tests |
|--------|---------|--------|-------|
| `main` | Production | ✅ Stable | 110/110 |
| `feature/phase-7-production-hardening` | Phase 7 work | 🔄 Active | TBD |

### Merged Branches (Historical)

All previous phase work was done directly on `main` during initial development. Now that we're production-ready, we use feature branches.

---

## Commit Message Format

Follow Conventional Commits format:

```
<type>(<scope>): <description> (Linear-ID)

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `test`: Test additions/changes
- `chore`: Maintenance tasks
- `perf`: Performance improvements

**Example:**
```
feat(metrics): add enhanced Prometheus metrics (EBA-14)

- Add request latency histograms by endpoint
- Add cache hit/miss rate gauges
- Add database query time metrics
- Add error rate counters by type

Implements Phase 7 monitoring requirements.
```

---

## Release Process

### Version Tagging

When ready to release:

```bash
git checkout main
git tag -a v0.2.0-alpha -m "Release v0.2.0-alpha: Phase 7 Complete"
git push origin v0.2.0-alpha
```

### Changelog

Maintain a `CHANGELOG.md` with all changes:
- Features added
- Bugs fixed
- Breaking changes
- Migration guides

---

## Linear Integration

### Issue References

- All commits should reference Linear issues
- PR titles include Linear ID: `(EBA-14)`
- PR descriptions link to Linear issue

### Branch Naming

Format: `type/eba-XX-short-description`

**Examples:**
- `feature/eba-14-phase-7-production-hardening`
- `fix/eba-19-cache-invalidation-bug`
- `docs/eba-20-api-reference-update`

---

## Benefits of This Strategy

✅ **Safe Development:**
- Main branch always deployable
- Can experiment in feature branches
- Easy rollback if needed

✅ **Team Collaboration:**
- Multiple developers can work simultaneously
- Clear ownership of branches
- Code review process

✅ **Quality Assurance:**
- All changes go through CI
- PR reviews catch issues
- Tests run on every push

✅ **Traceability:**
- Clear history of changes
- Linked to Linear issues
- Easy to find when features were added

---

## Current Status

- ✅ `main` branch: Production-ready
- ✅ Feature branch created: `feature/phase-7-production-hardening`
- ✅ Branch pushed to GitHub
- ✅ Ready for Phase 7 development
- ✅ Main branch protected from experimental changes

**Safe to start Phase 7 implementation!** 🚀

