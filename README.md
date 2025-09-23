# Berghain Kantine Playlist Generator

This project automatically generates a Spotify playlist based on the artists scheduled to perform at Berghain's Kantine. It scrapes the event listings from the Berghain website, finds the top tracks for each artist on Spotify, and creates or updates a playlist with those tracks.

## Requirements

- Python 3.12+
- Docker (for containerized execution)

## Configuration

The application requires Spotify API credentials to function. You can get these by creating a new app in your [Spotify Developer Dashboard](https://developer.spotify.com/documentation/web-api/concepts/apps).

Create a `.env` file in the root of the project with the following content:

```env
# Spotify API Credentials
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:9090

# Optional: Customize script behavior
PARALLEL_WORKERS=8
MAX_TRACK_NUMBER_PER_ARTIST=3
PLAYLIST_NAME=Berghain Am Kantine: Next Up
```

### Environment Variables

| Variable                      | Required | Description                                                                                                           | Default                       |
|------------------------------|----------|-----------------------------------------------------------------------------------------------------------------------|-------------------------------|
| `SPOTIFY_CLIENT_ID`          | Yes      | Spotify application client ID.                                                                                        | —                             |
| `SPOTIFY_CLIENT_SECRET`      | Yes      | Spotify application client secret.                                                                                    | —                             |
| `SPOTIFY_REDIRECT_URI`       | Yes      | Redirect URI configured in your Spotify app. Must be reachable; if running in Docker, ensure your host matches port. | Example: `http://127.0.0.1:9090` |
| `PLAYLIST_NAME`              | No       | Name of the Spotify playlist to create or update.                                                                     | `Berghain Am Kantine: Next Up` |
| `PARALLEL_WORKERS`           | No       | Number of concurrent workers for scraping event details.                                                              | `8`                           |
| `MAX_TRACK_NUMBER_PER_ARTIST`| No       | Maximum number of top tracks to add per artist.                                                                       | `3`                           |

## Usage

### Running with Docker (Recommended)

The easiest way to run the script is using Docker Compose. This method handles all dependencies and ensures a consistent environment.

1. **Build and run the container:**

    ```bash
    docker-compose up --build
    ```

    The first time you run this, you will be prompted to authenticate with Spotify. Open the URL printed in the console, grant access, and you will be redirected to the `SPOTIFY_REDIRECT_URI`. The authentication token will be saved in the `./cache` directory, so you won't need to authenticate again unless the token expires.

### Running Locally

You can also run the script directly on your machine.

1. **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

2. **Run the script:**

    ```bash
    python main.py
    ```

    Similar to the Docker method, you will need to complete the Spotify OAuth flow in your browser upon first run.
