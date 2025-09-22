
from abc import ABC


class AbstractPlaylistGenerator(ABC):

    def __init__(self, playlist_name: str) -> None:
        super().__init__()
        self._playlist_name = playlist_name

    def get_playlist_id_by_name(self, playlist_name: str) -> str | None:
        # returns the playlist ID if found, otherwise None
        raise NotImplementedError("Subclasses must implement this method.")

    def get_top_tracks_for_artist(self, artist_name: str, max_tracks: int) -> list[str]:
        raise NotImplementedError("Subclasses must implement this method.")

    def generate_playlist(self, list_of_track_ids: list[str]) -> bool:
        raise NotImplementedError("Subclasses must implement this method.")
