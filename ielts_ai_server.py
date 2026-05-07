"""
IELTS AI Proxy Server
- Nhận transcript từ web app (POST /analyze)
- Gửi tới Gemini thông qua cookie (không tốn API)
- Trả kết quả chấm điểm IELTS về cho web app
"""

import os
import sys
import json
import asyncio
import datetime
import threading
import time
import hashlib
import re
import mysql.connector
from mysql.connector import Error
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from loguru import logger
    from gemini_webapi import GeminiClient
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
except ImportError:
    print("Đang cài đặt gemini-webapi...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "gemini-webapi"])
    from loguru import logger
    from gemini_webapi import GeminiClient
    logger.remove()
    logger.add(sys.stderr, level="WARNING")

# ============================================================
# GLOBAL: Gemini client & chat (khởi tạo 1 lần duy nhất)
# ============================================================
gemini_client = None
gemini_chat = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(SCRIPT_DIR, "cookie.js")

# Directory for AI Output in the writing app
WRITING_APP_DATA_DIR = r"d:\ietls_wrrting\data\ai_output"
os.makedirs(WRITING_APP_DATA_DIR, exist_ok=True)

# Speaking project AI vocab directory (served directly by http.server)
SPEAKING_VOCAB_DIR = os.path.join(SCRIPT_DIR, "ai_vocab")
SPEAKING_SUGGESTIONS_DIR = os.path.join(SCRIPT_DIR, "ai_suggestions")
os.makedirs(SPEAKING_VOCAB_DIR, exist_ok=True)
os.makedirs(SPEAKING_SUGGESTIONS_DIR, exist_ok=True)

DICTIONARY_CACHE_FILE = os.path.join(SCRIPT_DIR, "dictionary_cache.json")
THEORY_DIR = r"d:\ietls_wrrting\pages\theory"

def load_dictionary_cache():
    if os.path.exists(DICTIONARY_CACHE_FILE):
        try:
            with open(DICTIONARY_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_to_dictionary_cache(word, data):
    cache = load_dictionary_cache()
    cache[word.lower().strip()] = data
    try:
        with open(DICTIONARY_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"[CACHE ERROR] {e}")


def load_cookies(cookie_file: str) -> tuple[str, str]:
    with open(cookie_file, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    cookie_map = {c["name"]: c["value"] for c in cookies if "name" in c}
    psid   = cookie_map.get("__Secure-1PSID", "")
    psidts = cookie_map.get("__Secure-1PSIDTS", "")
    if not psid or not psidts:
        raise ValueError("Không tìm thấy cookie __Secure-1PSID hoặc __Secure-1PSIDTS!")
    return psid, psidts


async def init_gemini():
    global gemini_client, gemini_chat
    psid, psidts = load_cookies(COOKIE_FILE)
    gemini_client = GeminiClient(psid, psidts)
    await gemini_client.init()
    
    # 1. Thử tìm chat_name từ Database trước
    db_chat_name = None
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT chat_name FROM ai_tasks WHERE status = 'success' AND chat_name IS NOT NULL ORDER BY completed_at DESC LIMIT 1")
            row = cursor.fetchone()
            if row: db_chat_name = row[0]
            cursor.close()
            conn.close()
    except: pass

    print("Đang đồng bộ cuộc trò chuyện từ Gemini...")
    conversations = gemini_client.list_chats()
    
    selected_conv = None
    
    # Ưu tiên 1: Theo Database
    if db_chat_name:
        selected_conv = next((c for c in conversations if c.title == db_chat_name), None)
        if selected_conv:
            print(f"[REUSE] Khôi phục hội thoại từ DB: {db_chat_name}")

    # Ưu tiên 2: Theo tiêu đề mặc định
    if not selected_conv:
        target_title = "chuyên gia về ielts speaking"
        selected_conv = next((c for c in conversations if target_title.lower() in c.title.lower()), None)
        if selected_conv:
            print(f"[FOUND] Tìm thấy hội thoại chuyên gia: {selected_conv.title}")

    if selected_conv:
        gemini_chat = gemini_client.start_chat(cid=selected_conv.cid)
    else:
        print(f"[NEW] Không tìm thấy hội thoại cũ, đang tạo mới...")
        gemini_chat = gemini_client.start_chat()
        
    print("[OK] Gemini đã sẵn sàng!")


# ============================================================
# MYSQL DATABASE MANAGEMENT
# ============================================================
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "ielts_speaking"
}

# Fallback JSON Queue
JSON_QUEUE_FILE = os.path.join(SCRIPT_DIR, "ai_queue.json")
def load_json_queue():
    if os.path.exists(JSON_QUEUE_FILE):
        try:
            with open(JSON_QUEUE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_json_queue(queue):
    try:
        with open(JSON_QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[JSON QUEUE ERROR] {e}")

def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        print(f"[DB ERROR] Connection failed: {e}")
        return None

def init_db():
    print("[DB] Initializing database...")
    sys.stdout.flush()
    try:
        # Connect without database to create it
        temp_config = DB_CONFIG.copy()
        db_name = temp_config.pop("database")
        print(f"[DB] Connecting to MySQL at {temp_config['host']}...")
        sys.stdout.flush()
        conn = mysql.connector.connect(**temp_config)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute(f"USE {db_name}")
        print(f"[DB] Using database {db_name}")
        sys.stdout.flush()
        
        # Create tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_tasks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                task_hash VARCHAR(64) UNIQUE,
                task_type VARCHAR(20),
                task_data JSON,
                status VARCHAR(20) DEFAULT 'pending',
                chat_name VARCHAR(255),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("[DB OK] Database and tables initialized.")
    except Error as e:
        print(f"[DB ERROR] Initialization failed: {e}")

def add_to_queue(task_type, data):
    # Create hash to avoid duplicates
    hash_str = f"{task_type}_{json.dumps(data, sort_keys=True)}"
    task_hash = hashlib.sha256(hash_str.encode()).hexdigest()
    
    conn = get_db_connection()
    if not conn:
        print(f"[QUEUE] DB Connection failed. Using JSON fallback for {task_type}.")
        queue = load_json_queue()
        hash_str = f"{task_type}_{json.dumps(data, sort_keys=True)}"
        task_hash = hashlib.sha256(hash_str.encode()).hexdigest()
        if any(t['task_hash'] == task_hash for t in queue):
            return {"status": "pending"}
        queue.append({
            "id": len(queue) + 1,
            "task_hash": task_hash,
            "task_type": task_type,
            "task_data": json.dumps(data),
            "status": "pending",
            "created_at": datetime.datetime.now().isoformat()
        })
        save_json_queue(queue)
        return {"status": "enqueued_json"}
    
    try:
        cursor = conn.cursor()
        # Check if already exists (pending or success)
        cursor.execute("SELECT status FROM ai_tasks WHERE task_hash = %s", (task_hash,))
        existing = cursor.fetchone()
        
        if existing:
            status = existing[0]
            if status == 'pending':
                print(f"[QUEUE] Task already exists with status: pending. Skipping.")
                return {"status": "pending"}
            if status == 'success':
                # Check if the file actually exists
                qid = data.get("id")
                vocab_type = data.get("vocab_type", "vocabulary")
                band = data.get("band", 8)
                
                exists = False
                if task_type == "vocab":
                    clean_qid = str(qid).replace(" ", "_").replace("/", "-")
                    filename = f"{clean_qid}_vocab_{vocab_type}.json"
                    exists = os.path.exists(os.path.join(WRITING_APP_DATA_DIR, "vocab", filename))
                elif task_type == "barem":
                    clean_qid = str(qid).replace(" ", "_").replace("/", "-")
                    filename = f"{clean_qid}_band{band}.json"
                    exists = os.path.exists(os.path.join(WRITING_APP_DATA_DIR, "suggestions", filename))
                
                if exists:
                    print(f"[QUEUE] Task already exists with status: success and file exists. Skipping.")
                    return {"status": "success"}
                else:
                    print(f"[QUEUE] Task marked as success but file missing. Re-queuing...")
        
        # Insert new task
        sql = "INSERT INTO ai_tasks (task_hash, task_type, task_data, status) VALUES (%s, %s, %s, 'pending')"
        cursor.execute(sql, (task_hash, task_type, json.dumps(data)))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "enqueued"}
    except Error as e:
        print(f"[DB ERROR] Add to queue failed: {e}. Using JSON fallback.")
        queue = load_json_queue()
        # Check if already exists
        if any(t['task_hash'] == task_hash for t in queue):
            return {"status": "pending"}
        
        queue.append({
            "id": len(queue) + 1,
            "task_hash": task_hash,
            "task_type": task_type,
            "task_data": json.dumps(data),
            "status": "pending",
            "created_at": datetime.datetime.now().isoformat()
        })
        save_json_queue(queue)
        return {"status": "enqueued_json"}

def get_queue_size():
    conn = get_db_connection()
    if not conn: return 0
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ai_tasks WHERE status = 'pending'")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except:
        return len([t for t in load_json_queue() if t['status'] == 'pending'])

async def process_queue_worker():
    global gemini_chat
    print("[WORKER] MySQL Queue worker started.")
    
    # Initial session recovery attempt
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT chat_name FROM ai_tasks WHERE status = 'success' AND chat_name IS NOT NULL ORDER BY completed_at DESC LIMIT 1")
            row = cursor.fetchone()
            if row and gemini_client:
                # If we have a previous chat name, try to find it in the client
                # This depends on your gemini_web_api library capabilities
                print(f"[WORKER] Found previous chat session: {row[0]}")
            cursor.close()
            conn.close()
    except Exception as e:
        print(f"[WORKER] Recovery error: {e}")

    while True:
        conn = get_db_connection()
        if not conn:
            # Try JSON Queue Fallback
            queue = load_json_queue()
            pending_tasks = [t for t in queue if t['status'] == 'pending']
            if pending_tasks:
                task = pending_tasks[0]
                task_id = task['id']
                task_type = task['task_type']
                data = json.loads(task['task_data'])
                
                if gemini_chat is None:
                    await asyncio.sleep(5)
                    continue
                
                print(f"\n\n[WORKER-JSON] --- PROCESSING TASK #{task_id} ---")
                try:
                    if task_type == "theory_perfection":
                        result = await generate_theory_perfection(data["filename"])
                        save_theory_to_file(data["filename"], result)
                    elif task_type == "txt_to_html_lesson":
                        result = await generate_txt_to_html_lesson(data["filename"])
                        save_lesson_to_file(data["filename"], result)
                    
                    # Mark as success
                    for t in queue:
                        if t['id'] == task_id:
                            t['status'] = 'success'
                            t['completed_at'] = datetime.datetime.now().isoformat()
                    save_json_queue(queue)
                    print(f"[WORKER-JSON] Task #{task_id} success.")
                except Exception as ex:
                    print(f"[WORKER-JSON ERROR] {ex}")
                    for t in queue:
                        if t['id'] == task_id:
                            t['status'] = 'failed'
                    save_json_queue(queue)
                
                await asyncio.sleep(5)
            else:
                await asyncio.sleep(10)
            continue
            
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Real-time progress stats
            cursor.execute("SELECT status, COUNT(*) as count FROM ai_tasks GROUP BY status")
            rows = cursor.fetchall()
            stats = {row['status']: row['count'] for row in rows}
            total = sum(stats.values())
            done = stats.get('success', 0) + stats.get('failed', 0)
            pending = stats.get('pending', 0)
            percent = (done / total * 100) if total > 0 else 0

            # Prioritize BAREM and IMAGE over VOCAB to avoid early rate limits
            cursor.execute("""
                SELECT * FROM ai_tasks 
                WHERE status = 'pending' 
                ORDER BY 
                    CASE 
                        WHEN task_type = 'writing_guide' THEN 1
                        WHEN task_type = 'theory_perfection' THEN 1
                        WHEN task_type = 'writing_sample' THEN 1
                        WHEN task_type = 'barem' THEN 2 
                        WHEN task_type = 'image' THEN 3
                        ELSE 4
                    END, 
                    created_at ASC 
                LIMIT 1
            """)
            task = cursor.fetchone()
            
            if pending > 0:
                print(f"\r[PROGRESS] {done}/{total} tasks ({percent:.1f}%) | {pending} pending", end="", flush=True)
            
            if task:
                task_id = task['id']
                task_type = task['task_type']
                data = json.loads(task['task_data'])
                
                # Check Gemini readiness
                if gemini_chat is None:
                    print(f"\n[WORKER] Gemini not ready. Waiting for initialization...")
                    await asyncio.sleep(5)
                    continue

                # Super safe title access
                chat_title = "IELTS Expert"
                try:
                    if gemini_chat:
                        if hasattr(gemini_chat, 'title'):
                            chat_title = str(gemini_chat.title)
                        elif hasattr(gemini_chat, 'metadata'):
                            if isinstance(gemini_chat.metadata, dict):
                                chat_title = gemini_chat.metadata.get("title", "IELTS Session")
                            else:
                                chat_title = "IELTS Session"
                except:
                    pass
                
                print(f"\n\n[WORKER] --- PROCESSING TASK #{task_id} ---")
                print(f"[TYPE] {task_type.upper()}")
                print(f"[CHAT] {chat_title}")
                
                error_occurred = False
                try:
                    if task['task_type'] == "barem":
                        result = await generate_barem_suggestion(data["question"], data["band"])
                        save_barem_to_file(data["id"], data["band"], result)
                    elif task['task_type'] == "vocab":
                        # Pass the chunk number to ensure diversity
                        chunk_num = data.get("chunk", 1)
                        result_json = await generate_vocab_for_question(
                            data["question"], 
                            data["count"], 
                            data.get("vocab_type", "vocabulary"),
                            chunk=chunk_num
                        )
                        save_vocab_to_file(data["id"], result_json, data.get("vocab_type", "vocabulary"))
                    elif task['task_type'] == "writing_guide":
                        result = await generate_writing_guide(data["question"], data.get("task_type_num", 2))
                        save_writing_guide_to_file(data["id"], result)
                    elif task['task_type'] == "writing_sample":
                        result = await generate_writing_sample(data["question"], data.get("task_type_num", 2), data.get("band", 8))
                        save_writing_sample_to_file(data["id"], data.get("band", 8), result)
                    elif task['task_type'] == "task1_chart":
                        result = await generate_task1_chart_data(data["question"], data["sample"], data.get("guide", ""))
                        save_chart_to_file(data["id"], result)
                    elif task['task_type'] == "theory_perfection":
                        result = await generate_theory_perfection(data["filename"])
                        save_theory_to_file(data["filename"], result)
                    elif task['task_type'] == "txt_to_html_lesson":
                        result = await generate_txt_to_html_lesson(data["filename"])
                        save_lesson_to_file(data["filename"], result)
                    
                    cursor.execute(
                        "UPDATE ai_tasks SET status = 'success', chat_name = %s, completed_at = %s WHERE id = %s",
                        (chat_title, datetime.datetime.now(), task_id)
                    )
                    conn.commit()
                    # Trigger manifest update
                    update_ai_data_list()
                except Exception as e:
                    error_occurred = True
                    err_msg = str(e)
                    print(f"[ERROR] Task #{task_id} FAILED: {err_msg}")
                    
                    if "aborted" in err_msg.lower() or "429" in err_msg or "expired" in err_msg.lower():
                        print(f"[!] [WARNING] Google Limit or Auth issue detected.")
                    
                    cursor.execute(
                        "UPDATE ai_tasks SET status = 'failed', chat_name = %s, completed_at = %s WHERE id = %s",
                        (chat_title, datetime.datetime.now(), task_id)
                    )
                
                conn.commit()
                # Nghỉ 30s nếu lỗi để tránh bị ban, nghỉ 2s nếu thành công
                wait_time = 30 if error_occurred else 2
                print(f"[WORKER] Task #{task_id} finished. Next in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                await asyncio.sleep(2)
            
            cursor.close()
            conn.close()
        except Error as e:
            # Try JSON Queue
            queue = load_json_queue()
            pending_tasks = [t for t in queue if t['status'] == 'pending']
            if pending_tasks:
                task = pending_tasks[0]
                task_id = task['id']
                task_type = task['task_type']
                data = json.loads(task['task_data'])
                
                if gemini_chat is None:
                    await asyncio.sleep(5)
                    continue
                
                print(f"\n\n[WORKER-JSON] --- PROCESSING TASK #{task_id} ---")
                try:
                    if task_type == "theory_perfection":
                        result = await generate_theory_perfection(data["filename"])
                        save_theory_to_file(data["filename"], result)
                    
                    # Mark as success
                    for t in queue:
                        if t['id'] == task_id:
                            t['status'] = 'success'
                            t['completed_at'] = datetime.datetime.now().isoformat()
                    save_json_queue(queue)
                    print(f"[WORKER-JSON] Task #{task_id} success.")
                except Exception as ex:
                    print(f"[WORKER-JSON ERROR] {ex}")
                    for t in queue:
                        if t['id'] == task_id:
                            t['status'] = 'failed'
                    save_json_queue(queue)
                
                await asyncio.sleep(5)
            else:
                await asyncio.sleep(10)

def save_barem_to_file(qid, band, content):
    suggestions_dir = os.path.join(WRITING_APP_DATA_DIR, "suggestions")
    os.makedirs(suggestions_dir, exist_ok=True)
    clean_qid = str(qid).replace(" ", "_").replace("/", "-")
    filename = f"{clean_qid}_band{band}.json"
    data = {"id": qid, "band": band, "content": content, "timestamp": datetime.datetime.now().isoformat(), "source": "AI"}
    with open(os.path.join(suggestions_dir, filename), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_vocab_to_file(qid, vocab_list, vocab_type="vocabulary"):
    vocab_dir = os.path.join(WRITING_APP_DATA_DIR, "vocab")
    os.makedirs(vocab_dir, exist_ok=True)
    clean_qid = str(qid).replace(" ", "_").replace("/", "-")
    
    # Tag vocabulary with type
    for v in vocab_list:
        v["type"] = vocab_type
    
    payload = {"id": qid, "vocab": vocab_list, "type": vocab_type}

    # Overwrite master file in writing dir
    filename = f"{clean_qid}_vocab_{vocab_type}.json"
    with open(os.path.join(vocab_dir, filename), "a", encoding="utf-8") as f:
        # Append: read existing, merge, write back
        pass

    # Merge into existing writing dir file
    master_path = os.path.join(vocab_dir, filename)
    if os.path.exists(master_path):
        try:
            with open(master_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            existing_words = {v["word"] for v in existing.get("vocab", [])}
            new_entries = [v for v in vocab_list if v["word"] not in existing_words]
            existing["vocab"] = existing.get("vocab", []) + new_entries
            payload = existing
        except:
            pass
    with open(master_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Also save timestamped copy to speaking project ai_vocab/ so browser can serve it
    ts = int(datetime.datetime.now().timestamp())
    speaking_filename = f"{clean_qid}_vocab_{vocab_type}_{ts}.json"
    speaking_path = os.path.join(SPEAKING_VOCAB_DIR, speaking_filename)
    with open(speaking_path, "w", encoding="utf-8") as f:
        json.dump({"id": qid, "vocab": vocab_list, "type": vocab_type}, f, ensure_ascii=False, indent=2)
    print(f"[VOCAB] Saved {len(vocab_list)} words to ai_vocab/{speaking_filename}")
    
    # Also update image prompts
    update_image_prompts(vocab_list)

def save_writing_guide_to_file(qid, content):
    guide_dir = os.path.join(WRITING_APP_DATA_DIR, "guides")
    os.makedirs(guide_dir, exist_ok=True)
    clean_qid = str(qid).replace(" ", "_").replace("/", "-")
    filename = f"{clean_qid}_guide.json"
    data = {"id": qid, "guide": content, "timestamp": datetime.datetime.now().isoformat()}
    with open(os.path.join(guide_dir, filename), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_writing_sample_to_file(qid, band, content):
    sample_dir = os.path.join(WRITING_APP_DATA_DIR, "samples")
    os.makedirs(sample_dir, exist_ok=True)
    clean_qid = str(qid).replace(" ", "_").replace("/", "-")
    filename = f"{clean_qid}_sample_band{band}.json"
    data = {"id": qid, "band": band, "sample": content, "timestamp": datetime.datetime.now().isoformat()}
    with open(os.path.join(sample_dir, filename), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_chart_to_file(qid, chart_data):
    chart_dir = os.path.join(WRITING_APP_DATA_DIR, "charts")
    os.makedirs(chart_dir, exist_ok=True)
    clean_qid = str(qid).replace(" ", "_").replace("/", "-")
    filename = f"{clean_qid}_chart.json"
    data = {"id": qid, "chartData": chart_data, "timestamp": datetime.datetime.now().isoformat()}
    with open(os.path.join(chart_dir, filename), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_theory_to_file(filename, content):
    file_path = os.path.join(THEORY_DIR, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[THEORY] Saved perfected file: {filename}")

def update_image_prompts(vocab_list):
    conn = get_db_connection()
    if not conn: return
    try:
        cursor = conn.cursor()
        for v in vocab_list:
            word = v.get("word", "")
            if not word: continue
            clean_word = "".join(c for c in word.lower().strip() if c.isalnum() or c in " -").replace(" ", "_")
            task_id = f"word_{clean_word}"
            
            prompt = f"Professional educational illustration of the IELTS vocabulary word '{word}', definition: {v.get('meaning', '')}. High quality, clear, minimalist style."
            
            # Use the existing add_to_queue logic but with cursor
            hash_str = f"image_{json.dumps({'id': task_id, 'word': word}, sort_keys=True)}"
            task_hash = hashlib.sha256(hash_str.encode()).hexdigest()
            
            sql = "INSERT IGNORE INTO ai_tasks (task_hash, task_type, task_data, status) VALUES (%s, %s, %s, 'pending')"
            cursor.execute(sql, (task_hash, "image", json.dumps({"id": task_id, "word": word, "prompt": prompt})))
            
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[QUEUE] Enqueued {len(vocab_list)} image tasks.")
    except Exception as e:
        print(f"[DB ERROR] Image enqueuing failed: {e}")

def update_ai_data_list():
    try:
        # Read from speaking project dirs (served by http.server)
        v_files = [f for f in os.listdir(SPEAKING_VOCAB_DIR) if f.endswith('.json')] if os.path.exists(SPEAKING_VOCAB_DIR) else []
        s_files = [f for f in os.listdir(SPEAKING_SUGGESTIONS_DIR) if f.endswith('.json')] if os.path.exists(SPEAKING_SUGGESTIONS_DIR) else []
        
        list_path = os.path.join(SCRIPT_DIR, "public", "ai_data_list.json")
        with open(list_path, "w", encoding="utf-8") as f:
            json.dump({
                "ai_vocab": v_files,
                "ai_suggestions": s_files
            }, f, ensure_ascii=False, indent=2)
        print(f"[LIST] Updated ai_data_list.json: {len(v_files)} vocab, {len(s_files)} suggestions.")
    except Exception as e:
        print(f"[LIST ERROR] {e}")

async def generate_vocab_for_question(question, count, vocab_type="vocabulary", chunk=1):
    global gemini_chat
    
    type_prompts = {
        "collocation": "các Collocations (cụm từ hay đi kèm nhau) nâng cao",
        "phrasal_verb": "các Phrasal Verbs (cụm động từ) tự nhiên",
        "idiom": "các Idioms (thành ngữ) đắt giá",
        "vocabulary": "từ vựng/collocation nâng cao"
    }
    
    selected_type = type_prompts.get(vocab_type, type_prompts["vocabulary"])
    
    # Inject randomness to prevent repetitive responses
    import random
    seed = random.randint(1000, 9999)

    prompt = f"""Bạn là chuyên gia IELTS. Đây là yêu cầu phần #{chunk} cho câu hỏi này.
Hãy đề xuất {count} {selected_type} (Band 8-9) KHÁC BIỆT HOÀN TOÀN và KHÔNG ĐƯỢC TRÙNG LẶP với bất kỳ gợi ý nào trước đó cho câu hỏi IELTS Speaking sau:
Câu hỏi: {question}

Yêu cầu ĐỊNH DẠNG kết quả là JSON ARRAY (không có văn bản dẫn nhập), mỗi object gồm:
- word: từ/cụm từ
- ipa: phiên âm chuẩn
- meaning: nghĩa tiếng Việt
- example: câu ví dụ tiếng Anh tự nhiên

Ví dụ: [{{ "word": "penchant for", "ipa": "/ˈpentʃənt/", "meaning": "sở thích đặc biệt", "example": "I have a penchant for classical music." }}]

(Unique ID: {seed})
"""
    response = await gemini_chat.send_message(prompt)
    txt = response.text.strip()
    if "```json" in txt:
        txt = txt.split("```json")[1].split("```")[0].strip()
    elif "```" in txt:
        txt = txt.split("```")[1].split("```")[0].strip()
    return json.loads(txt)


def build_ielts_prompt(recordings: list) -> str:
    """Tạo prompt IELTS chấm điểm từ danh sách bản ghi."""
    entries = []
    for i, r in enumerate(recordings, 1):
        entries.append(
            f"Bài {i}:\n"
            f"  Topic: {r.get('topic', 'N/A')}\n"
            f"  Question: {r.get('question', 'N/A')}\n"
            f"  Transcript: \"{r.get('transcript', '')}\""
        )
    body = "\n\n".join(entries)

    return f"""Bạn là Giám khảo IELTS Speaking cấp cao và Chuyên gia Ngôn ngữ học.
    Hãy phân tích các bản ghi nói dưới đây:
    
    {body}
    
    Hãy trả về kết quả duy nhất dưới định dạng JSON với cấu trúc sau:
    {{
      "scores": {{
        "overall": float,
        "fluency": float,
        "lexical": float,
        "grammar": float,
        "pronunciation": float
      }},
      "transcript_analysis": [
        {{
          "word": "từ gốc",
          "status": "correct" | "grammar_error" | "vocab_error" | "pronunciation_minor" | "pronunciation_severe",
          "ipa": "phiên âm IPA chính xác của từ này trong ngữ cảnh",
          "correction": "từ đúng (nếu status là grammar_error hoặc vocab_error, ngược lại để null)"
        }},
        ...
      ],
      "improved_sentences": [
        {{
          "original": "câu gốc của người dùng",
          "improved": "câu đã được nâng cấp lên Band 8-9",
          "explanation": "giải thích ngắn gọn tại sao câu này tốt hơn"
        }},
        ...
      ]
    }}

    LƯU Ý QUAN TRỌNG:
    - `transcript_analysis` phải chứa TẤT CẢ các từ trong đoạn hội thoại theo đúng thứ tự.
    - `ipa` phải là phiên âm chuẩn quốc tế.
    - `status` phải đánh giá chính xác từng từ.
    - Chỉ trả về JSON, không kèm văn bản giải thích.
    """


async def analyze_recordings(recordings: list) -> dict:
    """Gửi prompt tới Gemini và nhận phản hồi dưới dạng JSON."""
    global gemini_chat
    if gemini_chat is None:
        raise RuntimeError("Gemini chưa được khởi tạo!")
    
    try:
        prompt = build_ielts_prompt(recordings)
        response = await gemini_chat.send_message(prompt)
        
        if not response or not response.text:
            return {"error": "AI returned an empty response"}

        raw_txt = response.text.strip()
        txt = raw_txt
        
        # Robust JSON Extraction
        if "```json" in txt:
            txt = txt.split("```json")[1].split("```")[0].strip()
        elif "```" in txt:
            txt = txt.split("```")[1].split("```")[0].strip()
        
        # Find actual JSON boundaries
        start_obj = txt.find('{')
        end_obj = txt.rfind('}')
        start_arr = txt.find('[')
        end_arr = txt.rfind(']')
        
        # Determine if we have an object or an array
        if start_obj != -1 and (start_arr == -1 or start_obj < start_arr):
            if end_obj != -1:
                txt = txt[start_obj:end_obj+1]
        elif start_arr != -1:
            if end_arr != -1:
                txt = txt[start_arr:end_arr+1]
        
        data = json.loads(txt)
        
        # Handle list response (some models return a list of analyses)
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
            
        if not isinstance(data, dict):
            # Try to see if the response is wrapped in a top-level key
            return {"error": "AI response is not a JSON object", "raw": raw_txt}

        # Normalize structure - handle nested wrappers like {"analysis": {...}} or {"feedback": {...}}
        for wrapper in ["analysis", "feedback", "result", "report"]:
            if wrapper in data and isinstance(data[wrapper], dict) and "scores" in data[wrapper]:
                data = data[wrapper]
                break

        # Ensure essential keys exist to prevent 'undefined' in frontend
        if "scores" not in data or not isinstance(data["scores"], dict):
            data["scores"] = {"overall": 0, "fluency": 0, "lexical": 0, "grammar": 0, "pronunciation": 0}
        
        if "transcript_analysis" not in data:
            data["transcript_analysis"] = []
            
        if "improved_sentences" not in data:
            data["improved_sentences"] = []
            
        return data
    except asyncio.TimeoutError:
        return {"error": "Gemini request timed out (120s)"}
    except Exception as e:
        raw_output = response.text if 'response' in locals() and hasattr(response, 'text') else "N/A"
        print(f"AI Process Error: {e}\nRaw Output: {raw_output[:500]}...")
        return {"error": f"AI Process Error: {str(e)}", "raw": raw_output}


async def lookup_word(word: str) -> dict:
    """Tra cứu thông tin chi tiết của một từ hoặc cụm từ từ Gemini (có cache)."""
    global gemini_chat
    
    word_clean = word.lower().strip()
    cache = load_dictionary_cache()
    if word_clean in cache:
        print(f"[CACHE HIT] {word_clean}")
        return cache[word_clean]

    if gemini_chat is None:
        raise RuntimeError("Gemini chưa được khởi tạo!")
    
    print(f"[AI LOOKUP] {word_clean} (Querying Gemini...)")
    prompt = f"""Bạn là một từ điển IELTS thông minh. Hãy giải thích từ/cụm từ sau: "{word_clean}"
    
    Yêu cầu trả về định dạng JSON (không có văn bản dẫn nhập) với các trường:
    - word: chính là từ/cụm từ đó
    - ipa: phiên âm chuẩn (US/UK)
    - meaning: nghĩa tiếng Việt ngắn gọn, súc tích
    - example: một câu ví dụ hay, tự nhiên trong ngữ cảnh IELTS
    - context: giải thích ngắn gọn về cách dùng hoặc ngữ cảnh nên dùng từ này (ví dụ: dùng trong formal writing, dùng để nhấn mạnh, v.v.)
    
    Ví dụ: {{ "word": "mitigate", "ipa": "/ˈmɪt.ɪ.ɡeɪt/", "meaning": "giảm thiểu, làm nhẹ bớt", "example": "Government should implement policies to mitigate the effects of climate change.", "context": "Dùng trong formal writing/speaking khi nói về việc giảm bớt hậu quả tiêu cực." }}
    """
    response = await gemini_chat.send_message(prompt)
    txt = response.text.strip()
    if "```json" in txt:
        txt = txt.split("```json")[1].split("```")[0].strip()
    elif "```" in txt:
        txt = txt.split("```")[1].split("```")[0].strip()
    
    try:
        data = json.loads(txt)
        save_to_dictionary_cache(word_clean, data)
        return data
    except Exception as e:
        print(f"[AI ERROR] JSON parsing failed: {e}")
        print(f"[RAW RESPONSE] {txt}")
        raise e


async def generate_barem_suggestion(question: str, band: int) -> str:
    """Yêu cầu Gemini tạo câu trả lời mẫu cho một band điểm cụ thể."""
    global gemini_chat
    if gemini_chat is None:
        raise RuntimeError("Gemini chưa được khởi tạo!")
    
    prompt = f"""Bạn là Giám khảo IELTS chuyên nghiệp. Hãy viết một câu trả lời mẫu cho câu hỏi sau ở mức điểm Band {band}:
Câu hỏi: {question}

Yêu cầu cực kỳ quan trọng:
1. Độ dài phù hợp với thực tế thi (khoảng 150-250 từ).
2. Từ vựng và cấu trúc ngữ pháp tương ứng với mức Band {band}.
3. Nếu là Band 8-9, hãy dùng các collocation và idiomatic expressions tự nhiên, phong phú.
4. ĐỊNH DẠNG: Chỉ trả về nội dung câu trả lời mẫu, KHÔNG bao gồm bất kỳ lời dẫn nào.
5. Cố gắng chia đoạn nếu cần thiết để dễ đọc.
"""
    response = await gemini_chat.send_message(prompt)
    return response.text.strip()


async def generate_writing_guide(question: str, task_type_num: int = 2) -> str:
    """Tạo hướng dẫn lập dàn ý và ý tưởng cho Writing Task 1 hoặc 2."""
    global gemini_chat
    if gemini_chat is None: raise RuntimeError("Gemini chưa được khởi tạo!")
    
    task_desc = "IELTS Writing Task 1 (Mô tả biểu đồ/quy trình)" if task_type_num == 1 else "IELTS Writing Task 2 (Nghị luận xã hội)"
    
    prompt = f"""Bạn là chuyên gia IELTS Writing. Hãy lập Hướng dẫn làm bài và Gợi ý ý tưởng cho đề bài sau:
Loại bài: {task_desc}
Đề bài: {question}

Yêu cầu ĐỊNH DẠNG và NỘI DUNG cực kỳ quan trọng:
1. **Phân tích đề bài**: Xác định dạng bài (Line, Bar, Pie, Process...) và yêu cầu chính.
2. **Gợi ý Paraphrase**: Đưa ra các cách diễn đạt khác cho từ khóa chính trong đề bài (Dùng mũi tên → để chỉ sự thay đổi, KHÔNG dùng ký hiệu LaTeX như $).
   - Ví dụ: The graph shows → The line graph illustrates
3. **Dàn bài gợi ý**:
   - **Introduction**: Cách mở bài nhanh.
   - **Overview**: 2 điểm nổi bật nhất cần nêu.
   - **Body Paragraphs**: Chia đoạn logic (ví dụ theo năm, theo hạng mục).
4. **Từ vựng & Cấu trúc ghi điểm**: Liệt kê 3-5 cụm từ cao cấp phù hợp với đề.

LƯU Ý THẨM MỸ:
- Sử dụng tiêu đề Markdown (###) rõ ràng.
- Sử dụng danh sách gạch đầu dòng (-) hoặc số (1.).
- Sử dụng **in đậm** cho các từ khóa/cụm từ quan trọng.
- TUYỆT ĐỐI KHÔNG dùng ký hiệu LaTeX như `$\rightarrow$`. Hãy dùng ký tự `→` thông thường.
- Ngôn ngữ trình bày: Tiếng Việt (kèm thuật ngữ Tiếng Anh chuyên môn).
"""
    response = await gemini_chat.send_message(prompt)
    return response.text.strip()


async def check_draft(question: str, draft: str) -> str:
    """Chấm điểm và nhận xét cho bản thảo câu trả lời của người dùng."""
    global gemini_chat
    if gemini_chat is None:
        raise RuntimeError("Gemini chưa được khởi tạo!")
        
    prompt = f"""Bạn là một chuyên gia IELTS giàu kinh nghiệm. Hãy chấm điểm và cung cấp nhận xét chi tiết cho câu trả lời (draft) của người dùng.

Câu hỏi: "{question}"
Bản thảo câu trả lời: "{draft}"

Yêu cầu phản hồi bằng tiếng Việt với định dạng HTML (chỉ lấy phần body, không cần <html> hay <body> tag), bao gồm:
1. **Estimated Band Score**: Một con số ước lượng (ví dụ: 6.5).
2. **Detailed Feedback**: Nhận xét về Lexical Resource (từ vựng) và Grammatical Range (ngữ pháp).
3. **High-level Suggestions**: Gợi ý ít nhất 3-5 từ vựng hoặc cấu trúc nâng cao để thay thế, giúp nâng band điểm.
4. **Sample Improvement**: Viết lại câu trả lời này một cách hoàn thiện hơn ở mức Band 8.0+.

Hãy sử dụng các class Tailwind CSS (đã có sẵn trong web app) để trang trí cho đẹp mắt (ví dụ: bg-indigo-50, text-indigo-700, rounded-xl, v.v.).
"""
    response = await gemini_chat.send_message(prompt)
    return response.text


async def generate_writing_sample(question: str, task_type_num: int = 2, band: int = 8) -> str:
    """Tạo bài mẫu IELTS Writing Task 1 hoặc 2."""
    global gemini_chat
    if gemini_chat is None: raise RuntimeError("Gemini chưa được khởi tạo!")
    
    if task_type_num == 1:
        prompt = f"""Bạn là Giám khảo IELTS. Hãy viết bài mẫu Band {band} cho đề Writing Task 1 sau:
Đề bài: {question}

Yêu cầu:
- Phân tích số liệu/quy trình một cách chuyên nghiệp.
- Độ dài ít nhất 150 từ.
- Dùng từ vựng mô tả xu hướng/so sánh cao cấp.
- ĐỊNH DẠNG: Chỉ trả về nội dung bài mẫu.
"""
    else:
        prompt = f"""Bạn là Giám khảo IELTS. Hãy viết bài mẫu Band {band} cho đề Writing Task 2 sau:
Đề bài: {question}

Yêu cầu:
- Lập luận sắc bén, logic.
- Độ dài khoảng 250-300 từ.
- Dùng từ vựng Band 8-9, cấu trúc phức hợp.
- ĐỊNH DẠNG: Chỉ trả về nội dung bài mẫu.
"""
    response = await gemini_chat.send_message(prompt)
    return response.text.strip()

async def generate_theory_perfection(filename: str) -> str:
    """Hoàn thiện trang lý thuyết IELTS Writing Task 1."""
    global gemini_chat
    if gemini_chat is None: raise RuntimeError("Gemini chưa được khởi tạo!")

    file_path = os.path.join(THEORY_DIR, filename)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {filename}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    prompt = f"""Bạn là một chuyên gia IELTS Writing hàng đầu và là một chuyên gia giáo dục chuyên về UX/UI giáo dục.
Tôi có một trang lý thuyết IELTS Writing Task 1 hiện tại (HTML/Tailwind). Hãy viết lại TOÀN BỘ file này để nó trở nên hoàn hảo, đẳng cấp và giàu tính sư phạm hơn.

Nội dung hiện tại:
{content}

YÊU CẦU NÂNG CẤP:
1. **chuyên gia giải thích**: Thêm các đoạn phân tích chuyên sâu về cách sử dụng từ vựng/cấu trúc, sắc thái ý nghĩa (connotation).
2. **Ví dụ (VD) Band 8-9**: Bổ sung ít nhất 5 ví dụ thực tế minh họa cho các cấu trúc trong bài. Mỗi ví dụ có dịch nghĩa và phân tích điểm đắt giá.
3. **Sơ đồ/Trực quan**: Sử dụng các thành phần Tailwind (div, flex, grid) để tạo sơ đồ tư duy hoặc quy trình học tập ngay trong trang.
4. **Bảng so sánh (Tables)**: Sử dụng table Tailwind để phân loại từ vựng (ví dụ: Động từ vs Danh từ, Mức độ nhẹ vs Mạnh).
5. **Phân biệt từ (Distinction)**: Thêm mục so sánh các từ dễ nhầm lẫn trong chủ đề này (ví dụ: 'increase' vs 'rocket').
6. **Luyện tập tại chỗ (Interactive Practice)**: Thêm 3-5 câu bài tập dịch hoặc điền từ kèm theo nút "Hiện đáp án" (sử dụng JS đơn giản hoặc Tailwind hidden toggle).
7. **Thiết kế cao cấp**: Sử dụng các hiệu ứng hover, gradient, và bo góc đặc trưng của "IELTS Mastery" mà chúng ta đang xây dựng.

QUY TẮC TRẢ VỀ:
- Chỉ trả về mã HTML hoàn chỉnh, không kèm văn bản giải thích ngoài code.
- Giữ nguyên các script tag (Lucide, Tailwind, navigation links).
- Đảm bảo file có thể chạy độc lập.
"""
    response = await gemini_chat.send_message(prompt)
    new_content = response.text.strip()
    
    # Extract HTML if wrapped in triple backticks
    if "```html" in new_content:
        new_content = new_content.split("```html")[1].split("```")[0].strip()
    elif "```" in new_content:
        new_content = new_content.split("```")[1].split("```")[0].strip()

    if "<!DOCTYPE html>" in new_content or "<html" in new_content:
        return new_content
    else:
        raise ValueError(f"Failed to get valid HTML for {filename}")



async def generate_txt_to_html_lesson(filename: str) -> str:
    """Chuyển đổi file TXT đã chia nhỏ thành bài học IELTS HTML chuyên nghiệp."""
    global gemini_chat
    if gemini_chat is None: raise RuntimeError("Gemini chưa được khởi tạo!")

    txt_path = os.path.join(SCRIPT_DIR, "data", "txt_split", filename)
    if not os.path.exists(txt_path):
        raise FileNotFoundError(f"File not found: {filename}")

    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()

    prompt = f"""Bạn là một chuyên gia IELTS Senior Tutor (Giảng viên cao cấp) với phong cách giảng dạy hiện đại, chuyên sâu và dễ hiểu.
Tác giả của nội dung này là: Phạm Tiến Dũng Gia Sư.

NHIỆM VỤ:
Hãy chuyển đổi nội dung văn bản thô sau đây thành một bài học IELTS HTML "bản đẹp" đẳng cấp chuyên gia.

YÊU CẦU NỘI DUNG:
1. Trình bày dưới dạng bài giảng (Lesson) có cấu trúc logic.
2. Càng có nhiều biểu đồ, sơ đồ (sử dụng Mermaid.js hoặc Table), mô tả, ví dụ (Band 8-9), bài tập thực hành, giải thích chi tiết, so sánh các điểm ngữ pháp/từ vựng càng tốt.
3. TUYỆT ĐỐI XÓA hoàn toàn các từ 'ZIM' hoặc 'Zim Academy' nếu thấy trong văn bản. Thay vào đó, ghi rõ tác giả là: 'Phạm Tiến Dũng Gia Sư'.
4. Thêm các phần "Teacher's Note" hoặc "Pro Tip" để tăng tính sư phạm.
5. Ngôn ngữ: Tiếng Việt (có thuật ngữ Tiếng Anh chuyên sâu).

YÊU CẦU KỸ THUẬT:
- Sử dụng Tailwind CSS (CDN) để thiết kế giao diện premium, sáng sủa, hiện đại.
- Sử dụng các font chữ đẹp (Inter/Roboto).
- Bài học phải có tính tương tác cao (ví dụ: các phần Accordion hoặc Tab nếu cần, bài tập có đáp án ẩn/hiện).
- Chỉ trả về phần nội dung bên trong <body> (không cần <html> hay <head> nếu trả về body, nhưng nếu trả về full HTML thì càng tốt).

VĂN BẢN THÔ CẦN CHUYỂN ĐỔI:
---
{content}
---

CHỈ TRẢ VỀ MÃ HTML HOÀN CHỈNH (CÓ ĐỦ THẺ DOCTYPE, HTML, HEAD, BODY), KHÔNG GIẢI THÍCH GÌ THÊM.
"""
    response = await gemini_chat.send_message(prompt)
    new_html = response.text.strip()
    
    # 1. Clean code blocks
    if "```html" in new_html:
        new_html = new_html.split("```html")[1].split("```")[0].strip()
    elif "```" in new_html:
        new_html = new_html.split("```")[1].split("```")[0].strip()

    # 2. Fix Markdown links accidentally injected into attributes (e.g. href="[url](url)")
    new_html = re.sub(r'\[(https?://.*?)\]\(https?://.*?\)', r'\1', new_html)

    # 3. Inject Tailwind Silencer & Security Script
    security_tag = f"<script src='../../assets/js/security.js?v={int(time.time())}'></script>"
    silencer = f"""
    {security_tag}
    <script>
        (function() {
            const originalWarn = console.warn;
            console.warn = function(...args) {
                if (args[0] && typeof args[0] === 'string' && args[0].includes('cdn.tailwindcss.com')) return;
                originalWarn.apply(console, args);
            };
        })();
    </script>
    """
    if "</head>" in new_html:
        new_html = new_html.replace("</head>", f"{silencer}\n</head>")
    else:
        new_html = silencer + new_html

    return new_html

def save_lesson_to_file(filename, html):
    lessons_dir = os.path.join(SCRIPT_DIR, "pages", "lessons")
    os.makedirs(lessons_dir, exist_ok=True)
    
    output_filename = filename.replace(".txt", ".html")
    output_path = os.path.join(lessons_dir, output_filename)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[LESSON] Saved perfected lesson: {output_filename}")

async def generate_task1_chart_data(question: str, sample: str, guide: str = "") -> dict:
    """Trích xuất dữ liệu từ câu hỏi, bài mẫu và hướng dẫn Task 1 để tạo JSON cho Chart.js."""
    global gemini_chat
    if gemini_chat is None:
        raise RuntimeError("Gemini chưa được khởi tạo!")
    
    prompt = f"""Bạn là chuyên gia dữ liệu IELTS. Hãy trích xuất dữ liệu từ câu hỏi, bài mẫu và hướng dẫn Writing Task 1 sau để tạo cấu trúc JSON hoàn chỉnh cho Chart.js.

Câu hỏi: {question}
Hướng dẫn/Gợi ý: {guide}
Bài mẫu: {sample}

Yêu cầu ĐỊNH DẠNG kết quả là một JSON Object DUY NHẤT (không có văn bản giải thích), gồm:
- type: 'line', 'bar', 'pie', hoặc 'radar' tùy thuộc vào nội dung.
- labels: Mảng các nhãn (ví dụ: các năm, các quốc gia).
- datasets: Mảng các dataset, mỗi dataset gồm:
  - label: Tên của dataset.
  - data: Mảng các giá trị số tương ứng.
  - (Tùy chọn) borderColor: Mã màu Hex đẹp.

Ví dụ: {{ "type": "bar", "labels": ["2010", "2012"], "datasets": [{{ "label": "Exports", "data": [100, 150] }}] }}

GHI CHÚ: 
1. Ưu tiên số liệu chính xác từ bài mẫu.
2. Sử dụng "Hướng dẫn/Gợi ý" để xác định xu hướng hoặc các mốc dữ liệu quan trọng nếu bài mẫu chưa mô tả chi tiết.
3. Trả về đúng 1 khối code JSON DUY NHẤT.
"""
    response = await gemini_chat.send_message(prompt)
    txt = response.text.strip()
    if "```json" in txt:
        txt = txt.split("```json")[1].split("```")[0].strip()
    elif "```" in txt:
        txt = txt.split("```")[1].split("```")[0].strip()
    
    try:
        return json.loads(txt)
    except Exception as e:
        print(f"[AI ERROR] JSON parsing failed: {e}")
        # Return a fallback empty structure
        return {"type": "bar", "labels": [], "datasets": []}


# ============================================================
# HTTP REQUEST HANDLER
# ============================================================
class IELTSHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # In log gọn hơn
        print(f"[{self.command}] {self.path} — {args[1] if len(args) > 1 else ''}")

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        # Clean path: remove query params and trailing slashes
        clean_path = self.path.split('?')[0].rstrip('/')
        if clean_path == "": clean_path = "/"
        print(f"[SERVER] GET: {clean_path} (Full: {self.path})")

        if clean_path == "/health":
            self._json_response(200, {"status": "ok", "queue_size": get_queue_size()})
        elif clean_path == "/queue_status":
            conn = get_db_connection()
            if not conn:
                self._json_response(500, {"error": "DB Connection failed"})
                return
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT status, COUNT(*) as count FROM ai_tasks GROUP BY status")
            rows = cursor.fetchall()
            status_map = {r['status']: r['count'] for r in rows}
            cursor.close()
            conn.close()
            self._json_response(200, {
                "pending": status_map.get('pending', 0),
                "success": status_map.get('success', 0),
                "failed": status_map.get('failed', 0),
                "current": status_map.get('processing', 0) > 0
            })
        elif clean_path == "/list-ai-data":
            try:
                v_dir = os.path.join(WRITING_APP_DATA_DIR, "vocab")
                s_dir = os.path.join(WRITING_APP_DATA_DIR, "suggestions")
                
                v_files = [f for f in os.listdir(v_dir) if f.endswith('.json')] if os.path.exists(v_dir) else []
                s_files = [f for f in os.listdir(s_dir) if f.endswith('.json')] if os.path.exists(s_dir) else []
                
                print(f"[SERVER] Found {len(v_files)} vocab, {len(s_files)} suggestions.")
                self._json_response(200, {
                    "ai_vocab": v_files,
                    "ai_suggestions": s_files
                })
            except Exception as e:
                print(f"[SERVER] Error: {e}")
                self._json_response(500, {"error": str(e)})
        elif clean_path == "/reports":
            reports_dir = os.path.join(WRITING_APP_DATA_DIR, "reports")
            if not os.path.exists(reports_dir):
                self._json_response(200, {"reports": []})
                return
            reports = []
            for f in sorted(os.listdir(reports_dir), reverse=True):
                if f.endswith(".html") or f.endswith(".json"):
                    reports.append({
                        "filename": f,
                        "timestamp": os.path.getmtime(os.path.join(reports_dir, f))
                    })
            self._json_response(200, {"reports": reports})
        elif clean_path.startswith("/report/"):
            filename = clean_path.replace("/report/", "")
            report_path = os.path.join(WRITING_APP_DATA_DIR, "reports", filename)
            if os.path.exists(report_path):
                with open(report_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self._html_response(200, content)
            else:
                self._json_response(404, {"error": "Báo cáo không tồn tại"})
        elif clean_path.startswith("/get_suggestions/"):
            qid = clean_path.replace("/get_suggestions/", "")
            suggestions_dir = os.path.join(WRITING_APP_DATA_DIR, "suggestions")
            results = []
            if os.path.exists(suggestions_dir):
                for f in os.listdir(suggestions_dir):
                    if f.startswith(qid + "_") or f.startswith(qid.replace(" ", "_") + "_"):
                        try:
                            with open(os.path.join(suggestions_dir, f), "r", encoding="utf-8") as file:
                                results.append(json.load(file))
                        except: pass
            self._json_response(200, results)
        elif clean_path == "/queue_status_full":
            conn = get_db_connection()
            if not conn:
                self._json_response(500, {"error": "DB Connection failed"})
                return
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT status, COUNT(*) as count FROM ai_tasks GROUP BY status")
            rows = cursor.fetchall()
            status_map = {r['status']: r['count'] for r in rows}
            cursor.execute("SELECT * FROM ai_tasks ORDER BY created_at DESC LIMIT 50")
            history = cursor.fetchall()
            for h in history:
                if h['created_at']: h['created_at'] = h['created_at'].isoformat()
                if h['completed_at']: h['completed_at'] = h['completed_at'].isoformat()
            self._json_response(200, {
                "pending": status_map.get('pending', 0),
                "success": status_map.get('success', 0),
                "failed": status_map.get('failed', 0),
                "history": history
            })
            cursor.close()
            conn.close()
        elif clean_path.startswith("/get_ai_vocab/"):
            qid = clean_path.replace("/get_ai_vocab/", "")
            results = []
            if os.path.exists(SPEAKING_VOCAB_DIR):
                for f in os.listdir(SPEAKING_VOCAB_DIR):
                    if f.startswith(qid + "_") or f.startswith(qid.replace(" ", "_") + "_"):
                        try:
                            with open(os.path.join(SPEAKING_VOCAB_DIR, f), "r", encoding="utf-8") as file:
                                data = json.load(file)
                                results.extend(data.get("vocab", []))
                        except: pass
            self._json_response(200, results)
        else:
            self._json_response(404, {"error": "Endpoint không tồn tại"})

    def do_POST(self):
        # Chuẩn hóa path: loại bỏ query params và trailing slash
        path = self.path.split('?')[0].rstrip('/')
        if not path: path = "/"
        
        print(f"[SERVER] POST: {self.path} (Clean: {path})")
        
        if path == "/analyze":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body)
                recordings = data.get("recordings", [])
                if not recordings:
                    self._json_response(400, {"error": "Thiếu dữ liệu recordings"})
                    return

                print(f"[ANALYZE] Nhận {len(recordings)} bản ghi, đang gửi tới Gemini...")
                # Chạy async trong thread loop
                result = asyncio.run_coroutine_threadsafe(
                    analyze_recordings(recordings),
                    _event_loop
                ).result(timeout=120)

                # Lưu báo cáo vào folder
                reports_dir = os.path.join(WRITING_APP_DATA_DIR, "reports")
                os.makedirs(reports_dir, exist_ok=True)
                
                import datetime
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"report_{timestamp}.json"
                
                # Lưu dưới dạng JSON
                with open(os.path.join(reports_dir, filename), "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

                self._json_response(200, result)
            except json.JSONDecodeError:
                self._json_response(400, {"error": "JSON không hợp lệ"})
            except Exception as e:
                print(f"[ERROR] {e}")
                self._json_response(500, {"error": str(e)})
        elif self.path == "/analyze-voices-txt":
            try:
                # Đọc file voices.txt từ thư mục script
                voices_path = os.path.join(SCRIPT_DIR, "voices.txt")
                if not os.path.exists(voices_path):
                    self._json_response(404, {"error": "Không tìm thấy file voices.txt"})
                    return
                
                with open(voices_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                import re
                recordings = []
                chunks = re.split(r'Entry \d+:', content)
                for chunk in chunks:
                    if not chunk.strip(): continue
                    topic_match = re.search(r'Topic:\s*(.*)', chunk)
                    question_match = re.search(r'Question:\s*(.*)', chunk)
                    transcript_match = re.search(r'Transcript:\s*(.*)', chunk, re.DOTALL)
                    if topic_match and question_match and transcript_match:
                        recordings.append({
                            "topic": topic_match.group(1).strip(),
                            "question": question_match.group(1).strip(),
                            "transcript": transcript_match.group(1).strip()
                        })
                
                if not recordings:
                    self._json_response(400, {"error": "File voices.txt không có dữ liệu hợp lệ"})
                    return

                print(f"[FILE-ANALYZE] Đang phân tích {len(recordings)} bản ghi từ voices.txt...")
                result = asyncio.run_coroutine_threadsafe(
                    analyze_recordings(recordings),
                    _event_loop
                ).result(timeout=120)

                # Lưu báo cáo dưới dạng JSON
                reports_dir = os.path.join(WRITING_APP_DATA_DIR, "reports")
                os.makedirs(reports_dir, exist_ok=True)
                import datetime
                filename = f"report_voices_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                
                with open(os.path.join(reports_dir, filename), "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

                self._json_response(200, result)
            except Exception as e:
                print(f"[ERROR] {e}")
                self._json_response(500, {"error": str(e)})
        elif path == "/enqueue_barem":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body)
                count = int(data.get("count", 1))
                for i in range(count):
                    add_to_queue("barem", {
                        "id": data.get("id"),
                        "question": data.get("question"),
                        "band": data.get("band", 8)
                    })
                self._json_response(200, {"status": "enqueued", "count": count})
            except Exception as e:
                self._json_response(500, {"error": str(e)})
        elif path == "/enqueue_vocab":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body)
                import time
                add_to_queue("vocab", {
                    "id": data.get("id"),
                    "question": data.get("question"),
                    "count": int(data.get("count", 10)),
                    "vocab_type": data.get("vocab_type", "vocabulary"),
                    "request_time": time.time() # To allow multiple requests for same question
                })
                self._json_response(200, {"status": "enqueued"})
            except Exception as e:
                self._json_response(500, {"error": str(e)})
        elif path == "/enqueue_writing":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body)
                qid = data.get("id")
                question = data.get("question")
                task_type_num = int(data.get("task_type_num", 2))
                band = int(data.get("band", 8))
                
                # Add all 3 tasks to queue
                add_to_queue("writing_guide", {"id": qid, "question": question, "task_type_num": task_type_num})
                add_to_queue("vocab", {"id": qid, "question": question, "count": 10, "vocab_type": "vocabulary"})
                add_to_queue("writing_sample", {"id": qid, "question": question, "task_type_num": task_type_num, "band": band})
                
                self._json_response(200, {"status": "all_enqueued", "id": qid})
            except Exception as e:
                self._json_response(500, {"error": str(e)})
        elif path == "/enqueue_task1_chart":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body)
                add_to_queue("task1_chart", {
                    "id": data.get("id"),
                    "question": data.get("question"),
                    "sample": data.get("sample"),
                    "guide": data.get("guide", "")
                })
                self._json_response(200, {"status": "enqueued", "id": data.get("id")})
            except Exception as e:
                self._json_response(500, {"error": str(e)})
        elif path == "/enqueue_theory":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body)
                filenames = data.get("filenames", [])
                for fname in filenames:
                    add_to_queue("theory_perfection", {"filename": fname})
                self._json_response(200, {"status": "enqueued", "count": len(filenames)})
            except Exception as e:
                self._json_response(500, {"error": str(e)})
        elif path == "/enqueue_lessons":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body)
                filenames = data.get("filenames", [])
                for fname in filenames:
                    add_to_queue("txt_to_html_lesson", {"filename": fname})
                self._json_response(200, {"status": "enqueued_lessons", "count": len(filenames)})
            except Exception as e:
                self._json_response(500, {"error": str(e)})
        elif path == "/check_draft":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body)
                question = data.get("question")
                draft = data.get("draft")
                if not question or not draft:
                    self._json_response(400, {"error": "Cần cung cấp question và draft"})
                    return
                
                print(f"[DRAFT] Đang kiểm tra bản thảo cho: {question[:30]}...")
                result = asyncio.run_coroutine_threadsafe(
                    check_draft(question, draft),
                    _event_loop
                ).result(timeout=120)
                
                self._json_response(200, {"feedback": result})
            except Exception as e:
                self._json_response(500, {"error": str(e)})
        elif path == "/lookup":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body)
                word = data.get("word")
                if not word:
                    self._json_response(400, {"error": "Cần cung cấp từ khóa"})
                    return
                
                print(f"[LOOKUP] Đang tra cứu: {word}")
                result = asyncio.run_coroutine_threadsafe(
                    lookup_word(word),
                    _event_loop
                ).result(timeout=60)
                
                self._json_response(200, result)
            except Exception as e:
                self._json_response(500, {"error": str(e)})
        else:
            self._json_response(404, {"error": "Endpoint không tồn tại"})

    def _html_response(self, code: int, html: str):
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _json_response(self, code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)


# ============================================================
# MAIN
# ============================================================
_event_loop: asyncio.AbstractEventLoop = None

def run_server():
    server = HTTPServer(("0.0.0.0", 5679), IELTSHandler)
    print("=" * 55)
    print("  IELTS AI Proxy Server")
    print("  http://localhost:5679")
    print("  POST /lookup   — tra cứu từ vựng")
    print("  POST /analyze  — phân tích voices.txt")
    print("  POST /check_draft — chấm nháp cá nhân")
    print("  POST /enqueue_barem — yêu cầu tạo barem mới")
    print("  GET  /health   — kiểm tra trạng thái")
    print("=" * 55)
    server.serve_forever()


async def main():
    global _event_loop
    _event_loop = asyncio.get_event_loop()

    print("[1/3] Khởi động HTTP server...")
    sys.stdout.flush()
    import threading
    t_server = threading.Thread(target=run_server, daemon=True)
    t_server.start()

    print("[2/3] Khởi tạo Database...")
    sys.stdout.flush()
    init_db()
    update_ai_data_list()  # Rebuild manifest from speaking project on every startup
    
    # Start Queue Worker
    asyncio.create_task(process_queue_worker())

    print("[3/3] Kết nối Gemini (chạy ngầm)...")
    sys.stdout.flush()
    try:
        await init_gemini()
    except Exception as e:
        print(f"[ERROR] Gemini initialization failed: {e}")
        sys.stdout.flush()

    print("\n[READY] Server sẵn sàng.\n")
    sys.stdout.flush()

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n[STOP] Server đã dừng.")
        sys.stdout.flush()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
