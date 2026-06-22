# Contributing to pos

Thanks for your interest in improving pos!

## Ways to contribute

- **Report a bug** — open an issue with steps to reproduce.
- **Suggest a feature** — open an issue describing the use case.
- **Send a pull request** — for fixes and features (see below).

## Development setup

```sh
git clone https://github.com/glebis/pos
cd pos
uv sync
```

Run the tests before submitting:

```sh
uv run pytest -q
```

The Raycast extension under [`raycast/`](raycast/) is a separate Node package:

```sh
cd raycast && npm install
npm test        # unit tests
npm run lint    # Raycast lint (types + manifest)
```

## Pull requests

1. Fork and branch off `main`.
2. Keep changes focused; one logical change per PR.
3. Add or update tests for behaviour changes.
4. Ensure the test suite passes and the diff is clean.
5. Describe the *why* in the PR body, not just the *what*.

## Licensing of contributions

Unless you state otherwise in writing, contributions intentionally submitted for
inclusion are accepted under the project's [Apache-2.0](LICENSE) terms — except
contributions to `raycast/`, which is [MIT-licensed](raycast/LICENSE) to satisfy
the Raycast Store.

By contributing, you certify that you have the right to submit the work and that
it does not include code copied from unlicensed, source-available,
non-commercial, GPL, AGPL, LGPL, or otherwise incompatible sources.

AI-assisted contributions are allowed, but generated output must be reviewed as
source code, not pasted blindly. Do not submit generated code that matches public
code unless that public code has a compatible license and the required notices
are preserved. When a contribution is substantially AI-assisted, mention the tool
and the human review performed in the PR description.

## Code of conduct

This project follows the [Code of Conduct](CODE_OF_CONDUCT.md). By
participating, you are expected to uphold it.
