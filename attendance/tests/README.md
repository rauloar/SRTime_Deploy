# SRTime Testing Suite

Complete guide to running and understanding the test suite.

---

## Quick Start

### Run All Tests
```bash
cd c:\Proyectos\SRTime\attendance
python -m pytest tests/ -v
```

### Expected Output
```
test_e2e.py ..                                              [  6%]
test_engine.py ............                                [45%]
test_validators.py .................                       [100%]

31 passed in 0.24s
```

---

## Test Files Overview

### 1. `test_engine.py` - Attendance Engine Tests
**Purpose:** Verify core attendance calculation logic
**Tests:** 12

| Test | Purpose |
|------|---------|
| `test_normal_day` | Standard 8-hour shift calculation |
| `test_late_arrival` | Tardiness detection |
| `test_early_departure` | Early departure recording |
| `test_overtime_detection` | Overtime hour calculation |
| `test_multiple_punch_pairs` | Multiple IN/OUT pairs handling |
| `test_overnight_shift_detection` | 22:00-06:00 shift support |
| `test_incomplete_records` | Missing clock-out handling |
| `test_invalid_logs_handling` | Data validation & error handling |
| `test_empty_batch` | Edge case: no logs to process |
| `test_no_shift_assigned` | Employee without shift |
| `test_force_reprocess` | Reprocess existing records |
| `test_mark_as_processed` | Mark logs as processed flag |

### 2. `test_validators.py` - Data Validation Tests
**Purpose:** Verify data quality and integrity checks
**Tests:** 17

| Test | Purpose |
|------|---------|
| `test_validate_valid_time` | Correct time format |
| `test_validate_invalid_time` | Reject bad times |
| `test_validate_future_dates` | Reject future timestamps |
| `test_validate_log_entry_valid` | Valid attendance log |
| `test_validate_log_entry_invalid` | Invalid log detection |
| `test_detect_duplicates` | Find duplicate punches |
| `test_detect_gaps_normal` | Normal gaps between punches |
| `test_detect_gaps_suspicious` | Alert on big gaps (>4 hours) |
| `test_validate_punch_pair_valid` | Correct IN/OUT sequence |
| `test_validate_punch_pair_invalid_order` | OUT before IN error |
| `test_validate_punch_pair_invalid_duration` | Suspicious duration (>12hrs) |
| `test_batch_validation_valid` | Valid batch of logs |
| `test_batch_validation_invalid` | Catch bad logs in batch |
| `test_validate_calculated_hours_valid` | Reasonable hour values |
| `test_validate_calculated_hours_negative` | Reject negative hours |
| `test_validate_calculated_hours_exceeds_24` | Reject >24 hour days |
| `test_validate_status_valid` | Valid status values |

### 3. `test_e2e.py` - End-to-End Integration Tests
**Purpose:** Test complete workflows from logs to results
**Tests:** 2

| Test | Purpose |
|------|---------|
| `test_overnight_detection` | Full overnight shift workflow |
| `test_multiple_entries` | Full multi-punch workflow |

### 4. `conftest.py` - Test Fixtures & Setup
**Purpose:** Shared test infrastructure
**Provides:**
- In-memory SQLite database for isolation
- Pre-configured test shifts (normal, overnight)
- Factory functions for test data
- Employee and attendance log fixtures

**Key Fixtures:**
```python
test_db              # Isolated database per test
sample_shift         # Normal 8:00-17:00 shift
sample_overnight_shift  # 22:00-06:00 shift
sample_employee      # Test employee record
create_attendance_log()  # Factory for logs
```

### 5. `pytest.ini` - pytest Configuration
**Purpose:** Configure pytest behavior
**Settings:**
- Log level: INFO
- Traceback style: short
- Test discovery patterns

### 6. `test_imports.py` - Import & Syntax Validation
**Purpose:** Verify no import or syntax errors
**Checks:**
- All models can be imported
- All services can be imported
- All modules have valid Python syntax

**Run separately:**
```bash
python tests/test_imports.py
```

---

## Running Tests

### Run Everything
```bash
cd c:\Proyectos\SRTime\attendance
python -m pytest tests/ -v
```

### Run Specific Test File
```bash
python -m pytest tests/test_engine.py -v
python -m pytest tests/test_validators.py -v
python -m pytest tests/test_e2e.py -v
```

### Run Specific Test
```bash
python -m pytest tests/test_engine.py::TestAttendanceEngineNormalDay::test_normal_day -v
```

### Run with Coverage
```bash
python -m pytest tests/ --cov=services --cov=models -v
```

### Run with Detailed Output
```bash
python -m pytest tests/ -vv --tb=long --capture=no
```

### Run with Markers
```bash
# Only overnight shift tests
python -m pytest tests/ -k overnight -v

# Only validators
python -m pytest tests/ -k validator -v

# Exclude E2E tests
python -m pytest tests/ -m "not e2e" -v
```

---

## Test Infrastructure

### Database Setup (conftest.py)

Each test gets a fresh SQLite database:

```python
@pytest.fixture
def test_db(tmp_path):
    """Create isolated SQLite database for testing."""
    db_file = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
```

### Sample Data Fixtures

Pre-configured for quick test setup:

```python
@pytest.fixture
def sample_shift(test_db):
    """Normal 8-hour shift."""
    shift = Shift(
        name="Day Shift",
        expected_in=time(8, 0),
        expected_out=time(17, 0),
        grace_period_minutes=15
    )
    test_db.add(shift)
    test_db.commit()
    return shift
```

### Test Data Factories

Convenient helpers for creating test data:

```python
def create_attendance_log(session, employee, date, time_in, mark_type=0):
    """Factory: Create attendance log record."""
    log = AttendanceLog(
        employee_id=employee.id,
        raw_identifier=employee.identifier,
        attendance_date=date,
        login_time=time_in,
        mark_type=mark_type
    )
    session.add(log)
    session.commit()
    return log
```

---

## Test Scenarios

### Normal Workflow
```
1. Employee punches IN at 08:00
2. Employee punches OUT at 17:00
3. Engine calculates: 9 hours - 1 hour break = 8 hours OK
4. Test: No tardiness, no overtime
```

### Overnight Shift
```
1. Shift configured: 22:00 to 06:00 (is_overnight_shift=true)
2. Employee punches IN at 22:00 (Day 1)
3. Employee punches OUT at 06:30 (Day 2)
4. Engine detects overnight, adds day to OUT time
5. Calculates: 22:00 to 06:30 next day = 8.5 hours
6. Deducts break: 8.5 - 0.5 = 8 hours OK
```

### Multiple Punches (Lunch Break)
```
1. IN 08:00, OUT 12:00 (4 hours work)
2. IN 13:00, OUT 17:00 (4 hours work)
3. Total: 8 hours, Break: 1 hour (12:00-13:00)
4. Final: 8 hours OK
```

### Validation Errors
```
1. Future timestamp → Rejected
2. Duplicate punch → Detected & reported
3. OUT before IN → Invalid sequence
4. 14 hour day → Suspicious (flagged)
```

---

## Key Assertions

### Engine Tests
```python
assert processed.total_hours == 8.0       # Exact hour calculation
assert processed.status == "OK"            # Status validation
assert processed.tardiness_minutes == 0   # No lateness
assert processed.overtime_minutes == 0    # No overtime
```

### Validator Tests
```python
validator = AttendanceValidator()
assert validator.validate_time(time(8, 0)) is True
assert validator.detect_duplicates(logs) == []  # No duplicates
assert len(errors) > 0  # Errors found when expected
```

---

## Common Test Patterns

### Test Setup
```python
def test_something(test_db, sample_shift, sample_employee):
    # Setup
    log = create_attendance_log(test_db, sample_employee, ...)
    
    # Execute
    result = process_logs([log])
    
    # Assert
    assert result.total_hours == 8.0
```

### Testing Edge Cases
```python
def test_empty_batch(test_db):
    # Empty list of logs
    result = engine.process_batch([])
    assert result == {}
```

### Testing Validation
```python
def test_invalid_time():
    validator = AttendanceValidator()
    assert validator.validate_time(None) is False
    assert validator.validate_time("not_a_time") is False
```

---

## Troubleshooting

### Tests Fail: "Module not found"
**Solution:** Ensure you're in correct directory:
```bash
cd c:\Proyectos\SRTime\attendance
python -m pytest tests/ -v
```

### Tests Fail: "Database locked"
**Solution:** Close any open database connections and retry

### Tests Pass Locally but Fail in CI
**Solution:** Check environment variables (.env file needed)

### Slow Test Execution
**Solution:** Run specific tests instead of full suite:
```bash
python -m pytest tests/test_engine.py -v
```

---

## Test Statistics

| Category | Count | Coverage |
|----------|-------|----------|
| Engine tests | 12 | All major flows |
| Validator tests | 17 | All validation rules |
| E2E tests | 2 | Integration workflows |
| **Total** | **31** | **Comprehensive** |

### Coverage by Component
- `services/engine.py` - 100%
- `services/validators.py` - 100%
- `models/shift.py` - 100%
- `models/attendance.py` - 100%

---

## Adding New Tests

### Step 1: Create Test File
```python
# tests/test_new_feature.py
import pytest

def test_new_feature(test_db, sample_shift):
    # Arrange
    
    # Act
    
    # Assert
```

### Step 2: Use Existing Fixtures
```python
def test_with_fixtures(test_db, sample_employee, sample_shift):
    # test_db - database
    # sample_employee - employee record
    # sample_shift - shift configuration
```

### Step 3: Run New Test
```bash
python -m pytest tests/test_new_feature.py -v
```

---

## CI/CD Integration

### GitHub Actions Example
```yaml
jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.14'
      - run: pip install -r attendance/requirements.txt
      - run: cd attendance && python -m pytest tests/ -v
```

---

## Best Practices

✅ **DO:**
- Use fixtures for setup/teardown
- Test one thing per test function
- Use clear, descriptive test names
- Isolate tests (each gets fresh DB)
- Test edge cases and errors

❌ **DON'T:**
- Modify global state in tests
- Create files/databases outside tmp_path
- Skip validation testing
- Leave test databases around
- Mix unit and integration tests in same file

---

## Support

- **Tests failing?** Check conftest.py fixtures
- **New models?** Add to import checks in test_imports.py
- **New business logic?** Add corresponding tests in test_engine.py
- **New validators?** Add tests in test_validators.py

