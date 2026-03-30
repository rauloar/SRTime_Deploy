# Requirements Freeze - Version Snapshot

**Date**: 2026-03-29  
**Status**: Frozen at commit 6bdbb03  
**Total Packages**: 61

## Purpose

`requirements-frozen.txt` contains exact versions of all dependencies for reproducible deployments.

## Files

- **`requirements.txt`** - Development requirements (flexible versions for local development)
- **`requirements-frozen.txt`** - Production requirements (exact versions for deployments)

## Usage

### Development Installation
```bash
pip install -r requirements.txt
```

### Production Installation (Reproducible)
```bash
pip install -r requirements-frozen.txt
```

## What's in the Freeze

### Core Dependencies
- **FastAPI** 0.115.12 - Web framework
- **SQLAlchemy** 2.0+ - ORM
- **Alembic** 1.18.4 - Database migrations
- **psycopg2-binary** 2.9.11 - PostgreSQL driver
- **PySide6** 6.7+ - Desktop UI
- **pandas** 3.0.1 - Data processing

### Testing & Development
- **pytest** 9.0+ - Test framework
- **pytest-cov** - Coverage reporting
- **cryptography** 46.0.5 - Security

### See Full List
```bash
cat requirements-frozen.txt
```

## Regenerating the Freeze

When dependencies change, regenerate:

```bash
cd attendance
python -m pip freeze > requirements-frozen.txt

# Then commit
git add requirements-frozen.txt
git commit -m "chore: update frozen requirements"
git push
```

## Version Control

- Commit frozen requirements after major updates
- Keep versions in git history for rollback capability
- Compare versions across commits: `git diff <commit1> <commit2> -- requirements-frozen.txt`

## Installation Example

```bash
# Fresh installation with exact versions
git clone https://github.com/rauloar/SRTime_Deploy.git
cd SRTime_Deploy/attendance
pip install -r requirements-frozen.txt

# All packages installed with exact versions
# No compatibility issues or version conflicts
```

## Maintenance

Review and update frozen requirements:
- **Monthly**: Check for security updates
- **Quarterly**: Update dependencies to latest stable versions
- **As needed**: Address vulnerabilities or add new dependencies

---

**Next Step**: Commit and push this freeze snapshot to protect against dependency drift.
