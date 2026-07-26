# Migration: PersistentVolume → Kubernetes Secret (chart v3)

Chart **v3.0.0** removes the hostPath-backed PersistentVolume/PersistentVolumeClaim
that previously stored the Spotify token, and moves the token into a dedicated
`spotify-token` Kubernetes Secret that the pod reads and writes via the API.

This is a **breaking change** and requires a one-time re-seed.

## Steps

1. **Upgrade the chart** to v3.0.0 (via your usual Helmfile/release process).

2. **Seed the token into the Secret** (the old PV token cannot be reused — see below):

   ```bash
   make seed-token
   # then run the printed kubectl command
   ```

   See [token-seeding.md](./token-seeding.md) for details.

3. **Remove the old PV/PVC** once the new setup is confirmed working:

   ```bash
   kubectl delete pvc spotify-cache-pvc --namespace jobs
   kubectl delete pv spotify-cache-pv
   ```

   (The old hostPath directory `/main/spotify/cache` on the node can also be
   deleted manually if desired.)

## Why the old token can't be reused

The old on-disk token was written with Python's `str(dict)` (single quotes,
`True`/`False`/`None`), which is **not valid JSON**. The new handler reads JSON,
so it cannot parse the old file. It also lacks the `seeded_at` stamp needed for
lifetime logging. Regenerate the token with the seed script rather than copying
the old file.
