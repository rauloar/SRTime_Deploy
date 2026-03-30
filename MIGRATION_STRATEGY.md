# Complete Database Migration Strategy for SRTime

This document provides a comprehensive overview of how database migrations work for both deployment scenarios.

---

## Executive Summary

| Aspect | PostgreSQL (Server) | SQLite (Standalone) |
|--------|-------------------|-------------------|
| **When Used** | Company network / API deployment | Windows desktop app (standalone) |
| **Migration Tool** | Alembic (Python framework) | Direct SQL scripts (Python) |
| **How to Migrate** | `alembic upgrade head` | `python migrate_legacy_sqlite.py` |
| **Deployment** | Centrally managed | User runs before app update |
| **Backup Strategy** | Server snapshots (IT managed) | Auto-timestamped backups created |
| **Documentation** | `DATABASE_MIGRATIONS.md`, `MIGRATION_LOG.md` | `SQLITE_MIGRATIONS.md` (this file) |
| **Idempotent** | ✅ Yes (safe to run multiple times) | ✅ Yes (safe to run multiple times) |

---

## Scenario 1: PostgreSQL Deployment (Company Network)

### Setup
```
Infrastructure: PostgreSQL server (production database)
Used by: Web UI, Windows app (remote API calls)
Managed by: IT/DevOps team
```

### Migration Workflow

**1. Developer makes schema changes**
```python
# File: attendance/models/shift.py
class Shift(Base):
    __tablename__ = "shifts"
    # ... existing columns ...
    is_overnight_shift = Column(Boolean, default=False)  # NEW
    break_duration_minutes = Column(Integer, default=0)  # NEW
```

**2. Generate migration script**
```bash
cd c:\Proyectos\SRTime
alembic revision --autogenerate -m "Add overnight shift support"
# Creates: alembic/versions/e2d3a29b7890_add_is_overnight_shift...py
```

**3. Review generated migration**
```python
# Auto-generated file checks for differences
def upgrade():
    op.add_column('shifts', sa.Column('is_overnight_shift', sa.Boolean(), 
                  nullable=False, server_default='false'))
    op.add_column('shifts', sa.Column('break_duration_minutes', sa.Integer(), 
                  nullable=False, server_default='0'))

def downgrade():
    op.drop_column('shifts', 'break_duration_minutes')
    op.drop_column('shifts', 'is_overnight_shift')
```

**4. Test locally**
```bash
alembic upgrade head    # Apply to local dev DB
python -m pytest attendance\tests\ -v  # Verify no regressions (31/31 PASSED)
python verify_migration.py  # Check schema matches models
```

**5. Deploy to production**
```bash
# On production server:
alembic upgrade head

# Result:
INFO  [alembic.runtime.migration] Running upgrade  -> e2d3a29b7890
[OK] Database migrated to e2d3a29b7890
```

### Key Files
- `alembic.ini` - Alembic configuration
- `alembic/env.py` - Database connection setup
- `alembic/versions/` - Migration scripts (versioned)
- `MIGRATION_LOG.md` - Record of completed migrations

---

## Scenario 2: SQLite Deployment (Windows Standalone App)

### Setup
```
Infrastructure: SQLite database file (attendance.db) in app directory
Used by: Windows desktop app (local, no network)
Managed by: Individual user / app auto-update
```

### Migration Workflow

**1. Developer updates SQLAlchemy model** (same as PostgreSQL)
```python
# File: attendance/models/shift.py
class Shift(Base):
    is_overnight_shift = Column(Boolean, default=False)  # Same changes
    break_duration_minutes = Column(Integer, default=0)
```

**2. Update migration scripts**
```python
# File: attendance/migrate_sqlite.py (generic migration)
# Adds logic to check for new columns

# File: dist/SRTIime_Win/migrate_legacy_sqlite.py (app-specific)
# Used by app when deploying new versions

# Both contain:
if add_column_if_missing(cur, "shifts", "is_overnight_shift", ...):
    changed.append("shifts.is_overnight_shift")
```

**3. Test locally**
```bash
cd c:\Proyectos\SRTime
python attendance/migrate_sqlite.py
python -m pytest attendance\tests\ -v  # Verify (31/31 PASSED)
python dist/SRTIime_Win/verify_sqlite_migration.py  # Check schema
```

**4. Deploy to users**
```bash
# Package updated SRTime_Win.exe with:
# - Updated Python code
# - migrate_legacy_sqlite.py (updated)
# - Old attendance.db remains with user

# User runs (before launching new version):
python migrate_legacy_sqlite.py

# Result:
[OK] Backup created: attendance.bak_20260329_205923.db
[OK] Applied migrations:
  - shifts.is_overnight_shift
  - shifts.break_duration_minutes
[OK] Active login users: 1
[DONE] SQLite migration finished.
```

### Key Files
- `attendance/migrate_sqlite.py` - Generic development migration script
- `dist/SRTIime_Win/migrate_legacy_sqlite.py` - App-bundled migration
- `SQLITE_MIGRATIONS.md` - User-facing migration docs

---

## Migration Comparison Matrix

### PostgreSQL (Alembic)

✅ **Strengths**
- Automatic schema detection (`--autogenerate`)
- Built-in versioning and history tracking
- Rollback support (`downgrade` command)
- Handles complex database changes
- Production-grade tool used industry-wide
- Schema sync with source control

❌ **Limitations**
- Requires central database server
- Requires IT/DevOps coordination
- More complex setup

### SQLite (Direct Python Scripts)

✅ **Strengths**
- No external tool dependencies
- Simple, transparent logic (readable Python)
- Automatic backups before each migration
- Zero deployment overhead
- Works on user machines without IT involvement
- Instant results

❌ **Limitations**
- Manual version tracking
- Limited rollback (backups only)
- Requires more careful testing before release

---

## Both Strategies: New Columns Added

### PostgreSQL Applied

```
Database: PostgreSQL server
Table: shifts
Changes:
  • is_overnight_shift (BOOLEAN, default: false)
  • break_duration_minutes (INTEGER, default: 0)
Status: e2d3a29b7890 (current)
```

### SQLite Applied

```
Database: SQLite 3
Location: attendance.db
Table: shifts
Changes:
  • is_overnight_shift (BOOLEAN, default: 0)
  • break_duration_minutes (INTEGER, default: 0)
Backup: attendance.bak_20260329_205923.db
Status: All records have defaults
```

---

## Migration Rules for Developers

### When Adding New Database Features

1. **Update SQLAlchemy Model**
   - Edit `attendance/models/shift.py` (example)
   - Add new Column with sensible defaults

2. **For PostgreSQL:**
   - Run: `alembic revision --autogenerate -m "description"`
   - Review: Generated SQL file in `alembic/versions/`
   - Test: `alembic upgrade head` + `pytest`

3. **For SQLite:**
   - Update: `attendance/migrate_sqlite.py`
   - Update: `dist/SRTIime_Win/migrate_legacy_sqlite.py`
   - Test: `python migrate_sqlite.py` + `pytest`

4. **For Both:**
   - Test thoroughly with all existing data patterns
   - Run full test suite: `pytest attendance/tests/ -v`
   - Document change in relevant .md file

### Migration Characteristics (Both systems)

- ✅ **Backward compatible** - Existing code works without changes
- ✅ **Idempotent** - Safe to run multiple times
- ✅ **Non-destructive** - Only adds columns/tables, never deletes
- ✅ **Data preserving** - All existing records protected
- ✅ **Defaulted** - New columns have sensible defaults

---

## Verification Commands

### PostgreSQL

```bash
# Check current version
alembic current

# View all migrations
alembic history

# Verify schema matches models
python verify_migration.py

# Test application
python -m pytest attendance/tests/ -v
```

### SQLite

```bash
# Check table structure
python -c "import sqlite3; c = sqlite3.connect('attendance.db'); c.execute('PRAGMA table_info(shifts)'); print([r[1:3] for r in c.fetchall()])"

# Verify migration
python dist/SRTIime_Win/verify_sqlite_migration.py

# Test application
python -m pytest attendance/tests/ -v
```

---

## Deployment Checklist

### For PostgreSQL Release
- [ ] Update SQLAlchemy models
- [ ] Generate Alembic migration
- [ ] Review generated SQL
- [ ] Test locally with `pytest`
- [ ] Commit migration to Git
- [ ] Deploy to staging first
- [ ] Production validation with `alembic current`

### For SQLite Release
- [ ] Update SQLAlchemy models
- [ ] Update `migrate_sqlite.py`
- [ ] Update `dist/SRTIime_Win/migrate_legacy_sqlite.py`
- [ ] Test locally with `pytest`
- [ ] Verify with standalone script
- [ ] Create Windows app build
- [ ] Include migration scripts in distribution
- [ ] Include `SQLITE_MIGRATIONS.md` in release notes

---

## Quick Reference: Data Schema v2

### Shifts Table (BOTH SYSTEMS)

```sql
CREATE TABLE shifts (
    id INTEGER PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    expected_in TIME NOT NULL,
    expected_out TIME NOT NULL,
    grace_period_minutes INTEGER DEFAULT 15,
    is_overnight_shift BOOLEAN DEFAULT FALSE,         -- NEW
    break_duration_minutes INTEGER DEFAULT 0          -- NEW
);
```

### Column Purposes

| Column | Purpose | Example |
|--------|---------|---------|
| `is_overnight_shift` | Detect shifts crossing midnight | true if shift is 22:00-06:00 |
| `break_duration_minutes` | Minutes to deduct from worked hours | 30 for a 30-min lunch break |

---

## Status Report

### PostgreSQL Migration
- Migration ID: `e2d3a29b7890`
- Status: ✅ Applied successfully
- Test Results: 31/31 PASSED
- Data Impact: Low (schema extension only)
- Breaking Changes: None

### SQLite Migration
- Status: ✅ Applied successfully  
- Deployment: Windows app ready
- Backup: Automatic (bak_20260329_205923.db)
- Test Results: 31/31 PASSED
- Data Impact: Low (schema extension only)
- Breaking Changes: None

---

## Questions?

- **PostgreSQL/Alembic issues**: See `DATABASE_MIGRATIONS.md`
- **SQLite/standalone issues**: See `SQLITE_MIGRATIONS.md`
- **Schema questions**: Check `attendance/models/shift.py`
- **API/UI compatibility**: Confirmed in `ALIGNMENT_CHECK.md`, `CAMBIOS_REALIZADOS.md`

