# Dependency policy

Runtime and development dependencies are pinned to exact versions. Dependabot
checks Python, GitHub Actions, and container dependencies every Monday. It must
wait at least seven days after a package release before opening a normal
grouped pull request. Security updates may be prioritized separately after
human review.

Dependency pull requests must pass CI, preserve coverage, and explain any
security or compatibility impact. Never bypass the release-age gate by manually
editing a version unless an active vulnerability or incident is documented.

Generated files, virtual environments, caches, secrets, editor settings, and
build artifacts are excluded by `.gitignore`. `.env.example` remains tracked
because it contains safe defaults rather than credentials. CI validates both
the ignore behavior and Dependabot cooldown.
