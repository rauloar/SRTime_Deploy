# SQLite Database Migrations for Standalone Windows App

This guide explains how to manage database migrations for the SRTime Windows app when running in **SQLite standalone mode**.

---

## Quick Start

### For End Users (Windows App Standalone)

If you have the **standalone Windows executable**, migrations are applied automatically:

1. **First Run:** The app automatically creates/updates the database on startup
2. **Updates:** When you update the app, run the migration script before launching:
   ```bash
   python migrate_legacy_sqlite.py
   ```
3. **Done:** Your database will be up-to-date with zero data loss

### For Developers

If you're developing with SQLite locally, use:

```bash
# From project root
python attendance/migrate_sqlite.py

# Or from attendance directory
cd attendance
python migrate_sqlite.py
```

---

## What's New in This Migration

### Changes to `shifts` Table

Two new columns added to support overnight shift handling:

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `is_overnight_shift` | BOOLEAN | 0 (false) | Mark shifts that cross midnight (e.g., 22:00-06:00) |
| `break_duration_minutes` | INTEGER | 0 | Configurable break time to deduct from calculated hours |

### Example Migrations Already Applied

The migration script has also handled:
- ✅ `auth_user.role` - User role (added long ago, preserved)
- ✅ `auth_user.must_change_password` - Password change enforcement
- ✅ `users.shift_id` - Link employee to shift
- ✅ `attendance_log.is_processed` - Mark logs as processed
- ✅ `processed_attendance` - Calculate attendance records

---

## Migration Process

### What The Migration Script Does

1. **Backup:** Creates timestamped backup before any changes
   ```
   attendance.bak_20260329_205923.db  ← Safe-keeping copy
   ```

2. **Schema Updates:** Adds missing columns if needed (idempotent)
   ```
   ALTER TABLE shifts ADD COLUMN is_overnight_shift BOOLEAN DEFAULT 0
   ALTER TABLE shifts ADD COLUMN break_duration_minutes INTEGER DEFAULT 0
   ```

3. **Data Safety:** Sets defaults for all existing records
   ```sql
   UPDATE shifts SET is_overnight_shift = 0 WHERE is_overnight_shift IS NULL
   UPDATE shifts SET break_duration_minutes = 0 WHERE break_duration_minutes IS NULL
   ```

4. **Validation:** Ensures system remains usable
   ```
   [OK] Active login users: 1
   ```

### Idempotent & Safe

- ✅ **Safe to run multiple times** - Second run does nothing (already migrated)
- ✅ **No data loss** - Existing data preserved, only schema extended
- ✅ **Rollback available** - Backup file created every run
- ✅ **Non-blocking** - App continues to work before/after migration

---

## Different Scenarios

### Scenario 1: Fresh Installation

```bash
# App will auto-create everything on first run
# No manual action needed!
```

### Scenario 2: Updating from Old Version

```bash
# Before running updated app
python migrate_legacy_sqlite.py

# Output
[OK] Backup created: attendance.bak_20260329_205923.db
[OK] Applied migrations:
  - shifts.is_overnight_shift
  - shifts.break_duration_minutes
[OK] Active login users: 1
[DONE] SQLite migration finished.

# Now launch the app - all features available!
```

### Scenario 3: Development/Testing

```bash
# After cloning repo
cd attendance
python migrate_sqlite.py

# Test suite
python -m pytest tests/ -v
```

### Scenario 4: Troubleshooting

If something goes wrong:

```bash
# Restore from backup
rm attendance.db
mv attendance.bak_20260329_205923.db attendance.db

# Try again
python migrate_legacy_sqlite.py
```

---

## File Locations

### For Standalone App (Windows EXE)
```
SRTime_Win/
  ├── SRTime_Win.exe              ← Run this
  ├── attend ance.db              ← Local database
  ├── migrate_legacy_sqlite.py     ← Run this before updating app
  └── verify_sqlite_migration.py   ← Run this to verify
```

### For Development
```
SRTime/
  ├── attendance/
  │   ├── migrate_sqlite.py        ← Generic migration script
  │   ├── core/database.py         ← DB configuration
  │   └── models/shift.py          ← Shift model with new columns
  └── MIGRATION_LOG.md             ← PostgreSQL migration docs
  └── DATABASE_MIGRATIONS.md       ← PostgreSQL/Alembic guide
```

---

## Command Reference

### Check Current Schema

```bash
# View shifts table structure
python -c "import sqlite3; c = sqlite3.connect('attendance.db'); c.execute('PRAGMA table_info(shifts)'); print([row for row in c.fetchall()])"

# Quick check with verification script
python verify_sqlite_migration.py
```

### Backup & Restore

```bash
# Backup
copy attendance.db attendance.bak_manual.db

# Restore
copy attendance.bak_manual.db attendance.db
```

### Manual Column Addition (if needed)

```sql
-- If you want to manually add columns
ALTER TABLE shifts ADD COLUMN is_overnight_shift BOOLEAN DEFAULT 0;
ALTER TABLE shifts ADD COLUMN break_duration_minutes INTEGER DEFAULT 0;
```

---

## PostgreSQL vs SQLite

### PostgreSQL (Company Network)
- Use: `alembic upgrade head`
- Location: Server-hosted database
- Managed: IT/DevOps team
- Docs: See `DATABASE_MIGRATIONS.md` and `MIGRATION_LOG.md`

### SQLite (Standalone Windows App)
- Use: `python migrate_legacy_sqlite.py`
- Location: `attendance.db` in app directory
- Managed: Individual users/app deployment
- Docs: This file

---

## Verification

### Post-Migration Checklist

After running migration, verify everything works:

```bash
# 1. Check migrations applied
python verify_sqlite_migration.py
# Output: [OK] SQLite migration verification PASSED!

# 2. Launch app (if automated startup available)
# Should connect to database without errors

# 3. Run tests (if developer)
python -m pytest attendance\tests\ -v
# Should see: 31 PASSED
```

---

## Troubleshooting

### Q: "Database not found" error
**A:** Ensure `attendance.db` exists in the same directory as the script. Run app once to auto-create it.

### Q: Migration hangs or seems stuck
**A:** Check file permissions. Database might be locked by other process. Close any open connections and retry.

### Q: "is_overnight_shift" column not showing up
**A:** Run verification: `python verify_sqlite_migration.py`
If still missing, delete backup and retry: `python migrate_legacy_sqlite.py`

### Q: Lost data during migration
**A:** Restore from backup: `move attendance.bak_YYYYMMDD_HHMMSS.db attendance.db`
All backups are timestamped and preserved.

---

## For App Developers

### Adding New Migrations

1. **Modify SQLAlchemy model** in `attendance/models/shift.py`
2. **Add migration code** to `migrate_sqlite.py` function
3. **Update** `dist/SRTIime_Win/migrate_legacy_sqlite.py` similarly
4. **Test locally:** `python migrate_sqlite.py`
5. **Document** in this file

---

## Additional Resources

- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [Python sqlite3 module](https://docs.python.org/3/library/sqlite3.html)

