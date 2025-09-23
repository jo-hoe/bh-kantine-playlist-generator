
from enum import auto
from functools import lru_cache
import logging
from math import e, log
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import CacheHandler
from app.playlist.abstract_playlist_generator import AbstractPlaylistGenerator


class FileCacheHandler(CacheHandler):
    """
    A cache handler that stores tokens in a file.
    """

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath

    def get_cached_token(self):
        try:
            with open(self.filepath, "r") as f:
                token_info = f.read()
                return eval(token_info)  # Convert string back to dictionary
        except FileNotFoundError:
            logging.warning(f"Token cache file not found at: {self.filepath}")
            return None
        except Exception as e:
            logging.error(f"Error reading token from cache: {e}")
            return None

    def save_token_to_cache(self, token_info):
        try:
            with open(self.filepath, "w") as f:
                f.write(str(token_info))  # Convert dictionary to string
        except Exception as e:
            logging.error(f"Error saving token to cache: {e}")


class SpotifyPlaylistGenerator(AbstractPlaylistGenerator):

    TRACK_ID_LIMIT = 50  # Spotify API limit for track IDs per request
    REQUIRED_SCOPES = "user-library-read,playlist-read-private,playlist-modify-private,playlist-modify-public"

    def __init__(self, playlist_name: str,
                 maximum_tracks_per_artist: int,
                 token_cache_file_path: str,
                 is_running_in_container: bool) -> None:
        super().__init__(playlist_name, maximum_tracks_per_artist)
        self._token_cache_file_path = token_cache_file_path
        self._is_running_in_container = is_running_in_container

        self._init_token_cache()

    def _init_token_cache(self) -> None:
        if not self._does_file_exist(self._token_cache_file_path) or self._is_file_empty(self._token_cache_file_path):
            logging.info(
                f"Token cache file is missing or empty at: {self._token_cache_file_path}. A new file will be created upon authentication.")

        self._get_spotify_client()

    def _does_file_exist(self, file_path: str) -> bool:
        try:
            with open(file_path, 'r'):
                return True
        except FileNotFoundError:
            return False

    def _is_file_empty(self, file_path: str) -> bool:
        try:
            with open(file_path, 'r') as f:
                content = f.read().strip()
                return not bool(content)
        except FileNotFoundError:
            return False

    @lru_cache(maxsize=1)
    def _get_spotify_client(self) -> spotipy.Spotify:
        # setup Spotify API
        cache_handler = FileCacheHandler(filepath=self._token_cache_file_path)
        automatically_open_browser = not self._is_running_in_container

        # check if env variables are set
        if cache_handler.get_cached_token() not in [None, ""]:
            logging.info(
                "Environment variables for Spotify credentials not fully set - using cached token.")
            # rely on cached token only
            return spotipy.Spotify(auth_manager=SpotifyOAuth(scope=self.REQUIRED_SCOPES, cache_handler=cache_handler))
        elif all([var in os.environ for var in ["SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET", "SPOTIPY_REDIRECT_URI"]]):
            logging.info(
                "Using Spotify credentials from environment variables.")
            return spotipy.Spotify(auth_manager=SpotifyOAuth(scope=self.REQUIRED_SCOPES,
                                                             client_id=os.environ["SPOTIPY_CLIENT_ID"],
                                                             client_secret=os.environ["SPOTIPY_CLIENT_SECRET"],
                                                             redirect_uri=os.environ["SPOTIPY_REDIRECT_URI"],
                                                             open_browser=automatically_open_browser))
        else:
            logging.error("No valid Spotify authentication method available.")
            raise EnvironmentError(
                "Spotify credentials not set and no cached token available.")

    def get_playlist_id_by_name(self, playlist_name: str) -> str | None:
        # returns the playlist ID if found, otherwise None
        client = self._get_spotify_client()
        playlists = client.current_user_playlists()
        for playlist in playlists['items']:
            if playlist['name'] == playlist_name:
                return playlist['id']
        return None

    def get_top_tracks_for_artist(self, artist_name: str, maximum_tracks_per_artist: int) -> list[str]:
        client = self._get_spotify_client()
        results = client.search(q='artist:' + artist_name, type='artist')
        items = results['artists']['items']
        if not items:
            logging.warning(f"No artist found for name: {artist_name}")
            return []

        # get artist ID of artist with exact name match
        artist_id = None
        for item in items:
            if item['name'].lower() == artist_name.lower():
                artist_id = item['id']
                break
        if not artist_id:
            logging.warning(
                f"No exact artist match found for name: {artist_name}")
            return []

        top_tracks_data = client.artist_top_tracks(artist_id)
        if not top_tracks_data or 'tracks' not in top_tracks_data:
            logging.warning(f"No top tracks found for artist: {artist_name}")
            return []

        # Prefer tracks where only the given artist is credited
        solo_tracks = []
        other_tracks = []
        for track in top_tracks_data['tracks']:
            artist_names = [a['name'].lower() for a in track['artists']]
            if len(track['artists']) == 1 and artist_names[0] == artist_name.lower():
                solo_tracks.append(track['id'])
            else:
                other_tracks.append(track['id'])

        # Fill up to maximum_tracks_per_artist, preferring solo tracks
        track_ids = solo_tracks[:maximum_tracks_per_artist]
        if len(track_ids) < maximum_tracks_per_artist:
            needed = maximum_tracks_per_artist - len(track_ids)
            track_ids += other_tracks[:needed]

        return track_ids

    def update_playlist(self, playlist_id: str, list_of_track_ids: list[str]) -> bool:
        # Updates the playlist with the given track IDs
        # The new track IDs should replace any existing tracks in the playlist
        if not list_of_track_ids:
            logging.warning("No track IDs provided to update the playlist.")
            return False

        client = self._get_spotify_client()
        try:
            # Retrieve all tracks from the playlist using pagination
            while True:
                response = client.playlist_tracks(
                    playlist_id, limit=100)
                items = response.get('items', [])
                if not items:
                    break
                client.playlist_remove_all_occurrences_of_items(
                    playlist_id, [item['track']['id'] for item in items])

            for i in range(0, len(list_of_track_ids), self.TRACK_ID_LIMIT):
                chunk = list_of_track_ids[i:i + self.TRACK_ID_LIMIT]
                client.playlist_add_items(playlist_id, chunk)

            logging.info(
                f"Playlist with ID: {playlist_id} updated with {len(list_of_track_ids)} tracks.")
            return True
        except Exception as e:
            logging.error(
                f"Failed to update playlist with ID: {playlist_id}. Error: {e}")
            return False

    def generate_playlist(self, playlist_name: str) -> bool:
        # Generates an empty playlist with the given name
        client = self._get_spotify_client()
        try:
            client.user_playlist_create(user=client.current_user()[
                                        'id'], name=playlist_name)
            logging.info(f"Playlist created successfully: {playlist_name}")
            return True
        except Exception as e:
            logging.error(
                f"Failed to create playlist: {playlist_name}. Error: {e}")
            return False
