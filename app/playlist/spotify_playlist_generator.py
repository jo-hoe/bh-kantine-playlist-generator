
from functools import lru_cache
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

    def __init__(self, playlist_name: str, token_cache_file_path: str) -> None:
        super().__init__(playlist_name)
        self._token_cache_file_path = token_cache_file_path

    @lru_cache(maxsize=1)
    def _get_spotify_client(self) -> spotipy.Spotify:
        # setup Spotify API
        scope = "user-library-read,playlist-read-private,playlist-modify-private,playlist-modify-public"
        cache_handler = FileCacheHandler(filepath=self._token_cache_file_path)
        return spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope, cache_handler=cache_handler))

    def get_playlist_id_by_name(self, playlist_name: str) -> str | None:
        client = self._get_spotify_client()

        playlists = client.current_user_playlists()
        for playlist in playlists['items']:
            if playlist['name'] == playlist_name:
                return playlist['id']

        return ''
