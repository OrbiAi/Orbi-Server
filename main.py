from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import sqlite3
from datetime import datetime
import uuid
import json
from queue import Queue
from threading import Thread
import pytesseract
import requests
from datetime import datetime
from db_utils import get_stats, get_captures, get_capture_info, delete_capture

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

with open('config.json') as config_file:
    config = json.load(config_file)

DATA_DIR = config['data_dir']
DATABASE = os.path.join(DATA_DIR, 'captures.db')
OLLAMA_SERVER = config['ollama_server']
TESSERACT_CMD = config['tesseract_dir']
HOST = config['host']
PORT = config['port']

from frontend import frontend
app.register_blueprint(frontend)

def init_db():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.exists(os.path.join(DATA_DIR, 'images')):
        os.makedirs(os.path.join(DATA_DIR, 'images'))
    conn = sqlite3.connect(DATABASE, check_same_thread=False)
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

init_db()

conn = sqlite3.connect(DATABASE, check_same_thread=False)
cursor = conn.cursor()

# mark all incomplete captures as failed
incomplete_captures = get_captures(incomplete_only=True)
print(f"Marking {len(incomplete_captures)} incomplete captures as failed")
for capture in incomplete_captures:
    cursor.execute('''
        UPDATE captures SET processed = 2 WHERE id = ?
    ''', (capture['id'],))
conn.commit()

capture_queue = Queue()
retry_limit = 1  # todo: add to config.json

def process_capture():
    while True:
        capture_id, retries = capture_queue.get()
        try:
            print(f"Processing capture {capture_id}, attempt {retries + 1}")
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
            # mark as processed
            cursor.execute('''
                UPDATE captures SET processed = 1 WHERE id = ?
            ''', (capture_id,))
            conn.commit()
            print(f"Capture {capture_id} processed successfully.")
        except Exception as e:
            print(f"Error processing capture {capture_id}: {e}")
            if retries < retry_limit - 1:
                capture_queue.put((capture_id, retries + 1))
            else:
                print(f"Capture {capture_id} failed after {retry_limit} attempts.")
                # proccessed = 2 means failed
                cursor.execute('''
                    UPDATE captures SET processed = 2 WHERE id = ?
                ''', (capture_id,))
                conn.commit()
        finally:
            capture_queue.task_done()

# modify queue to include retry count
def add_capture_to_queue(capture_id):
    capture_queue.put((capture_id, 0))

Thread(target=process_capture, daemon=True).start()

@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.strftime(format)

@app.template_filter('to_datetime')
def to_datetime(value):
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value

@app.route('/api/submit', methods=['POST'])
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
        # add to queue for processing
        add_capture_to_queue(capture_id)
        return jsonify(message="Capture submitted"), 200

@app.route('/api/search', methods=['GET'])
def search_endpoint():
    query = request.args.get('query', '')
    max_items = request.args.get('max', type=int, default=-1)
    skip_items = request.args.get('skip', type=int, default=0)
    processed_only = request.args.get('processed_only', 'false').lower() == 'true'
    capture_list = get_captures(max=max_items, skip=skip_items, search=query, processed_only=processed_only)
    return jsonify(capture_list)

@app.route('/api/info/<id>', methods=['GET'])
def info_endpoint(id):
    capture_dict = get_capture_info(id)
    if not capture_dict:
        return jsonify(message="Capture not found"), 404
    return jsonify(capture_dict)

@app.route('/api/delete/<id>', methods=['DELETE'])
def delete_endpoint(id):
    if delete_capture(id):
        return jsonify(message="Capture and image deleted")
    else:
        return jsonify(message="Capture not found"), 404
    
@app.route('/api/images/<name>', methods=['GET'])
def images_endpoint(name):
    print(os.path.join(DATA_DIR, 'images', name))
    return send_from_directory(os.path.join(DATA_DIR, 'images'), name)

@app.route('/api/stats', methods=['GET'])
def stats_endpoint():
    total_captures, processed_captures, readable_size = get_stats()
    return jsonify({
        'total_captures': total_captures,
        'processed_captures': processed_captures,
        'total_size': readable_size
    })

if __name__ == '__main__':
    app.run(debug=True, host=HOST, port=PORT)