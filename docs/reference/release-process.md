# Release Process

This document describes how to prepare, tag, verify, and rollback releases for Claude Superpowers.

## Version Numbering

We follow [Semantic Versioning](https://semver.org/) (semver):

- **MAJOR** (`X.0.0`) -- breaking changes (removed CLI commands, changed config keys, removed APIs)
- **MINOR** (`0.X.0`) -- new features, backward-compatible additions
- **PATCH** (`0.0.X`) -- bug fixes, documentation updates, internal refactoring

Pre-release versions use a hyphen suffix: `1.0.0-alpha.1`, `1.0.0-rc.1`.

## Preparing a Release

1. **Update the version** in `pyproject.toml` and `superpowers/__init__.py`:

   ```
   # pyproject.toml
   version = "1.2.0"

   # superpowers/__init__.py
   __version__ = "1.2.0"
   ```

2. **Run the prepare command** to validate everything:

   ```bash
   claw release prepare 1.2.0
   ```

   This checks:
   - Version is valid semver
   - Git working tree is clean (no uncommitted changes)
   - `pyproject.toml` version matches the target version
   - Generates a changelog from git log since the last tag

3. **Review the changelog** output and update `CHANGELOG.md` if needed.

4. **Commit the version bump**:

   ```bash
   git add pyproject.toml superpowers/__init__.py CHANGELOG.md
   git commit -m "chore: bump version to 1.2.0"
   ```

## Creating a Release Tag

```bash
claw release tag 1.2.0
# Or with a custom message:
claw release tag 1.2.0 -m "Release with new browser engine"
```

This creates an annotated git tag `v1.2.0`.

To push the tag to remote:

```bash
git push origin v1.2.0
```

## Verifying a Release

After tagging, verify everything is consistent:

```bash
claw release verify 1.2.0
```

This checks:
- Tag `v1.2.0` exists locally
- `pyproject.toml` version matches `1.2.0`

## Viewing the Changelog

```bash
# Changelog since last tag
claw release changelog

# Changelog between specific refs
claw release changelog --from-tag v1.0.0 --to-ref v1.2.0
```

## Changelog Format

Changelogs are generated from conventional commit messages, grouped by type:

```
### Features
- add widget support
- implement dark mode

### Bug Fixes
- fix null pointer in config loader

### Chores
- update dependencies
```

Commit types recognized: `feat`, `fix`, `chore`, `docs`, `ci`, `refactor`, `test`, `perf`, `style`.

## Migration Checking

When upgrading between versions, check for breaking changes:

```bash
claw release migrate 0.1.0 0.2.0
```

This scans git diffs for:
- Removed or renamed CLI commands
- Changed configuration keys
- Removed public Python APIs

It outputs a Markdown migration guide with specific steps.

## Rollback Procedure

If a release needs to be reverted:

1. **Delete the local tag**:

   ```bash
   claw release rollback 1.2.0
   ```

2. **If the tag was pushed**, also delete the remote tag:

   ```bash
   git push origin :refs/tags/v1.2.0
   ```

3. **If a GitHub release was created**, delete it:

   ```bash
   gh release delete v1.2.0 --yes
   ```

4. **Revert the version bump commit** if needed:

   ```bash
   git revert HEAD
   ```

## CI/CD Integration

The `.github/workflows/release.yml` workflow triggers on tag pushes matching `v*`. It:

1. Runs the full test suite
2. Builds a Docker image and pushes to `ghcr.io`
3. Creates a GitHub release with the changelog

The `.github/workflows/deploy.yml` workflow can be triggered manually or after a release to deploy via SSH.

## Migration Guide Template

When writing a migration guide manually (for major releases), use this structure:

```markdown
# Migration Guide: v1.x -> v2.0

## Breaking Changes
- [List each breaking change with before/after examples]

## Removed Features
- [List removed features and alternatives]

## New Requirements
- [List new dependencies or configuration]

## Step-by-Step Upgrade
1. Back up your configuration
2. Update code references (see breaking changes)
3. Pull and install: `git pull && pip install -e .`
4. Run tests: `pytest`
5. Verify: `claw --version`

## Rollback
[Instructions to revert if something goes wrong]
```
