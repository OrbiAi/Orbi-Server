import os
import sqlite3
import json

with open('config.json') as config_file:
    config = json.load(config_file)

DATA_DIR = config['data_dir']
DATABASE = os.path.join(DATA_DIR, 'captures.db')

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024

def get_stats():
    conn = sqlite3.connect(DATABASE)
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
    conn.close()
    return total_captures, processed_captures, readable_size

def get_captures(max=-1, skip=0, search="", ignore_incomplete=False):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    query = '''
        SELECT * FROM captures
        WHERE (LOWER(open_windows) LIKE LOWER(?) OR LOWER(text_seen) LIKE LOWER(?))
    '''
    params = ['%' + search + '%', '%' + search + '%']
    
    if ignore_incomplete:
        query += ' AND processed = 1'
    
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
    conn.close()
    return capture_list

def get_capture_info(capture_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM captures WHERE id = ?
    ''', (capture_id,))
    capture = cursor.fetchone()
    conn.close()
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
    conn = sqlite3.connect(DATABASE)
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
        conn.close()
        return True
    else:
        conn.close()
        return False
