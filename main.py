import os
import logging
import sys
from dotenv import load_dotenv

from app.crawler import URL_MAPPING, get_event_date_details_for_url
from app.playlist.spotify_playlist_generator import SpotifyPlaylistGenerator


def main():
    # Load environment variables from .env file if not in Docker
    is_running_in_container = os.environ.get(
        "IS_RUNNING_IN_CONTAINER", "false").lower() == "true"

    if not is_running_in_container:
        load_dotenv()

    token_cache_path = os.environ.get(
        "TOKEN_CACHE_FILE_PATH", os.path.join("cache", "token_cache.txt"))
    token_storage = os.environ.get("TOKEN_STORAGE", "file").lower()
    token_secret_name = os.environ.get("TOKEN_SECRET_NAME", "spotify-token")
    token_secret_key = os.environ.get("TOKEN_SECRET_KEY", "token_cache.json")
    token_secret_namespace = os.environ.get("TOKEN_SECRET_NAMESPACE", "")
    playlist_name = os.environ.get(
        "PLAYLIST_NAME", "Kantine Am Berghain: Next Up")
    max_track_number_per_artist = int(
        os.environ.get("MAX_TRACK_NUMBER_PER_ARTIST", 3))
    url_key = os.environ.get("LOCATION", "kantine").lower()
    if url_key not in URL_MAPPING:
        raise ValueError(
            f"Invalid LOCATION '{url_key}' provided. Valid options are: {list(URL_MAPPING.keys())}")

    tracks = get_event_date_details_for_url(
        URL_MAPPING[url_key])

    generator = SpotifyPlaylistGenerator(
        playlist_name,
        max_track_number_per_artist,
        token_cache_path,
        is_running_in_container,
        token_storage=token_storage,
        token_secret_name=token_secret_name,
        token_secret_key=token_secret_key,
        token_secret_namespace=token_secret_namespace)

    success = generator.process(tracks)

    if not success:
        raise RuntimeError("Failed to update the playlist.")


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)

    try:
        main()
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        sys.exit(1)

    logging.info("Script completed successfully.")
    sys.exit(0)
