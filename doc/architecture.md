# Token storage architecture

The Spotify OAuth token is stored differently depending on where the app runs.
Selection is driven by the `TOKEN_STORAGE` environment variable (`file` | `secret`).

## Local development — `FileCacheHandler`

- `TOKEN_STORAGE` unset (defaults to `file`).
- Token is read from and written to a local JSON file (default
  `cache/token_cache.txt`).
- `python main.py` opens a browser on first run to authenticate.

## In-cluster — `K8sSecretCacheHandler`

- `TOKEN_STORAGE=secret` (set by the chart's ConfigMap).
- **Read**: the `spotify-token` Secret is mounted read-only as a file at
  `/app/secrets/token/token_cache.json`. Reading a file needs no API call and no
  RBAC, and is resilient to a briefly-unreachable API server at startup.
- **Write**: refreshed/rotated tokens are written back by patching the Secret via
  the Kubernetes API (`patch_namespaced_secret`). This is the only operation that
  needs RBAC (`get`, `patch` on the single Secret).

## Serialization

The token blob is stored as **JSON** (`json.dumps`/`json.loads`) — idiomatic for
spotipy's own cache handlers and for the Kubernetes client. Note the distinction:

- The Secret **manifest** is YAML (like every Kubernetes manifest).
- The token **value** stored inside the Secret is a JSON string.

## Lifetime tracking (`seeded_at`)

Spotify does not expose a refresh-token expiry (`expires_in`/`expires_at`
describe only the 1-hour access token). We record `seeded_at` (ISO-8601 UTC) at
seed time and compute `180 days − age` on each run to log the remaining lifetime.
Both cache handlers re-inject `seeded_at` on write-back, because spotipy's
refreshed token blob does not carry it. The figure is an approximation from our
recorded seed time (not Spotify's server clock), accurate to about a day.

## Namespace

The deployment namespace is `jobs`. RBAC (ServiceAccount, Role, RoleBinding) is
created in the release namespace by the chart.
