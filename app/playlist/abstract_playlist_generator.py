
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
        # Updates the playlist with the given track IDs
        # The new track IDs should replace any existing tracks in the playlist
        raise NotImplementedError("Subclasses must implement this method.")

    @abc.abstractmethod
    def generate_playlist(self, playlist_name: str) -> bool:
        # Generates an empty playlist with the given name
        raise NotImplementedError("Subclasses must implement this method.")

    def process(self, artists_performance_dates: list[tuple[datetime, str]]) -> bool:
        # ordered list of by performance date
        artists_performance_dates.sort(key=lambda x: x[0])

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
        for _, artist_name in artists_performance_dates:
            track_ids = self.get_top_tracks_for_artist(
                artist_name, self._maximum_tracks_per_artist)
            if track_ids:
                all_track_ids.extend(track_ids)
            else:
                logging.warning(
                    f"No tracks found for artist: {artist_name}")

        # Filter out duplicates while preserving order
        unique_track_ids = list(dict.fromkeys(all_track_ids))
        duplicates_count = len(all_track_ids) - len(unique_track_ids)
        if duplicates_count > 0:
            logging.info(f"Filtered out {duplicates_count} duplicate track(s)")

        return self.update_playlist(playlist_id, unique_track_ids)
