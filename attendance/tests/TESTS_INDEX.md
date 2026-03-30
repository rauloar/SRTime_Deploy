# Test Suite - Quick Index

Complete reference to all testing in SRTime project.

---

## Directory Structure

```
c:\Proyectos\SRTime\
├── run_tests.py ........................ Test suite runner (root)
└── attendance\tests\
    ├── README.md ....................... Complete testing guide
    ├── __init__.py ..................... Package marker
    ├── conftest.py ..................... Fixtures & setup
    ├── pytest.ini ...................... Configuration
    ├── test_imports.py ................. Import validation
    ├── test_engine.py .................. Engine logic tests (12)
    ├── test_validators.py .............. Validation tests (17)
    └── test_e2e.py ..................... Integration tests (2)
```

---

## Running Tests

### From Project Root
```bash
# All tests
python run_tests.py

# Specific options
python run_tests.py --verbose      # Detailed output
python run_tests.py --coverage     # Include coverage
python run_tests.py --quick        # Skip E2E tests
python run_tests.py --imports      # Only import checks
python run_tests.py --pattern overnight  # Pattern match
python run_tests.py --summary      # Show test summary
```

### From attendance Directory
```bash
cd attendance

# All tests
python -m pytest tests/ -v

# Specific test file
python -m pytest tests/test_engine.py -v
python -m pytest tests/test_validators.py -v
python -m pytest tests/test_e2e.py -v

# With coverage
python -m pytest tests/ --cov=services --cov=models -v

# Pattern matching
python -m pytest tests/ -k overnight -v
python -m pytest tests/ -k validator -v
```

### Run Validation Only
```bash
cd attendance
python tests/test_imports.py
```

---

## Test Files At-a-Glance

### test_engine.py (12 Tests)
Tests the core attendance calculation engine.

```
✅ test_normal_day ........................ 8-hour shift
✅ test_late_arrival ..................... Tardiness detection
✅ test_early_departure .................. Early leave
✅ test_overtime_detection ............... Overtime calc
✅ test_multiple_punch_pairs ............. Multiple IN/OUT
✅ test_overnight_shift_detection ........ 22:00-06:00 shifts
✅ test_incomplete_records ............... Missing clock-out
✅ test_invalid_logs_handling ............ Error handling
✅ test_empty_batch ...................... Edge case: no logs
✅ test_no_shift_assigned ................ No shift configured
✅ test_force_reprocess .................. Reprocess records
✅ test_mark_as_processed ................ Set processed flag
```

### test_validators.py (17 Tests)
Tests data validation and quality checks.

```
✅ test_validate_valid_time .............. Valid time format
✅ test_validate_invalid_time ............ Invalid time
✅ test_validate_future_dates ............ Reject future
✅ test_validate_log_entry_valid ......... Valid log
✅ test_validate_log_entry_invalid ....... Invalid log
✅ test_detect_duplicates ................ Find duplicates
✅ test_detect_gaps_normal ............... Normal gaps
✅ test_detect_gaps_suspicious ........... Suspicious gaps
✅ test_validate_punch_pair_valid ........ Valid IN/OUT
✅ test_validate_punch_pair_invalid_order  OUT before IN
✅ test_validate_punch_pair_invalid_duration  Too long
✅ test_batch_validation_valid ........... Valid batch
✅ test_batch_validation_invalid ......... Invalid batch
✅ test_validate_calculated_hours_valid .. Reasonable hours
✅ test_validate_calculated_hours_negative  Reject negative
✅ test_validate_calculated_hours_exceeds_24  Reject >24h
✅ test_validate_status_valid ............ Valid status
```

### test_e2e.py (2 Tests)
Full end-to-end integration workflows.

```
✅ test_overnight_detection ............. Overnight shift workflow
✅ test_multiple_entries ................ Multi-punch workflow
```

---

## Test Fixtures

Available in `conftest.py` for all tests:

### Database Fixture
```python
@pytest.fixture
def test_db():
    """Fresh SQLite database for each test."""
    # Automatically provides isolated DB
```

### Employee Fixtures
```python
@pytest.fixture
def sample_employee(test_db):
    """Normal employee (8:00-17:00)."""
    return employee_with_shift(test_db, sample_shift)

@pytest.fixture  
def sample_employee_night(test_db):
    """Night shift employee (22:00-06:00)."""
    return employee_with_shift(test_db, sample_overnight_shift)
```

### Shift Fixtures
```python
@pytest.fixture
def sample_shift(test_db):
    """Standard day shift: 08:00-17:00."""
    return Shift(name="Day", expected_in=time(8,0), expected_out=time(17,0))

@pytest.fixture
def sample_overnight_shift(test_db):
    """Night shift: 22:00-06:00."""
    return Shift(name="Night", expected_in=time(22,0), expected_out=time(6,0))
```

### Data Fixtures
```python
@pytest.fixture
def logs_normal_day(test_db):
    """Normal 8-hour day: 08:00 IN -> 17:00 OUT."""
    
@pytest.fixture
def logs_overnight(test_db):
    """Overnight shift: 22:00 IN -> 06:30 OUT."""
    
@pytest.fixture
def logs_multiple_entries(test_db):
    """Multiple IN/OUT: lunch break scenario."""
```

### Factory Function
```python
def create_attendance_log(session, employee, date, time_in, 
                          mark_type=0):
    """Create test attendance log."""
    # Helper to create custom logs
```

---

## Test Results Expected

### Full Suite
```
test_e2e.py ..                                          [  6%]
test_engine.py ............                             [ 45%]
test_validators.py .................                    [100%]

======================== 31 passed in 0.24s ========================
```

### With Coverage
```
services/engine.py .................... 100%
services/validators.py ................ 100%
models/shift.py ....................... 100%
models/attendance.py .................. 100%

======================== 31 passed, 95% coverage ==================
```

---

## Common Quick Commands

### Run Single Test
```bash
cd attendance
python -m pytest tests/test_engine.py::TestAttendanceEngineNormalDay::test_normal_day -v
```

### Run All Overnight Tests
```bash
cd attendance
python -m pytest tests/ -k overnight -v
```

### Run All Validator Tests
```bash
cd attendance
python -m pytest tests/ -k validator -v
```

### Validate Imports
```bash
cd attendance
python tests/test_imports.py
```

### Full Report
```bash
python run_tests.py --verbose --coverage
```

---

## Test Organization by Component

### Engine Tests
- Location: `tests/test_engine.py`
- File: `services/engine.py`
- Scenarios: Normal, overnight, multiple punches, errors
- Count: 12 tests

### Validator Tests
- Location: `tests/test_validators.py`
- File: `services/validators.py`
- Scenarios: Valid inputs, invalid inputs, edges, batches
- Count: 17 tests

### Integration Tests
- Location: `tests/test_e2e.py`
- Tests: Multiple components together
- Scenarios: Complete workflows
- Count: 2 tests

### Import Validation
- Location: `tests/test_imports.py`
- Checks: All modules importable
- Verifies: No syntax errors
- Standalone script

---

## Adding New Tests

### 1. Create Test Function
```python
# In appropriate test file
def test_new_feature(test_db, sample_shift):
    """Test description."""
    # Arrange - setup
    # Act - execute
    # Assert - verify
```

### 2. Use Fixtures
```python
def test_something(test_db, sample_employee, sample_shift):
    # Access fixtures directly
```

### 3. Run Test
```bash
python -m pytest tests/test_file.py::test_new_feature -v
```

---

## Troubleshooting

### Tests won't run
```bash
# Ensure you're in attendance directory
cd c:\Proyectos\SRTime\attendance
python -m pytest tests/ -v
```

### Import errors
```bash
# Run validation first
python tests/test_imports.py

# Check sys.path includes attendance root
python -c "import sys; print('\\n'.join(sys.path))"
```

### Database locked
```bash
# Close other connections
# Restart terminal
# Try again
```

### Slow tests
```bash
# Run quick tests only
python run_tests.py --quick

# Run specific test
python -m pytest tests/test_engine.py::TestAttendanceEngineNormalDay::test_normal_day -v
```

---

## Files Modified in Tests

### New Files
- ✅ `tests/test_imports.py` - Import validation script
- ✅ `tests/README.md` - Complete testing guide
- ✅ `run_tests.py` - Root level test runner

### Updated Files
- ✅ `conftest.py` - Fixtures (already complete)
- ✅ `pytest.ini` - Config (already complete)
- ✅ `test_engine.py` - Tests (already complete)
- ✅ `test_validators.py` - Tests (already complete)
- ✅ `test_e2e.py` - Tests (already complete)

---

## Next Steps

1. **Quick Start**: `python run_tests.py`
2. **Read Details**: `attendance/tests/README.md`
3. **Explore Code**: Check individual test files
4. **Run Coverage**: `python run_tests.py --coverage`
5. **Add Tests**: Follow "Adding New Tests" section

---

## Support

- **General questions**: See `tests/README.md`
- **Test patterns**: Check existing test files
- **Fixtures list**: See `conftest.py`
- **Commands**: Run `python run_tests.py --help`

