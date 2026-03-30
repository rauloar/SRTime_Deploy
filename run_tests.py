#!/usr/bin/env python3
"""
Comprehensive Test Suite Runner for SRTime Attendance System.

This script runs all tests with various options and provides
a clean report of test results.

Usage:
    python run_tests.py                 # Run all tests with summary
    python run_tests.py --verbose       # Verbose output
    python run_tests.py --coverage      # Include coverage report
    python run_tests.py --quick         # Run fast tests only
    python run_tests.py --imports       # Validate imports only
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

# Add attendance to path
ATTENDANCE_DIR = Path(__file__).resolve().parent / "attendance"
TESTS_DIR = ATTENDANCE_DIR / "tests"


def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def run_command(cmd, description=""):
    """Run a command and return exit code."""
    if description:
        print(f"[INFO] {description}")
        print(f"[CMD]  {' '.join(cmd)}\n")
    
    result = subprocess.run(cmd, cwd=ATTENDANCE_DIR)
    return result.returncode


def validate_imports():
    """Run import validation tests."""
    print_header("IMPORT & SYNTAX VALIDATION")
    
    cmd = [sys.executable, str(TESTS_DIR / "test_imports.py")]
    return run_command(cmd, "Validating module imports and syntax")


def run_all_tests(verbose=False, coverage=False, quick=False):
    """Run full test suite."""
    print_header("RUNNING TEST SUITE")
    
    cmd = [sys.executable, "-m", "pytest", "tests/", "-v"]
    
    if quick:
        cmd.append("-m")
        cmd.append("not e2e")
        description = "Running quick tests (excluding E2E)"
    else:
        description = "Running full test suite"
    
    if verbose:
        cmd.append("-vv")
        cmd.append("--tb=long")
    else:
        cmd.append("-q")
        cmd.append("--tb=line")
    
    if coverage:
        cmd.extend([
            "--cov=services",
            "--cov=models", 
            "--cov-report=term-missing",
            "--cov-report=html"
        ])
    
    return run_command(cmd, description)


def run_specific_tests(test_pattern):
    """Run tests matching pattern."""
    print_header(f"RUNNING TESTS: {test_pattern}")
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/", "-v", "-k", test_pattern
    ]
    
    return run_command(cmd, f"Running tests matching: {test_pattern}")


def print_test_summary():
    """Print summary of test files."""
    print_header("TEST SUITE SUMMARY")
    
    print("Test Files:")
    print("  - test_engine.py ..................... 12 tests (engine logic)")
    print("  - test_validators.py ................ 17 tests (data validation)")
    print("  - test_e2e.py ....................... 2 tests (integration)")
    print("  - test_imports.py ................... Import/syntax checks")
    print()
    print("Support Files:")
    print("  - conftest.py ....................... Fixtures & setup")
    print("  - pytest.ini ........................ Test configuration")
    print()
    print("Total: 31 unit/integration tests + import validation")
    print()
    print("Fixtures Available:")
    print("  - test_db ........................... Isolated SQLite database")
    print("  - sample_shift ..................... Normal 8:00-17:00 shift")
    print("  - sample_overnight_shift .......... 22:00-06:00 shift")
    print("  - sample_employee .................. Test employee record")
    print("  - create_attendance_log() ......... Factory for test logs")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run SRTime test suite with various options"
    )
    
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")
    parser.add_argument("--coverage", "-c", action="store_true",
                        help="Include coverage report")
    parser.add_argument("--quick", "-q", action="store_true",
                        help="Run only quick tests (exclude E2E)")
    parser.add_argument("--imports", "-i", action="store_true",
                        help="Validate imports only")
    parser.add_argument("--pattern", "-p", type=str,
                        help="Run tests matching pattern (e.g., overnight)")
    parser.add_argument("--summary", "-s", action="store_true",
                        help="Show test summary and exit")
    
    args = parser.parse_args()
    
    # Verify test directory exists
    if not TESTS_DIR.exists():
        print(f"[ERROR] Tests directory not found: {TESTS_DIR}")
        sys.exit(1)
    
    print()
    print("SRTime Attendance System - Test Suite Runner")
    print("=" * 70)
    
    exit_code = 0
    
    # Show summary if requested
    if args.summary:
        print_test_summary()
        return 0
    
    # Import validation
    import_code = validate_imports()
    if import_code != 0:
        print("\n[ERROR] Import validation failed!")
        sys.exit(1)
    
    # If imports-only requested, stop here
    if args.imports:
        return 0
    
    # Run tests with requested options
    if args.pattern:
        exit_code = run_specific_tests(args.pattern)
    else:
        exit_code = run_all_tests(
            verbose=args.verbose,
            coverage=args.coverage,
            quick=args.quick
        )
    
    # Final summary
    print_header("TEST RUN COMPLETE")
    
    if exit_code == 0:
        print("[OK] All tests passed!")
        if args.coverage:
            print("[OK] Coverage report generated: htmlcov/index.html")
    else:
        print("[ERROR] Some tests failed!")
    
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[INFO] Test run interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
