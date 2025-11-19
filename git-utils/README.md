# Git Utils

Collection of Git utilities for managing GitHub repositories with personal access tokens.

## Files

- `gittoken`: Global CLI tool for managing GitHub tokens and user config
- `git_remote_token.py`: Local script for updating remote URLs with tokens
- `git_config.json`: Local configuration file for owner-token mappings

## Usage

### Global Tool (gittoken)

```bash
# Setup global config
./gittoken setup

# List configured tokens
./gittoken list

# Update remote and set user config
./gittoken auth

# Dry run
./gittoken auth --dry-run

# Only set user config
./gittoken auth --config-only --dry-run
```

### Local Script

```bash
# Update remote with token
python git_remote_token.py

# List tokens
python git_remote_token.py --list-tokens

# Dry run
python git_remote_token.py --dry-run
```

## Configuration

### Global Config (~/.git-tokens.json)

```json
{
  "owner_tokens": {
    "owner1": "ghp_token1",
    "owner2": "ghp_token2"
  },
  "owners": {
    "owner1": {
      "name": "Your Name",
      "email": "your.email@example.com"
    }
  }
}
```

### Local Config (git_config.json)

```json
{
  "owner_tokens": {
    "owner1": "ghp_token1"
  }
}
```

## Features

- Automatically detect GitHub owner from remote URL
- Insert personal access token into HTTPS URLs
- Set git user.name and user.email based on owner
- Support for both HTTPS and SSH URLs (converts SSH to HTTPS)
- Dry-run mode for safe testing
- Global and local configuration options