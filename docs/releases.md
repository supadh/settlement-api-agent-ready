# Release and rollback

Merges to `main` run Release Please. Conventional commit messages are grouped
into a release pull request that updates `CHANGELOG.md` and the version
manifest. Merging that pull request creates a GitHub release. Publishing the
release builds the service image and pushes immutable semantic-version tags to
GitHub Container Registry.

## Ownership

The Settlement API maintainers own release pull requests, container publishing,
and production rollout decisions. A maintainer verifies CI before merging a
release pull request.

## Roll forward

Prefer a corrective release:

1. Reproduce the defect against the released image.
2. Merge the smallest tested fix to `main`.
3. Merge the updated Release Please pull request.
4. Deploy the new immutable image tag.

## Roll back

If a corrective release cannot be produced safely, redeploy the last known-good
immutable GHCR tag. Do not overwrite or reuse published tags. Record the failed
version and rollback reason in the incident timeline.
