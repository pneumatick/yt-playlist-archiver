# YouTube Playlist Archiver

A Python tool for retrieving, archiving, searching, and exporting YouTube playlist data using the **YouTube Data API v3**.
The program stores playlist metadata and video information locally in a **SQLite database**, allowing offline inspection, searching, and change tracking over time.

---

## Features

* GUI interface (PySide6) and command-line interface
* Authenticate with YouTube using **OAuth 2.0**
* Archive playlists locally into a SQLite database
* Incrementally update playlists when new videos are added
* Search videos locally (FTS5) both within and across playlists
* Import and export playlists to share directly with others
* Detect playlist updates using ETags to conserve API requests and reduce network traffic

---

## Requirements

* Python 3.14.x
* Poetry
* Google Cloud project with **YouTube Data API v3** enabled
* OAuth client credentials file (`client_secret.json`)

## Installation

### Users

Users can install the latest release as a discrete executable [here](https://github.com/pneumatick/yt-playlist-archiver/releases).

To run the program, simply run

```bash
./yt-dp [FLAG]
```

where `[FLAG]` is the flag you choose to run the program with.

### Developers

It is recommended that developers install and use Poetry to manage packages, avoid conflicts between them, and ensure that deprecations do not alter the program's functionality. To install the necessary packages/modules, run

```bash
poetry install
```

Then run the program with

```bash
poetry run ./yt-pa.py [FLAG]
```

where `[FLAG]` is the flag you choose to run the program with. Otherwise, dependencies must be installed manually.

---

## Setup

In order to prevent the need of requiring payment for this program, users must set up their own Google Cloud project in order to manage their own API useage and any fees incurred (unlikely unless many massive playlists are being archived/checked daily). Documentation relating to the steps below can be found [here](https://developers.google.com/workspace/guides/get-started).

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

This token will be reused automatically on future runs, so logging in again will not be necessary until the token expires.

---

## Usage

Launch GUI (will be the default mode for the majority of users):

```bash
./yt-pa --gui
```

### Command-line interface

Retrieve a playlist:

```bash
./yt-pa --id PLAYLIST_ID
```

Retrieve the first N items:

```bash
./yt-pa --id PLAYLIST_ID --number 25
```

Archive a playlist locally:

```bash
./yt-pa --archive PLAYLIST_ID
```

List archived playlists:

```bash
./yt-pa --list
```

Open a locally archived playlist:

```bash
./yt-pa --open PLAYLIST_ID
```

Search for a video:

```bash
./yt-pa --search PLAYLIST_ID "video title"
```

Export playlist to CSV:

```bash
./yt-pa --export PLAYLIST_ID
```

Import playlist from CSV:

```bash
./yt-pa --import PLAYLIST_FILENAME
```

Delete playlist from local database:

```bash
./yt-pa --delete PLAYLIST_ID
```

---

## Database

The program automatically creates a local SQLite database:

```
playlists.db
```

Tables:

* `playlist_data` — playlist metadata
* `playlist_items` — videos within a given playlist
* `videos` — video titles and status
* `videos_fts` - virtual table for video search queries (linked to `videos` table, updated by triggers)

---

## Notes

* The program supports both public and private playlists (when authenticated with a YouTube channel that has permission to view them).
* Playlist updates are detected using **ETag comparison** to avoid unnecessary API requests.
* Exported playlists can be transferred between machines and imported back into the database. This is mostly for sharing playlists between users or for data analysis purposes. If transfering or backing up all archived info is desired, simply copy and paste `playlists.db` into the desired location.

---
