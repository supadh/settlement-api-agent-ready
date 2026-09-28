# Automated Droid review

`.github/workflows/droid-review.yml` runs Factory Droid when a non-draft pull
request is opened, reopened, or marked ready for review. The workflow grants
only the repository permissions required to read changes and publish review
feedback.

## Repository setup

1. Install the Factory Droid GitHub App for this repository.
2. Generate an API key at <https://app.factory.ai/settings/api-keys>.
3. Add it as the repository Actions secret `FACTORY_API_KEY`.
4. Open a non-draft pull request and confirm the **Droid Auto Review** workflow
   posts review content on the pull request.

The workflow references `${{ secrets.FACTORY_API_KEY }}` and must never contain
an actual API key. Review guidance belongs in repository-owned agent
instructions and skills so review behavior changes through normal code review.

## Failure handling

- If authentication fails, confirm the GitHub App can access this repository
  and rotate the API key if necessary.
- If the workflow cannot comment, check its pull-request and issue permissions.
- Keep the pull request open while retrying a failed workflow so the eventual
  review remains attached to the correct change.
