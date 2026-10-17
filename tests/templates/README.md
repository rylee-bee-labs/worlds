# Test Templates

Contributor guide for writing tests in this repository.

## Running tests

```bash
# All tests (fast, deterministic, 30s timeout)
uv run pytest --timeout=30

# One test file, verbose
uv run pytest tests/templates/test_capability_example.py -v

# One test function
uv run pytest tests/templates/test_capability_example.py::TestCapabilityHealth::test_healthy_returns_healthy -v
```

## Copying a template

1. Copy the template file you need (e.g. `test_capability_example.py`).
2. Replace the fixture values: swap fake providers, world state, and policy keys for your real ones.
3. Keep the `sys.path.insert` hack at the top — it's how tests find `src/personal_world` without install.
4. Run `uv run pytest --timeout=30` to confirm nothing broke.

## What each template protects

| Template | Invariant |
|---|---|
| `test_capability_example.py` | Status always reflects real provider evidence; stale/conflicting/missing data is surfaced honestly. |
| `test_authorization_example.py` | Cemented policies block non-user mutation; brain proposes, world decides. |
| `test_provider_adapter_example.py` | Providers fail closed; garbage input never corrupts world state. |
| `test_regression_example.py` | A specific bug stays fixed. |

## Fast tests vs integration tests

- **Fast tests** (these templates): deterministic, no real model, no network, no I/O. Use hand-rolled fakes. Run in <1s.
- **Integration tests**: hit real APIs, need `PW_API_TOKEN` or Ollama running. Mark with `@pytest.mark.integration` and skip in CI by default.

## Conventions

- `sys.path.insert(0, ...)` at the top of every test file.
- `pytest.fixture` for shared setup.
- Plain `assert` — no `unittest.mock`, no `assertEqual`.
- Hand-rolled fakes (see `fixtures.py`) — never import `unittest.mock`.
- Every test has a docstring naming the invariant it protects.
