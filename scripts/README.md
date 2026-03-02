# Scripts

Development and CI helper scripts. Run from the repository root, for example:

```bash
python scripts/check_setup.py
python scripts/run_all_examples.py
OPTIMIZATION_SANDBOX_POOLING=true python scripts/benchmark_pooling.py -n 5
```

- **check_setup.py** — Verify required packages for examples.
- **run_all_examples.py** / **run_all_examples.sh** — Run the example suite.
- **run_all_tests.sh**, **run_live_tests.sh** — Test runners.
- **run_monty_verification.py** — Monty runtime verification.
- **run_test_with_logging.py**, **run_tests_and_save.py** — Test runs with logging or saved output.
- **benchmark_pooling.py** — Sandbox pooling benchmarks.
- **verify_examples.py** — Example verification.
- **debug_trial.sh** — Debug helper.

The canonical test suite is `pytest tests/`; see CONTRIBUTING.md.
