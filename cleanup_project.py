#!/usr/bin/env python3
"""
PROJECT CLEANUP AUTOMATION SCRIPT

This script performs the safe cleanup of obsolete development files
and reorganizes the project structure as recommended in PROJECT_CLEANUP_AUDIT.md

PHASES:
  1. Delete obsolete scripts (safe - all in git history)
  2. Create new directory structure
  3. Move utility scripts to organized locations
  4. Archive old documentation
  5. Display summary and next steps
"""

import os
import shutil
import sys
from pathlib import Path
from datetime import datetime

# Color codes for terminal output
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

PROJECT_ROOT = Path(__file__).parent

# Files to delete (PHASE 1)
OBSOLETE_SCRIPTS_ATTENDANCE = [
    'add_default_shift.py',
    'debug_users.py',
    'emulate_edit.py',
    'test2.py',
    'test_ui.py',
    'update_db.py',
    'update_db2.py',
    'update_db3.py',
    'validate_code.py',
]

OBSOLETE_SCRIPTS_ROOT = [
    'setup_test_db.py',
]

# Files to move (PHASE 3)
SCRIPTS_TO_MOVE = [
    {
        'src': 'attendance/create_api_admin.py',
        'dst': 'scripts/database/create_admin_user.py',
        'desc': 'Create admin user utility',
    },
    {
        'src': 'attendance/setup_postgres.py',
        'dst': 'scripts/database/setup_postgres.py',
        'desc': 'PostgreSQL setup utility',
    },
    {
        'src': 'verify_migration.py',
        'dst': 'scripts/migration/verify_migration.py',
        'desc': 'Migration verification tool',
    },
]

# Documentation files to archive (PHASE 4)
DOCS_TO_ARCHIVE = [
    'ALIGNMENT_CHECK.md',
    'CAMBIOS_REALIZADOS.md',
    'FILES_CHANGED_SUMMARY.md',
    'MIGRATION_COMPLETE.md',
    'MIGRATION_LOG.md',
]

# Reference docs to consolidate (keep at root temporarily)
DOCS_TO_CONSOLIDATE = [
    'DATABASE_MIGRATIONS.md',
    'MIGRATIONS_QUICK_START.md',
    'MIGRATION_STRATEGY.md',
]

def print_header(text):
    """Print a formatted header."""
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}{BLUE}{text:^70}{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}\n")

def print_success(text):
    """Print success message."""
    print(f"{GREEN}✓{RESET} {text}")

def print_error(text):
    """Print error message."""
    print(f"{RED}✗{RESET} {text}")

def print_warning(text):
    """Print warning message."""
    print(f"{YELLOW}⚠{RESET} {text}")

def print_info(text):
    """Print info message."""
    print(f"{BLUE}ℹ{RESET} {text}")

def delete_obsolete_scripts(dry_run=True):
    """PHASE 1: Delete obsolete scripts."""
    print_header("PHASE 1: DELETING OBSOLETE SCRIPTS")
    
    deleted_count = 0
    
    # Delete from attendance/
    for script in OBSOLETE_SCRIPTS_ATTENDANCE:
        filepath = PROJECT_ROOT / 'attendance' / script
        if filepath.exists():
            if dry_run:
                print_info(f"[DRY RUN] Would delete: attendance/{script}")
            else:
                filepath.unlink()
                print_success(f"Deleted: attendance/{script}")
            deleted_count += 1
        else:
            print_warning(f"Not found: attendance/{script}")
    
    # Delete from root
    for script in OBSOLETE_SCRIPTS_ROOT:
        filepath = PROJECT_ROOT / script
        if filepath.exists():
            if dry_run:
                print_info(f"[DRY RUN] Would delete: {script}")
            else:
                filepath.unlink()
                print_success(f"Deleted: {script}")
            deleted_count += 1
        else:
            print_warning(f"Not found: {script}")
    
    return deleted_count

def create_new_structure(dry_run=True):
    """PHASE 2: Create new directory structure."""
    print_header("PHASE 2: CREATING NEW DIRECTORIES")
    
    directories = [
        'docs/archive',
        'scripts/database',
        'scripts/migration',
    ]
    
    created_count = 0
    
    for dir_path in directories:
        full_path = PROJECT_ROOT / dir_path
        if full_path.exists():
            print_warning(f"Already exists: {dir_path}/")
        else:
            if dry_run:
                print_info(f"[DRY RUN] Would create: {dir_path}/")
            else:
                full_path.mkdir(parents=True, exist_ok=True)
                print_success(f"Created: {dir_path}/")
            created_count += 1
    
    return created_count

def move_files(dry_run=True):
    """PHASE 3: Move utility scripts to organized locations."""
    print_header("PHASE 3: MOVING UTILITY SCRIPTS")
    
    moved_count = 0
    
    for move_info in SCRIPTS_TO_MOVE:
        src = PROJECT_ROOT / move_info['src']
        dst = PROJECT_ROOT / move_info['dst']
        desc = move_info['desc']
        
        if not src.exists():
            print_warning(f"Source not found: {move_info['src']}")
            continue
        
        if dst.exists():
            print_warning(f"Destination already exists: {move_info['dst']}")
            continue
        
        if dry_run:
            print_info(f"[DRY RUN] Would move: {move_info['src']} → {move_info['dst']}")
            print_info(f"         ({desc})")
        else:
            shutil.move(str(src), str(dst))
            print_success(f"Moved: {move_info['src']} → {move_info['dst']}")
            print_info(f"       ({desc})")
        
        moved_count += 1
    
    return moved_count

def archive_documentation(dry_run=True):
    """PHASE 4: Archive old documentation."""
    print_header("PHASE 4: ARCHIVING DOCUMENTATION")
    
    archived_count = 0
    
    for doc_file in DOCS_TO_ARCHIVE:
        src = PROJECT_ROOT / doc_file
        dst = PROJECT_ROOT / 'docs' / 'archive' / doc_file
        
        if not src.exists():
            print_warning(f"Not found: {doc_file}")
            continue
        
        if dst.parent.exists() is False:
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
        
        if dry_run:
            print_info(f"[DRY RUN] Would archive: {doc_file} → docs/archive/")
        else:
            shutil.move(str(src), str(dst))
            print_success(f"Archived: {doc_file}")
        
        archived_count += 1
    
    print_info(f"Reference docs to consolidate later: {', '.join(DOCS_TO_CONSOLIDATE)}")
    
    return archived_count

def create_cleanup_summary():
    """Create a summary file of changes made."""
    summary = f"""# PROJECT CLEANUP SUMMARY
    
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Script: cleanup_project.py

## Changes Made

### Files Deleted
- Deleted {len(OBSOLETE_SCRIPTS_ATTENDANCE)} obsolete scripts from attendance/
- Deleted {len(OBSOLETE_SCRIPTS_ROOT)} obsolete scripts from root

### Directories Created
- docs/archive/ - Archive for old documentation
- scripts/database/ - Database utility scripts
- scripts/migration/ - Migration utility scripts

### Files Moved
- create_api_admin.py → scripts/database/create_admin_user.py
- setup_postgres.py → scripts/database/setup_postgres.py
- verify_migration.py → scripts/migration/verify_migration.py

### Documentation Archived
{chr(10).join(f'- {doc}' for doc in DOCS_TO_ARCHIVE)}

### Documentation to Consolidate (Next Step)
{chr(10).join(f'- {doc}' for doc in DOCS_TO_CONSOLIDATE)}

## Verification Steps

1. Run tests to ensure nothing broke:
   python run_tests.py --quick

2. Verify app still runs:
   python attendance/main.py

3. Check git status:
   git status

4. Review changes:
   git diff --stat

5. Commit changes:
   git add -A
   git commit -m "chore: project cleanup & reorganization"

## Next Steps

1. Create docs/README.md with documentation index
2. Create scripts/README.md with utility scripts index
3. Add individual README.md files to scripts/database/ and scripts/migration/
4. Consolidate reference documentation in docs/
5. Update .gitignore if needed
6. Push to repository

"""
    return summary

def verify_git_status():
    """Check if git is initialized and show status."""
    print_header("GIT STATUS CHECK")
    
    git_dir = PROJECT_ROOT / '.git'
    if git_dir.exists():
        print_success("Git repository found")
        return True
    else:
        print_error("Git repository NOT found")
        print_warning("Consider initializing git: git init")
        return False

def show_summary(deleted, created, moved, archived, dry_run=True):
    """Display cleanup summary."""
    print_header("CLEANUP SUMMARY")
    
    if dry_run:
        print_warning("DRY RUN MODE - No files were actually modified")
        print()
    
    print(f"Scripts to delete:        {BOLD}{len(OBSOLETE_SCRIPTS_ATTENDANCE) + len(OBSOLETE_SCRIPTS_ROOT)}{RESET}")
    print(f"Directories to create:    {BOLD}{created}{RESET}")
    print(f"Scripts to move:          {BOLD}{len(SCRIPTS_TO_MOVE)}{RESET}")
    print(f"Documentation to archive: {BOLD}{len(DOCS_TO_ARCHIVE)}{RESET}")
    
    print()
    print(f"Total items to process:   {BOLD}{deleted + created + moved + archived}{RESET}")

def show_next_steps():
    """Display next steps."""
    print_header("NEXT STEPS")
    
    print("1. Review the cleanup plan in PROJECT_CLEANUP_AUDIT.md")
    print()
    print("2. Run cleanup in SIMULATION mode first:")
    print("   python cleanup_project.py --dry-run")
    print()
    print("3. Review the proposed changes")
    print()
    print("4. Run cleanup for real:")
    print("   python cleanup_project.py --execute")
    print()
    print("5. Verify everything works:")
    print("   python run_tests.py --quick")
    print()
    print("6. Commit changes:")
    print("   git add -A")
    print(f"   git commit -m 'chore: project cleanup & reorganization'")
    print()
    print("7. Read PROJECT_CLEANUP_AUDIT.md for detailed documentation")

def main():
    """Main cleanup orchestration."""
    print(f"\n{BOLD}{BLUE}")
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║          SRTime PROJECT CLEANUP AUTOMATION SCRIPT              ║")
    print("║                                                                ║")
    print("║  Safe reorganization of development utilities and docs         ║")
    print("║  All deleted files remain in git history for recovery          ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"{RESET}\n")
    
    # Parse arguments
    dry_run = '--execute' not in sys.argv
    
    if dry_run:
        print_warning("Running in DRY RUN mode (simulation only)")
        print_info("Use 'python cleanup_project.py --execute' to make actual changes")
        print()
    else:
        print_warning("Running in EXECUTE mode - actual files will be modified!")
        response = input(f"{YELLOW}Are you sure? Type 'yes' to continue: {RESET}")
        if response.lower() != 'yes':
            print_error("Cleanup cancelled")
            sys.exit(1)
        print()
    
    # Verify git first
    if not verify_git_status():
        print_error("Please initialize git before running cleanup")
        sys.exit(1)
    
    # Execute phases
    try:
        deleted = delete_obsolete_scripts(dry_run=dry_run)
        created = create_new_structure(dry_run=dry_run)
        moved = move_files(dry_run=dry_run)
        archived = archive_documentation(dry_run=dry_run)
        
        # Show summary
        show_summary(deleted, created, moved, archived, dry_run=dry_run)
        
        # Show next steps
        show_next_steps()
        
        if not dry_run:
            # Save cleanup summary
            summary_file = PROJECT_ROOT / 'CLEANUP_EXECUTED.md'
            with open(summary_file, 'w') as f:
                f.write(create_cleanup_summary())
            print_success(f"\nCleanup summary saved to: CLEANUP_EXECUTED.md")
        
        print()
        
    except Exception as e:
        print_error(f"Error during cleanup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
