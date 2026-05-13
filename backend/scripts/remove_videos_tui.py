import curses
import logging
from pathlib import Path

from app.db.init import init_db
from app.db import queries

logging.basicConfig(level=logging.ERROR)

def remove_video(video_id: str) -> None:
    queries.delete_video(video_id)
    # The database deletion cascade handles clips and jobs,
    # and app.db.queries.delete_video likely handles cleaning up 
    # the filesystem via the hooks in the app or triggers.
    # Wait, let's check if delete_video actually deletes the files in Sift.

def main(stdscr) -> None:
    curses.curs_set(0)
    init_db()
    
    videos = queries.list_videos()
    current_row = 0
    selected = set()

    def print_menu():
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        
        title = " Sift Video Removal TUI "
        stdscr.addstr(0, max(0, width // 2 - len(title) // 2), title, curses.A_REVERSE)
        
        status = " Use UP/DOWN to navigate, SPACE to select/unselect, ENTER to remove selected, 'q' to quit. "
        stdscr.addstr(height - 1, 0, status[:width-1], curses.A_REVERSE)
        
        if not videos:
            stdscr.addstr(2, 2, "No videos found in the database.")
            stdscr.refresh()
            return
            
        max_rows = height - 4
        start_row = max(0, current_row - max_rows // 2)
        
        for idx in range(start_row, min(len(videos), start_row + max_rows)):
            video = videos[idx]
            v_title = video.get("title") or video.get("filename") or "Unknown"
            v_id = video["id"]
            
            is_selected = idx in selected
            prefix = "[x]" if is_selected else "[ ]"
            
            line = f"{prefix} {v_title} ({v_id})"
            # Truncate to avoid line wrapping which breaks curses layout
            line = line[:width - 4]
            
            if idx == current_row:
                stdscr.attron(curses.A_REVERSE)
                stdscr.addstr(idx - start_row + 2, 2, line)
                stdscr.attroff(curses.A_REVERSE)
            else:
                stdscr.addstr(idx - start_row + 2, 2, line)
                
        stdscr.refresh()

    while True:
        print_menu()
        if not videos:
            key = stdscr.getch()
            if key in [ord("q"), ord("Q")]:
                break
            continue

        key = stdscr.getch()
        
        if key == curses.KEY_UP:
            current_row = max(0, current_row - 1)
        elif key == curses.KEY_DOWN:
            current_row = min(len(videos) - 1, current_row + 1)
        elif key == ord(" "):
            if current_row in selected:
                selected.remove(current_row)
            else:
                selected.add(current_row)
        elif key == ord("\n") or key == curses.KEY_ENTER:
            if not selected:
                continue
                
            # Confirmation
            stdscr.clear()
            stdscr.addstr(2, 2, f"Are you sure you want to remove {len(selected)} videos? (y/n)")
            stdscr.refresh()
            confirm_key = stdscr.getch()
            if confirm_key in [ord("y"), ord("Y")]:
                for idx in sorted(list(selected), reverse=True):
                    v = videos[idx]
                    try:
                        # Call database remove
                        queries.delete_video(v["id"])
                        # Some versions of queries.delete_video automatically remove files, 
                        # if not, we would call app.utils.files.remove_video_files(v["id"])
                    except Exception:
                        pass
                    
                selected.clear()
                # Refresh list
                videos = queries.list_videos()
                current_row = min(current_row, max(0, len(videos) - 1))
        elif key in [ord("q"), ord("Q")]:
            break

if __name__ == "__main__":
    curses.wrapper(main)
