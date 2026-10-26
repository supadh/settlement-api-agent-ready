Implement the Linear ticket at the bottom of this prompt in this repository.

- Follow `AGENTS.md` for setup, conventions, and validation. Dependencies from
  `requirements-dev.txt` are already installed.
- Make the smallest change that satisfies every acceptance criterion. Add tests
  for new behavior, including the failure cases.
- If routes or request models change, regenerate the schema with
  `python scripts/generate_openapi.py`.
- Run `python -m pytest tests` and `pre-commit run --all-files`, and fix any
  failures before you finish.
- Commit your work on the current branch with a conventional commit message
  that ends with the ticket identifier, for example
  `feat: add partial refund endpoint (MER-12)`. Do not push, create branches,
  or open a pull request; the workflow does that.
- Finish with a short summary: what changed, how you verified it, and anything
  left open. That summary becomes the pull request description.

---

