#!/usr/bin/env python3
"""
Cross-platform script to deploy to k3d cluster.
Reads environment variables from .env file and executes helm install.
Works on Windows, Linux, and macOS.
"""

import os
import sys
import subprocess
import argparse
from dotenv import load_dotenv


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Deploy to k3d cluster')
    parser.add_argument('--image-name', default='bh-playlist-generator', 
                       help='Docker image name (default: bh-playlist-generator)')
    parser.add_argument('--image-version', default='latest',
                       help='Docker image version (default: latest)')
    args = parser.parse_args()
    
    # Get the root directory (where this script is located relative to project root)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    
    # Configuration
    image_name = args.image_name.strip('"')  # Remove quotes if present
    image_version = args.image_version.strip('"')  # Remove quotes if present
    env_file_path = os.path.join(root_dir, ".env")
    
    # Load environment variables from .env file using python-dotenv
    if not os.path.exists(env_file_path):
        print(f"Error: .env file not found at {env_file_path}")
        print("Please create .env with SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, and SPOTIFY_REDIRECT_URI")
        sys.exit(1)
    
    load_dotenv(env_file_path)
    
    # Check required environment variables
    required_vars = ["SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_REDIRECT_URI"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Error: Missing required environment variables in .env file: {', '.join(missing_vars)}")
        sys.exit(1)
    
    # Prepare helm install command using os.path.join
    charts_path = os.path.join(root_dir, "charts", image_name)
    helm_cmd = [
        "helm", "install", image_name,
        charts_path,
        "--set", f"cronjob.image.repository=registry.localhost:5001/{image_name}",
        "--set", f"cronjob.image.tag={image_version}",
        "--set", f"secret.data.spotifyClientId={os.getenv('SPOTIFY_CLIENT_ID')}",
        "--set", f"secret.data.spotifyClientSecret={os.getenv('SPOTIFY_CLIENT_SECRET')}",
        "--set", f"secret.data.spotifyRedirectUri={os.getenv('SPOTIFY_REDIRECT_URI')}"
    ]
    
    print("Deploying to k3d cluster...")
    print(f"Using environment variables from: {env_file_path}")
    
    # Execute helm command
    try:
        result = subprocess.run(helm_cmd, check=True, capture_output=True, text=True)
        print("Deployment successful!")
        if result.stdout:
            print("Output:", result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error: Helm install failed with exit code {e.returncode}")
        if e.stdout:
            print("stdout:", e.stdout)
        if e.stderr:
            print("stderr:", e.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: helm command not found. Please make sure Helm is installed and in your PATH.")
        sys.exit(1)


if __name__ == "__main__":
    main()
