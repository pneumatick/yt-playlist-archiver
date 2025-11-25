import argparse
import os
import sqlite3
import datetime
import traceback

import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow

# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret. You can acquire an OAuth 2.0 client ID and client secret from
# the {{ Google Cloud Console }} at
# {{ https://cloud.google.com/console }}.
# Please ensure that you have enabled the YouTube Data API for your project.
# For more information about using OAuth2 to access the YouTube Data API, see:
#   https://developers.google.com/youtube/v3/guides/authentication
# For more information about the client_secrets.json file format, see:
#   https://developers.google.com/api-client-library/python/guide/aaa_client_secrets

CLIENT_SECRETS_FILE = 'client_secret.json'

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account.
SCOPES = ['https://www.googleapis.com/auth/youtube']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

# Global YouTube API variables
youtube = None

# Global SQLite3 variables
conn = None
cursor = None

# Authorize the request and store authorization credentials. (OAuth 2.0)
def get_authenticated_service():
  flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
  credentials = flow.run_console()
  return build(API_SERVICE_NAME, API_VERSION, credentials = credentials)

# Get the API key from the specified text file
def get_api_key(path="secrets.txt"):
    try:
        with open(path, 'r') as f:
            key = f.read().strip()
            return key
    except Exception as e:
        print(f"An error occured while attempting to get API key: {e}")
        return None

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
            cursor.execute(
                '''
                    INSERT INTO videos
                    (vid_id, status) VALUES (?, ?)
                ''',
                (video_id, status)
            )
        except sqlite3.IntegrityError as e:
            print("Video already archived. Skipping...")

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

# Check if the playlist has received changes since the last archival event
def check_playlist_for_changes(playlist_id) -> (bool, str):
    try:
        # Get the playlist's etag
        request = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=playlist_id,
            maxResults=0
        )
        response = request.execute()
        etag = response["etag"]

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

# Archive an entire playlist
def archive_playlist(playlist_id):
    (changed, etag) = check_playlist_for_changes(playlist_id)

    if changed and etag:
        get_entire_playlist(playlist_id, "archive")
        now = datetime.datetime.now()
        # Update existing playlist
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

    # OAuth 2.0
    #youtube = get_authenticated_service()

    key = get_api_key()
    if not key:
        print("Failed to get API key. Quitting...")
        quit()

    try:
        # Set up YouTube API (global variable)
        youtube = build(API_SERVICE_NAME, API_VERSION, developerKey=key)

        # Get args
        args = parser.parse_args()

        # Load or create database
        instantiate_db()

        # Execute functions according to args

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
        # Archive an entire playlist by id
        elif args.archive:
            archive_playlist(args.archive)
            
        # Close database connection
        conn.close()
    except HttpError as e:
        print('An HTTP error %d occurred:\n%s' % (e.resp.status, e.content))
    except Exception as e:
        print(f"An error has occurred: {e}")
        traceback.print_exc()

