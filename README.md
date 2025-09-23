# bh-kantine-playlist-generator

### Secrets

The script assumes that either a token cache file exists or that the following environment variables are set:

```txt
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret
SPOTIPY_REDIRECT_URI=your_redirect_uri (e.g. 'http://127.0.0.1:9090')
```

In case environment variables are used, the app will open a local HTTP server to handle the OAuth redirect and obtain the token.
You can get these values by creating a Spotify Developer account and [creating a new app](https://developer.spotify.com/documentation/web-api/concepts/apps).

