# K3D Testing Setup for BH Playlist Generator

This document describes how to test the BH Playlist Generator Helm chart using k3d (lightweight Kubernetes).

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [k3d](https://k3d.io/#installation) - lightweight Kubernetes in Docker
- [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/)
- [Helm](https://helm.sh/docs/intro/install/)
- Make (for using the provided Makefile commands)

### Windows Installation

```bash
# Install k3d
winget install rancher-sandbox.k3d

# Or using chocolatey
choco install k3d

# Install kubectl
winget install Kubernetes.kubectl

# Install helm
winget install Helm.Helm
```

## Quick Start

To get started with testing the BH Playlist Generator using k3d, use the make commands provided in the Makefile. Run `make help` to see all available options and their descriptions.

## Available Make Commands

For a complete list of available make commands and their descriptions, run:

```bash
make help
```

This will display all available targets with detailed explanations of what each command does.

## Configuration

### Spotify Credentials

Before deploying, you need to create a `.env` file with your Spotify API credentials:

1. **Copy the example file:**

   ```bash
   cp .env.example .env
   ```

2. **Edit the .env file** with your actual Spotify credentials:

   ```bash
   # .env
   SPOTIFY_CLIENT_ID=your_actual_spotify_client_id
   SPOTIFY_CLIENT_SECRET=your_actual_spotify_client_secret
   SPOTIFY_REDIRECT_URI=your_actual_spotify_redirect_uri
   ```

The deployment process uses a cross-platform Python script (`k3d/deploy-k3d.py`) that automatically reads these values from the `.env` file when deploying to k3d. This solution works on **Windows, Linux, and macOS** without any shell-specific dependencies.

**Note:** The `.env` file is automatically ignored by git (should be in .gitignore) to keep your credentials secure.

### Cross-Platform Compatibility

The Make targets use a Python script instead of shell commands, ensuring compatibility across all platforms:

- **Windows**: Works with PowerShell, Command Prompt, or WSL
- **Linux**: Works with bash, zsh, or any POSIX shell
- **macOS**: Works with bash, zsh, or any POSIX shell

The Python script handles environment variable loading and Helm deployment consistently across all platforms.

### Persistent Volume

The chart creates a PersistentVolume that maps to `/main/spotify/cache` inside the k3d cluster. This is automatically mounted from your local `./cache` directory thanks to the k3d configuration.

## Testing the CronJob

The CronJob is scheduled to run daily at 9 AM by default. For testing purposes, you can:

1. **Manually trigger a job:**

   ```bash
   kubectl create job --from=cronjob/bh-playlist-generator manual-test-job
   ```

2. **Check job status:**

   ```bash
   kubectl get jobs
   kubectl get pods
   ```

3. **View job logs:**

   ```bash
   kubectl logs job/manual-test-job
   ```

4. **Clean up test job:**

   ```bash
   kubectl delete job manual-test-job
   ```

## Troubleshooting

### Common Issues

1. **k3d cluster won't start:**
   - Check if ports 6551 and 5001 are available
   - Stop any existing cluster first to clean up

2. **Docker image push fails:**
   - Ensure Docker is running
   - Stop and restart the k3d cluster

3. **PersistentVolume issues:**
   - Ensure the `./cache` directory exists: `mkdir -p cache`
   - Check volume permissions in the pod logs

4. **Helm install fails:**
   - Test the chart first to validate it
   - Check if the chart name conflicts: `helm list`

### Debug Commands

```bash
# Check k3d cluster status
k3d cluster list

# Check all pods in the cluster
kubectl get pods --all-namespaces

# Describe a specific resource
kubectl describe cronjob bh-playlist-generator

# Check persistent volume status
kubectl get pv,pvc

# Port forward to access internal services (if needed)
kubectl port-forward svc/some-service 8080:80
```

## Chart Development

When making changes to the chart, use the make commands provided in the Makefile to test locally, restart the deployment, and check the changes. Run `make help` for specific commands.

## Clean Up

To completely clean up everything, use the make commands provided in the Makefile. Run `make help` to see available cleanup options.

This will remove the k3d cluster, local Docker registry, and all associated Docker images.
