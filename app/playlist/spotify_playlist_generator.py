from __future__ import annotations

from functools import lru_cache
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
import json
import logging
import os

import spotipy
from spotipy.cache_handler import CacheHandler
from spotipy.oauth2 import SpotifyOAuth

from app.playlist.abstract_playlist_generator import AbstractPlaylistGenerator


JSONDict = Dict[str, Any]

# Spotify Developer-Dashboard refresh tokens have a hard 6-month lifetime that
# cannot be extended by refreshing access tokens. Spotify exposes no expiry field
# for the refresh token, so we track it ourselves via a "seeded_at" stamp written
# at seed time (see scripts/seed-token.py).
REFRESH_TOKEN_LIFETIME_DAYS: int = 180
REFRESH_TOKEN_WARN_THRESHOLD_DAYS: int = 21

# Extra key stored inside the token blob to record when authorization happened.
SEEDED_AT_KEY: str = "seeded_at"


def _log_refresh_token_lifetime(token_info: Optional[JSONDict]) -> None:
    """
    Log how much of the refresh token's 180-day lifetime remains, based on the
    "seeded_at" stamp. This is an approximation from our recorded seed time (not
    Spotify's server clock), accurate to roughly a day, and the only available
    signal since Spotify does not expose refresh-token expiry.
    """
    if not token_info:
        return

    seeded_at_raw = token_info.get(SEEDED_AT_KEY)
    if not seeded_at_raw:
        logging.info(
            "Spotify refresh token lifetime unknown (no 'seeded_at' stamp). "
            "Re-seed via scripts/seed-token.py to establish it.")
        return

    try:
        seeded_at = datetime.fromisoformat(seeded_at_raw)
        if seeded_at.tzinfo is None:
            seeded_at = seeded_at.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        logging.warning(
            f"Could not parse 'seeded_at' value: {seeded_at_raw!r}. "
            "Re-seed to refresh the stamp.")
        return

    age_days = (datetime.now(timezone.utc) - seeded_at).days
    remaining_days = REFRESH_TOKEN_LIFETIME_DAYS - age_days
    seeded_date = seeded_at.date().isoformat()

    if remaining_days <= REFRESH_TOKEN_WARN_THRESHOLD_DAYS:
        logging.warning(
            f"Spotify refresh token: ~{remaining_days} days until expiry "
            f"(seeded {seeded_date}). Re-seed soon via scripts/seed-token.py.")
    else:
        logging.info(
            f"Spotify refresh token: ~{remaining_days} days until expiry "
            f"(seeded {seeded_date}).")


class SpotifyPlaylistGenerator(AbstractPlaylistGenerator):
    """
    Spotify-backed implementation that:
    - Resolves artists with a robust, normalized two-pass search
    - Selects tracks from recent singles and albums (prefers solo tracks)
    - Replaces playlist items using the February 2026 API (/playlists/{id}/items)
    """

    # API limits and pagination
    SEARCH_LIMIT: int = 10                # API max for /search as of Feb 2026
    SEARCH_MAX_PAGES: int = 10            # Scan up to 100 results
    ALBUM_PAGE_LIMIT: int = 20            # artist_albums paging
    ALBUM_PAGE_MAX_PAGES: int = 3         # up to 60 albums/singles per type
    ALBUM_TRACK_PAGE_LIMIT: int = 50      # album_tracks paging
    # conservative chunk size for POST /playlists/{id}/items
    PLAYLIST_ITEMS_CHUNK_SIZE: int = 50

    # Scopes restricted to least privilege for this generator
    REQUIRED_SCOPES: str = "playlist-read-private,playlist-modify-private,playlist-modify-public"

    # Required environment variables
    ENVIRONMENT_VARIABLES: List[str] = [
        "SPOTIFY_CLIENT_ID",
        "SPOTIFY_CLIENT_SECRET",
        "SPOTIFY_REDIRECT_URI",
    ]

    def __init__(
        self,
        playlist_name: str,
        maximum_tracks_per_artist: int,
        token_cache_file_path: str,
        is_running_in_container: bool,
        token_storage: str = "file",
        token_secret_name: str = "spotify-token",
        token_secret_key: str = "token_cache.json",
        token_secret_namespace: str = "",
    ) -> None:
        super().__init__(playlist_name, maximum_tracks_per_artist)
        self._token_cache_file_path = token_cache_file_path
        self._is_running_in_container = is_running_in_container
        # Token storage: "file" (local dev) or "secret" (in-cluster k8s Secret).
        # In "secret" mode, token_cache_file_path is the mounted Secret file path.
        self._token_storage = token_storage.lower()
        self._token_secret_name = token_secret_name
        self._token_secret_key = token_secret_key
        self._token_secret_namespace = token_secret_namespace
        # Warm client (and validate env) early
        self._get_spotify_client()

    def _build_cache_handler(self) -> CacheHandler:
        """
        Select the cache handler based on the configured token storage backend.
        """
        if self._token_storage == "secret":
            return K8sSecretCacheHandler(
                secret_name=self._token_secret_name,
                secret_key=self._token_secret_key,
                namespace=self._token_secret_namespace,
                mounted_file_path=self._token_cache_file_path,
            )

        handler = FileCacheHandler(filepath=self._token_cache_file_path)
        if not handler.does_file_contain_data(self._token_cache_file_path):
            logging.info(
                f"Token cache file is missing or empty at: {self._token_cache_file_path}. "
                "A new file will be created upon authentication."
            )
        return handler

    @lru_cache(maxsize=1)
    def _get_spotify_client(self) -> spotipy.Spotify:
        """
        Construct a single spotipy client with OAuth configured.
        """
        automatically_open_browser = not self._is_running_in_container

        cache_handler = self._build_cache_handler()
        _log_refresh_token_lifetime(cache_handler.get_cached_token())

        missing = [
            v for v in self.ENVIRONMENT_VARIABLES if not os.environ.get(v)]
        if missing:
            raise EnvironmentError(
                f"Spotify credentials are missing: {', '.join(missing)}")

        auth = SpotifyOAuth(
            scope=self.REQUIRED_SCOPES,
            client_id=os.environ["SPOTIFY_CLIENT_ID"],
            client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
            redirect_uri=os.environ["SPOTIFY_REDIRECT_URI"],
            open_browser=automatically_open_browser,
            cache_handler=cache_handler,
        )
        return spotipy.Spotify(auth_manager=auth)

    # --------------------------
    # Public API implementations
    # --------------------------

    def get_playlist_id_by_name(self, playlist_name: str) -> Optional[str]:
        """
        Return ID of a user-owned playlist matching the provided name.
        Scans pages of /me/playlists to find an exact name match.
        """
        client = self._get_spotify_client()
        offset = 0
        limit = 50
        while True:
            playlists = client.current_user_playlists(
                limit=limit, offset=offset) or {}
            items: List[JSONDict] = playlists.get("items", [])
            for p in items:
                if p.get("name") == playlist_name:
                    return p.get("id")
            if not items or len(items) < limit:
                break
            offset += limit
        return None

    def get_top_tracks_for_artist(self, artist_name: str, maximum_tracks_per_artist: int) -> List[str]:
        """
        Single strategy: derive tracks from the artist's singles and albums, newest first, preferring solo tracks.
        """
        artist_id = self._find_artist_id(artist_name)
        if not artist_id:
            logging.warning(
                f"No exact artist match found for name: {artist_name}")
            return []

        try:
            ordered_album_ids = self._ordered_artist_album_ids(artist_id)
            solo_ids, other_ids = self._collect_track_ids_with_preference(
                artist_name, ordered_album_ids)

            # Prefer solo tracks, then fill with others
            result: List[str] = solo_ids[:maximum_tracks_per_artist]
            if len(result) < maximum_tracks_per_artist:
                needed = maximum_tracks_per_artist - len(result)
                result.extend(other_ids[:needed])
            return result
        except Exception as e:
            logging.error(
                f"Failed to collect album tracks for artist {artist_name} ({artist_id}). Error: {e}"
            )
            return []

    def update_playlist(self, playlist_id: str, list_of_track_ids: List[str]) -> bool:
        """
        Replace playlist items with provided track IDs. This is a single-path implementation:
        - Clear playlist via PUT /playlists/{id}/items with empty URIs
        - Add items in chunks via POST /playlists/{id}/items
        """
        if not list_of_track_ids:
            logging.warning("No track IDs provided to update the playlist.")
            return False

        uris = self._to_track_uris(list_of_track_ids)
        try:
            self._replace_playlist_items(playlist_id, uris)
            logging.info(
                f"Playlist with ID: {playlist_id} updated with {len(list_of_track_ids)} tracks.")
            return True
        except Exception as e:
            logging.error(
                f"Failed to update playlist with ID: {playlist_id}. Error: {e}")
            return False

    def generate_playlist(self, playlist_name: str) -> bool:
        """
        Create a new empty playlist using POST /me/playlists.
        """
        client = self._get_spotify_client()
        try:
            client._post("me/playlists", payload={"name": playlist_name})
            logging.info(f"Playlist created successfully: {playlist_name}")
            return True
        except Exception as e:
            logging.error(
                f"Failed to create playlist: {playlist_name}. Error: {e}")
            return False

    # --------------------------
    # Internal helpers - Search
    # --------------------------

    def _find_artist_id(self, artist_name: str) -> Optional[str]:
        """
        Resolve an artist ID using two-pass search:
        1) Primary: artist:"Original Name" with pagination, exact normalized match first, then containment heuristics.
        2) Fallback: artist:normalized_name if no candidate found in primary.
        """
        normalized_input = self._normalize_name(artist_name)

        # Pass 1: original quoted name
        cand = self._best_artist_candidate(
            self._search_artists(f'artist:"{artist_name.strip()}"'),
            normalized_input,
        )
        if cand:
            return cand

        # Pass 2: normalized name
        return self._best_artist_candidate(self._search_artists(f"artist:{normalized_input}"), normalized_input)

    def _search_artists(self, query: str) -> Iterable[JSONDict]:
        """
        Paginate artist search results with limit=10 up to SEARCH_MAX_PAGES pages.
        """
        client = self._get_spotify_client()
        offset = 0
        for _ in range(self.SEARCH_MAX_PAGES):
            results = client.search(
                q=query, type="artist", limit=self.SEARCH_LIMIT, offset=offset) or {}
            items = (results.get("artists") or {}).get(
                "items", [])  # type: ignore[assignment]
            for it in items or []:
                yield it
            if not items or len(items) < self.SEARCH_LIMIT:
                break
            offset += self.SEARCH_LIMIT

    def _best_artist_candidate(self, items: Iterable[JSONDict], normalized_input: str) -> Optional[str]:
        """
        Choose best artist candidate by:
        - exact normalized match first
        - then containment with minimum length difference
        """
        best_id: Optional[str] = None
        best_score: Optional[int] = None

        for item in items:
            name = item.get("name", "")
            cand_id = item.get("id")
            if not cand_id:
                continue
            norm = self._normalize_name(name)
            if norm == normalized_input:
                return cand_id
            if normalized_input in norm or norm in normalized_input:
                score = abs(len(norm) - len(normalized_input))
                if best_score is None or score < best_score:
                    best_score = score
                    best_id = cand_id

        return best_id

    @staticmethod
    def _normalize_name(s: str) -> str:
        """
        Normalize artist names to improve matching:
        - Unicode NFKD decompose and strip combining marks
        - Lowercase
        - Replace '&' with 'and'
        - Remove non-alphanumeric (except spaces)
        - Collapse whitespace
        - Drop leading 'the'
        """
        import unicodedata
        import re

        if not isinstance(s, str):
            return ""
        s = unicodedata.normalize("NFKD", s)
        s = "".join(c for c in s if not unicodedata.combining(c))
        s = s.lower()
        s = s.replace("&", " and ")
        s = re.sub(r"[^a-z0-9\s]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        if s.startswith("the "):
            s = s[4:].strip()
        return s

    # --------------------------------
    # Internal helpers - Albums/Tracks
    # --------------------------------

    def _ordered_artist_album_ids(self, artist_id: str) -> List[str]:
        """
        Return album IDs in desired order: recent singles first, then recent albums.
        """
        singles = self._fetch_artist_albums(artist_id, album_type="single")
        albums = self._fetch_artist_albums(artist_id, album_type="album")
        ordered_ids = [aid for aid, _ in singles] + [aid for aid, _ in albums]
        return ordered_ids

    def _fetch_artist_albums(self, artist_id: str, album_type: str) -> List[Tuple[str, datetime]]:
        """
        Fetch artist albums/singles and return (album_id, parsed_release_date), sorted desc by date.
        """
        client = self._get_spotify_client()
        items_with_date: List[Tuple[str, datetime]] = []

        offset = 0
        for _ in range(self.ALBUM_PAGE_MAX_PAGES):
            resp = client.artist_albums(
                artist_id, album_type=album_type, limit=self.ALBUM_PAGE_LIMIT, offset=offset
            ) or {}
            items: List[JSONDict] = resp.get("items", [])
            for a in items:
                aid = a.get("id")
                if not aid:
                    continue
                release_date = a.get("release_date", "0000-01-01")
                items_with_date.append(
                    (aid, self._parse_release_date(release_date)))
            if not items or len(items) < self.ALBUM_PAGE_LIMIT:
                break
            offset += self.ALBUM_PAGE_LIMIT

        items_with_date.sort(key=lambda t: t[1], reverse=True)
        return items_with_date

    def _collect_track_ids_with_preference(self, artist_name: str, album_ids: List[str]) -> Tuple[List[str], List[str]]:
        """
        Iterate album tracks in order of provided album IDs and split into:
        - solo track IDs (exact single-artist match)
        - other track IDs
        Deduplicate across albums.
        """
        client = self._get_spotify_client()
        target_name = self._normalize_name(artist_name)
        solo: List[str] = []
        other: List[str] = []
        seen: set[str] = set()

        for album_id in album_ids:
            offset = 0
            while True:
                tracks_resp = client.album_tracks(
                    album_id, limit=self.ALBUM_TRACK_PAGE_LIMIT, offset=offset) or {}
                items: List[JSONDict] = tracks_resp.get("items", [])
                if not items:
                    break

                for tr in items:
                    tid = tr.get("id")
                    if not tid or tid in seen:
                        continue
                    seen.add(tid)

                    artists = tr.get("artists", []) or []
                    artist_names = [self._normalize_name(
                        a.get("name", "")) for a in artists]
                    if len(artist_names) == 1 and artist_names[0] == target_name:
                        solo.append(tid)
                    else:
                        other.append(tid)

                if len(items) < self.ALBUM_TRACK_PAGE_LIMIT:
                    break
                offset += self.ALBUM_TRACK_PAGE_LIMIT

        return solo, other

    @staticmethod
    def _parse_release_date(val: str) -> datetime:
        """
        Parse Spotify release_date which can be YYYY, YYYY-MM, or YYYY-MM-DD.
        """
        for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
            try:
                return datetime.strptime(val, fmt)
            except Exception:
                continue
        return datetime.min

    # ------------------------------
    # Internal helpers - Playlists
    # ------------------------------

    def _to_track_uris(self, track_ids: List[str]) -> List[str]:
        """
        Convert raw track IDs to Spotify track URIs.
        """
        return [f"spotify:track:{tid}" for tid in track_ids if tid]

    def _replace_playlist_items(self, playlist_id: str, uris: List[str]) -> None:
        """
        Clear playlist by replacing with empty list, then append items in chunks.
        """
        client = self._get_spotify_client()
        # Clear
        client._put(f"playlists/{playlist_id}/items", payload={"uris": []})
        # Append chunks
        for i in range(0, len(uris), self.PLAYLIST_ITEMS_CHUNK_SIZE):
            chunk = uris[i: i + self.PLAYLIST_ITEMS_CHUNK_SIZE]
            client._post(
                f"playlists/{playlist_id}/items", payload={"uris": chunk})


def _preserve_seeded_at(token_info: JSONDict, previous: Optional[JSONDict]) -> JSONDict:
    """
    Ensure the "seeded_at" stamp survives write-backs. Spotipy rewrites the whole
    token blob on refresh and its token_info will not contain "seeded_at", so we
    copy it forward from the previously-cached blob when it is missing.
    """
    if token_info.get(SEEDED_AT_KEY):
        return token_info
    if previous and previous.get(SEEDED_AT_KEY):
        token_info = dict(token_info)
        token_info[SEEDED_AT_KEY] = previous[SEEDED_AT_KEY]
    return token_info


class FileCacheHandler(CacheHandler):
    """
    Cache handler that stores the token as JSON in a local file. Used for local
    development; the produced file is what scripts/seed-token.py uploads to the
    Kubernetes Secret.
    """

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath

    def get_cached_token(self) -> Optional[JSONDict]:
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return None
                return json.loads(content)
        except FileNotFoundError:
            logging.warning(f"Token cache file not found at: {self.filepath}")
            return None
        except json.JSONDecodeError as e:
            logging.error(
                f"Token cache at {self.filepath} is not valid JSON: {e}. "
                "It may be an old-format token; re-seed via scripts/seed-token.py.")
            return None
        except Exception as e:
            logging.error(f"Error reading token from cache: {e}")
            return None

    def save_token_to_cache(self, token_info: JSONDict) -> None:
        try:
            token_info = _preserve_seeded_at(token_info, self.get_cached_token())
            with open(self.filepath, "w", encoding="utf-8") as f:
                f.write(json.dumps(token_info))
        except Exception as e:
            logging.error(f"Error saving token to cache: {e}")

    def does_file_contain_data(self, file_path: str) -> bool:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return bool(f.read().strip())
        except FileNotFoundError:
            return False


class K8sSecretCacheHandler(CacheHandler):
    """
    Cache handler for in-cluster use. Reads the token from a Kubernetes Secret
    mounted as a read-only volume file (fast, no API/RBAC needed on the read
    path) and writes refreshed/rotated tokens back by patching the Secret via
    the Kubernetes API (the only operation requiring RBAC).

    The token is stored as JSON under `secret_key` inside the Secret.
    """

    def __init__(self, secret_name: str, secret_key: str, namespace: str,
                 mounted_file_path: str) -> None:
        self.secret_name = secret_name
        self.secret_key = secret_key
        self.namespace = namespace
        self.mounted_file_path = mounted_file_path

    def get_cached_token(self) -> Optional[JSONDict]:
        try:
            with open(self.mounted_file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return None
                return json.loads(content)
        except FileNotFoundError:
            logging.info(
                f"Token Secret not yet mounted/populated at: {self.mounted_file_path}. "
                "Seed it via scripts/seed-token.py.")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"Mounted token Secret is not valid JSON: {e}.")
            return None
        except Exception as e:
            logging.error(f"Error reading token from mounted Secret: {e}")
            return None

    def save_token_to_cache(self, token_info: JSONDict) -> None:
        try:
            token_info = _preserve_seeded_at(token_info, self.get_cached_token())
            api = self._load_incluster_client()
            namespace = self._resolve_namespace()
            body = {"stringData": {self.secret_key: json.dumps(token_info)}}
            api.patch_namespaced_secret(
                name=self.secret_name, namespace=namespace, body=body)
            logging.info(
                f"Persisted refreshed Spotify token to Secret '{self.secret_name}'.")
        except Exception as e:
            # Do not crash the run if write-back fails; the token is still valid
            # in memory for this run and will be refreshed again next time.
            logging.error(
                f"Failed to persist token to Secret '{self.secret_name}': {e}")

    def _resolve_namespace(self) -> str:
        if self.namespace:
            return self.namespace
        try:
            with open(
                "/var/run/secrets/kubernetes.io/serviceaccount/namespace",
                "r", encoding="utf-8",
            ) as f:
                return f.read().strip()
        except Exception:
            return "default"

    @staticmethod
    def _load_incluster_client():
        # Lazy import so local runs never require the kubernetes package.
        from kubernetes import client, config
        config.load_incluster_config()
        return client.CoreV1Api()
