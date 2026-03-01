# Vault

## What Is the Vault?

The vault is an encrypted credential store that lets Claude Code manage secrets (API keys, tokens, passwords) without ever writing them to disk in plaintext. Under the hood, it is a JSON object encrypted with [age](https://age-encryption.org), a modern file encryption tool.

Credentials are stored in a single encrypted file at `~/.claude-superpowers/vault.enc`. They can be injected into skill environments at runtime, keeping secrets out of `.env` files, shell history, and logs.

## How age Encryption Works

[age](https://github.com/FiloSottile/age) is a simple, modern encryption tool that uses X25519 key pairs.

1. **`age-keygen`** generates an identity file containing a private key and its corresponding public key
2. **Encryption** uses the public key -- anyone with it can encrypt data, but only the private key holder can decrypt
3. **Decryption** requires the identity file (private key)

The vault uses age as a subprocess:

- **Encrypt**: `echo '{"key":"value"}' | age -r <public-key> > vault.enc`
- **Decrypt**: `age -d -i age-identity.txt < vault.enc`

No age library is linked -- the `age` and `age-keygen` CLI binaries must be installed on the system.

## Initial Setup

### Prerequisites

Install age via Homebrew:

```bash
brew install age
```

### Initialize the Vault

```bash
claw vault init
```

This does three things:

1. **Generates an age keypair** at `~/.claude-superpowers/age-identity.txt` (chmod 600)
2. **Creates an empty encrypted vault** at `~/.claude-superpowers/vault.enc` (chmod 600)
3. **Stores the identity file path** in macOS Keychain under the service `claude-superpowers-vault`

Output:

```
Vault initialized.
  Identity: /Users/you/.claude-superpowers/age-identity.txt
  Vault:    /Users/you/.claude-superpowers/vault.enc
  Public key: age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p
```

If an identity file already exists, `init` skips key generation and reuses the existing key.

## Storing and Retrieving Credentials

### Store a Secret

```bash
claw vault set ANTHROPIC_API_KEY sk-ant-abc123...
claw vault set SLACK_BOT_TOKEN xoxb-...
claw vault set DB_PASSWORD hunter2
```

Each `set` decrypts the vault, adds/updates the key, and re-encrypts.

### Retrieve a Secret

By default, values are masked:

```bash
$ claw vault get ANTHROPIC_API_KEY
ANTHROPIC_API_KEY = sk****23
```

Use `--reveal` to show the full value:

```bash
$ claw vault get ANTHROPIC_API_KEY --reveal
sk-ant-abc123...
```

### List All Keys

```bash
$ claw vault list
       Vault Keys
┌────┬────────────────────┐
│  # │ Key                │
├────┼────────────────────┤
│  1 │ ANTHROPIC_API_KEY  │
│  2 │ DB_PASSWORD        │
│  3 │ SLACK_BOT_TOKEN    │
└────┴────────────────────┘
```

Keys are sorted alphabetically. Values are never shown in the list view.

### Delete a Secret

```bash
$ claw vault delete DB_PASSWORD
Deleted DB_PASSWORD
```

Raises an error if the key does not exist.

## macOS Keychain Integration

On macOS, `claw vault init` stores the identity file path in the system Keychain:

- **Service**: `claude-superpowers-vault`
- **Account**: `age-identity`
- **Password**: (the filesystem path to `age-identity.txt`)

This is a convenience feature -- it lets future phases locate the identity file without hardcoded paths. The Keychain entry stores the *path* to the key, not the key itself.

If Keychain access fails (non-macOS, permissions denied), the operation is silently skipped. The vault works fine without it.

## Security Model

### Encryption at Rest

- All secrets are stored in a single age-encrypted file (`vault.enc`)
- The vault is never written to disk in plaintext
- The identity file (private key) is created with `chmod 600`
- The vault file is written with `chmod 600`

### Atomic Writes

Every write operation (set, delete) follows this pattern:

1. Decrypt the vault into memory
2. Modify the in-memory dictionary
3. Re-encrypt to a temporary file (`.vault-*.tmp`)
4. Atomically rename the temp file to `vault.enc` using `os.replace()`

This prevents corruption if the process is interrupted mid-write. If anything fails, the temporary file is cleaned up and the original vault is untouched.

### Sandboxed Skill Execution

When skills are run via `SkillLoader.run_sandboxed()`:

- Skills **without** `vault` permission get a minimal environment: `PATH`, `HOME`, `LANG`, `TERM` only
- Skills **with** `vault` permission receive the full environment, including any vault-injected variables
- This prevents accidental secret leakage to untrusted skills

### What Is NOT Protected

- The identity file is a plaintext age private key on disk. Anyone with filesystem access to `~/.claude-superpowers/age-identity.txt` can decrypt the vault.
- The vault is only as secure as your filesystem permissions and user account.
- Secrets are briefly held in memory during decrypt/encrypt cycles.

## Programmatic API

The `Vault` class can be used directly from Python:

```python
from superpowers.vault import Vault

v = Vault()

# Initialize (only needed once)
v.init()

# CRUD operations
v.set("MY_KEY", "my-secret-value")
value = v.get("MY_KEY")        # "my-secret-value"
keys = v.list_keys()           # ["MY_KEY"]
v.delete("MY_KEY")

# Export for environment injection
env = v.export_env()                    # All keys as dict
env = v.export_env(["KEY1", "KEY2"])    # Specific keys only
```

### Custom Paths

```python
v = Vault(
    vault_path="/custom/path/vault.enc",
    identity_file="/custom/path/age-identity.txt",
)
```

## CLI Reference

### `claw vault init`

Generate age keypair and create empty vault. Safe to run multiple times -- skips if identity already exists.

### `claw vault set <key> <value>`

Store or update a credential. The key is case-sensitive.

### `claw vault get <key> [--reveal]`

Retrieve a credential. Masked by default; use `--reveal` to show the full value.

### `claw vault list`

List all stored keys in a table. Values are never displayed.

### `claw vault delete <key>`

Remove a credential. Errors if the key does not exist.
