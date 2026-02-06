import argparse
import os
import sqlite3
import datetime
import traceback
import difflib
import csv
import pandas as pd

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import google_auth_oauthlib.flow
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

# Global YouTube API variables
youtube = None

# Global SQLite3 variables
conn = None
cursor = None

# Table columns
PLAYLIST_ITEMS_COLS = ['p_id', 'vid_id', 'position', 'added']
VIDEOS_COLS = ['vid_id', 'title', 'status']

# Authorize the request and store authorization credentials. (OAuth 2.0)
def get_authenticated_service():
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

# Retrieve n items (50 max) from a playlist
def get_playlist_page(playlist_id, n_items = 50, next_page = None):
    if n_items < 1 or n_items > 50:
        print(f"Cannot retrieve {n_items} list items (range 1 - 50)...")
        return None

    if not next_page:
        request = youtube.playlistItems().list(
            part="snippet,contentDetails,status",
            playlistId=playlist_id,
            maxResults=n_items
        )
    else:
        request = youtube.playlistItems().list(
            part="snippet,contentDetails,status",
            playlistId=playlist_id,
            maxResults=n_items,
            pageToken=next_page
        )

    response = request.execute()

    return response

# Print all playlist items in a response
def print_playlist_response(response):
    for item in response['items']:
        video_title = item['snippet']['title']
        video_id = item['contentDetails']['videoId']
        position = item['snippet']['position']
        print(f"{position}: Video Title: {video_title}, Video ID: {video_id}")

def archive_playlist_response(playlist_id, response):
    for item in response['items']:
        video_title = item['snippet']['title']
        video_id = item['contentDetails']['videoId']
        position = item['snippet']['position']
        status = item['status']['privacyStatus']
        print(f"{position}: Video Title: {video_title}, Video ID: {video_id}")
        now = datetime.datetime.now() 
        try:
            cursor.execute(
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
            cursor.execute(
                '''
                    INSERT INTO videos
                    (vid_id, title, status) VALUES (?, ?, ?)
                ''',
                (video_id, video_title, status)
            )
        except sqlite3.IntegrityError as e:
            print("Video has been stored previously. Skipping...")

# Get all playlist items
def get_entire_playlist(playlist_id, behavior):
    end_reached = False

    response = get_playlist_page(playlist_id)
    while not end_reached:
        if not response:
            print("No response received...")
            return

        # Handle the response
        if behavior == "print":
            print_playlist_response(response)
        elif behavior == "archive":
            archive_playlist_response(playlist_id, response)
        else:
            print(f"Unknown behavior specified: {behavior}")
            return

        # Get the next page if possible, otherwise end loop
        if "nextPageToken" in response:
            nextPageToken = response["nextPageToken"]
            response = get_playlist_page(
                playlist_id, 
                next_page=nextPageToken
            )
        else:
            end_reached = True
            continue

    return

# Get a specified number of playlist items
def get_n_playlist_items(playlist_id, n_items):
    if n_items < 0:
        return
    elif n_items <= 50:
        response = get_playlist_page(playlist_id, n_items=n_items)
        print_playlist_response(response)
        return

    # Getting more than 50 items
    end_reached = False

    response = get_playlist_page(playlist_id)
    n_items -= 50
    while not end_reached:
        if not response:
            print("No response received...")
            return

        # Print playlist items for now
        print_playlist_response(response)
        # Get the next page if possible, otherwise end loop
        if "nextPageToken" in response and n_items > 0:
            nextPageToken = response["nextPageToken"]
            # Get max items (50) at a time while n > 50
            response = get_playlist_page(
                youtube, 
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

# Return a list of playlist IDs from a file
def get_playlist_ids(path):
    ids = []

    try:
        with open(path, 'r') as f:
            ids = [line.strip() for line in f]
    except FileNotFoundError as e:
        print(f"Error opening playlist file: {e}")
    except:
        print("Something went wrong with the playlist file...")

    return ids

# Get all items from a list of playlists
def retrieve_items_from_playlists(path, n_items=None):
    playlist_ids = []

    playlist_ids = get_playlist_ids(path)
        
    for i, p_id in enumerate(playlist_ids):
        if not n_items:
            print(f"\nGetting entire playlist with ID {p_id}\n")
            get_entire_playlist(p_id)
        elif type(n_items) is int:
            print(f"\nGetting {n_items} items from playlist with ID {p_id}\n")
            get_n_playlist_items(p_id, n_items)
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
            get_n_playlist_items(p_id, n_items[i])

    return

def get_etag(playlist_id) -> str:
    request = youtube.playlistItems().list(
        part="contentDetails",
        playlistId=playlist_id,
        maxResults=0
    )
    response = request.execute()
    return response["etag"]

# Check if the playlist has received changes since the last archival event
def check_playlist_for_changes(playlist_id) -> (bool, str):
    try:
        # Get the playlist's etag
        etag = get_etag(playlist_id)

        # Compare received etag to stored
        cursor.execute(
            '''SELECT etag FROM playlist_data WHERE p_id = ?''',
            (playlist_id,)
        )
        result = cursor.fetchall()
        if not result:
            print(f"Playlist {playlist_id} not archived.")
            return (False, "")
        elif etag == result[0][0]:
            return (False, "")
        else:
            return (True, etag)
    except Exception as e:
        print(f"Error when checking playlist for changes: {e}")

# Get relevant playlist information
def get_playlist_info(playlist_id):
    request = youtube.playlists().list(
        part='snippet',
        id=playlist_id
    )
    response = request.execute()
    
    return response["items"][0]["snippet"]["title"]

# Archive an entire playlist
def archive_playlist(playlist_id):
    # Check if the playlist is new or not
    cursor.execute('''
        SELECT * FROM playlist_data WHERE p_id = ?
    ''', (playlist_id,))
    result = cursor.fetchall()

    if result:
        # Check if the playlist has changed since the last update
        (changed, etag) = check_playlist_for_changes(playlist_id)

        if changed and etag:
            # Update existing playlist
            peek_playlist_top(playlist_id)
            now = datetime.datetime.now()
            cursor.execute('''
                UPDATE playlist_data 
                SET last_update = ?, etag = ?
                WHERE p_id = ?
                ''',
                ((int(now.timestamp()), etag, playlist_id))
            )
            conn.commit()
            print("Playlist successfully updated")
        else:
            print("No changes since last update")
    else:
        # Archive new playlist
        get_entire_playlist(playlist_id, "archive")
        playlist_title = get_playlist_info(playlist_id)
        now = datetime.datetime.now()
        etag = get_etag(playlist_id)
        cursor.execute('''
            INSERT INTO playlist_data 
            (p_id, title, created, last_update, etag) 
            VALUES (?, ?, ?, ?, ?)
            ''',
            (
                playlist_id, playlist_title, int(now.timestamp()), 
                int(now.timestamp()), etag
            )
        )
        conn.commit()
        print("Playlist successfully archived")

# Update playlist by peeking from the top
def peek_playlist_top(playlist_id): 
    new_videos = { "items": [] } 
    more = True 
 
    response = get_playlist_page(playlist_id) 
 
    # Check if video is in playlist or not and handle accordingly 
    while more: 
        for item in response['items']: 
            video_id = item['contentDetails']['videoId'] 
             
            cursor.execute( 
                ''' 
                    SELECT * FROM playlist_items  
                    WHERE p_id = ? AND vid_id = ? 
                ''', 
                (playlist_id, video_id) 
            ) 
            result = cursor.fetchall() 
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
            response = get_playlist_page(playlist_id, next_page = token) 
 
     
    # Add the new videos and increment positions of old videos 
    if len(new_videos["items"]) > 0: 
        cursor.execute(
            '''
                UPDATE playlist_items SET position = position + ?
                WHERE p_id = ? AND position >= ? - 1
            ''',
            (len(new_videos["items"]), playlist_id, len(new_videos["items"]))
        )
        archive_playlist_response(playlist_id, new_videos) 
 
    return

def print_all_playlists():
    cursor.execute('''SELECT * FROM playlist_data''')
    result = cursor.fetchall()

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

def print_videos_from_playlist(playlist_id, order = "DESC"):
    if order == "DESC":
        cursor.execute(
            '''SELECT * FROM playlist_items WHERE p_id = ? ORDER BY position DESC''', 
            (playlist_id,)
        )
    elif order == "ASC":
        cursor.execute(
            '''SELECT * FROM playlist_items WHERE p_id = ? ORDER BY position ASC''', 
            (playlist_id,)
        )
    else:
        print(f"Unknown order {order}...")
    result = cursor.fetchall()

    for video in result:
        vid_id = video[1]

        # Get video-specific info
        cursor.execute(
           '''SELECT * FROM videos WHERE vid_id = ?''',
           (vid_id,)
        )
        vid_res = cursor.fetchall()
        title = vid_res[0][1]
        status = vid_res[0][2]

        position = video[2] + 1
        added = datetime.datetime.fromtimestamp(video[3])

        print(
            f"\n{position}: {title}\n" +
            f"URL: https://www.youtube.com/watch?v={vid_id}" +
            f"\nAdded: {added}\nStatus: {status}"
        )

# Search for a video in the specified playlist
def search_in_playlist(playlist_id, query, n_results = 10):
    # Fetch all videos from the specified playlist
    cursor.execute(
         '''SELECT videos.title, videos.vid_id FROM videos
         LEFT JOIN playlist_items ON playlist_items.vid_id = videos.vid_id
         WHERE playlist_items.p_id = ?''',
         (playlist_id,)
     )
    result = cursor.fetchall()
    title_list = [row[0] for row in result]
    # Set for for possible future REPL to mimic YouTube scroll feature
    # Example: n=100, show 10 results at a time, option to view next page, etc.
    vid_dict = {row[0]: "https://www.youtube.com/watch?v=" + row[1] for row in result}

    # Search for the closest titles to the search query string
    close_matches = difflib.get_close_matches(
            query, 
            title_list, 
            n=n_results, 
            cutoff=0.15     # Roughly the sweet spot for my purposes
    )

    # Print best matches
    if not close_matches:
        print("No close matches found...")
    else:
        for close_match in close_matches:
            print(f"\n{close_match}: {vid_dict[close_match]}\n")

    return

# NOTE: Only change from above is SQL query. Combine in future...
def search_all_videos(query, n_results = 10):
    cursor.execute('''SELECT title, vid_id FROM videos''')
    result = cursor.fetchall()
    title_list = [row[0] for row in result]
    # Set for for possible future REPL to mimic YouTube scroll feature
    # Example: n=100, show 10 results at a time, option to view next page, etc.
    vid_dict = {row[0]: "https://www.youtube.com/watch?v=" + row[1] for row in result}

    # Search for the closest titles to the search query string
    close_matches = difflib.get_close_matches(
            query, 
            title_list, 
            n=n_results, 
            cutoff=0.15     # Roughly the sweet spot for my purposes
    )

    # Print best matches
    if not close_matches:
        print("No close matches found...")
    else:
        for close_match in close_matches:
            print(f"\n{close_match}: {vid_dict[close_match]}\n")

    return

# Export a playlist as a set of CSV files (one for videos, other for metadata)
def export_playlist(playlist_id):
    META_COLS = ["p_id", "title", "created", "last_update", "etag"]

    # Export the playlist's metadata
    cursor.execute(
        '''SELECT * FROM playlist_data WHERE p_id = ?''',
        (playlist_id,)
    )
    metadata = cursor.fetchall()[0]
    path = f"{metadata[1]}.csv"
    metadict = {}
    for i, col in enumerate(metadata):
        metadict[META_COLS[i]] = col
    meta_df = pd.DataFrame([metadict])
    meta_df.to_csv(path + ".meta", index=False)

    ### Exporting the playlist ###

    # Get and format relevant column names (accomodates user-generated cols)
    # NOTE: 'videos.vid_id' and 'playlist_items.p_id' omitted by list slice
    cursor.execute('''SELECT name FROM pragma_table_info('playlist_items')''')
    items_cols = ["playlist_items." + i[0] for i in cursor.fetchall()[1:]]
    cursor.execute('''SELECT name FROM pragma_table_info('videos')''')
    videos_cols = ["videos." + i[0] for i in cursor.fetchall()[1:]]
    col_names = ', '.join(items_cols) + ', ' + ', '.join(videos_cols)

    # Get the relevant playlist item and video data
    query = (
        "SELECT %s FROM playlist_items "
        "JOIN videos ON playlist_items.vid_id = videos.vid_id "
        "WHERE playlist_items.p_id = ? ORDER BY playlist_items.position ASC"
    ) % col_names
    cursor.execute(
         query,
         (playlist_id,)
    )
    result = cursor.fetchall()

    # Export the data
    playlist_df = pd.DataFrame(result, columns=(items_cols + videos_cols))
    playlist_df.to_csv(path, index=False)
    
    return

# Import playlist data
# NOTE: Does not currently handle playlists already stored in the database
def import_playlist(file_name):
    # Load playlist data and metadata from the relevant file
    meta_df = pd.read_csv(file_name + ".meta")
    playlist_df = pd.read_csv(file_name)

    # Store playlist metadata
    metadata = tuple(meta_df.values[0])
    try:
        cursor.execute('''
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
            cursor.execute('''
                INSERT INTO playlist_items (p_id, vid_id, position, added)
                VALUES (?, ?, ?, ?)''',
                items_data
            )
        except sqlite3.IntegrityError as e:
            print("Playlist item already exists. Skipping...")

        # Storing video data
        try:
            cursor.execute('''
                INSERT INTO videos (vid_id, title, status)
                VALUES (?, ?, ?)''',
                videos_data
            )
        except sqlite3.IntegrityError as e:
            print("Video already exists. Skipping...")

    conn.commit()

    return

# Delete the specified playlist
# TODO: Test if video is retained when two playlists include it
def delete_playlist(playlist_id):
    # Remove playlist metadata
    cursor.execute(
        '''DELETE FROM playlist_data WHERE p_id = ?''', 
        (playlist_id,)
    )

    # Remove playlist
    cursor.execute(
        '''DELETE FROM playlist_items WHERE p_id = ?''', 
        (playlist_id,)
    )

    # Remove video data from videos referenced only by the specified playlist
    cursor.execute('''
        DELETE FROM videos
        WHERE vid_id IN (
            SELECT v.vid_id
            FROM videos v
            LEFT JOIN playlist_items p
                ON v.vid_id = p.vid_id
            WHERE p.vid_id IS NULL
        )'''
    )

    conn.commit()

    return

# Instantiate or load the database
def instantiate_db():
    global conn
    global cursor
    conn = sqlite3.connect('playlists.db')
    cursor = conn.cursor()

    # Create required tables if necessary
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS playlist_data (
            p_id VARCHAR(64) PRIMARY KEY,
            title VARCHAR(256),
            created INTEGER,
            last_update INTEGER,
            etag VARCHAR(32)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS playlist_items (
            p_id VARCHAR(64),
            vid_id VARCHAR(16),
            position INTEGER,
            added INTEGER,
            PRIMARY KEY (p_id, vid_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            vid_id VARCHAR(16) PRIMARY KEY,
            title VARCHAR(256),
            status VARCHAR(16)
        )
    ''')

    conn.commit()

if __name__ == '__main__':

    # Argparse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i", "--id",
        help="Retrieve a single playlist by ID"
    )
    parser.add_argument(
        "-n", "--number", 
        type=int,
        help="Number of playlist items to retrieve"
    )
    parser.add_argument(
        "--n_list",
        nargs="+",
        type=int,
        help="List of number of playlist items to retrieve (size of list" +
             "must equal total number of playlists)"
    )
    parser.add_argument(
        "--file",
        nargs="?",
        default=None,
        const="playlists.txt",
        help="Use playlist ID file (default 'playlists.txt')"
    )
    parser.add_argument(
        "-c", "--check",
        help="Check playlist for changes by ID"
    )
    parser.add_argument(
        "-a", "--archive",
        help="Archive an entire playlist by ID"
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="Display a list of all archived playlists"
    )
    parser.add_argument(
        "-o", "--open",
        help="Open a playlist"
    )
    parser.add_argument(
        "--ascend",
        action="store_true",
        help="Print playlist in ascending order"
    )
    parser.add_argument(
        "--search",
        nargs='+',
        help="Search for a video by title in the specified playlist " +
             "(order: playlist ID, video title)"
    )
    parser.add_argument(
        "--export",
        help="Export a playlist as a set of CSV files"
    )
    parser.add_argument(
        "--import",
        dest="import_file",
        help="Import a playlist from a set of CSV files"
    )
    parser.add_argument(
        "--delete",
        help="Delete a locally stored playlist by ID"
    )

    try:
        # Get args
        args = parser.parse_args()

        # Load or create database
        instantiate_db()

        # Execute functions according to args

        ''' Local Functions '''

        # Archive an entire playlist by id
        if args.archive:
            archive_playlist(args.archive)
        # List all archived playlists
        elif args.list:
            print_all_playlists()
        # Print videos from a playlist
        elif args.open:
            if args.ascend:
                print_videos_from_playlist(args.open, order="ASC")
            else:
                print_videos_from_playlist(args.open, order="DESC")
        # Search for a video in a playlist
        elif args.search:
            # Search all videos
            if len(args.search) == 1:
                search_all_videos(args.search[0])
            # Search specific playlist
            if len(args.search) == 2:
                playlist_id = args.search[0]
                title = args.search[1]
                search_in_playlist(playlist_id, title)
        # Importing/exporting
        elif args.export:
            export_playlist(args.export)
        elif args.import_file:
            import_playlist(args.import_file)
        # Deleting playlists
        elif args.delete:
            delete_playlist(args.delete)

        ''' Remote Functions '''

        """
        key = get_api_key()
        if not key:
            print("Failed to get API key. Quitting...")
            quit()
        # Set up YouTube API (global variable)
        youtube = build(API_SERVICE_NAME, API_VERSION, developerKey=key)
        """
        # OAuth 2.0
        youtube = get_authenticated_service()

        # Single playlist
        if args.id:
            playlist_id = args.id
            if not args.number:
                get_entire_playlist(playlist_id, "print")
            else:
                n_items = args.number
                print(f"Getting {n_items} items from playlist {playlist_id}")
                get_n_playlist_items(playlist_id, n_items=n_items)
        # Playlist file
        elif args.file:
            if args.number:
                n_items = args.number
                retrieve_items_from_playlists(args.file, n_items)
            elif args.n_list:
                n_list = args.n_list
                retrieve_items_from_playlists(args.file, n_list)
            else:
                retrieve_items_from_playlists(args.file) 
        # Checking playlist for changes
        elif args.check:
            check_playlist_for_changes(args.check)


    except HttpError as e:
        print('An HTTP error %d occurred:\n%s' % (e.resp.status, e.content))
        traceback.print_exc()
    except Exception as e:
        print(f"An error has occurred: {e}")
        traceback.print_exc()

    # Close database connection
    conn.close()

