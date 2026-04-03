import argparse
import traceback

import archiver as arch
import sys
from gui_archiver import create_gui_application, PlaylistArchiverGUI, MainWindow

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
        help="Search for videos using FTS5 full-text search (order: playlist ID (optional), query)"
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
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch YouTube Playlist Archiver GUI"
    )

    try:
        # Get args
        args = parser.parse_args()

        # Load or create database
        arch.instantiate_db()

        # Execute functions according to args

        ''' Local Functions '''

        # List all archived playlists
        if args.list:
            arch.print_all_playlists()
        # Print videos from a playlist
        elif args.open:
            if args.ascend:
                arch.print_videos_from_playlist(args.open, order="ASC")
            else:
                arch.print_videos_from_playlist(args.open, order="DESC")
        # Search for a video in a playlist
        elif args.search:
            # Search all videos
            if len(args.search) == 1:
                arch.search_all_videos_fts(args.search[0])
            # Search specific playlist
            if len(args.search) == 2:
                playlist_id = args.search[0]
                title = args.search[1]
                arch.search_in_playlist_fts(playlist_id, title)
        # Importing/exporting
        elif args.export:
            arch.export_playlist(args.export)
        elif args.import_file:
            arch.import_playlist(args.import_file)
        # Deleting playlists
        elif args.delete:
            arch.delete_playlist(args.delete)

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
        arch.youtube = arch.get_authenticated_service()

        # Single playlist
        if args.id:
            playlist_id = args.id
            if not args.number:
                arch.get_entire_playlist(playlist_id, "print")
            else:
                n_items = args.number
                print(f"Getting {n_items} items from playlist {playlist_id}")
                arch.get_n_playlist_items(playlist_id, n_items=n_items)
        # Playlist file
        elif args.file:
            if args.number:
                n_items = args.number
                arch.retrieve_items_from_playlists(args.file, n_items)
            elif args.n_list:
                n_list = args.n_list
                arch.retrieve_items_from_playlists(args.file, n_list)
            else:
                arch.retrieve_items_from_playlists(args.file) 
        # Checking playlist for changes
        elif args.check:
            arch.check_playlist_for_changes(args.check)
        # Archive an entire playlist by id
        elif args.archive:
            arch.archive_playlist(args.archive)
        # GUI
        elif args.gui:
            # Create QApplication and launch GUI
            gui = create_gui_application(arch.conn, arch.cursor)
            window = gui.window
            gui.window.show()
            gui.app.exec()
            
            # Only close db when app is closed
            @gui.app.lastWindowClosed.connect
            def on_closed():
                print("GUI closing...")
            quit()


    except arch.HttpError as e:
        print('An HTTP error %d occurred:\n%s' % (e.resp.status, e.content))
        traceback.print_exc()
    except Exception as e:
        print(f"An error has occurred: {e}")
        traceback.print_exc()

    # Close database connection
    arch.conn.close()

