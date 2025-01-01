from flask import Flask, jsonify, request, send_from_directory
import os
import sqlite3
from datetime import datetime
import uuid
import json
from queue import Queue
from threading import Thread
import pytesseract
import requests

app = Flask(__name__)

with open('config.json') as config_file:
    config = json.load(config_file)

DATA_DIR = config['data_dir']
DATABASE = os.path.join(DATA_DIR, 'captures.db')
OLLAMA_SERVER = config['ollama_server']
TESSERACT_CMD = config['tesseract_dir']
HOST = config['host']
PORT = config['port']

def init_db():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.exists(os.path.join(DATA_DIR, 'images')):
        os.makedirs(os.path.join(DATA_DIR, 'images'))
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS captures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            image_name TEXT NOT NULL,
            focused_window TEXT,
            open_windows TEXT,
            text_seen TEXT,
            ai_description TEXT,
            processed BOOLEAN DEFAULT FALSE
        )
    ''')
    conn.commit()
    conn.close()

capture_queue = Queue()

def process_capture():
    while True:
        capture_id = capture_queue.get()
        print(f"Processing capture {capture_id}")
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        # get info
        cursor.execute('''
            SELECT * FROM captures WHERE id = ?
        ''', (capture_id,))
        capture = cursor.fetchone()
        file_name = capture[2]
        file_path = os.path.join(os.path.join(DATA_DIR, 'images'), file_name)
        focused_window = capture[3]
        open_windows = capture[4]
        # ocr
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
        text_seen = ' '.join(pytesseract.image_to_string(file_path).split())
        cursor.execute('''
            UPDATE captures SET text_seen = ? WHERE id = ?
        ''', (text_seen, capture_id))
        # ai
        data = {
            "model": "llama3:8b",
            "system": "You will be given text, which is seen on someone's computer screen, as well as their open windows. Your ONLY job is to respond with an assumption of what you think they're doing on their computer.  You shouldn't mention why you think so, you should just say what they're doing, say it clearly, be confident. You should provide it in a documentation-style text, should be 1-6 sentences in a 3rd person view and past simple time, refer to the user as 'user'. You should ONLY say about what the user is currently doing on the MAIN window, unless the other windows are clearly related.",
            "prompt": f"Focused window: {focused_window}\nOpen windows: {open_windows}\nText on screen: {text_seen}",
            "stream": False
        }
        r = requests.post(OLLAMA_SERVER, json=data)
        r.raise_for_status()
        ai_description = r.json()['response']
        cursor.execute('''
            UPDATE captures SET ai_description = ? WHERE id = ?
        ''', (ai_description, capture_id))
        # ---
        cursor.execute('''
            UPDATE captures SET processed = 1 WHERE id = ?
        ''', (capture_id,))
        conn.commit()
        conn.close()
        capture_queue.task_done()

Thread(target=process_capture, daemon=True).start()

@app.route('/')
def index():
    return jsonify({ "info": "This is the internal API used for Orbi. For documentation, visit the GitHub repo." })

@app.route('/submit', methods=['POST'])
def submit_endpoint():
    if 'file' not in request.files:
        return jsonify(message="No file part"), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify(message="No selected file"), 400

    json_data = request.form.get('json')
    if json_data:
        json_data = json.loads(json_data)
        if json_data['windows'].get('focused') is None or json_data['windows'].get('open') is None:
            json_data = None

    if file:
        file_name = str(uuid.uuid4()) + '.jpg'  # generate unique name
        file_path = os.path.join(os.path.join(DATA_DIR, 'images'), file_name)
        file.save(file_path)
        # write to db
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        if not json_data:
            cursor.execute('''
                INSERT INTO captures (timestamp, image_name) VALUES (?, ?)
            ''', (datetime.now().isoformat(), file_name))
        else:
            cursor.execute('''
                INSERT INTO captures (timestamp, image_name, focused_window, open_windows) VALUES (?, ?, ?, ?)
            ''', (datetime.now().isoformat(), file_name, json_data['windows']['focused'], str(json_data['windows']['open'])))
        capture_id = cursor.lastrowid
        conn.commit()
        conn.close()
        # add to queue for processing
        capture_queue.put(capture_id)
        return jsonify(message="Capture submitted"), 200

@app.route('/search', methods=['GET'])
def search_endpoint():
    query = request.args.get('query', '')
    max_items = request.args.get('max', type=int, default=-1)
    skip_items = request.args.get('skip', type=int, default=0)
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM captures
        WHERE LOWER(open_windows) LIKE LOWER(?) OR LOWER(text_seen) LIKE LOWER(?)
        ORDER BY id DESC
        LIMIT ? OFFSET ?
    ''', (f'%{query}%', f'%{query}%', max_items if max_items > 0 else -1, skip_items))
    captures = cursor.fetchall()
    conn.close()
    
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
    
    return jsonify(capture_list)

@app.route('/info/<id>', methods=['GET'])
def info_endpoint(id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM captures WHERE id = ?
    ''', (id,))
    capture = cursor.fetchone()
    conn.close()
    if not capture:
        return jsonify(message="Capture not found"), 404
    
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
    return jsonify(capture_dict)

@app.route('/delete/<id>', methods=['DELETE'])
def delete_endpoint(id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT image_name FROM captures WHERE id = ?
    ''', (id,))
    capture = cursor.fetchone()
    if capture:
        image_name = capture[0]
        image_path = os.path.join(os.path.join(DATA_DIR, 'images'), image_name)
        if os.path.exists(image_path):
            os.remove(image_path)
        cursor.execute('''
            DELETE FROM captures WHERE id = ?
        ''', (id,))
        conn.commit()
        conn.close()
        return jsonify(message="Capture and image deleted")
    else:
        conn.close()
        return jsonify(message="Capture not found"), 404
    
@app.route('/images/<name>', methods=['GET'])
def images_endpoint(name):
    print(os.path.join(DATA_DIR, 'images', name))
    return send_from_directory(os.path.join(DATA_DIR, 'images'), name)

@app.route('/stats', methods=['GET'])
def stats_endpoint():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) FROM captures
    ''')
    total_captures = cursor.fetchone()[0]
    conn.close()
    
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(DATA_DIR):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    
    return jsonify({
        'total_captures': total_captures,
        'total_size': total_size
    })

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host=HOST, port=PORT)