# Quick Start: Database Migrations

Choose your scenario and follow the steps.

---

## I Have... PostgreSQL (Company Server)

### Before Running New Code

**Step 1:** Connect to your PostgreSQL server (or ask your IT admin)

**Step 2:** Run this ONE command:
```bash
cd c:\Proyectos\SRTime
alembic upgrade head
```

**Step 3:** Verify:
```bash
alembic current
# Output should show: e2d3a29b7890 (head)
```

**Done!** Your database is updated with overnight shift support.

---

## I Have... Windows Standalone App (SRTime_Win.exe)

### Before Launching Updated App

**Step 1:** Open Command Prompt in the app directory

**Step 2:** Run this ONE command:
```bash
python migrate_legacy_sqlite.py
```

**Step 3:** See this output:
```
[OK] Backup created: attendance.bak_20260329_205923.db
[OK] Applied migrations:
 - shifts.is_overnight_shift
 - shifts.break_duration_minutes
[OK] Active login users: 1
[DONE] SQLite migration finished.
```

**Step 4:** Launch the app normally
```bash
python SRTime_Win.exe
# or click the shortcut
```

**Done!** Your app now supports overnight shifts.

---

## I'm Developing (Both Systems)

### Setup

```bash
# From project root
cd c:\Proyectos\SRTime

# 1. PostgreSQL (optional - if you have server)
alembic upgrade head

# 2. SQLite (for testing)
cd attendance
python migrate_sqlite.py

# 3. Run tests
python -m pytest tests/ -v
```

**Expected: 31/31 PASSED** ✅

---

## Database Now Supports

### Overnight Shifts
```sql
-- Example: Night shift 22:00 to 06:00
INSERT INTO shifts (name, expected_in, expected_out, is_overnight_shift) 
VALUES ('Night', '22:00', '06:00', true);
```

### Configurable Breaks  
```sql
-- Example: Hour lunch break
INSERT INTO shifts (name, expected_in, expected_out, break_duration_minutes) 
VALUES ('Day', '08:00', '17:00', 60);
```

---

## Couldn't Apply Migration?

### Error: "Database not found"
```
Solution: Ensure attendance.db is in the same folder as migrate_legacy_sqlite.py
```

### Error: "Permission denied"
```
Solution: Close other programs using the database and try again
```

### Error: "Column already exists"
```
Solution: Thisis normal - migration already applied. You're good to go!
```

### Need to Undo?
```bash
# SQLite: Restore backup
move attendance.db attendance.db.old
move attendance.bak_20260329_205923.db attendance.db

# PostgreSQL: Rollback
alembic downgrade -1
```

---

## Verify It Worked

### For PostgreSQL
```bash
python verify_migration.py
# Should show: [OK] Migration verification PASSED!
```

### For SQLite
```bash
python dist\SRTIime_Win\verify_sqlite_migration.py
# Should show: [OK] SQLite migration verification PASSED!
```

---

## That's It!

Your database is now ready for overnight shift handling. 

**Next:** Configure your shifts to use the new features!

