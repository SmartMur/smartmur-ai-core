## Summary

<!-- What changed and why? Link to related issue(s) if applicable. -->

## Type

- [ ] `feat` -- new feature
- [ ] `fix` -- bug fix
- [ ] `chore` -- maintenance, dependency updates
- [ ] `docs` -- documentation only
- [ ] `refactor` -- code change that neither fixes a bug nor adds a feature
- [ ] `test` -- adding or updating tests

## Testing

<!-- What tests were added or run to verify this change? -->

```bash
PYTHONPATH=. .venv/bin/pytest tests/ --ignore=tests/test_telegram_concurrency.py -q
```

## Checklist

- [ ] Tests pass locally
- [ ] Linter passes (`ruff check .`)
- [ ] No `shell=True` in subprocess calls
- [ ] No bare `except:` clauses
- [ ] New public functions have type hints and docstrings
- [ ] Documentation updated (if applicable)
- [ ] No secrets committed
