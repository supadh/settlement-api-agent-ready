# Security policy and repository controls

## Reporting

Do not open a public issue for a suspected vulnerability or exposed secret.
Contact the repository owner privately with the affected version, impact, and
reproduction steps. Never include live card data, tokens, or credentials.

## Required change path

All changes should use a pull request. The owner in `.github/CODEOWNERS` reviews
application, workflow, dependency, and security changes. CI, Security, and Droid
Auto Review must pass before merge. Direct pushes to `main` are prohibited by
team policy.

GitHub branch-protection APIs return `403` for this private repository on its
current plan. Because the platform cannot enforce the policy, maintainers must
not merge or push around the required checks. Enabling GitHub Pro or making the
repository public would allow these rules to become server-enforced.

## Automated controls

The Security workflow runs on pull requests, pushes to `main`, weekly, and on
demand:

- Gitleaks scans full Git history and redacts findings.
- pip-audit checks runtime dependencies against vulnerability advisories.
- Bandit performs Python security analysis.
- OWASP ZAP scans a live instance using the committed OpenAPI contract.

JSON security reports and the ZAP report are retained as workflow artifacts.
Verified findings block the workflow and must be fixed or documented with a
specific risk acceptance. Dependabot proposes grouped, cooldown-protected
updates that receive the same review and checks as other pull requests.

## Temporary dependency advisories

As of 2026-09-28, the package index does not publish a FastAPI version that
permits the fixed Starlette releases, or compatible releases for the other
transitive findings below. CI uses exact, reviewable advisory exceptions rather
than disabling dependency auditing:

- Requests: `PYSEC-2026-2275`
- Starlette: `PYSEC-2026-161`, `PYSEC-2026-249`, `PYSEC-2026-248`,
  `PYSEC-2026-2281`, `PYSEC-2026-2280`
- AnyIO: `GHSA-82r6-8w77-94w6`, `GHSA-5p39-cfhj-2xmp`
- urllib3: `PYSEC-2026-142`, `PYSEC-2026-141`
- Click: `PYSEC-2026-2132`

The service does not call the affected archive extraction, static file,
`HTTPEndpoint`, process pool, IDN TLS, low-level proxy, or `click.edit`
interfaces. Review and remove these exceptions as soon as compatible patched
versions are available.
