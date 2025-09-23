import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.crawler import get_all_event_date_urls, get_event_date_details
from app.playlist.spotify_playlist_generator import SpotifyPlaylistGenerator


if __name__ == "__main__":
    import logging
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)

    event_date_urls = get_all_event_date_urls()
    tracks: list[tuple[datetime, str]] = []
    max_workers = int(os.environ.get("PARALLEL_WORKERS", 8))
    max_track_number_per_artist = int(
        os.environ.get("MAX_TRACK_NUMBER_PER_ARTIST", 3))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(
            get_event_date_details, url): url for url in event_date_urls}
        for future in as_completed(future_to_url):
            details = future.result()
            tracks.extend(details)

    generator = SpotifyPlaylistGenerator(
        "Berghain Am Kantine: Next Up", max_track_number_per_artist, os.path.join("cache", "token_cache.txt"))

    generator.process(tracks)
