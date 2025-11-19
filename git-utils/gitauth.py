import subprocess
import os
import re
import json
import argparse
from urllib.parse import urlparse

# Path to config file
CONFIG_FILE = os.path.expanduser('~/.git/git_auth.json')

def load_config():
    """Load full config from file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading config file {CONFIG_FILE}: {e}")
            return {}
    return {}

def load_owner_tokens():
    """Load owner to token mapping from config file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get('owner_tokens', {})
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading config file {CONFIG_FILE}: {e}")
            return {}
    else:
        print(f"Config file {CONFIG_FILE} not found. Please create it with owner_tokens mapping.")
        return {}

# Load tokens at module level
OWNER_TOKENS = load_owner_tokens()

def save_config(config):
    """Save full config to file."""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except IOError as e:
        print(f"Error saving config file {CONFIG_FILE}: {e}")
        return False

def add_owner_token(owner, token):
    """Add or update a token for an owner."""
    config = load_config()
    if 'owner_tokens' not in config:
        config['owner_tokens'] = {}
    config['owner_tokens'][owner] = token
    
    if save_config(config):
        print(f"Token for owner '{owner}' saved.")
        global OWNER_TOKENS
        OWNER_TOKENS = config['owner_tokens']

def is_git_repo():
    """Check if the current directory is a Git repository."""
    return os.path.isdir('.git')

def get_current_branch():
    """Get the current Git branch name."""
    try:
        result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                                capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None

def get_remote_url(remote_name='origin'):
    """Get the URL of the specified remote."""
    try:
        result = subprocess.run(['git', 'remote', 'get-url', remote_name],
                                capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None

def set_remote_url(remote_name, url):
    """Set the URL for the specified remote."""
    try:
        subprocess.run(['git', 'remote', 'set-url', remote_name, url],
                       check=True)
        # Mask the token in the displayed URL
        masked_url = re.sub(r'https://([^@]+)@', r'https://***@', url)
        print(f"Updated remote '{remote_name}' to: {masked_url}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to set remote URL: {e}")

def parse_github_url(url):
    """Parse GitHub URL to extract owner and repo."""
    # Handle HTTPS URLs
    if url.startswith('https://'):
        parsed = urlparse(url)
        if parsed.hostname == 'github.com':
            path_parts = parsed.path.strip('/').split('/')
            if len(path_parts) >= 2:
                owner = path_parts[0]
                repo = path_parts[1].replace('.git', '')  # Remove .git if present
                return owner, repo, 'https'
    # Handle SSH URLs (git@github.com:owner/repo.git)
    elif url.startswith('git@'):
        match = re.match(r'git@github\.com:([^/]+)/(.+)\.git', url)
        if match:
            owner = match.group(1)
            repo = match.group(2)  # Already without .git
            return owner, repo, 'ssh'
    return None, None, None

def update_remote_with_token(dry_run=False, remote_name='origin'):
    """Update the remote URL to include the appropriate GitHub token based on the owner."""
    if not is_git_repo():
        print("Not a Git repository.")
        return

    remote_url = get_remote_url(remote_name)
    if not remote_url:
        print(f"No remote '{remote_name}' found.")
        return

    owner, repo, protocol = parse_github_url(remote_url)
    if not owner:
        print("Not a GitHub repository or unsupported URL format.")
        return

    token = OWNER_TOKENS.get(owner)
    if not token:
        print(f"No token configured for owner '{owner}'.")
        return

    if protocol == 'https':
        # Insert token into HTTPS URL
        new_url = f"https://{token}@github.com/{owner}/{repo}.git"
    elif protocol == 'ssh':
        # For SSH, we might need to convert to HTTPS with token
        # Since the example is HTTPS, we'll convert SSH to HTTPS
        new_url = f"https://{token}@github.com/{owner}/{repo}.git"
    else:
        print("Unsupported protocol.")
        return

    if dry_run:
        masked_new_url = re.sub(r'https://([^@]+)@', r'https://***@', new_url)
        print(f"Dry run: Would update remote '{remote_name}' from {remote_url} to {masked_new_url}")
    else:
        set_remote_url(remote_name, new_url)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Update Git remote URL with GitHub token based on owner.')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without making changes')
    parser.add_argument('--remote', default='origin', help='Remote name to update (default: origin)')
    parser.add_argument('--list-tokens', action='store_true', help='List configured owner-token mappings')
    parser.add_argument('--add-token', nargs=2, metavar=('OWNER', 'TOKEN'), help='Add or update a token for an owner')

    args = parser.parse_args()

    if args.add_token:
        add_owner_token(args.add_token[0], args.add_token[1])
    elif args.list_tokens:
        print("Configured owner-token mappings:")
        for owner, token in OWNER_TOKENS.items():
            masked_token = token[:4] + '*' * (len(token) - 4) if len(token) > 4 else token
            print(f"  {owner}: {masked_token}")
    else:
        update_remote_with_token(dry_run=args.dry_run, remote_name=args.remote)