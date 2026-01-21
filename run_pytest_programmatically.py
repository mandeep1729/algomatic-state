
import pytest
import sys
import os

sys.path.append(os.getcwd())

test_files = [
    "tests/unit/features/test_returns.py",
    "tests/unit/features/test_volatility.py",
    "tests/unit/features/test_volume.py",
    "tests/unit/features/test_anchor.py",
    "tests/unit/features/test_time_of_day.py",
    "tests/unit/features/test_market_context.py",
    "tests/unit/features/test_registry.py",
    "tests/unit/features/test_pipeline.py",
    "tests/unit/features/test_intrabar.py"
]

failed_files = []

for f in test_files:
    print(f"Running {f}...")
    # -q for quiet
    retcode = pytest.main(["-v", "-q", f])
    if retcode != 0:
        print(f"FAIL: {f}")
        failed_files.append(f)
    else:
        print(f"PASS: {f}")

if failed_files:
    print(f"Failed files: {failed_files}")
    sys.exit(1)

print("All files passed!")
sys.exit(0)
