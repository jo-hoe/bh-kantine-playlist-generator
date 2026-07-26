# Seeding the Spotify token

> **Spotify Developer-Dashboard refresh tokens expire after a hard 180-day limit
> that cannot be extended by refreshing.** You must re-run the seed procedure at
> least every 180 days, and immediately whenever a job logs `invalid_grant` /
> `Refresh token revoked`. **Set a calendar reminder.**

The cronjob authenticates to Spotify using an OAuth token stored in a Kubernetes
Secret (`spotify-token`). The initial token can only be obtained through an
interactive browser login, so it must be seeded from a developer machine.

## Recommended: the helper script

```bash
make seed-token
# or, with options:
python scripts/seed-token.py --namespace jobs
```

This will:

1. Read your Spotify credentials from `.env`.
2. Open a browser for the OAuth flow — approve the requested scopes.
3. Write the token as JSON and stamp `seeded_at` (so the app can log the
   remaining lifetime).
4. Show your current `kubectl` context, tell you whether the Secret already
   exists, and print (and copy to your clipboard) the command to run.

The script **does not touch your cluster**. Review the printed command, confirm
the context is correct, and run it yourself:

```bash
kubectl create secret generic spotify-token \
    --namespace jobs \
    --from-file=token_cache.json=cache/token_cache.txt \
    --dry-run=client -o yaml | kubectl apply -f -
```

### When `kubectl` runs on a remote SSH host

If you run `kubectl` on a bastion / cluster host you SSH into (not on your
laptop), the token file is on your laptop but the command must run remotely.
Generate the manifest locally and pipe it into `kubectl apply` over SSH — the
token never lands on the remote host's disk:

```bash
kubectl create secret generic spotify-token \
    --namespace jobs \
    --from-file=token_cache.json=cache/token_cache.txt \
    --dry-run=client -o yaml \
  | ssh youruser@yourhost 'kubectl apply -f -'
```

PowerShell equivalent (backtick line continuation):

```powershell
kubectl create secret generic spotify-token `
    --namespace jobs `
    --from-file=token_cache.json=cache/token_cache.txt `
    --dry-run=client -o yaml `
  | ssh youruser@yourhost 'kubectl apply -f -'
```

Notes:
- This needs `kubectl` on your **laptop** too, but only for the client-side
  `--dry-run` (it does not contact any cluster).
- Use an SSH user that is allowed to log in. A piped stdin conflicts with an
  interactive password prompt, so prefer key-based auth. If you must use a
  password, use `scp` to copy the token to the host first, then run the
  `kubectl create ... | kubectl apply -f -` command there and delete the file
  afterwards.

## Manual equivalent (no script)

```bash
cp .env.example .env          # fill in your Spotify credentials
python main.py                # browser opens; writes JSON to cache/token_cache.txt
```

Then create/update the Secret with the same command as above.

> The manual path does **not** stamp `seeded_at`, so the app will log
> "refresh token lifetime unknown". Prefer the script so lifetime logging works.

## How the pod self-updates the token

Spotify access tokens expire hourly and may return a rotated refresh token. The
pod persists these back to the Secret automatically:

- The pod runs as ServiceAccount `spotify-playlist-sa`.
- A `Role` grants `get` and `patch` on **only** the `spotify-token` Secret
  (scoped via `resourceNames`).
- A `RoleBinding` binds it in the deployment namespace (`jobs`).
- On refresh, the app patches the Secret with the new token. The `seeded_at`
  stamp is preserved across every write-back, so the 180-day clock is not reset.

Reads use the Secret mounted as a read-only file; only write-backs use the API.

## When to re-seed

- **At the latest every 180 days** — the hard refresh-token expiry.
- **Immediately** when logs show `invalid_grant` / `Refresh token revoked`
  (also happens if you change your Spotify password or revoke app access).
- The app logs remaining lifetime on each run (INFO, or WARNING under 21 days).

## Key-name consistency checklist

The Secret key `token_cache.json` must match in **all** of these places:

- `charts/bh-playlist-generator/values.yaml` → `tokenSecret.key`
- ConfigMap env `TOKEN_SECRET_KEY` (rendered from the same value)
- The cache handler default in `app/playlist/spotify_playlist_generator.py`
- The mounted filename (`tokenSecret.mountPath` + key)
- The `--from-file=token_cache.json=...` argument in the seed command
