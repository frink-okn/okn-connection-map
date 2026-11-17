# Contributing

Thank you for helping. Issues and pull requests are welcome, from code to wording.

- **Report a wrong answer:** open an issue with the two graph names, the output of `ocm paths A B --json`, and what you expected. Wrong "connect" answers are as important to us as missed ones.
- **Add an identifier type:** see [docs/08_architecture.md](docs/08_architecture.md#adding-an-identifier-type). Every new rule needs a test, including a look-alike that must be rejected.
- **Code style:** Python 3.9+, standard library only, read-only toward every service. Keep messages plain, so non-programmers can understand them.
- **Before a pull request:** `python -m unittest discover -s tests` must pass.
- **Be gentle on the federation:** use `--only` for experiments, and keep `--sleep` at 0.5 seconds or more.
