# Database Migrations Guide

This guide explains how to manage database migrations for the SRTime project using Alembic.

---

## Quick Reference

### Create a New Migration
```bash
# After modifying SQLAlchemy models
alembic revision --autogenerate -m "Description of changes"
```

### Apply Migrations
```bash
# Apply all pending migrations
alembic upgrade head

# Apply up to a specific revision
alembic upgrade e2d3a29b7890
```

### Rollback Migrations
```bash
# Rollback one migration
alembic downgrade -1

# Rollback to a specific revision
alembic downgrade e2d3a29b7890^
```

### Check Status
```bash
# See current migration version
alembic current

# View all migration history
alembic history

# View migration details
alembic show e2d3a29b7890
```

---

## Workflow: Adding a New Model Column

### Step 1: Modify the SQLAlchemy Model
Edit the model file (e.g., `attendance/models/shift.py`):
```python
class Shift(Base):
    __tablename__ = "shifts"
    # ... existing columns ...
    new_column = Column(String(100), nullable=False, default="value")
```

### Step 2: Generate Migration
```bash
cd c:\Proyectos\SRTime
alembic revision --autogenerate -m "Add new_column to shifts table"
```

### Step 3: Review Generated Migration
Open the file in `alembic/versions/`:
- ✅ Check the `upgrade()` function has correct SQL
- ✅ Check the `downgrade()` function can reverse it
- ✅ Add `server_default` for existing row compatibility

```python
def upgrade():
    op.add_column('shifts', sa.Column('new_column', sa.String(100), 
                  nullable=False, server_default='value'))
```

### Step 4: Apply Migration
```bash
alembic upgrade head
```

### Step 5: Verify
```bash
python verify_migration.py
python -m pytest attendance\tests\ -v
```

---

## Best Practices

### ✅ DO

- **Always test locally first:** Create migration and test with `pytest`
- **Use descriptive messages:** `"Add X to Y table"` not `"update schema"`
- **Set appropriate constraints:** Use `nullable=False`, `server_default`, etc.
- **Keep migrations small:** One feature per migration
- **Verify backward compatibility:** Run existing tests after migration
- **Document manual steps:** Add comments if migration requires setup

### ❌ DON'T

- **Don't mix multiple features:** One migration = one logical change
- **Don't skip verification:** Always run tests after migration
- **Don't manually edit generated migrations:** Review → adjust → verify
- **Don't forget defaults:** Existing records need sensible defaults
- **Don't deploy without testing:** Test on development database first

---

## Common Scenarios

### Scenario 1: Add a Required Column to an Existing Table

Problem: Adding `NOT NULL` column to table with existing data

Solution:
```python
def upgrade():
    # Add nullable first
    op.add_column('table_name', sa.Column('new_col', sa.String()))
    # Set values for existing rows
    op.execute("UPDATE table_name SET new_col = 'default_value'")
    # Make NOT NULL
    op.alter_column('table_name', 'new_col', nullable=False)
```

### Scenario 2: Rename a Column

Problem: `birthday` → `date_of_birth`

Solution:
```python
def upgrade():
    op.alter_column('users', 'birthday', new_column_name='date_of_birth')

def downgrade():
    op.alter_column('users', 'date_of_birth', new_column_name='birthday')
```

### Scenario 3: Add Foreign Key Constraint

Problem: Need to link two tables

Solution:
```python
def upgrade():
    op.add_column('child_table', sa.Column('parent_id', sa.Integer(), nullable=False))
    op.create_foreign_key('fk_name', 'child_table', 'parent_table', 
                          ['parent_id'], ['id'])
```

### Scenario 4: Revert Changes

If a migration causes problems:
```bash
# See what's wrong
alembic history  # Find revision before the bad one
alembic downgrade bad_revision_id^
# Fix and regenerate if needed
alembic revision --autogenerate -m "Fix description"
alembic upgrade head
```

---

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Run Database Migrations
  run: |
    cd ${{ github.workspace }}/SRTime
    alembic upgrade head

- name: Run Tests
  run: |
    python -m pytest attendance/tests/ -v
```

---

## Troubleshooting

### Issue: Migration fails with "alembic_version table not found"
**Solution:** First migration creates this table automatically
```bash
alembic upgrade head  # Creates alembic_version table
```

### Issue: Autogenerate doesn't detect model changes
**Solution:** Ensure models are imported in `alembic/env.py`
```python
from models.shift import Shift  # Add missing import
```

### Issue: Need to manually adjust migration
**Solution:** Edit the file in `alembic/versions/`:
1. Stop at your migration step
2. Edit the migration file
3. Run `alembic upgrade head`
4. Test with pytest

### Issue: PostgreSQL vs SQLite differences
**Solution:** Alembic handles differences automatically. Use:
```python
# For multi-database compatibility
from sqlalchemy import text
op.execute(text("..."))  # Use SQLAlchemy text() for SQL
```

---

## Project-Specific Notes

### Database Configuration
Alembic reads from `attendance/core/database.py`:
- **Development:** SQLite (`attendance.db`)
- **Production:** PostgreSQL (via `.env` variables)

### ENV Variables Required
```
DB_ENGINE=postgres
DB_HOST=your_host
DB_PORT=5432
DB_USER=your_user
DB_PASS=your_password
DB_NAME=attendance
```

### Running Migrations Programmatically
```python
from alembic.config import Config
from alembic import command

cfg = Config("alembic.ini")
command.upgrade(cfg, "head")  # Apply all migrations
```

---

## Additional Resources

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/en/20/)
- [Project Database Schema](../attendance/core/database.py)

