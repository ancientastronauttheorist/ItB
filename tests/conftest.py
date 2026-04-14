"""Pytest configuration for ItB tests.

Registers the `regression` marker for slow full-corpus replay tests.
Run only fast unit tests: `pytest -m "not regression"`.
Run only regression tests:  `pytest -m regression`.
"""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "regression: slow full-corpus replay tests",
    )
