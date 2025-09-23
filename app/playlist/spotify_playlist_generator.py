
from functools import lru_cache
import logging
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
            return None
        except Exception as e:
            print(f"Error reading token from cache: {e}")
            return None

    def save_token_to_cache(self, token_info):
        try:
            with open(self.filepath, "w") as f:
                f.write(str(token_info))  # Convert dictionary to string
        except Exception as e:
            print(f"Error saving token to cache: {e}")


class SpotifyPlaylistGenerator(AbstractPlaylistGenerator):

    def __init__(self, playlist_name: str, maximum_tracks_per_artist: int, token_cache_file_path: str) -> None:
        super().__init__(playlist_name, maximum_tracks_per_artist)
        self._token_cache_file_path = token_cache_file_path

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
        scope = "user-library-read,playlist-read-private,playlist-modify-private,playlist-modify-public"
        cache_handler = FileCacheHandler(filepath=self._token_cache_file_path)
        return spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope, cache_handler=cache_handler))

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

        artist_id = items[0]['id']
        top_tracks_data = client.artist_top_tracks(artist_id)
        top_tracks = top_tracks_data['tracks'][:maximum_tracks_per_artist]
        track_ids = [track['id'] for track in top_tracks]
        return track_ids

    def update_playlist(self, playlist_id: str, list_of_track_ids: list[str]) -> bool:
        # Updates the playlist with the given track IDs
        # The new track IDs should replace any existing tracks in the playlist
        client = self._get_spotify_client()
        try:
            client.playlist_replace_items(playlist_id, list_of_track_ids)
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
            client.user_playlist_create(user=client.current_user()['id'], name=playlist_name)
            logging.info(f"Playlist created successfully: {playlist_name}")
            return True
        except Exception as e:
            logging.error(f"Failed to create playlist: {playlist_name}. Error: {e}")
            return False