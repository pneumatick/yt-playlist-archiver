"""
YouTube Playlist Archiver - A Python module for archiving YouTube playlists to SQLite databases.

This module provides functionality to:
    - Authenticate with the YouTube Data API v3 via OAuth 2.0
    - Archive entire playlists or retrieve a specified number of items
    - Store playlist and video data in SQLite with full-text search support (FTS5)
    - Track playlist changes using ETags
    - Export/import playlist data as CSV files

Usage:
    from archiver import Archiver
    archiver = Archiver()
    archiver.authenticate()
    archiver.archive_playlist("playlist_id")

Author: pneumatick
"""

import os
import sqlite3
import datetime
import pandas as pd

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow

# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret. You can acquire an OAuth 2.0 client ID and client secret from
# the {{ Google Cloud Console }} at
# {{ https://cloud.google.com/console }}.
CLIENT_SECRETS_FILE = 'client_secret.json'

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account.
SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

# Table columns
PLAYLIST_ITEMS_COLS = ['p_id', 'vid_id', 'position', 'added']
VIDEOS_COLS = ['vid_id', 'title', 'status']

# NOTE: Consider renaming to InfoManager (more accurate and descriptive)
class Archiver:
    """Singleton class for managing YouTube playlist archival operations.

    The Archiver class provides a singleton interface for interacting with the
    YouTube Data API v3, storing data in SQLite, and performing various archival
    operations on YouTube playlists including adding, updating, deleting, and searching.

    Attributes:
        _instance (Archiver): Singleton instance of the class.
        _youtube: Cached YouTube API service object.
        _conn: SQLite database connection.
        _cursor: SQLite database cursor.

    Example:
        >>> archiver = Archiver()
        >>> archiver.authenticate()
        >>> archiver.archive_playlist("PLxxx")
    """

    _instance = None
    _instance = None

    # Global YouTube API variables
    _youtube = None

    # Global SQLite3 variables
    _conn = None
    _cursor = None

    def __init__(self):
        """Initialize the Archiver singleton and create database tables.

        Called after singleton instance creation to set up the database connection
        and create required tables (playlist_data, playlist_items, videos, videos_fts)
        with triggers for full-text search synchronization.

        Note: This method is automatically called when creating a new Archiver instance
            via __new__. The singleton pattern ensures only one Archiver exists.
        """
        self._instantiate_db()

    def __new__(cls):
        """Create or return the singleton instance of the class.

        Implements the singleton pattern by ensuring only one instance of Archiver
        ever exists. Subsequent calls to create an Archiver will return the same
        cached instance instead of creating a new one.

        Returns:
            Archiver: The existing singleton instance if it exists, otherwise creates a new one.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __del__(self):
        """Destructor called when the Archiver instance is being garbage collected.

        Closes the SQLite database connection to free up resources. Note that in a
        typical application lifecycle, this may not be called unless the program exits
        normally without explicit cleanup.

        Example:
            archiver = Archiver()
            # ... use archiver ...
            del archiver  # Triggers this method
        """
        print("Closing database...")
        self._conn.close()

    def _get_authenticated_service(self):
        """Authenticate with Google OAuth 2.0 and return a YouTube API service object.

        This method handles the OAuth 2.0 authentication flow, including:
        - Loading existing credentials from token.json if available
        - Refreshing expired tokens using the refresh_token
        - Prompting for browser authorization when no valid credentials exist
        - Saving new credentials to token.json for subsequent use

        Args:
            _self: Unused first argument required by non-static method definition.

        Returns:
            googleapiclient.discovery.Resource: The YouTube API v3 service object ready for API calls.

        Note:
            OAuth 2.0 client credentials must be configured in client_secret.json before first use.
        """
        credentials = None

        # Load token if it exists
        if os.path.exists("token.json"):
            credentials = Credentials.from_authorized_user_file("token.json", SCOPES)

        # Request login when credentials are nonexistent or expired
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
                credentials = flow.run_local_server(port=0)

            # Save token for subsequent use
            with open("token.json", "w") as token:
                token.write(credentials.to_json())

        return build(API_SERVICE_NAME, API_VERSION, credentials = credentials)
    
    def authenticate(self):
        """Authenticate with YouTube API and cache the service object.

        This method initializes the cached YouTube API service by calling _get_authenticated_service,
        storing the result in self._youtube for subsequent use. Call this method before
        performing any archival operations to ensure the YouTube API is properly connected.

        Example:
            archiver = Archiver()
            archiver.authenticate()  # Connects to YouTube API
            archiver.archive_playlist("PLxxx")

        Note:
            Requires that client_secret.json is configured in the current directory.
        """
        self._youtube = self._get_authenticated_service()

    '''
    # Get the API key from the specified text file
    def get_api_key(path="secrets.txt"):
        try:
            with open(path, 'r') as f:
                key = f.read().strip()
                return key
        except Exception as e:
            print(f"An error occured while attempting to get API key: {e}")
            return None
    '''

    def _get_playlist_page(self, playlist_id, n_items=50, next_page=None):
        """Retrieve a page of items from a YouTube playlist.

        Makes an API request to fetch up to `n_items` (maximum 50 per Google's limits)
        from the specified playlist. If a next_page token is provided, continues fetching
        from that point in the playlist.

        Args:
            playlist_id (str): The YouTube playlist ID.
            n_items (int): Maximum number of items to retrieve (1-50). Defaults to 50.
            next_page (str, optional): The nextPageToken from a previous response for pagination.

        Returns:
            dict or None: The API response containing 'items' key if successful, None otherwise.
        """
        if n_items < 1 or n_items > 50:
            print(f"Cannot retrieve {n_items} list items (range 1 - 50)...")
            return None

        if not next_page:
            request = self._youtube.playlistItems().list(
                part="snippet,contentDetails,status",
                playlistId=playlist_id,
                maxResults=n_items
            )
        else:
            request = self._youtube.playlistItems().list(
                part="snippet,contentDetails,status",
                playlistId=playlist_id,
                maxResults=n_items,
                pageToken=next_page
            )

        try:
            response = request.execute()
        except HttpError as e:
            print(f"YouTube API error ({e.status_code}): {e.reason}")
            return None

        return response

    @staticmethod
    def print_playlist_response(response):
        """Print all video items from a YouTube API playlist response.

        Iterates through the response items and prints each video's position, title,
        and ID to standard output in a numbered list format.

        Args:
            response (dict): The playlistItems.list() API response containing an 'items' key.

        Example:
            >>> response = archiver._youtube.playlistItems().list(...).execute()
            >>> Archiver.print_playlist_response(response)
            0: Video Title: Something, Video ID: abc123
            1: Video Title: Something else, Video ID: def456
        """
        for item in response['items']:
            video_title = item['snippet']['title']
            video_id = item['contentDetails']['videoId']
            position = item['snippet']['position']
            print(f"{position}: Video Title: {video_title}, Video ID: {video_id}")

    def _archive_playlist_response(self, playlist_id, response):
        """Archive items from a YouTube playlist API response to SQLite database.

        Processes each item in the response, extracting video metadata and inserting
        it into both the playlist_items table and videos table (avoiding duplicates).

        Args:
            playlist_id (str): The YouTube playlist ID for which items are being archived.
            response (dict): The API response containing 'items' key with video data.

        Raises:
            sqlite3.IntegrityError: Caught when a video already exists in the database,
                printing a message and skipping that video.
        """
        for item in response['items']:
            video_title = item['snippet']['title']
            video_id = item['contentDetails']['videoId']
            position = item['snippet']['position']
            status = item['status']['privacyStatus']
            print(f"{position}: Video Title: {video_title}, Video ID: {video_id}")
            now = datetime.datetime.now() 
            try:
                self._cursor.execute(
                    '''
                        INSERT INTO playlist_items
                        (p_id, vid_id, position, added) 
                        VALUES (?, ?, ?, ?) 
                    ''', 
                    (playlist_id, video_id, position, int(now.timestamp()))
                )
            except sqlite3.IntegrityError as e:
                print("Video already in playlist. Skipping...")
            try:
                self._cursor.execute(
                    '''
                        INSERT INTO videos
                        (vid_id, title, status) VALUES (?, ?, ?)
                    ''',
                    (video_id, video_title, status)
                )
            except sqlite3.IntegrityError as e:
                print("Video has been stored previously. Skipping...")

    def get_entire_playlist(self, playlist_id, behavior):
        """Retrieve or print all items from a YouTube playlist with pagination.

        Fetches the complete contents of a playlist by paginating through results until
        no more pages remain. The `behavior` parameter determines how each page is handled:
        - "print": Prints video titles and IDs to console
        - "archive": Stores items in the SQLite database via _archive_playlist_response

        Args:
            playlist_id (str): The YouTube playlist ID.
            behavior (str): Either "print" or "archive". Any other value triggers an error.

        Returns:
            None
        """
        end_reached = False

        response = self._get_playlist_page(playlist_id)
        while not end_reached:
            if not response:
                print("No response received...")
                return

            # Handle the response
            if behavior == "print":
                self.print_playlist_response(response)
            elif behavior == "archive":
                self._archive_playlist_response(playlist_id, response)
            else:
                print(f"Unknown behavior specified: {behavior}")
                return

            # Get the next page if possible, otherwise end loop
            if "nextPageToken" in response:
                nextPageToken = response["nextPageToken"]
                response = self._get_playlist_page(
                    playlist_id, 
                    next_page=nextPageToken
                )
            else:
                end_reached = True
                continue

        return

    def get_n_playlist_items(self, playlist_id, n_items):
        """Retrieve a specified number of items from a YouTube playlist.

        Fetches up to `n_items` videos from the playlist (must be <= 50 per Google's limits).
        If n_items exceeds 50, fetches all available items and prints them. Otherwise,
        retrieves exactly n_items items and prints them.

        Args:
            playlist_id (str): The YouTube playlist ID.
            n_items (int): Number of items to retrieve (must be >= 0).

        Returns:
            None
        """
        if n_items < 0:
            return
        elif n_items <= 50:
            response = self._get_playlist_page(playlist_id, n_items=n_items)
            self.print_playlist_response(response)
            return

        # Getting more than 50 items
        end_reached = False

        response = self._get_playlist_page(playlist_id)
        n_items -= 50
        while not end_reached:
            if not response:
                print("No response received...")
                return

            # Print playlist items for now
            self.print_playlist_response(response)
            # Get the next page if possible, otherwise end loop
            if "nextPageToken" in response and n_items > 0:
                nextPageToken = response["nextPageToken"]
                # Get max items (50) at a time while n > 50
                response = self._get_playlist_page(
                    self._youtube, 
                    playlist_id,
                    n_items=50 if n_items >= 50 else n_items,
                    next_page=nextPageToken
                )
                if n_items >= 50:
                    n_items -= 50
                else:
                    n_items = 0
                    continue
            else:
                end_reached = True
                continue

        return

    def _get_playlist_ids(self, path):
        """Read playlist IDs from a text file into a list.

        Parses each line of the specified file as a playlist ID and returns them as a list.
        Empty lines and whitespace are stripped but included if non-empty after stripping.

        Args:
            path (str): Filesystem path to the playlist IDs file (one ID per line).

        Returns:
            list[str]: List of playlist IDs read from the file, or empty list on error.

        Raises:
            FileNotFoundError: If the specified file does not exist.
        """
        ids = []

        try:
            with open(path, 'r') as f:
                ids = [line.strip() for line in f]
        except FileNotFoundError as e:
            print(f"Error opening playlist file: {e}")
        except:
            print("Something went wrong with the playlist file...")

        return ids

    def retrieve_items_from_playlists(self, path, n_items=None):
        """Process multiple playlists according to configuration options.

        Reads playlist IDs from the specified file and processes each playlist based
        on how many items to retrieve:
        - If n_items is None or 0: Archives/prints entire playlist (uses get_entire_playlist)
        - If n_items is an int: Retrieves exactly n_items items per playlist
        - If n_items is a list: Each element specifies items for corresponding playlist

        Args:
            path (str): Path to file containing one playlist ID per line.
            n_items (int or list or None): Number of items per playlist, or list of counts,
                or None for entire playlists.

        Returns:
            None
        """
        playlist_ids = []

        playlist_ids = self._get_playlist_ids(path)
            
        for i, p_id in enumerate(playlist_ids):
            if not n_items:
                print(f"\nGetting entire playlist with ID {p_id}\n")
                self.get_entire_playlist(p_id)
            elif type(n_items) is int:
                print(f"\nGetting {n_items} items from playlist with ID {p_id}\n")
                self.get_n_playlist_items(p_id, n_items)
            elif type(n_items) is list:
                if len(n_items) != len(playlist_ids):
                    n = len(n_items)
                    p = len(playlist_ids)
                    print(
                        f"Error: n_list size ({n}) != number of " +
                        f"playlists ({p}). Returning..."
                    )
                    return
                print(f"\nGetting {n_items[i]} items from playlist with ID {p_id}\n")
                self.get_n_playlist_items(p_id, n_items[i])

        return

    def _get_etag(self, playlist_id) -> str:
        """Retrieve the ETag for a YouTube playlist.

        The ETag is an opaque identifier that Google uses to represent resource states.
        It changes whenever the playlist contents change, making it useful for detecting
        updates without fetching full playlist data.

        Args:
            playlist_id (str): The YouTube playlist ID.

        Returns:
            str: The ETag string from the API response.

        Raises:
            KeyError: If the playlist has no items (etag not present in response).
        """
        request = self._youtube.playlistItems().list(
            part="contentDetails",
            playlistId=playlist_id,
            maxResults=0
        )

        try:
            response = request.execute()
        except HttpError as e:
            print(f"YouTube API error ({e.status_code}): {e.reason}")
            return None

        return response["etag"]

    def check_playlist_for_changes(self, playlist_id) -> tuple[bool, str]:
        """Check whether a playlist has changed since last archived.

        Compares the current playlist's ETag with the stored ETag from the database.
        Returns a tuple indicating whether changes were detected and what the new
        ETag is (if any).

        Args:
            playlist_id (str): The YouTube playlist ID to check for changes.

        Returns:
            tuple[bool, str]: A two-element tuple where:
                - Element 0 is True if the playlist has changed since last archival
                - Element 1 is the current ETag string (empty string if no change)

        Raises:
            Exception: If an error occurs during ETag retrieval or database access.
        """
        try:
            # Get the playlist's etag
            etag = self._get_etag(playlist_id)

            # Compare received etag to stored
            self._cursor.execute(
                '''SELECT etag FROM playlist_data WHERE p_id = ?''',
                (playlist_id,)
            )
            result = self._cursor.fetchall()
            if not result:
                print(f"Playlist {playlist_id} not archived.")
                return (False, "")
            elif etag == result[0][0]:
                return (False, "")
            else:
                return (True, etag)
        except Exception as e:
            print(f"Error when checking playlist for changes: {e}")

    def _get_playlist_info(self, playlist_id):
        """Retrieve the title of a YouTube playlist from the API.

        Fetches basic snippet data for the specified playlist and extracts its title.

        Args:
            playlist_id (str): The YouTube playlist ID.

        Returns:
            str: The playlist's title, or raises KeyError if not found.
        """
        request = self._youtube.playlists().list(
            part='snippet',
            id=playlist_id
        )
        try:
            response = request.execute()
        except HttpError as e:
            print(f"YouTube API error ({e.status_code}): {e.reason}")
            return None
        
        return response["items"][0]["snippet"]["title"]

    def archive_playlist(self, playlist_id) -> bool:
        """Archive a YouTube playlist to the SQLite database.

        This method handles adding a new playlist to storage by:
        1. Fetching all items from the playlist (archiving them to database)
        2. Retrieving the playlist's title from the API
        3. Recording metadata including creation timestamp, last update timestamp, and ETag

        Args:
            playlist_id (str): The YouTube playlist ID to archive.

        Returns:
            bool: True if the playlist was successfully archived, False if already exists.
        """
        success = False

        self._cursor.execute('''
            SELECT * FROM playlist_data WHERE p_id = ?
        ''', (playlist_id,))
        result = self._cursor.fetchall()

        if not result:
            # Archive new playlist
            self.get_entire_playlist(playlist_id, "archive")
            playlist_title = self._get_playlist_info(playlist_id)
            now = datetime.datetime.now()
            etag = self._get_etag(playlist_id)
            self._cursor.execute('''
                INSERT INTO playlist_data 
                (p_id, title, created, last_update, etag) 
                VALUES (?, ?, ?, ?, ?)
                ''',
                (
                    playlist_id, playlist_title, int(now.timestamp()), 
                    int(now.timestamp()), etag
                )
            )
            self._conn.commit()
            print("Playlist successfully archived")
            success = True

        return success

    def update_playlist(self, playlist_id) -> bool:
        """Update existing playlist metadata after checking for content changes.

        This method determines whether a playlist has been modified since the last
        archival by comparing ETags. If changes are detected, it updates the
        last_update timestamp, ETag, and adds new videos into the database.

        Args:
            playlist_id (str): The YouTube playlist ID to update.

        Returns:
            bool: True if the playlist was updated or no action needed, False if not found.
        """
        success = False

        self._cursor.execute('''
            SELECT * FROM playlist_data WHERE p_id = ?
        ''', (playlist_id,))
        result = self._cursor.fetchall()

        if result:
            # Check if the playlist has changed since the last update
            (changed, etag) = self.check_playlist_for_changes(playlist_id)

            if changed and etag:
                # Update existing playlist
                self._peek_playlist_top(playlist_id)
                now = datetime.datetime.now()
                self._cursor.execute('''
                    UPDATE playlist_data 
                    SET last_update = ?, etag = ?
                    WHERE p_id = ?
                    ''',
                    ((int(now.timestamp()), etag, playlist_id))
                )
                self._conn.commit()
                print("Playlist successfully updated")
            else:
                print("No changes since last update")

            success = True
            
        return success

    def _peek_playlist_top(self, playlist_id):
        """Check for newly added videos at the top of a playlist.

        Scans through the most recent items in the playlist to identify videos that
        were not previously recorded in the database, and adds them until an existing 
        video is encountered.

        Args:
            playlist_id (str): The YouTube playlist ID to peek into.

        Returns:
            None
        """
        new_videos = { "items": [] } 
        more = True 
    
        response = self._get_playlist_page(playlist_id) 
    
        # Check if video is in playlist or not and handle accordingly 
        while more: 
            for item in response['items']: 
                video_id = item['contentDetails']['videoId'] 
                
                self._cursor.execute( 
                    ''' 
                        SELECT * FROM playlist_items  
                        WHERE p_id = ? AND vid_id = ? 
                    ''', 
                    (playlist_id, video_id) 
                ) 
                result = self._cursor.fetchall() 
                if result: 
                    print("Existing video encountered.")
                    more = False 
                    break 
                else: 
                    print(f"New video found: {item['snippet']['title']}")
                    new_videos['items'].append(item) 
    
            # Get the next page if necessary 
            if more and "nextPageToken" in response: 
                token = response["nextPageToken"] 
                response = self._get_playlist_page(playlist_id, next_page = token) 
    
        
        # Add the new videos and increment positions of old videos 
        if len(new_videos["items"]) > 0: 
            self._cursor.execute(
                '''
                    UPDATE playlist_items SET position = position + ?
                    WHERE p_id = ?
                ''',
                (len(new_videos["items"]), playlist_id)
            )
            self._archive_playlist_response(playlist_id, new_videos) 
    
        return

    def print_all_playlists(self):
        """Print details of all archived playlists to the console.

        Iterates through all playlists stored in the database and displays:
        - Playlist title
        - Playlist ID
        - Creation timestamp
        - Last update timestamp
        - Current ETag

        Example output:
            My Playlist:
            Playlist ID: PLxxx
            Created: 2024-01-01
            Last Updated: 2026-06-17
            Etag: abc123

        Returns:
            None
        """
        self._cursor.execute('''SELECT * FROM playlist_data''')
        result = self._cursor.fetchall()

        for playlist in result:
            p_id = playlist[0]
            title = playlist[1]
            created = datetime.datetime.fromtimestamp(playlist[2])
            last_update = datetime.datetime.fromtimestamp(playlist[3])
            etag = playlist[4]

            print(
                    f"\n{title}:\n" +
                    f"Playlist ID: {p_id}\nCreated: {created}\n" +
                    f"Last Updated: {last_update}\nEtag: {etag}\n"
            )

    def print_videos_from_playlist(self, playlist_id, order="DESC"):
        """Print video information from a playlist in specified order.

        Displays all videos stored for a given playlist with their position, title,
        URL, upload timestamp, and privacy status. The order parameter controls whether
        videos are displayed newest-to-oldest or oldest-to-newest.

        Args:
            playlist_id (str): The YouTube playlist ID.
            order (str): "DESC" for newest first (default), "ASC" for oldest first.

        Returns:
            None
        """
        if order == "DESC":
            self._cursor.execute(
                '''SELECT * FROM playlist_items WHERE p_id = ? ORDER BY position DESC''', 
                (playlist_id,)
            )
        elif order == "ASC":
            self._cursor.execute(
                '''SELECT * FROM playlist_items WHERE p_id = ? ORDER BY position ASC''', 
                (playlist_id,)
            )
        else:
            print(f"Unknown order {order}...")
        result = self._cursor.fetchall()

        for video in result:
            vid_id = video[1]

            # Get video-specific info
            self._cursor.execute(
            '''SELECT * FROM videos WHERE vid_id = ?''',
            (vid_id,)
            )
            vid_res = self._cursor.fetchall()
            title = vid_res[0][1]
            status = vid_res[0][2]

            position = video[2] + 1
            added = datetime.datetime.fromtimestamp(video[3])

            print(
                f"\n{position}: {title}\n" +
                f"URL: https://www.youtube.com/watch?v={vid_id}" +
                f"\nAdded: {added}\nStatus: {status}"
            )

    def search_in_playlist_fts(self, playlist_id, query, n_results=10):
        """Search for videos matching a query within a specific playlist.

        Uses SQLite's FTS5 virtual table to perform full-text search on video titles.
        Only returns results that are members of the specified playlist, ordered by
        relevance score. Useful for finding specific content within an archived playlist.

        Args:
            playlist_id (str): The YouTube playlist ID to search within.
            query (str): The search term or phrase to match against video titles.
            n_results (int): Maximum number of results to return (default 10).

        Returns:
            list[tuple]: List of tuples containing (title, vid_id, status, rank) for each match.
        """
        # Query videos that are in the playlist and match the FTS5 search
        self._cursor.execute('''
            SELECT v.title, v.vid_id, vids.status, v.rank
            FROM videos_fts AS v
            INNER JOIN videos AS vids ON vids.vid_id = v.vid_id
            INNER JOIN playlist_items ON playlist_items.vid_id = v.vid_id
            WHERE v.videos_fts MATCH ?
                AND playlist_items.p_id = ?
            ORDER BY v.rank
            LIMIT ?
        ''', (query, playlist_id, n_results))
        result = self._cursor.fetchall()

        return result
        
    def search_all_videos_fts(self, query, n_results=10):
        """Search for videos matching a query across all archived videos.

        Performs full-text search using the FTS5 virtual table without filtering by playlist.
        Returns results sorted by relevance across the entire database.

        Args:
            query (str): The search term or phrase to match against video titles.
            n_results (int): Maximum number of results to return (default 10).

        Returns:
            list[tuple]: List of tuples containing (title, vid_id, status, rank) for each match.
        """
        self._cursor.execute('''
            SELECT v.title, v.vid_id, v.status, f.rank
            FROM videos_fts AS f
            INNER JOIN videos as v ON v.vid_id = f.vid_id
            WHERE videos_fts MATCH ?
            ORDER BY f.rank
            LIMIT ?
        ''', (query, n_results))
        result = self._cursor.fetchall()
        
        return result

    @staticmethod
    def print_search_results(result):
        """Print search results to the console.

        Formats and displays search results, showing a link to each matched video.
        If no matches are found, prints an appropriate message instead.

        Args:
            result (list[tuple]): List of tuples from search operation, each containing
                (title, vid_id) that form a YouTube URL.

        Returns:
            None
        """
        # Print best matches
        if not result:
            print("No close matches found...")
        else:
            vid_dict = {row[0]: "https://www.youtube.com/watch?v=" + row[1] for row in result}
            for title, vid_id in vid_dict.items():
                print(f"\n{title}: {vid_id}\n")

        return

    def export_playlist(self, playlist_id):
        """Export an archived playlist as CSV files.

        Creates two files for each exported playlist:
        1. {title}.meta - Metadata file containing playlist title, creation date,
           last update timestamp, and current ETag
        2. {title}.csv - Data file containing all video items with their positions, IDs,
           titles, upload dates, privacy status, and any custom columns if present

        Args:
            playlist_id (str): The YouTube playlist ID to export.

        Returns:
            None
        """
        META_COLS = ["p_id", "title", "created", "last_update", "etag"]

        # Export the playlist's metadata
        self._cursor.execute(
            '''SELECT * FROM playlist_data WHERE p_id = ?''',
            (playlist_id,)
        )
        metadata = self._cursor.fetchall()[0]
        path = f"{metadata[1]}.csv"
        metadict = {}
        for i, col in enumerate(metadata):
            metadict[META_COLS[i]] = col
        meta_df = pd.DataFrame([metadict])
        meta_df.to_csv(path + ".meta", index=False)

        ### Exporting the playlist ###

        # Get and format relevant column names (accomodates user-generated cols)
        # NOTE: 'videos.vid_id' and 'playlist_items.p_id' omitted by list slice
        self._cursor.execute('''SELECT name FROM pragma_table_info('playlist_items')''')
        items_cols = ["playlist_items." + i[0] for i in self._cursor.fetchall()[1:]]
        self._cursor.execute('''SELECT name FROM pragma_table_info('videos')''')
        videos_cols = ["videos." + i[0] for i in self._cursor.fetchall()[1:]]
        col_names = ', '.join(items_cols) + ', ' + ', '.join(videos_cols)

        # Get the relevant playlist item and video data
        query = (
            "SELECT %s FROM playlist_items "
            "JOIN videos ON playlist_items.vid_id = videos.vid_id "
            "WHERE playlist_items.p_id = ? ORDER BY playlist_items.position ASC"
        ) % col_names
        self._cursor.execute(
            query,
            (playlist_id,)
        )
        result = self._cursor.fetchall()

        # Export the data
        playlist_df = pd.DataFrame(result, columns=(items_cols + videos_cols))
        playlist_df.to_csv(path, index=False)
        
        return

    # NOTE: Does not currently handle playlists already stored in the database
    def import_playlist(self, file_name):
        """Import archived playlist data from CSV files into the SQLite database.

        Reads playlist metadata and video items from corresponding CSV files and inserts
        them into the database tables. Prints a warning if the playlist already exists,
        skipping insert to avoid duplicate key errors.

        Args:
            file_name (str): Path to the CSV file containing video data. Corresponding
                .meta file should exist in the same directory.

        Returns:
            None

        Note:
            This operation does not handle re-importing a playlist that was already
            successfully stored previously. Existing metadata will be protected from
            duplicate insert errors.
        """
        # Load playlist data and metadata from the relevant file
        meta_df = pd.read_csv(file_name + ".meta")
        playlist_df = pd.read_csv(file_name)

        # Store playlist metadata
        metadata = tuple(meta_df.values[0])
        try:
            self._cursor.execute('''
                INSERT INTO playlist_data (p_id, title, created, last_update, etag)
                VALUES (?, ?, ?, ?, ?)''',
                metadata
            )
        except sqlite3.IntegrityError as e:
            print("Playlist metadata already stored. Skipping...")

        # Store the playlist data
        playlist_id = metadata[0]
        for row in playlist_df.itertuples():
            items_data = (playlist_id,) + row[1:len(PLAYLIST_ITEMS_COLS)]
            videos_data = (items_data[1],) + row[len(PLAYLIST_ITEMS_COLS):]

            # Storing playlist item data
            try:
                self._cursor.execute('''
                    INSERT INTO playlist_items (p_id, vid_id, position, added)
                    VALUES (?, ?, ?, ?)''',
                    items_data
                )
            except sqlite3.IntegrityError as e:
                print("Playlist item already exists. Skipping...")

            # Storing video data
            try:
                self._cursor.execute('''
                    INSERT INTO videos (vid_id, title, status)
                    VALUES (?, ?, ?)''',
                    videos_data
                )
            except sqlite3.IntegrityError as e:
                print("Video already exists. Skipping...")

        self._conn.commit()

        return

    def delete_playlist(self, playlist_id):
        """Remove a playlist and its associated data from the database.

        This operation is not reversible. When called:
        1. Deletes the playlist's metadata row from playlist_data table
        2. Removes all items from playlist_items table for that playlist
        3. Cleans up video records that were only referenced by this playlist,
           preserving videos that appear in other playlists

        Args:
            playlist_id (str): The YouTube playlist ID to delete.

        Returns:
            None

        Raises:
            sqlite3.IntegrityError: If a referenced foreign key prevents deletion.
        """
        # Remove playlist metadata
        self._cursor.execute(
            '''DELETE FROM playlist_data WHERE p_id = ?''', 
            (playlist_id,)
        )

        # Remove playlist
        self._cursor.execute(
            '''DELETE FROM playlist_items WHERE p_id = ?''', 
            (playlist_id,)
        )

        # Remove video data from videos referenced only by the specified playlist
        self._cursor.execute('''
            DELETE FROM videos
            WHERE vid_id IN (
                SELECT v.vid_id
                FROM videos v
                LEFT JOIN playlist_items p
                    ON v.vid_id = p.vid_id
                WHERE p.vid_id IS NULL
            )'''
        )

        self._conn.commit()

        return
    
    def handle_query(self, query, params=None):
        """Execute an arbitrary SQL query and return results.

        A convenience method for running custom queries against the SQLite database.
        Accepts both parameterized queries and raw queries.
        Returns all rows from the result set as a list of tuples.

        Args:
            query (str): The SQL query to execute. Use '?' placeholders for parameters.
            params (tuple or dict, optional): Parameters to substitute into the query.

        Returns:
            list[tuple]: All rows returned by the query execution, empty list if no rows.

        Example:
            >>> all_playlists = archiver.handle_query('SELECT * FROM playlist_data')
            >>> videos = archiver.handle_query(
            ...     'SELECT vid_id, title FROM videos ORDER BY position'
            ... )
        """
        if params:
            self._cursor.execute(query, params)
        else:
            self._cursor.execute(query)
        
        return self._cursor.fetchall()

    def _instantiate_db(self):
        """Create and/or connect to the SQLite database with schema.

        Establishes connection to playlists.db, creates a cursor for query execution,
        then defines all required tables:
        - playlist_data: Stores playlist metadata (title, timestamps, etag)
        - playlist_items: Stores individual video items per playlist
        - videos: Stores unique video information across all playlists
        - videos_fts: FTS5 virtual table for efficient full-text search

        Also creates database triggers that automatically maintain the FTS5 index
        whenever records are inserted, updated, or deleted in the videos table.

        Returns:
            None
        """
        self._conn = sqlite3.connect('playlists.db')
        self._cursor = self._conn.cursor()

        # Create required tables if necessary
        self._cursor.execute('''
            CREATE TABLE IF NOT EXISTS playlist_data (
                p_id VARCHAR(64) PRIMARY KEY,
                title VARCHAR(256),
                created INTEGER,
                last_update INTEGER,
                etag VARCHAR(32)
            )
        ''')
        self._cursor.execute('''
            CREATE TABLE IF NOT EXISTS playlist_items (
                p_id VARCHAR(64),
                vid_id VARCHAR(16),
                position INTEGER,
                added INTEGER,
                PRIMARY KEY (p_id, vid_id)
            )
        ''')
        self._cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                vid_id VARCHAR(16) PRIMARY KEY,
                title VARCHAR(256),
                status VARCHAR(16)
            )
        ''')
        
        # Create FTS5 virtual table for full-text search
        self._cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS videos_fts USING fts5(
                vid_id, 
                title, 
                content="videos",
                content_rowid="rowid",
                tokenize="trigram"
            )
        ''')
        
        # Create trigger to automatically sync FTS5 on INSERT
        self._cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS videos_ai AFTER INSERT ON videos BEGIN
                INSERT INTO videos_fts(rowid, vid_id, title) 
                VALUES (NEW.rowid, NEW.vid_id, NEW.title);
            END;
        ''')
        
        # Create trigger to automatically sync FTS5 on UPDATE
        self._cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS videos_au AFTER UPDATE ON videos BEGIN
                INSERT INTO videos_fts(videos_fts, rowid, vid_id, title) VALUES('delete', OLD.rowid, OLD.vid_id, OLD.title);
                INSERT INTO videos_fts(rowid, vid_id, title) VALUES (NEW.rowid, NEW.vid_id, NEW.title);
            END;
        ''')
        
        # Create trigger to automatically sync FTS5 on DELETE
        self._cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS videos_ad AFTER DELETE ON videos BEGIN
                INSERT INTO videos_fts(videos_fts, rowid, vid_id, title) VALUES('delete', OLD.rowid, OLD.vid_id, OLD.title);
            END;
        ''')

        self._conn.commit()