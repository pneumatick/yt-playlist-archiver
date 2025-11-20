import argparse
import os

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
def get_playlist_page(youtube, playlist_id, n_items = 50, next_page = None):
    if n_items < 1 or n_items > 50:
        print(f"Cannot retrieve {n_items} list items (range 1 - 50)...")
        return None

    if not next_page:
        request = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=n_items
        )
    else:
        request = youtube.playlistItems().list(
            part="snippet,contentDetails",
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
        print(f"Video Title: {video_title}, Video ID: {video_id}")

# Get all playlist items
def get_entire_playlist(youtube, playlist_id):
    end_reached = False

    response = get_playlist_page(youtube, playlist_id)
    while not end_reached:
        if not response:
            print("No response received...")
            return

        # Print playlist items for now
        print_playlist_response(response)
        # Get the next page if possible, otherwise end loop
        if "nextPageToken" in response:
            nextPageToken = response["nextPageToken"]
            response = get_playlist_page(
                youtube, 
                playlist_id, 
                next_page=nextPageToken
            )
        else:
            end_reached = True
            continue

    return

# Return a list of playlist IDs from a file
def get_playlist_ids(path="playlists.txt"):
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
def retrieve_items_from_playlists(youtube, path=""):
    playlist_ids = []

    if not path:
        playlist_ids = get_playlist_ids()
    else:
        playlist_ids = get_playlist_ids(path)
        
    for p_id in playlist_ids:
        print(f"\nGetting entire playlist with ID {p_id}\n")
        get_entire_playlist(youtube, p_id)

    return

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    # Add argparse arguments here

    # OAuth 2.0
    #youtube = get_authenticated_service()

    key = get_api_key()
    if not key:
        print("Failed to get API key. Quitting...")
        quit()

    try:
        youtube = build(API_SERVICE_NAME, API_VERSION, developerKey=key)
        # TESTS: Replace with argparse later...
        #get_entire_playlist(youtube, ENTER ID HERE)
        retrieve_items_from_playlists(youtube) 
    except HttpError as e:
        print('An HTTP error %d occurred:\n%s' % (e.resp.status, e.content))
    except Exception as e:
        print(f"An error has occurred: {e.content}")


