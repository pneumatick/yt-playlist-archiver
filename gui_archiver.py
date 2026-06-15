"""
YouTube Playlist Archiver - GUI Module

A PySide6-based graphical interface for browsing and viewing archived YouTube playlists.
"""

import sys
from datetime import datetime

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTableWidget, QTableWidgetItem, QPushButton, QLabel, QLineEdit,
        QDialog, QTextBrowser, QHeaderView, QFrame, QLabel, QSplitter
    )
    from PySide6.QtCore import Qt, Slot, QTimer
    from PySide6.QtGui import QFont
except ImportError:
    print("PySide6 is not installed. Please install it with: pip install PySide6")
    sys.exit(1)

# NOTE: This should probably be a field that main.py passes PlaylistArchiverGUI, 
# which passes it to MainWindow
import archiver
arch = archiver.Archiver()

class PlaylistArchiverGUI:
    """Main GUI class for the YouTube Playlist Archiver."""

    def __init__(self, app):
        """Initialize with a QApplication instance."""
        self.app = app  # Store reference to QApplication
        self.window = MainWindow(app)  # Pass app to window

class MainWindow(QMainWindow):
    """Main window for the playlist archiver GUI."""

    def __init__(self, app):
        super().__init__()
        self.app = app  # Store reference to QApplication
        self.search_timer = None  # Timer for debouncing search input
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""

        self.setWindowTitle("YouTube Playlist Archiver")
        self.setGeometry(100, 100, 1200, 800)

        # Central widget with splitter for panels
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        playlist_splitter = QSplitter()

        # Left panel - Playlist list
        left_panel = QFrame()
        left_panel.setMinimumWidth(400)
        left_layout = QVBoxLayout(left_panel)

        # Playlist search and filter section
        filter_section = QFrame()
        filter_section.setMaximumHeight(100)
        filter_layout = QHBoxLayout(filter_section)

        # Video search section for searching within playlist or all videos
        search_section = QFrame()
        search_layout = QHBoxLayout(search_section)

        self.video_search_input = QLineEdit()
        self.video_search_input.setPlaceholderText("Search videos...")
        self.video_search_input.textChanged.connect(self.on_video_search_text_changed)

        self.search_all_btn = QPushButton("Search All Videos")
        self.search_all_btn.clicked.connect(self.search_videos_all_playlists)

        self.search_playlist_btn = QPushButton("Search in Playlist")
        self.search_playlist_btn.clicked.connect(self.search_videos_in_playlist)
        self.search_playlist_btn.setEnabled(False)  # Enable when playlist selected

        # Add search button visibility indicator (hidden by default)
        self.search_button_placeholder = QLabel("")  # Placeholder to maintain layout

        search_layout.addWidget(QLabel("Video Search:"))
        search_layout.addWidget(self.video_search_input, 1)
        search_layout.addWidget(self.search_all_btn)
        search_layout.addWidget(self.search_playlist_btn)
        search_layout.addWidget(self.search_button_placeholder)

        # Hide search section until a playlist is selected (shown later by show_video_search_section())
        self.show_video_search_section()

        filter_layout.insertWidget(0, search_section, stretch=0)

        # Add video search section to the main layout
        main_layout.addWidget(filter_section)

        # Add playlist searching and sorting to the top of the left panel
        playlist_search_frame = QFrame()
        playlist_search_layout = QHBoxLayout(playlist_search_frame)

        self.playlist_search = QLineEdit()
        self.playlist_search.setPlaceholderText("Search playlists...")
        self.playlist_search.textChanged.connect(self.filter_playlists)

        playlist_search_layout.addWidget(QLabel("Search:"))
        playlist_search_layout.addWidget(self.playlist_search, 1)

        # Add refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_playlists)
        playlist_search_layout.addStretch()
        playlist_search_layout.addWidget(self.refresh_btn)

        left_layout.addWidget(playlist_search_frame)

        # Playlist table
        self.playlist_table = QTableWidget()
        self.playlist_table.setColumnCount(4)
        self.playlist_table.setHorizontalHeaderLabels([
            "Title", "Last Updated", "Created", "Playlist ID"
        ])
        for i in range(self.playlist_table.columnCount()):
            self.playlist_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        self.playlist_table.setAlternatingRowColors(True)
        self.playlist_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.playlist_table.itemClicked.connect(self.on_playlist_selected)
        self.playlist_table.setSortingEnabled(True)

        left_layout.addWidget(self.playlist_table)

        # Add buttons at bottom of left panel
        btn_section = QFrame()
        btn_layout = QHBoxLayout(btn_section)

        self.open_btn = QPushButton("Open Playlist In Browser")
        self.open_btn.clicked.connect(self.open_selected_playlist)
        self.open_btn.setEnabled(False)  # Enable when playlist selected

        self.check_btn = QPushButton("Check Playlist For Updates")
        self.check_btn.clicked.connect(self.update_playlist)
        self.check_btn.setEnabled(False)

        self.add_btn = QPushButton("Add New Playlist")
        self.add_btn.clicked.connect(self.add_playlist)

        self.del_btn = QPushButton("Delete Playlist")
        self.del_btn.clicked.connect(self.delete_playlist)

        btn_layout.addWidget(self.open_btn)
        btn_layout.addWidget(self.check_btn)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addStretch()

        left_layout.addWidget(btn_section)

        playlist_splitter.addWidget(left_panel)

        # Right panel - Details viewer
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)

        self.details_viewer = QTextBrowser()
        self.details_viewer.setMinimumHeight(400)
        self.details_viewer.setOpenExternalLinks(True)

        right_layout.addWidget(self.details_viewer, 1)
        playlist_splitter.addWidget(right_panel)

        # Add splitter to main layout
        main_layout.addWidget(playlist_splitter)

        # Apply font
        font = QFont("Segoe UI", 10)
        self.setFont(font)

        # Load playlists
        self.load_playlists()

    def show_video_search_section(self):
        """Show the video search section (initially hidden)."""
        self.search_button_placeholder.hide()
        self.search_playlist_btn.show()

    def hide_video_search_section(self):
        """Hide the video search section."""
        self.search_button_placeholder.show()
        self.search_playlist_btn.hide()

    @Slot(bool)
    def filter_playlists(self):
        """Filter playlists based on search text."""

        search_text = self.playlist_search.text().lower()
        if not search_text:
            self.refresh_playlists()
            return

        # Filter the table items
        for row in range(self.playlist_table.rowCount()):
            item_text = (
                str(self.playlist_table.item(row, 0).text())
            ).lower()
            is_visible = search_text in item_text

            if is_visible:
                self.playlist_table.setRowHidden(row, False)
            else:
                self.playlist_table.setRowHidden(row, True)

    def refresh_playlists(self):
        """Refresh the playlists table."""

        # Clear existing data and temporarily disable sorting
        self.playlist_table.setRowCount(0)
        self.playlist_table.setSortingEnabled(False)

        # Get playlists from database
        self.load_playlists()
        
        # Reenable sorting
        self.playlist_table.setSortingEnabled(True)

    def load_playlists(self):
        """Load and display all playlists."""

        query = """
            SELECT title, last_update, created, p_id
            FROM playlist_data
        """
        rows = arch.handle_query(query)

        self.playlist_table.setRowCount(0)
        for idx, row in enumerate(rows):
            try:
                last_update = datetime.fromtimestamp(row[1]).strftime("%Y-%m-%d %H:%M:%S")
                created = datetime.fromtimestamp(row[2]).strftime("%Y-%m-%d %H:%M:%S")
            except:
                last_update = str(row[1])
                created = str(row[2])

            self.playlist_table.insertRow(self.playlist_table.rowCount())
            self.playlist_table.setItem(idx, 0, QTableWidgetItem(row[0]))
            self.playlist_table.setItem(idx, 1, QTableWidgetItem(last_update))
            self.playlist_table.setItem(idx, 2, QTableWidgetItem(created))
            self.playlist_table.setItem(idx, 3, QTableWidgetItem(row[3]))

        self.playlist_search.clear()

    @Slot(int)
    def on_playlist_selected(self, item):
        """Handle playlist selection."""

        row = item.row()
        if row >= 0:
            # Enable action buttons
            self.search_playlist_btn.setEnabled(True)
            self.open_btn.setEnabled(True)
            self.check_btn.setEnabled(True)
            self.show_video_search_section()

            # Save the scrollbar position to prevent scrolling on append
            v_bar = self.details_viewer.verticalScrollBar()
            v_bar_pos = v_bar.value()

            # Show all videos from the selected playlist
            self.show_all_videos_from_playlist()

            # Restore scrollbar position
            v_bar.setValue(v_bar_pos)

    @Slot()
    def open_selected_playlist(self):
        """Open the selected playlist in a browser."""

        row = self.playlist_table.currentRow()
        if row < 0 or row >= self.playlist_table.rowCount():
            return

        p_id = self.playlist_table.item(row, 3).text()
        title = self.playlist_table.item(row, 0).text()

        # Open in default browser
        from urllib.parse import quote
        try:
            import webbrowser
            playlist_url = f"https://www.youtube.com/playlist?list={quote(p_id)}"
            webbrowser.open(playlist_url)
            self.details_viewer.append(f"\nOpening {title} in your browser...")
        except Exception as e:
            self.details_viewer.append(f"\nError opening playlist: {e}")

    @Slot()
    def show_all_videos_from_playlist(self):
        """Show all videos from the selected playlist."""

        row = self.playlist_table.currentRow()
        if row < 0 or row >= self.playlist_table.rowCount():
            return

        p_id = self.playlist_table.item(row, 3).text()
        title = self.playlist_table.item(row, 0).text()

        try:
            query = """
                SELECT v.title, v.status, pi.position, pi.vid_id, pi.added
                FROM videos v
                JOIN playlist_items pi ON v.vid_id = pi.vid_id
                WHERE pi.p_id = ?
                ORDER BY pi.position ASC
            """
            videos = arch.handle_query(query, (p_id,))

            if not videos:
                self.details_viewer.append("No videos found in this playlist.")
                return

            self.details_viewer.clear()
            self.details_viewer.append(f"<span>=== {title} ===\n</span>")
            self.details_viewer.append(f"<span>Total Videos: {len(videos)}\n</span>")
            self.details_viewer.append("<span>" + "-" * 50 + "\n</span>")

            for title_text, status, position, vid_id, added_timestamp in videos:
                try:
                    added = datetime.fromtimestamp(int(added)).strftime("%Y-%m-%d %H:%M:%S")
                except:
                    added = str(added_timestamp)

                self.details_viewer.append(
                    f"{position + 1}. [{status}] "
                    f"<a href=\"https://www.youtube.com/watch?v={vid_id}\">{title_text}</a>"
                )

            if len(videos) > 50:
                self.details_viewer.append("-" * 50 + "\n")
                self.details_viewer.append(
                    f"(Showing all {len(videos)} videos. Use browser for full playlist view.)"
                )

        except Exception as e:
            self.details_viewer.append(f"Error loading all videos: {e}")

    @Slot()
    def search_videos_in_playlist(self):
        """Search for videos in the selected playlist using FTS5."""

        row = self.playlist_table.currentRow()
        if row < 0 or row >= self.playlist_table.rowCount():
            return

        p_id = self.playlist_table.item(row, 3).text()
        title = self.playlist_table.item(row, 0).text()
        query_text = self.video_search_input.text().strip()

        if not query_text:
            self.details_viewer.append("Please enter a search term.")
            return

        # Use the FTS5 search from archiver.py directly via cursor
        try:
            search_results = arch.search_in_playlist_fts(p_id, query_text)

            if not search_results:
                self.details_viewer.append(f"No results found for '{query_text}' in {title}.")
                return

            self.details_viewer.clear()
            self.details_viewer.append(f"<span>=== Search Results in {title} ===\n</span>")
            self.details_viewer.append(f"<span>Search Term: {query_text}\n</span>")
            self.details_viewer.append(f"<span>Found {len(search_results)} result(s):\n</span>")
            self.details_viewer.append("<span>" + "-" * 50 + "\n</span>")

            for title_text, vid_id, rank in search_results:
                self.details_viewer.append(
                    f"• <a href=\"https://www.youtube.com/watch?v={vid_id}\">{title_text}</a>\n"
                )

            self.details_viewer.append("<span>" + "-" * 50 + "\n</span>")
            self.details_viewer.append(
                f"<span>(Showing top 10 results. Click any video to open in browser.)\n</span>"
            )

        except Exception as e:
            self.details_viewer.append(f"Error searching videos: {e}")

    @Slot(str)
    def on_video_search_text_changed(self, text=None):
        """Handle video search text change with debouncing."""
        
        # Stop the timer if running
        if self.search_timer:
            self.search_timer.stop()

        query_text = text if text is not None else self.video_search_input.text().strip()

        # Don't search if empty or too short (at least 3 characters)
        if not query_text or len(query_text) < 3:
            return

        # Start timer to debounce - wait 200ms after user stops typing
        self.search_timer = QTimer(self)
        self.search_timer.timeout.connect(lambda: None)
        self.search_timer.singleShot(200, self._perform_video_search)
        self.search_timer.start()

    def _perform_video_search(self):
        """Perform the actual video search using archiver FTS5 functions."""

        # If no playlist is selected, search all videos
        if self.playlist_table.currentRow() < 0:
            self.search_videos_all_playlists()
        else:
            self.search_videos_in_playlist()

    @Slot()
    def search_videos_all_playlists(self):
        """Search for videos across all playlists using FTS5."""

        query_text = self.video_search_input.text().strip()

        if not query_text:
            self.details_viewer.append("Please enter a search term.")
            return

        # Use the FTS5 search from archiver.py directly via cursor
        try:
            search_results = arch.search_all_videos_fts(query_text)

            if not search_results:
                self.details_viewer.append(f"No results found for '{query_text}' in all videos.")
                return

            self.details_viewer.clear()
            self.details_viewer.append(f"<span>=== Search Results (All Videos) ===\n</span>")
            self.details_viewer.append(f"<span>Search Term: {query_text}\n</span>")
            self.details_viewer.append(f"<span>Found {len(search_results)} result(s):\n</span>")
            self.details_viewer.append("<span>" + "-" * 50 + "\n</span>")

            for title_text, vid_id, rank in search_results:
                self.details_viewer.append(
                    f"• <a href=\"https://www.youtube.com/watch?v={vid_id}\">{title_text}</a>\n"
                )

            self.details_viewer.append("<span>" + "-" * 50 + "\n</span>")
            self.details_viewer.append(
                f"<span>(Showing top 10 results. Click any video to open in browser.)\n</span>"
            )

        except Exception as e:
            self.details_viewer.append(f"Error searching videos: {e}")
    
    @Slot()
    def update_playlist(self):
        """
           Check if the selected playlist has new videos added to it,
           and update the local data if so.
        """

        row = self.playlist_table.currentRow()
        if row < 0 or row >= self.playlist_table.rowCount():
            return

        p_id = self.playlist_table.item(row, 3).text()

        # Check for changes to playlist and update local data.
        success = arch.update_playlist(p_id)

        # Refresh playlist list upon update
        if success:
            self.refresh_playlists()
    
    @Slot()
    def add_playlist(self):
        popup = AddPlaylistPopup(self)
        popup.exec() # Blocks interaction with the main window
    
    @Slot()
    def delete_playlist(self):
        # Get and prepare relevant playlist info
        row = self.playlist_table.currentRow()
        if row < 0 or row >= self.playlist_table.rowCount():
            return

        title = self.playlist_table.item(row, 0).text()
        p_id = self.playlist_table.item(row, 3).text()

        playlist_info = {
            "Title": title,
            "Playlist ID": p_id
        }

        # Instantiate popup
        popup = DeletePlaylistPopup(playlist_info, parent=self)
        popup.exec() # Blocks interaction with the main window
        self.refresh_playlists()

class AddPlaylistPopup(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Add New Playlist")
        self.resize(300, 150)

        # Define layout and content
        layout = QVBoxLayout()
        label = QLabel("Enter Playlist Info")
        self.text_field = QLineEdit()
        self.text_field.setPlaceholderText("URL or ID...")
        add_btn = QPushButton("Add")

        # Connect relevant slot to add_btn
        add_btn.clicked.connect(self.add_playlist)

        layout.addWidget(label)
        layout.addWidget(self.text_field)
        layout.addWidget(add_btn)
        self.setLayout(layout)
    
    @Slot()
    def add_playlist(self):
        text = self.text_field.text()

        # Extract playlist ID from text (assuming URL or playlist ID)
        if "list=" in text:
            id = text.split("list=")[1].split("&")[0]
            print(id)
        else:
            id = text

        # Archive playlist
        success = arch.archive_playlist(id)
        if success:
            print("Archive successful")
            self.parent.refresh_playlists()
        else:
            print("Archive unsuccessful")

class DeletePlaylistPopup(QDialog):
    def __init__(self, playlist_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Delete Playlist")
        self.resize(300, 150)

        self.p_id = playlist_info["Playlist ID"]

        # Define layout and content
        layout = QVBoxLayout()

        label = QLabel("Are you sure you want to delete the following playlist?\n")

        info_text = "".join([f"{k}: {v}\n" for k, v in playlist_info.items()])
        info_label = QLabel(info_text)

        del_btn = QPushButton("Delete")

        # Connect relevant slot to del_btn
        del_btn.clicked.connect(self.del_playlist)

        layout.addWidget(label)
        layout.addWidget(info_label)
        layout.addWidget(del_btn)
        self.setLayout(layout)
    
    @Slot()
    def del_playlist(self):
        arch.delete_playlist(self.p_id)
        self.done(0)

def create_gui_application():
    """
    Factory function to create the GUI application.

    Returns:
        The PlaylistArchiverGUI instance (which contains the MainWindow)
    """

    app = QApplication([])
    gui = PlaylistArchiverGUI(app)

    return gui