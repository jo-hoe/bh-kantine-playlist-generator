import os
from datetime import datetime
from app.crawler import get_event_date_details_for_url, KANTINE_PROGRAM_URL
from app.playlist.spotify_playlist_generator import SpotifyPlaylistGenerator


if __name__ == "__main__":
    import logging
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)

    playlist_name = os.environ.get(
        "PLAYLIST_NAME", "Kantine Am Berghain: Next Up")
    max_track_number_per_artist = int(
        os.environ.get("MAX_TRACK_NUMBER_PER_ARTIST", 3))
    is_running_in_container = os.environ.get(
        "IS_RUNNING_IN_CONTAINER", "false").lower() == "true"

    tracks = get_event_date_details_for_url(KANTINE_PROGRAM_URL)

    generator = SpotifyPlaylistGenerator(
        playlist_name,
        max_track_number_per_artist,
        os.path.join("cache", "token_cache.txt"),
        is_running_in_container)

    generator.process(tracks)
