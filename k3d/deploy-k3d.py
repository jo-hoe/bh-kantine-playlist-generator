#!/usr/bin/env python3
"""
Cross-platform script to deploy to k3d cluster.
- Optionally creates the k3d cluster with an injected host volume for cache.
- Loads environment variables from .env and executes helm install.
Works on Windows, Linux, and macOS.
"""

import os
import sys
import subprocess
import argparse
from dotenv import load_dotenv


def run(cmd, not_found_msg, fail_prefix):
    """Run a command and handle common errors uniformly."""
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        return 0
    except FileNotFoundError:
        print(not_found_msg)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"{fail_prefix} (exit code {e.returncode})")
        if e.stdout:
            print("stdout:", e.stdout)
        if e.stderr:
            print("stderr:", e.stderr)
        sys.exit(1)


def project_root() -> str:
    """Return the repository root directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ensure_env(root_dir: str) -> str:
    """Ensure .env exists, load it, and validate required variables."""
    env_file = os.path.join(root_dir, ".env")
    if not os.path.exists(env_file):
        print(f"Error: .env file not found at {env_file}")
        print("Please create .env with SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, and SPOTIFY_REDIRECT_URI")
        sys.exit(1)

    load_dotenv(env_file)

    required_vars = ["SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_REDIRECT_URI"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"Error: Missing required environment variables in .env file: {', '.join(missing_vars)}")
        sys.exit(1)

    return env_file


def create_cluster(root_dir: str) -> None:
    """Create the k3d cluster."""
    cluster_config = os.path.join(root_dir, "k3d", "clusterconfig.yaml")

    k3d_cmd = [
        "k3d", "cluster", "create",
        "--config", cluster_config,
    ]

    print("Creating k3d cluster...")
    run(
        k3d_cmd,
        "Error: k3d command not found. Please make sure k3d is installed and in your PATH.",
        "Error: k3d cluster create failed",
    )


def helm_install(root_dir: str, image_name: str, image_version: str) -> None:
    """Install/upgrade the helm release using values from the environment."""
    charts_path = os.path.join(root_dir, "charts", image_name)
    helm_cmd = [
        "helm", "install", image_name,
        charts_path,
        "--set", f"cronjob.image.repository=registry.localhost:5001/{image_name}",
        "--set", f"cronjob.image.tag={image_version}",
        "--set", f"secret.data.spotifyClientId={os.getenv('SPOTIFY_CLIENT_ID')}",
        "--set", f"secret.data.spotifyClientSecret={os.getenv('SPOTIFY_CLIENT_SECRET')}",
        "--set", f"secret.data.spotifyRedirectUri={os.getenv('SPOTIFY_REDIRECT_URI')}",
    ]

    print("Deploying to k3d cluster...")
    run(
        helm_cmd,
        "Error: helm command not found. Please make sure Helm is installed and in your PATH.",
        "Error: Helm install failed",
    )
    print("Deployment successful!")


def parse_args():
    parser = argparse.ArgumentParser(description="Deploy to k3d cluster")
    parser.add_argument(
        "--image-name",
        default="bh-playlist-generator",
        help="Docker image name (default: bh-playlist-generator)",
    )
    parser.add_argument(
        "--image-version",
        default="latest",
        help="Docker image version (default: latest)",
    )
    parser.add_argument(
        "--create-cluster",
        action="store_true",
        help="Create k3d cluster (with host cache volume) before deploying",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    root_dir = project_root()

    # Create cluster and exit if requested (no .env needed)
    if args.create_cluster:
        create_cluster(root_dir)
        sys.exit(0)

    image_name = args.image_name.strip('"')
    image_version = args.image_version.strip('"')

    env_file = ensure_env(root_dir)
    print(f"Using environment variables from: {env_file}")

    helm_install(root_dir, image_name, image_version)


if __name__ == "__main__":
    main()
