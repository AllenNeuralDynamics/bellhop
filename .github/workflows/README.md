# CI

| Workflow | Trigger | Purpose |
|---|---|---|
| `test_and_lint.yml` | PR to main, manual | Tests on Windows, Python 3.11-3.14 (lint currently disabled) |
| `check_version.yml` | PR to main | Reject versions whose stable form is already released |
| `bellhop_release.yml` | PR to main, push to main, manual | Tag + build + release entry point |
| `tag-build-release.yml` | reusable | Called by `bellhop_release.yml`; builds/tests the exe and attaches artifacts |
| `tag-release.yml` | reusable | Called by `tag-build-release.yml`; extracts version, tags, creates the release |

## On PR to main
- Run tests (Windows, Python 3.11-3.14)
- Check that the version's stable form has not already been released
  (blocks merge only if `check-version` is a required status check)
- If the version number is in a [prerelease format](https://packaging.python.org/en/latest/specifications/version-specifiers/#pre-releases)
  and not yet tagged:
  - Make a tag and a GitHub release (marked as prerelease)
  - Build the exe (`just build`), smoke-test it (`just test_exe`),
    zip each folder in `dist/` and attach to the release

## On merge of PR into main
- Only if the version is **stable** and not yet tagged:
  - Make a tag and GitHub release
  - Build artifacts and add to the release
- Merging while the version is still a prerelease tags/releases nothing

## Notes
- If the tag for the current version already exists, tagging and build jobs are
  skipped (not failed), so re-runs are no-ops until the version is bumped
- `test_and_lint` and the release pipeline can also be run manually
  (`workflow_dispatch`)
- The reusable workflows support building/deploying docs to GitHub Pages, but
  this repo disables it (`build_docs: false`); enabling it also requires
  granting `pages: write` and `id-token: write` in `bellhop_release.yml`
