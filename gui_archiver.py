"""
YouTube Playlist Archiver - GUI Module

A PySide6-based graphical interface for browsing and viewing archived YouTube playlists.
"""

import sys
from datetime import datetime
from typing import List, Optional

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTableWidget, QTableWidgetItem, QPushButton, QLabel, QLineEdit,
        QComboBox, QSplitter, QTextBrowser, QHeaderView, QFrame
    )
    from PySide6.QtCore import Qt, Signal, Slot
    from PySide6.QtGui import QFont, QIcon
except ImportError:
    print("PySide6 is not installed. Please install it with: pip install PySide6")
    sys.exit(1)


class PlaylistArchiverGUI:
    """Main GUI class for the YouTube Playlist Archiver."""

    def __init__(self, app):
        """Initialize with a QApplication instance."""
        self.app = app  # Store reference to QApplication
        self.window = MainWindow(app)  # Pass app to window
        self.db_connection = None  # Will be passed from main.py
        self.cursor = None

    def set_db_connection(self, conn, cursor):
        """Set the database connection and cursor."""
        self.db_connection = conn
        self.cursor = cursor
        self.window.set_connection(conn, cursor)


class MainWindow(QMainWindow):
    """Main window for the playlist archiver GUI."""

    def __init__(self, app):
        super().__init__()
        self.app = app  # Store reference to QApplication
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("YouTube Playlist Archiver")
        self.setGeometry(100, 100, 1200, 800)

        # Central widget with splitter for panels
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)  # Changed to vertical layout

        # Left panel - Playlist list
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMinimumWidth(400)

        # Playlist search and filter section
        filter_section = QFrame()
        filter_layout = QHBoxLayout(filter_section)
        
        self.playlist_search = QLineEdit()
        self.playlist_search.setPlaceholderText("Search playlists...")
        self.playlist_search.textChanged.connect(self.filter_playlists)
        
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Newest First", "Oldest First", "Alphabetical"])
        self.sort_combo.currentIndexChanged.connect(self.refresh_playlists)
        
        filter_layout.addWidget(QLabel("Search:"))
        filter_layout.addWidget(self.playlist_search, 1)
        filter_layout.addWidget(QLabel("Sort by:"))
        filter_layout.addWidget(self.sort_combo)

        # Add refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_playlists)
        filter_layout.addStretch()
        filter_layout.addWidget(self.refresh_btn)

        left_layout.addWidget(filter_section)

        # Playlist table
        self.playlist_table = QTableWidget()
        self.playlist_table.setColumnCount(5)
        self.playlist_table.setHorizontalHeaderLabels([
            "Playlist ID", "Title", "Created", "Last Updated", "Etag"
        ])
        self.playlist_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.playlist_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.playlist_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.playlist_table.setAlternatingRowColors(True)
        self.playlist_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.playlist_table.itemClicked.connect(self.on_playlist_selected)
        #self.playlist_table.setItemSelectionBehavior(QTableWidget.SelectItems)
        
        left_layout.addWidget(self.playlist_table)

        # Add buttons at bottom of left panel
        btn_section = QFrame()
        btn_layout = QHBoxLayout(btn_section)
        
        self.open_btn = QPushButton("Open Playlist In Browser")
        self.open_btn.clicked.connect(self.open_selected_playlist)
        self.open_btn.setEnabled(False)  # Enable when playlist selected
        
        btn_layout.addWidget(self.open_btn)
        btn_layout.addStretch()

        left_layout.addWidget(btn_section)

        main_layout.addWidget(left_panel, stretch=1)

        # Right panel - Details viewer
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        
        self.details_viewer = QTextBrowser()
        self.details_viewer.setMinimumHeight(400)
        self.details_viewer.setOpenExternalLinks(True)
        
        detail_buttons_layout = QHBoxLayout()
        
        # View Videos button
        self.view_videos_btn = QPushButton("View Videos")
        self.view_videos_btn.clicked.connect(self.show_playlist_videos)
        self.view_videos_btn.setEnabled(False)
        detail_buttons_layout.addWidget(self.view_videos_btn)
        
        self.view_videos_btn2 = QPushButton("View All Videos (Full List)")
        self.view_videos_btn2.clicked.connect(self.show_all_videos_from_playlist)
        self.view_videos_btn2.setEnabled(False)
        detail_buttons_layout.addWidget(self.view_videos_btn2)

        right_layout.addWidget(self.details_viewer, 1)
        right_layout.addLayout(detail_buttons_layout, 2)
        main_layout.addWidget(right_panel, stretch=3)

        # Apply font
        font = QFont("Segoe UI", 10)
        self.setFont(font)

    def set_connection(self, conn, cursor):
        """Set the database connection for the GUI."""
        self.db_connection = conn
        self.cursor = cursor
        self.load_playlists()

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
                str(self.playlist_table.item(row, 1).text()) + " " +
                str(self.playlist_table.item(row, 0).text())
            ).lower()
            is_visible = search_text in item_text

            if is_visible:
                self.playlist_table.setRowHidden(row, False)
            else:
                self.playlist_table.setRowHidden(row, True)

    def refresh_playlists(self):
        """Refresh the playlists table."""
        # Clear existing data
        self.playlist_table.setRowCount(0)

        # Apply sorting
        sort_order = {
            "Newest First": Qt.DescendingOrder,
            "Oldest First": Qt.AscendingOrder,
            "Alphabetical": Qt.AscendingOrder  # Sort by title
        }
        order = sort_order.get(self.sort_combo.currentText(), Qt.AscendingOrder)

        # Get playlists from database
        query = """
            SELECT p_id, title, created, last_update, etag 
            FROM playlist_data 
            ORDER BY created {}
        """.format("DESC" if order == Qt.DescendingOrder else "ASC")

        self.cursor.execute(query)
        rows = self.cursor.fetchall()

        for idx, row in enumerate(rows):
            p_id_item = QTableWidgetItem(row[0])
            title_item = QTableWidgetItem(row[1])
            
            try:
                created_item = QTableWidgetItem(datetime.fromtimestamp(row[2]).strftime("%Y-%m-%d %H:%M:%S"))
            except:
                created_item = QTableWidgetItem(str(row[2]))

            try:
                last_update_item = QTableWidgetItem(datetime.fromtimestamp(row[3]).strftime("%Y-%m-%d %H:%M:%S"))
            except:
                last_update_item = QTableWidgetItem(str(row[3]))

            etag_item = QTableWidgetItem(row[4]) if row[4] else QTableWidgetItem("-")

            self.playlist_table.insertRow(self.playlist_table.rowCount())
            self.playlist_table.setItem(idx, 0, p_id_item)
            self.playlist_table.setItem(idx, 1, title_item)
            self.playlist_table.setItem(idx, 2, created_item)
            self.playlist_table.setItem(idx, 3, last_update_item)
            self.playlist_table.setItem(idx, 4, etag_item)

    def load_playlists(self):
        """Load and display all playlists."""
        query = "SELECT p_id, title, created, last_update, etag FROM playlist_data ORDER BY created DESC"
        self.cursor.execute(query)
        rows = self.cursor.fetchall()

        for idx, row in enumerate(rows):
            try:
                created = datetime.fromtimestamp(row[2]).strftime("%Y-%m-%d %H:%M:%S")
                last_update = datetime.fromtimestamp(row[3]).strftime("%Y-%m-%d %H:%M:%S")
            except:
                created = str(row[2])
                last_update = str(row[3])

            self.playlist_table.insertRow(self.playlist_table.rowCount())
            self.playlist_table.setItem(idx, 0, QTableWidgetItem(row[0]))
            self.playlist_table.setItem(idx, 1, QTableWidgetItem(row[1]))
            self.playlist_table.setItem(idx, 2, QTableWidgetItem(created))
            self.playlist_table.setItem(idx, 3, QTableWidgetItem(last_update))
            self.playlist_table.setItem(idx, 4, QTableWidgetItem(row[4]) if row[4] else QTableWidgetItem("-"))

        self.playlist_search.clear()
        #self.playlist_table.setSelectionRow(self.playlist_table.rowCount() - 1)

    @Slot(int)
    def on_playlist_selected(self, item):
        """Handle playlist selection."""
        row = item.row()
        if row >= 0:
            p_id = self.playlist_table.item(row, 0).text()
            title = self.playlist_table.item(row, 1).text()

            # Enable action buttons
            self.open_btn.setEnabled(True)
            self.view_videos_btn.setEnabled(True)
            self.view_videos_btn2.setEnabled(True)

            # Update details viewer with playlist info
            try:
                created_dt = datetime.fromtimestamp(
                    int(self.playlist_table.item(row, 2).text())
                ).strftime("%Y-%m-%d %H:%M:%S")
            except:
                created_dt = self.playlist_table.item(row, 2).text()

            try:
                last_update_dt = datetime.fromtimestamp(
                    int(self.playlist_table.item(row, 3).text())
                ).strftime("%Y-%m-%d %H:%M:%S")
            except:
                last_update_dt = self.playlist_table.item(row, 3).text()

            self.details_viewer.clear()
            self.details_viewer.append(f"=== {title} ===")
            self.details_viewer.append(f"Playlist ID: {p_id}")
            self.details_viewer.append(f"Created: {created_dt}")
            self.details_viewer.append(f"Last Updated: {last_update_dt}")

    @Slot()
    def open_selected_playlist(self):
        """Open the selected playlist in a browser."""
        row = self.playlist_table.currentRow()
        if row < 0 or row >= self.playlist_table.rowCount():
            return

        p_id = self.playlist_table.item(row, 0).text()
        title = self.playlist_table.item(row, 1).text()
        
        # Construct YouTube playlist URL
        url = f"https://www.youtube.com/playlist?list={p_id}"
        
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
    def show_playlist_videos(self):
        """Show videos from the selected playlist (paged view)."""
        row = self.playlist_table.currentRow()
        if row < 0 or row >= self.playlist_table.rowCount():
            return

        p_id = self.playlist_table.item(row, 0).text()
        title = self.playlist_table.item(row, 1).text()

        try:
            self.cursor.execute(
                """SELECT vid_id, position, added FROM playlist_items 
                   WHERE p_id = ? ORDER BY position ASC LIMIT 50""",
                (p_id,)
            )
            videos = self.cursor.fetchall()

            if not videos:
                self.details_viewer.append("No videos in this playlist.")
                return

            self.details_viewer.clear()
            self.details_viewer.append(f"=== {title} - Videos ({len(videos)} items) ===\n")

            for vid_id, position, added_timestamp in videos:
                try:
                    added = datetime.fromtimestamp(int(added)).strftime("%Y-%m-%d %H:%M:%S")
                except:
                    added = str(added_timestamp)
                
                video_url = f"https://www.youtube.com/watch?v={vid_id}"
                self.details_viewer.append(f"{position + 1}. {video_url}")
            else:
                # Load more button
                next_page_token_query = f"""SELECT nextPageToken FROM playlistItemsList 
                    WHERE playlistId = '{p_id}'"""
                try:
                    # Simple approach - just show count and let user see first 50
                    self.details_viewer.append(f"\n--- First {len(videos)} of 50 videos shown ---")
                    self.details_viewer.append("To see more, check the playlist in your browser or use export functionality.")
                except:
                    pass

        except Exception as e:
            self.details_viewer.append(f"Error loading videos: {e}")

    @Slot()
    def show_all_videos_from_playlist(self):
        """Show all videos from the selected playlist."""
        row = self.playlist_table.currentRow()
        if row < 0 or row >= self.playlist_table.rowCount():
            return

        p_id = self.playlist_table.item(row, 0).text()
        title = self.playlist_table.item(row, 1).text()

        try:
            query = """
                SELECT v.title, v.status, pi.position, pi.vid_id, pi.added
                FROM videos v
                JOIN playlist_items pi ON v.vid_id = pi.vid_id
                WHERE pi.p_id = ?
                ORDER BY pi.position ASC
            """
            self.cursor.execute(query, (p_id,))
            videos = self.cursor.fetchall()

            if not videos:
                self.details_viewer.append("No videos found in this playlist.")
                return

            self.details_viewer.clear()
            self.details_viewer.append(f"=== {title} ===\n")
            self.details_viewer.append(f"Total Videos: {len(videos)}\n")
            self.details_viewer.append("-" * 50 + "\n")

            for title_text, status, position, vid_id, added_timestamp in videos:
                try:
                    added = datetime.fromtimestamp(int(added)).strftime("%Y-%m-%d %H:%M:%S")
                except:
                    added = str(added_timestamp)

                self.details_viewer.append(
                    f"{position + 1}. {title_text} [{status}] - "
                    f"https://www.youtube.com/watch?v={vid_id}"
                )

            if len(videos) > 50:
                self.details_viewer.append("-" * 50 + "\n")
                self.details_viewer.append(
                    f"(Showing all {len(videos)} videos. Use browser for full playlist view.)"
                )

        except Exception as e:
            self.details_viewer.append(f"Error loading all videos: {e}")


def create_gui_application(conn, cursor):
    """
    Factory function to create the GUI application.
    
    Args:
        app: QApplication instance (created externally)
        conn: SQLite3 connection object
        cursor: SQLite3 cursor object
    
    Returns:
        The PlaylistArchiverGUI instance (which contains the MainWindow)
    """
    app = QApplication([])
    gui = PlaylistArchiverGUI(app)
    gui.set_db_connection(conn, cursor)
    return gui

