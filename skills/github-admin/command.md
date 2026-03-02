# GitHub Admin

GitHub administration tool. Manage authentication, branch protection, and repo audits across all repos.

## Usage

```
/github-admin auth      Check authentication status
/github-admin login     Authenticate with GitHub (device flow)
/github-admin protect   Enable branch protection on all repos
/github-admin audit     Audit branch protection status
/github-admin repos     List all repos
```

## Subcommands

### `auth`
Checks whether `gh` is authenticated. If not, prints instructions.

### `login`
Starts the GitHub device-flow authentication. A code and URL are printed — open the URL in a browser and enter the code to authenticate.

### `protect`
Enables branch protection on the default branch of every repo with sensible defaults:
- Enforce admins
- Require 1 approving review (dismiss stale reviews)
- Disallow force pushes and branch deletions

### `audit`
Scans all repos and reports which default branches are protected and which are not.

### `repos`
Lists all repos for the configured owner with default branch, visibility, and fork status.

## Exit Codes

- 0: success (all repos protected / authenticated / etc.)
- 1: issues found (unprotected repos, failed protections, not authenticated)
- 2: execution error
