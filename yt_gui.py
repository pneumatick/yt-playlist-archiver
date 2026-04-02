#!/usr/bin/env python3
"""
YouTube Playlist Archiver - Graphical User Interface
A Tkinter-based GUI for the YouTube Playlist Archiver tool.
"""

import os
import sys
import sqlite3
from tkinter import *
from tkinter import ttk, messagebox, filedialog as fd
import datetime

# Global treeview widgets (shared between class methods and global functions)
# These are initialized to None and set by the GUI class when needed
playlist_treeview = None
video_treeview = None

# Helper function to get module-level status variable (uses provided master)
def _get_status_var(master=None):
    """Get or create StringVar for status bar."""
    global status_var
    if status_var is None:
        if master:
            status_var = StringVar(master, "Ready")
        else:
            # If no master provided, try to get Tk root
            try:
                from tkinter import _default_root as tk_root
                status_var = StringVar(tk_root, "Ready")
            except RuntimeError:
                status_var = None
    return status_var if status_var is not None else None


# Import core functions from main.py (excluding argparse)
import archiver as yt


# Global variables
root = None  # Tk root window
conn = None  # SQLite connection
cursor = None  # SQLite cursor
current_playlist_id = None  # Currently selected playlist

# Database tables
PLAYLIST_DATA_COLS = ['p_id', 'title', 'created', 'last_update', 'etag']
PLAYLIST_ITEMS_COLS = ['p_id', 'vid_id', 'position', 'added']
VIDEOS_COLS = ['vid_id', 'title', 'status']


def init_database():
    """Initialize/connect to the SQLite database."""
    global conn, cursor
    try:
        conn = yt.conn if yt.conn else None
        cursor = yt.cursor if yt.cursor else None
        
        if conn is None or cursor is None:
            # Instantiate a new database
            yt.instantiate_db()
            # Refresh globals
            conn = yt.conn
            cursor = yt.cursor
    except Exception as e:
        messagebox.showerror("Database Error", f"Failed to connect to database:\n{str(e)}")


def get_all_playlists():
    """Retrieve all playlists from the database."""
    try:
        if cursor is None:
            return []
        
        cursor.execute('''SELECT p_id, title, created, last_update, etag FROM playlist_data ORDER BY created DESC''')
        playlists = cursor.fetchall()
        return playlists
    except Exception as e:
        messagebox.showerror("Error", f"Failed to retrieve playlists: {str(e)}")
        return []


def load_playlists_into_treeview():
    """Load all playlists into the treeview widget."""
    try:
        # Clear existing items
        for item in playlist_treeview.get_children():
            playlist_treeview.delete(item)
        
        # Retrieve playlists
        playlists = get_all_playlists()
        
        # Add to treeview
        for p_id, title, created, last_update, etag in playlists:
            created_dt = datetime.datetime.fromtimestamp(created).strftime('%Y-%m-%d %H:%M')
            last_update_dt = datetime.datetime.fromtimestamp(last_update).strftime('%Y-%m-%d %H:%M')
            
            playlist_treeview.insert('', END, text=f"{title} (ID: {p_id})", 
                                    values=(created_dt, last_update_dt, etag[:8] if etag else ''))
        
        # Select first item if any exist
        if playlist_treeview.get_children():
            playlist_treeview.selection()[0]
            
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load playlists: {str(e)}")


def select_playlist(event):
    """Handle playlist selection."""
    selection = playlist_treeview.selection()
    if selection:
        for item in selection:
            p_id, title, created, last_update, etag = item
            
            # Update status bar
            status_var.set(f"Selected: {title} (ID: {p_id})")
            
            # Load playlist into frame
            load_playlist_videos(p_id)


def load_playlist_videos(playlist_id):
    """Load videos from a specific playlist."""
    global current_playlist_id
    
    try:
        current_playlist_id = playlist_id
        
        # Clear existing items in video treeview
        for item in video_treeview.get_children():
            video_treeview.delete(item)
        
        # Get all items from the playlist
        cursor.execute('''SELECT pi.p_id, pi.vid_id, pi.position + 1 as display_position, 
                             v.title, v.status, pi.added 
                        FROM playlist_items pi
                        JOIN videos v ON pi.vid_id = v.vid_id
                        WHERE pi.p_id = ? ORDER BY pi.position ASC''', (playlist_id,))
        
        items = cursor.fetchall()
        
        # Add to treeview with padding for position 0
        def get_position_text(pos):
            if pos is None or pos == '':
                return ''
            try:
                p = int(pos)
                if p == 0:
                    return '---'  # Indicate no position (playlist order)
                return str(p)
            except:
                return str(pos) if pos else ''
        
        for item in items:
            display_pos = get_position_text(item[2])
            status_icon = f"✓" if item[4] == 'private' else "▶"  # private/playable icons
            video_treeview.insert('', END, text=f"{status_icon} {item[3][:30]}", 
                                  values=(display_pos, item[1], item[5]))
            
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load playlist videos: {str(e)}")


def archive_playlist():
    """Archive a new playlist or check for changes in an existing one."""
    try:
        # Check if already archived, if so, offer update option
        cursor.execute('''SELECT * FROM playlist_data WHERE p_id = ?''', (current_playlist_id,))
        result = cursor.fetchone()
        
        if result:
            # Ask user what to do with existing playlist
            response = messagebox.askyesnocancel(
                "Playlist Exists",
                f"This playlist is already archived.\n\n"
                f"What would you like to do?\n\n"
                "[Yes] Update playlist (check for new videos)\n"
                "[No] Return to playlists list\n"
                "[Cancel] Cancel operation"
            )
            
            if response == 'yes':
                # Update existing playlist
                yt.peek_playlist_top(current_playlist_id)
                messagebox.showinfo("Update Complete", "Playlist updated successfully!")
            elif response == 'no':
                return  # User returned to playlists list
            elif response == 'cancel':
                return  # User cancelled
        
        else:
            # New playlist - ask for playlist ID
            playlist_id = input(f"\nEnter Playlist ID:\n>")
            
            if not playlist_id or playlist_id.strip() == "":
                messagebox.showwarning("Warning", "No playlist ID provided.")
                return
            
            # Ask how many items to archive or archive entire playlist
            while True:
                response = messagebox.askyesnocancel(
                    "Archive New Playlist",
                    f"Archive the entire playlist?\n\n"
                    "[Yes] Archive all videos\n"
                    "[No] Return to playlists list\n"
                    "[Cancel] Cancel operation"
                )
                
                if response == 'no':
                    return
                elif response == 'cancel':
                    return
                
                # Archive the playlist
                yt.archive_playlist(playlist_id)
                messagebox.showinfo("Success", "Playlist archived successfully!")
                return
                
    except Exception as e:
        messagebox.showerror("Error", f"Failed to archive playlist: {str(e)}")


def delete_playlist():
    """Delete a playlist from the database."""
    if not current_playlist_id:
        messagebox.showwarning("Warning", "No playlist selected.")
        return
    
    response = messagebox.askyesnocancel(
        "Delete Playlist?",
        f"Are you sure you want to permanently delete:\n{current_playlist_id}\n\n"
        f"This will remove all associated data."
    )
    
    if response == 'yes':
        try:
            yt.delete_playlist(current_playlist_id)
            messagebox.showinfo("Success", "Playlist deleted successfully!")
            load_playlists_into_treeview()  # Refresh playlist list
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete playlist: {str(e)}")
    elif response == 'no':
        return  # User cancelled


def export_playlist():
    """Export selected playlist to CSV files."""
    if not current_playlist_id:
        messagebox.showwarning("Warning", "No playlist selected.")
        return
    
    try:
        file_path = yt.export_playlist(current_playlist_id)
        
        if file_path:
            # Parse the returned path from export_playlist
            # The function returns None or raises exception on error
            pass
        
        messagebox.showinfo("Export Complete", 
                          "Playlist exported successfully!")
        
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export playlist: {str(e)}")


def search_videos():
    """Search for videos using FTS5."""
    query = input("\nEnter search query:\n>")
    
    if not query or query.strip() == "":
        messagebox.showwarning("Warning", "No search query provided.")
        return
    
    # Get playlist ID from selection or ask for it
    if current_playlist_id:
        try:
            yt.search_in_playlist_fts(current_playlist_id, query)
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {str(e)}")
    else:
        # Search all videos
        try:
            yt.search_all_videos_fts(query)
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {str(e)}")


def import_playlist():
    """Import a playlist from CSV files."""
    file_path = fd.askopenfilename(
        title="Select Playlist File",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    
    if not file_path:
        return
    
    # Extract base filename (remove path)
    base_name = os.path.basename(file_path)
    if base_name.endswith('.meta'):
        csv_file = f"{base_name[:-5]}.csv"
    else:
        csv_file = f"{base_name[:-4]}"
    
    try:
        yt.import_playlist(csv_file)
        messagebox.showinfo("Import Complete", "Playlist imported successfully!")
        load_playlists_into_treeview()  # Refresh playlist list
    except Exception as e:
        messagebox.showerror("Error", f"Failed to import playlist: {str(e)}")


def check_changes():
    """Check if a playlist has changed since last archive."""
    if not current_playlist_id:
        messagebox.showwarning("Warning", "No playlist selected.")
        return
    
    try:
        changed, etag = yt.check_playlist_for_changes(current_playlist_id)
        
        if changed:
            messagebox.showinfo("Change Detected",
                              f"Playlist {current_playlist_id} has changed since last archive.\n"
                              f"Etag: {etag}\n\nUse Archive to fetch new content.")
        else:
            messagebox.showinfo("No Changes",
                              f"Playlist {current_playlist_id} is up to date with the YouTube API.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to check for changes: {str(e)}")


def open_in_browser(url):
    """Open a URL in the default browser."""
    import webbrowser
    webbrowser.open(url)


def update_status_bar(status_text):
    """Update the status bar text."""
    status_var.set(status_text)


class PlaylistArchiverGUI:
    """Main GUI Application for YouTube Playlist Archiver."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Playlist Archiver")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # Configure style
        self.setup_styles()
        
        # Initialize database
        init_database()
        
        # Create main container
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create pages
        self.create_dashboard_tab()
        self.create_playlist_tab()
        self.create_archive_tab()
        self.create_search_tab()
        self.create_import_export_tab()
        
        # Setup status bar
        self.status_var = StringVar(value="Ready")
        self.status_frame = ttk.Frame(root)
        self.status_frame.pack(fill='x', side='bottom')
        self.status_label = ttk.Label(self.status_frame, textvariable=self.status_var, 
                                      anchor='w', style='TLabel')
        self.status_label.pack(side='right', fill='x', expand=True)
        
        # Setup log console (optional feature - similar to CLI output)
        self.log_frame = ttk.Frame(root)
        self.log_frame.pack(fill='both', expand=False, side='bottom')
        self.console_text = Text(self.log_frame, height=8, width=100)
        scrollbar = ttk.Scrollbar(self.log_frame, orient="vertical", command=self.console_text.yview)
        self.console_text.configure(yscrollcommand=scrollbar.set)
        
        self.console_text.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.log_frame.pack_propagate(False)
    
    def setup_styles(self):
        """Setup ttk styles."""
        style = ttk.Style()
        
        # Configure treeview styles
        style.configure("Treeview", rowheight=25)
        style.configure("Treeview.Heading", font=("Arial", 9, "bold"))
        
        # Configure notebook tabs
        style.configure("TNotebook.Tab", padding=10)
    
    def create_dashboard_tab(self):
        """Create the dashboard tab (list all playlists)."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Dashboard")
        
        # Title
        title_label = ttk.Label(frame, text="YouTube Playlist Archiver", font=("Arial", 16, "bold"))
        title_label.pack(side='top', pady=10)
        
        # Subtitle
        subtitle_label = ttk.Label(frame, 
                                   text="View and manage your archived playlists")
        subtitle_label.pack(side='top', pady=(5, 20))
        
        # Search bar for filtering playlists
        search_frame = ttk.Frame(frame)
        search_frame.pack(fill='x', pady=10)
        
        self.playlist_search_var = StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.playlist_search_var, 
                                 width=50)
        search_entry.pack(side='left', fill='x', expand=True)
        search_entry.bind('<KeyRelease>', lambda e: self.filter_playlists())
        
        # Refresh button
        refresh_btn = ttk.Button(search_frame, text="Refresh", command=lambda: load_playlists_into_treeview())
        refresh_btn.pack(side='right', padx=(5, 0))
        
        # Treeview for playlists
        columns = ('created', 'last_update', 'etag')
        self.playlist_treeview = ttk.Treeview(frame, columns=columns, show='headings', height=15)
        
        self.playlist_treeview.heading('#0', text='Playlist', anchor='w')
        self.playlist_treeview.heading('created', text='Created')
        self.playlist_treeview.heading('last_update', text='Last Updated')
        self.playlist_treeview.heading('etag', text='Etag (truncated)')
        
        self.playlist_treeview.heading('#0', command=lambda event: select_playlist(None))  # Selection handler placeholder
        
        self.playlist_treeview.column('#0', width=350)
        self.playlist_treeview.column('created', width=140)
        self.playlist_treeview.column('last_update', width=140)
        self.playlist_treeview.column('etag', width=200)
        
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.playlist_treeview.yview)
        self.playlist_treeview.configure(yscrollcommand=scrollbar.set)
        
        # Use pack layout for treeview and scrollbar (consistent with parent frame using pack)
        self.playlist_treeview.pack(fill='both', expand=True, padx=(0, 5))
        scrollbar.pack(side='right', fill='y')
        
        # Add sample playlists if empty (for demonstration)
        if len(self.playlist_treeview.get_children()) == 0:
            load_playlists_into_treeview()
    
    def filter_playlists(self):
        """Filter playlists based on search query."""
        search_text = self.playlist_search_var.get().lower()
        
        for item in self.playlist_treeview.get_children():
            title_col = self.playlist_treeview.item(item, 'text')
            if search_text in title_col.lower():
                self.playlist_treeview.see(item)
    
    def create_playlist_tab(self):
        """Create the playlist view tab (show videos in selected playlist)."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Playlist View")
        
        # Back button
        back_btn = ttk.Button(frame, text="<< Back to Dashboard", command=lambda: load_playlists_into_treeview())
        back_btn.pack(anchor='nw', pady=(0, 10))
        
        # Playlist info header
        header_frame = ttk.Frame(frame)
        header_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        self.playlist_id_label = ttk.Label(header_frame, text="Playlist ID: ", anchor='w')
        self.playlist_id_label.pack(side='left')
        
        self.playlist_title_label = ttk.Label(header_frame, text="", font=("Arial", 14, "bold"), anchor='w')
        self.playlist_title_label.pack(side='left', padx=(20, 0))
        
        # Action buttons row
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', padx=10)
        
        action_btns = [
            ("Archive", "archive_playlist", None),
            ("Delete", "delete_playlist", None),
            ("Check Changes", "check_changes", None),
            ("Export", "export_playlist", None),
            ("Search", "search_videos", None),
            ("Open in Browser", "open_in_browser", None),
        ]
        
        for i, (text, method, func_args) in enumerate(action_btns):
            btn = ttk.Button(btn_frame, text=text, command=method)
            btn.pack(side='left', padx=5, pady=5)
        
        # Video list treeview
        video_frame = ttk.Frame(frame)
        video_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        columns = ('position', 'vid_id', 'added')
        self.video_treeview = ttk.Treeview(video_frame, columns=columns, show='headings', height=20)
        
        self.video_treeview.heading('#0', text='Video', anchor='w')
        self.video_treeview.heading('position', text='Position')
        self.video_treeview.heading('vid_id', text='Video ID')
        self.video_treeview.heading('added', text='Added')
        
        self.video_treeview.column('#0', width=350)
        self.video_treeview.column('position', width=80)
        self.video_treeview.column('vid_id', width=150)
        self.video_treeview.column('added', width=140)
        
        scrollbar = ttk.Scrollbar(video_frame, orient="vertical", command=self.video_treeview.yview)
        self.video_treeview.configure(yscrollcommand=scrollbar.set)
        
        # Use pack layout for treeview and scrollbar (consistent with parent frame using pack)
        self.video_treeview.pack(fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
    
    def create_archive_tab(self):
        """Create the archive tab (archive new playlists)."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Archive Playlist")
        
        # Title
        title_label = ttk.Label(frame, text="Archive New Playlist", font=("Arial", 16, "bold"))
        title_label.pack(side='top', pady=20)
        
        # Instructions
        instructions_text = """Enter the playlist ID below to archive a new playlist from YouTube.
        
If you want to update an already archived playlist, go to the Dashboard and select it."""
        
        instructions_label = ttk.Label(frame, text=instructions_text, justify='left')
        instructions_label.pack(side='top', pady=(0, 20))
        
        # Input frame
        input_frame = ttk.Frame(frame)
        input_frame.pack(fill='x', padx=40, pady=(0, 30))
        
        ttk.Label(input_frame, text="Playlist ID:").grid(row=0, column=0, sticky='w')
        
        self.archive_playlist_id_var = StringVar()
        archive_entry = ttk.Entry(input_frame, textvariable=self.archive_playlist_id_var, width=50)
        archive_entry.grid(row=0, column=1, sticky='ew', padx=(0, 10))
        
        # Action buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=(0, 20))
        
        archive_btn = ttk.Button(btn_frame, text="Archive", command=self.run_archive)
        archive_btn.pack(side='left', padx=5)
        
        return_btn = ttk.Button(btn_frame, text="Return to Dashboard", 
                               command=lambda: load_playlists_into_treeview())
        return_btn.pack(side='left', padx=5)
    
    def run_archive(self):
        """Run the archive action on selected playlist."""
        if current_playlist_id:
            self.archive_playlist()
        else:
            # Get input from tab entry field
            playlist_id = self.archive_playlist_id_var.get().strip()
            if playlist_id:
                self.current_archive_id = playlist_id
    
    def create_search_tab(self):
        """Create the search tab (FTS5 full-text search)."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Search Videos")
        
        # Title
        title_label = ttk.Label(frame, text="Search Videos", font=("Arial", 16, "bold"))
        title_label.pack(side='top', pady=20)
        
        # Instructions
        instructions_text = """Search for videos using full-text search.
        
- If a playlist is selected from the Dashboard, search will be limited to that playlist.
- Otherwise, search across all archived videos."""
        
        instructions_label = ttk.Label(frame, text=instructions_text, justify='left')
        instructions_label.pack(side='top', pady=(0, 20))
        
        # Search input frame
        input_frame = ttk.Frame(frame)
        input_frame.pack(fill='x', padx=40, pady=(0, 30))
        
        ttk.Label(input_frame, text="Search Query:").grid(row=0, column=0, sticky='w')
        
        self.search_query_var = StringVar()
        search_entry = ttk.Entry(input_frame, textvariable=self.search_query_var, width=50)
        search_entry.grid(row=0, column=1, sticky='ew', padx=(0, 10))
        
        # Action buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=(0, 20))
        
        search_btn = ttk.Button(btn_frame, text="Search", command=self.run_search)
        search_btn.pack(side='left', padx=5)
        
        back_btn = ttk.Button(btn_frame, text="Back to Dashboard", 
                            command=lambda: load_playlists_into_treeview())
        back_btn.pack(side='left', padx=5)
    
    def run_search(self):
        """Run the search action."""
        query = self.search_query_var.get().strip()
        if query:
            search_videos()
    
    def create_import_export_tab(self):
        """Create the import/export tab."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Import / Export")
        
        # Title
        title_label = ttk.Label(frame, text="Import & Export Playlists", font=("Arial", 16, "bold"))
        title_label.pack(side='top', pady=20)
        
        # Instructions
        instructions_text = """Manage your playlist archives by importing or exporting to CSV files.
        
- Export: Convert a playlist to CSV (for backup or sharing)
- Import: Restore a playlist from a previously exported CSV file"""
        
        instructions_label = ttk.Label(frame, text=instructions_text, justify='left')
        instructions_label.pack(side='top', pady=(0, 20))
        
        # Export section
        export_frame = ttk.LabelFrame(frame, text="Export Playlist", padding=15)
        export_frame.pack(fill='x', padx=20, pady=(0, 10))
        
        btn_frame = ttk.Frame(export_frame)
        btn_frame.pack()
        
        export_btn = ttk.Button(btn_frame, text="Export Selected Playlist...", 
                               command=self.run_export)
        export_btn.pack(side='left', padx=5)
        
        # Import section
        import_frame = ttk.LabelFrame(frame, text="Import Playlist", padding=15)
        import_frame.pack(fill='x', padx=20, pady=(0, 10))
        
        btn_frame = ttk.Frame(import_frame)
        btn_frame.pack()
        
        import_btn = ttk.Button(btn_frame, text="Import Playlist from CSV...", 
                               command=self.run_import)
        import_btn.pack(side='left', padx=5)
        
        # Back button
        back_btn = ttk.Button(frame, text="Back to Dashboard", 
                            command=lambda: load_playlists_into_treeview())
        back_btn.pack(pady=(10, 20))
    
    def run_export(self):
        """Run the export action."""
        if current_playlist_id:
            self.export_playlist()
        else:
            messagebox.showwarning("Warning", "No playlist selected for export.")
    
    def run_import(self):
        """Run the import action."""
        self.import_playlist()
    
    def on_closing(self):
        """Handle application close event."""
        if messagebox.askyesno("Close Application", 
                              "Are you sure you want to close the application?\n"
                              "Unsaved changes will be lost."):
            # Close database connection
            if conn:
                conn.close()
            self.root.destroy()


def run_gui():
    """Launch the GUI application."""
    root = Tk()
    app = PlaylistArchiverGUI(root)
    
    # Register close event
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Run main loop
    root.mainloop()
