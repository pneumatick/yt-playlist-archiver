# YouTube Playlist Archiver

A command-line Python tool for retrieving, archiving, searching, and exporting YouTube playlist data using the **YouTube Data API v3**.
The program stores playlist metadata and video information locally in a **SQLite database**, allowing offline inspection, searching, and change tracking over time.

---

## Features

* Authenticate with YouTube using **OAuth 2.0**
* Retrieve full or partial playlist contents
* Archive playlists locally into a SQLite database
* Detect playlist updates using ETags
* Incrementally update playlists when new videos are added
* Search videos locally by fuzzy title matching
* Export playlists to CSV (videos + metadata)
* Import playlists from CSV
* Delete locally stored playlists
* Command-line interface for automation and scripting

---

## Requirements

* Python 3.9+
* Google Cloud project with **YouTube Data API v3** enabled
* OAuth client credentials file (`client_secret.json`)

Python dependencies:

```bash
pip install google-api-python-client google-auth google-auth-oauthlib pandas
```

---

## Setup

1. Create OAuth credentials in the Google Cloud Console.
2. Download the OAuth client secrets file and rename it:

```
client_secret.json
```

3. Place the file in the project directory.
4. Run the program once — the browser OAuth flow will appear and generate:

```
token.json
```

This token will be reused automatically on future runs.

---

## Usage

Retrieve a playlist:

```bash
python main.py --id PLAYLIST_ID
```

Retrieve the first N items:

```bash
python main.py --id PLAYLIST_ID --number 25
```

Archive a playlist locally:

```bash
python main.py --archive PLAYLIST_ID
```

List archived playlists:

```bash
python main.py --list
```

Open a locally archived playlist:

```bash
python main.py --open PLAYLIST_ID
```

Search for a video:

```bash
python main.py --search PLAYLIST_ID "video title"
```

Export playlist to CSV:

```bash
python main.py --export PLAYLIST_ID
```

Import playlist from CSV:

```bash
python main.py --import PLAYLIST_FILENAME
```

Delete playlist from local database:

```bash
python main.py --delete PLAYLIST_ID
```

---

## Database

The program automatically creates a local SQLite database:

```
playlists.db
```

Tables:

* `playlist_data` — playlist metadata
* `playlist_items` — playlist positions and timestamps
* `videos` — video titles and status

---

## Notes

* The program supports both public and private playlists (when authenticated with the correct YouTube channel).
* Playlist updates are detected using **ETag comparison** to avoid unnecessary API requests.
* Exported playlists can be transferred between machines and imported back into the database.

---
