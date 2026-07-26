#!/usr/bin/env python3
"""
Seed (or re-seed) the Spotify OAuth token file for upload to a Kubernetes Secret.

Spotify Developer-Dashboard refresh tokens have a hard 180-day lifetime that
cannot be extended by refreshing. You MUST re-run this script at least every
180 days, and immediately whenever the job logs 'invalid_grant' /
'Refresh token revoked'.

What it does:
  1. Validates Spotify credentials from .env.
  2. Runs the local OAuth flow (opens a browser) to produce a token file.
  3. Stamps 'seeded_at' (UTC) into the token JSON so the app can log the
     remaining refresh-token lifetime.
  4. Assembles the exact `kubectl` command, shows your current cluster context
     for a sanity check, and copies the command to your clipboard.

This script never mutates your cluster; you run the printed kubectl command
yourself (read-only `kubectl` calls are used only to show context). Works on
Windows, Linux, and macOS.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv


def project_root() -> str:
    """Return the repository root directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ensure_env(root_dir: str) -> None:
    """Ensure .env exists, load it, and validate required variables."""
    env_file = os.path.join(root_dir, ".env")
    if not os.path.exists(env_file):
        print(f"Error: .env file not found at {env_file}")
        print("Please create .env with SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, and SPOTIFY_REDIRECT_URI")
        sys.exit(1)

    load_dotenv(env_file)

    required_vars = ["SPOTIFY_CLIENT_ID",
                     "SPOTIFY_CLIENT_SECRET", "SPOTIFY_REDIRECT_URI"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(
            f"Error: Missing required environment variables in .env file: {', '.join(missing_vars)}")
        sys.exit(1)


def run_local_oauth(root_dir: str, token_file: str) -> None:
    """Run the local OAuth flow to produce the token cache file."""
    # Import here so the script fails fast on missing .env before importing app deps.
    sys.path.insert(0, root_dir)
    from app.playlist.spotify_playlist_generator import SpotifyPlaylistGenerator

    print("Starting Spotify OAuth flow (a browser window will open)...")
    # Constructing the generator warms the client, which triggers the OAuth
    # flow and writes the token file. File storage, browser enabled.
    SpotifyPlaylistGenerator(
        playlist_name=os.getenv("PLAYLIST_NAME", "Kantine Am Berghain: Next Up"),
        maximum_tracks_per_artist=int(os.getenv("MAX_TRACK_NUMBER_PER_ARTIST", 3)),
        token_cache_file_path=token_file,
        is_running_in_container=False,
        token_storage="file",
    )

    if not os.path.exists(token_file) or not os.path.getsize(token_file):
        print(f"Error: OAuth did not produce a token file at {token_file}")
        sys.exit(1)
    print(f"Token written to {token_file}")


def stamp_seeded_at(token_file: str) -> None:
    """Record the authorization time so the app can track the 180-day lifetime."""
    with open(token_file, "r", encoding="utf-8") as f:
        token_info = json.loads(f.read())
    token_info["seeded_at"] = datetime.now(timezone.utc).isoformat()
    with open(token_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(token_info))
    print(f"Stamped seeded_at={token_info['seeded_at']}")


def _kubectl(*args) -> "subprocess.CompletedProcess | None":
    """Run a read-only kubectl command, returning None if kubectl is unavailable."""
    if not shutil.which("kubectl"):
        return None
    try:
        return subprocess.run(
            ["kubectl", *args], capture_output=True, text=True, timeout=10)
    except Exception:
        return None


def show_cluster_context(namespace: str, secret_name: str) -> None:
    """Show the current context/namespace and whether the Secret already exists."""
    if not shutil.which("kubectl"):
        print("\nNote: kubectl not found on PATH — skipping cluster sanity check.")
        return

    ctx = _kubectl("config", "current-context")
    if ctx and ctx.returncode == 0 and ctx.stdout.strip():
        print(f"\nCurrent kubectl context: {ctx.stdout.strip()}")
        print("  -> Make sure this is the RIGHT cluster before running the command below.")

    existing = _kubectl("get", "secret", secret_name,
                        "--namespace", namespace, "--ignore-not-found",
                        "-o", "name")
    if existing and existing.returncode == 0:
        if existing.stdout.strip():
            print(f"  -> Secret '{secret_name}' already exists in '{namespace}' "
                  "and will be UPDATED (apply is idempotent).")
        else:
            print(f"  -> Secret '{secret_name}' does not exist in '{namespace}' yet "
                  "and will be CREATED.")


def copy_to_clipboard(text: str) -> bool:
    """Best-effort copy to the OS clipboard. Returns True on success."""
    candidates = []
    if sys.platform == "win32":
        candidates = [["clip"]]
    elif sys.platform == "darwin":
        candidates = [["pbcopy"]]
    else:
        candidates = [["xclip", "-selection", "clipboard"], ["wl-copy"]]

    for cmd in candidates:
        if not shutil.which(cmd[0]):
            continue
        try:
            subprocess.run(cmd, input=text, text=True, check=True)
            return True
        except Exception:
            continue
    return False


def build_kubectl_command(namespace: str, secret_name: str, secret_key: str, token_file: str) -> str:
    """Assemble the idempotent create-or-update command (key MUST match the handler)."""
    return (
        f"kubectl create secret generic {secret_name} \\\n"
        f"    --namespace {namespace} \\\n"
        f"    --from-file={secret_key}={token_file} \\\n"
        f"    --dry-run=client -o yaml | kubectl apply -f -"
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Seed/re-seed the Spotify token file for a Kubernetes Secret")
    parser.add_argument("--namespace", default="jobs",
                        help="Kubernetes namespace for the printed command (default: jobs)")
    parser.add_argument("--secret-name", default="spotify-token",
                        help="Secret name (default: spotify-token)")
    parser.add_argument("--secret-key", default="token_cache.json",
                        help="Key inside the Secret (default: token_cache.json)")
    parser.add_argument("--token-file", default=None,
                        help="Local token file path (default: <root>/cache/token_cache.txt)")
    return parser.parse_args()


def main():
    args = parse_args()
    root_dir = project_root()

    token_file = args.token_file or os.path.join(root_dir, "cache", "token_cache.txt")
    os.makedirs(os.path.dirname(token_file), exist_ok=True)

    ensure_env(root_dir)
    run_local_oauth(root_dir, token_file)
    stamp_seeded_at(token_file)

    show_cluster_context(args.namespace, args.secret_name)

    command = build_kubectl_command(
        args.namespace, args.secret_name, args.secret_key, token_file)

    print("\nToken file is ready. Run this to create/update the Secret:\n")
    print("  " + command.replace("\n", "\n  ") + "\n")

    if copy_to_clipboard(command):
        print("(Command copied to your clipboard.)")

    print("\nThe refresh token is valid for ~180 days from now.")
    print("Set a calendar reminder to re-run this before it expires.")


if __name__ == "__main__":
    main()
