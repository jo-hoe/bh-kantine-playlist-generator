
from abc import ABC
import abc
from datetime import datetime
import logging


class AbstractPlaylistGenerator(ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, playlist_name: str, maximum_tracks_per_artist: int) -> None:
        super().__init__()
        self._playlist_name = playlist_name
        self._maximum_tracks_per_artist = maximum_tracks_per_artist

    @abc.abstractmethod
    def get_playlist_id_by_name(self, playlist_name: str) -> str | None:
        # returns the playlist ID if found, otherwise None
        raise NotImplementedError("Subclasses must implement this method.")

    @abc.abstractmethod
    def get_top_tracks_for_artist(self, artist_name: str, maximum_tracks_per_artist: int) -> list[str]:
        raise NotImplementedError("Subclasses must implement this method.")

    @abc.abstractmethod
    def update_playlist(self, playlist_id: str, list_of_track_ids: list[str]) -> bool:
        raise NotImplementedError("Subclasses must implement this method.")

    @abc.abstractmethod
    def generate_playlist(self, playlist_name: str) -> bool:
        # Generates an empty playlist with the given name
        raise NotImplementedError("Subclasses must implement this method.")

    def process(self, artists_performance_dates: tuple[datetime, str]) -> bool:
        playlist_id = self.get_playlist_id_by_name(self._playlist_name)
        if not playlist_id:
            if self.generate_playlist(self._playlist_name):
                playlist_id = self.get_playlist_id_by_name(self._playlist_name)

        if not playlist_id:
            logging.error(
                f"Could not find or create playlist with name: {self._playlist_name}")
            return False

        logging.info(
            f"Using playlist ID: {playlist_id} for playlist name: {self._playlist_name}")

        all_track_ids = []
        for performance_date, artist_name in artists_performance_dates:
            track_ids = self.get_top_tracks_for_artist(
                artist_name, self._maximum_tracks_per_artist)
            if track_ids:
                all_track_ids.extend(track_ids)
            else:
                logging.warning(
                    f"No tracks found for artist: {artist_name}")

        return self.update_playlist(playlist_id, all_track_ids)
