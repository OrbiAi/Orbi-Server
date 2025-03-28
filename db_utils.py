import os
import sqlite3
import json
from contextlib import contextmanager

with open('config.json') as config_file:
    config = json.load(config_file)

DATA_DIR = config['data_dir']
DATABASE = os.path.join(DATA_DIR, 'captures.db')

@contextmanager
def get_db_connection():
    """Provide a context-managed database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
    try:
        yield conn
    finally:
        conn.close()

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024

def get_stats():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # get total captures
        cursor.execute('''
            SELECT COUNT(*) FROM captures
        ''')
        total_captures = cursor.fetchone()[0]
        # get processed captures
        cursor.execute('''
            SELECT COUNT(*) FROM captures WHERE processed = 1
        ''')
        processed_captures = cursor.fetchone()[0]
        # get total size
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(DATA_DIR):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        readable_size = format_size(total_size)
    return total_captures, processed_captures, readable_size

def get_captures(max=-1, skip=0, search="", processed_only=False, failed_only=False, incomplete_only=False):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = '''
            SELECT * FROM captures
            WHERE (LOWER(open_windows) LIKE LOWER(?) OR LOWER(text_seen) LIKE LOWER(?))
        '''
        params = ['%' + search + '%', '%' + search + '%']
        
        if incomplete_only:
            query += ' AND processed = 0'
        if processed_only:
            query += ' AND processed = 1'
        if failed_only:
            query += ' AND processed = 2'
        
        query += ' ORDER BY id DESC LIMIT ? OFFSET ?'
        params.extend([max, skip])
        
        cursor.execute(query, params)
        captures = cursor.fetchall()
        capture_list = []
        for capture in captures:
            capture_dict = {
                'id': capture[0],
                'timestamp': capture[1],
                'image_name': capture[2],
                'focused_window': capture[3],
                'open_windows': capture[4],
                'text_seen': capture[5],
                'ai_description': capture[6],
                'processed': capture[7]
            }
            capture_list.append(capture_dict)
    return capture_list

def get_capture_info(capture_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM captures WHERE id = ?
        ''', (capture_id,))
        capture = cursor.fetchone()
    if not capture:
        return None
    capture_dict = {
        'id': capture[0],
        'timestamp': capture[1],
        'image_name': capture[2],
        'focused_window': capture[3],
        'open_windows': capture[4],
        'text_seen': capture[5],
        'ai_description': capture[6],
        'processed': capture[7]
    }
    return capture_dict

def delete_capture(capture_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT image_name FROM captures WHERE id = ?
        ''', (capture_id,))
        capture = cursor.fetchone()
        if capture:
            image_name = capture[0]
            image_path = os.path.join(os.path.join(DATA_DIR, 'images'), image_name)
            if os.path.exists(image_path):
                os.remove(image_path)
            cursor.execute('''
                DELETE FROM captures WHERE id = ?
            ''', (capture_id,))
            conn.commit()
            return True
        else:
            return False

def mass_action_failed_captures(action):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if action == 'delete':
            cursor.execute('''
                SELECT image_name FROM captures WHERE processed = 2
            ''')
            failed_captures = cursor.fetchall()
            for capture in failed_captures:
                image_name = capture[0]
                image_path = os.path.join(os.path.join(DATA_DIR, 'images'), image_name)
                if os.path.exists(image_path):
                    os.remove(image_path)
            cursor.execute('''
                DELETE FROM captures WHERE processed = 2
            ''')
        elif action == 'retry':
            cursor.execute('''
                UPDATE captures SET processed = 0 WHERE processed = 2
            ''')
        conn.commit()