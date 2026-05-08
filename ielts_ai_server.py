def print_and_flush(*args, **kwargs):
    print(*args, **kwargs)
    import sys
    sys.stdout.flush()

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
    print_and_flush("Đang cài đặt gemini-webapi...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "gemini-webapi"])
    from loguru import logger
    from gemini_webapi import GeminiClient
    logger.remove()
    logger.add(sys.stderr, level="WARNING")

# ============================================================
# GLOBAL: Dual Gemini clients (Pro + Free)
# ============================================================
gemini_client_pro  = None   # Pro account → content generation
gemini_chat_pro    = None
gemini_client_free = None   # Free account → image prompts
gemini_chat_free   = None

# Keep these aliases so old code referencing gemini_chat still works
gemini_client = None
gemini_chat   = None

SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE_PRO  = os.path.join(SCRIPT_DIR, "cookie_pro.js")
COOKIE_FILE_FREE = os.path.join(SCRIPT_DIR, "cookie_free.js")
COOKIE_FILE      = COOKIE_FILE_PRO   # legacy alias

FREE_TYPES = ['vocab', 'ielts_quiz']
PRO_TYPES = ['practice_generation', 'writing_sample', 'writing_guide', 'barem', 'task1_chart', 'theory_perfection', 'vocab']

IMAGE_DIR = os.path.join(SCRIPT_DIR, "public", "image")
os.makedirs(IMAGE_DIR, exist_ok=True)

# TOGGLES
ENABLE_LESSON_IMAGES = False # Tạm thời tắt để ưu tiên tạo nội dung câu hỏi

def get_chat_for_task(task_type: str):
    """Return the appropriate chat session based on task type."""
    if task_type in FREE_TYPES:
        return gemini_chat_free if gemini_chat_free else gemini_chat_pro
    return gemini_chat_pro if gemini_chat_pro else gemini_chat_free

# Directory for AI Output in the writing app
WRITING_APP_DATA_DIR = r"d:\ietls_wrrting\data\ai_output"
os.makedirs(WRITING_APP_DATA_DIR, exist_ok=True)

# ============================================================
# NETWORK BINDING (For using 4G/Hotspot alongside WiFi)
# ============================================================
# Set this to your 4G interface IP (e.g., "192.168.118.133") or name (e.g., "Ethernet 2")
# Leave as None to use the system default network (usually WiFi)
BIND_4G_INTERFACE = None # Changed to None to test WiFi instead of 4G

def get_ip_of_interface(name_or_ip):
    """Helper to get IP of a named interface or return the IP directly."""
    if not name_or_ip: return None
    if "." in name_or_ip: return name_or_ip # Already an IP
    
    import subprocess
    try:
        # Use powershell to find the IP of an alias
        cmd = f'Get-NetIPAddress -InterfaceAlias "{name_or_ip}" -AddressFamily IPv4 | Select-Object -ExpandProperty IPAddress'
        res = subprocess.check_output(['powershell', '-Command', cmd], text=True).strip()
        if res:
            return res.split('\n')[0].strip()
    except:
        pass
    return name_or_ip

def patch_gemini_interface(interface_name_or_ip):
    """Monkey-patch Gemini library to bind requests to a specific network interface."""
    resolved_ip = get_ip_of_interface(interface_name_or_ip)
    if not resolved_ip:
        return
        
    from curl_cffi.requests import AsyncSession
    import functools
    
    # Store the original AsyncSession class
    original_init = AsyncSession.__init__
    
    @functools.wraps(original_init)
    def patched_init(self, *args, **kwargs):
        if 'interface' not in kwargs:
            kwargs['interface'] = resolved_ip
        original_init(self, *args, **kwargs)
        
    AsyncSession.__init__ = patched_init
    print_and_flush(f"[NETWORK] Gemini requests will be BINDED to IP: {resolved_ip}")

async def engineer_optimized_prompt(target_content_desc: str, chat=None) -> str:
    """Step 1: Use AI to create a perfect, specialized prompt for a specific task."""
    meta_prompt = f"""
    Act as an expert IELTS Prompt Engineer. 
    I need to generate high-quality content for: {target_content_desc}
    
    Task: Write a highly detailed, professional, and specialized prompt that I should send to an AI to get the absolute best, most accurate, and pedagogically sound result for this specific topic.
    The prompt you create should include specific constraints, tone, and formatting instructions.
    
    Return ONLY the text of the generated prompt. No preamble.
    """
    try:
        response = await (chat or gemini_chat_pro).send_message(meta_prompt)
        return response.text.strip()
    except Exception as e:
        print_and_flush(f"[PROMPT-ENG] Failed to engineer prompt: {e}. Falling back to default.")
        return target_content_desc

async def generate_ielts_quiz(word_or_topic: str, chat=None) -> str:
    """Step 2: Use the engineered prompt to generate a professional quiz."""
    # First, get the optimized prompt
    optimized_instruction = await engineer_optimized_prompt(f"A set of 3 diverse IELTS practice questions (MCQ, Fill in the blanks, and Synonyms) for the vocabulary: '{word_or_topic}'", chat=chat)
    
    print_and_flush(f"[PROMPT-ENG] Using specialized prompt for {word_or_topic}...")
    
    # Second, generate the actual content
    response = await (chat or gemini_chat_pro).send_message(optimized_instruction)
    return response.text.strip()

def save_quiz_to_file(task_id, result):
    path = os.path.join(WRITING_APP_DATA_DIR, f"quiz_{task_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write(result)




# Speaking project AI vocab directory (served directly by http.server)
SPEAKING_VOCAB_DIR = os.path.join(SCRIPT_DIR, "ai_vocab")
SPEAKING_SUGGESTIONS_DIR = os.path.join(SCRIPT_DIR, "ai_suggestions")
os.makedirs(SPEAKING_VOCAB_DIR, exist_ok=True)
os.makedirs(SPEAKING_SUGGESTIONS_DIR, exist_ok=True)

DICTIONARY_CACHE_FILE = os.path.join(SCRIPT_DIR, "dictionary_cache.json")
THEORY_DIR = r"d:\ietls_wrrting\pages\theory"

PRACTICE_UI_TEMPLATE = """
<div class="max-w-4xl mx-auto">
    <div class="bg-white dark:bg-slate-900 rounded-[3rem] border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden">
        <div class="bg-slate-50 dark:bg-slate-800/50 p-8 border-b border-slate-200 dark:border-slate-800">
            <div class="flex flex-col md:flex-row justify-between items-center gap-6">
                <div>
                    <h2 class="text-3xl font-black text-slate-900 dark:text-white mb-2">Luyện tập Chuyên sâu</h2>
                    <p class="text-slate-500 dark:text-slate-400">Hoàn thành bộ 200 câu hỏi để làm chủ kiến thức.</p>
                </div>
                <div class="flex items-center gap-4 bg-white dark:bg-slate-900 p-4 rounded-3xl shadow-inner">
                    <div class="text-center">
                        <p class="text-[10px] font-bold text-slate-400 uppercase">Tiến độ</p>
                        <p class="text-2xl font-black text-blue-600" id="practice-progress">0/200</p>
                    </div>
                    <div class="w-px h-10 bg-slate-100 dark:bg-slate-800"></div>
                    <div class="text-center">
                        <p class="text-[10px] font-bold text-slate-400 uppercase">Đúng</p>
                        <p class="text-2xl font-black text-emerald-500" id="practice-correct">0</p>
                    </div>
                </div>
            </div>
            <div class="flex flex-wrap gap-2 mt-8">
                <button onclick="filterPractice('all')" class="cat-btn active">Tất cả</button>
                <button onclick="filterPractice('Bài tập Dịch')" class="cat-btn">Dịch thuật</button>
                <button onclick="filterPractice('Word Box')" class="cat-btn">Word Box</button>
                <button onclick="filterPractice('Fill in the blank')" class="cat-btn">Điền từ</button>
                <button onclick="filterPractice('Chart Analysis')" class="cat-btn">Biểu đồ</button>
            </div>
        </div>
        <div class="p-8 md:p-12 min-h-[400px]" id="question-container"></div>
        <div class="bg-slate-50 dark:bg-slate-800/50 p-6 border-t border-slate-200 dark:border-slate-800 flex justify-between items-center">
            <button onclick="prevQuestion()" class="btn-nav"><i data-lucide="chevron-left"></i> Câu trước</button>
            <div class="text-sm font-bold text-slate-400" id="question-index">Câu 1 / 200</div>
            <button onclick="nextQuestion()" class="btn-nav">Câu tiếp <i data-lucide="chevron-right"></i></button>
        </div>
    </div>
</div>

<script>
    let allQuestions = [];
    let currentFiltered = [];
    let currentIndex = 0;
    let score = 0;
    let answered = new Set();

    function initPractice(data) {
        allQuestions = data;
        currentFiltered = [...allQuestions];
        renderQuestion();
    }

    function renderQuestion() {
        const q = currentFiltered[currentIndex];
        const container = document.getElementById('question-container');
        document.getElementById('question-index').innerText = `Câu ${currentIndex + 1} / ${currentFiltered.length}`;
        let html = `
            <div class="animate-fade-in">
                <div class="flex items-center gap-3 mb-6">
                    <span class="px-3 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-600 text-[10px] font-black uppercase tracking-widest rounded-full">${q.type}</span>
                    <span class="text-slate-300 dark:text-slate-600">#${q.id}</span>
                </div>
                <h3 class="text-xl md:text-2xl font-bold text-slate-900 dark:text-white mb-8 leading-relaxed">${q.question}</h3>
                <div class="space-y-3 mb-8">
        `;
        if (q.options && q.options.length > 0) {
            q.options.forEach(opt => {
                html += `<button onclick="checkAnswer(this, '${opt}')" class="option-btn w-full text-left p-4 rounded-2xl border-2 border-slate-100 dark:border-slate-800 hover:border-blue-500 transition-all mb-3 font-medium text-slate-700 dark:text-slate-300">${opt}</button>`;
            });
        } else {
            html += `
                <input type="text" id="ans-input" placeholder="Nhập đáp án của bạn..." class="w-full p-6 rounded-3xl border-2 border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 focus:border-blue-500 outline-none transition-all font-bold text-lg mb-4">
                <button onclick="checkInputAnswer()" class="w-full py-4 bg-slate-900 dark:bg-blue-600 text-white rounded-2xl font-bold shadow-xl">Kiểm tra đáp án</button>
            `;
        }
        html += `
                </div>
                <div id="feedback-area" class="hidden p-6 rounded-3xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700">
                    <p class="font-bold mb-2" id="result-text"></p>
                    <p class="text-sm text-slate-500 dark:text-slate-400 mb-4" id="explanation-text"></p>
                    <div class="p-4 bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800">
                        <p class="text-xs font-bold text-slate-400 uppercase mb-1">Đáp án đúng:</p>
                        <p class="font-mono text-emerald-600 dark:text-emerald-400 font-bold">${q.answer}</p>
                    </div>
                </div>
            </div>
        `;
        container.innerHTML = html;
        if (window.lucide) lucide.createIcons();
    }

    function checkAnswer(btn, val) {
        if (answered.has(currentFiltered[currentIndex].id)) return;
        const q = currentFiltered[currentIndex];
        const isCorrect = val === q.answer;
        if (isCorrect) { btn.classList.add('border-emerald-500', 'bg-emerald-50'); score++; }
        else { btn.classList.add('border-rose-500', 'bg-rose-50'); }
        showFeedback(isCorrect);
    }

    function checkInputAnswer() {
        const val = document.getElementById('ans-input').value.trim();
        const q = currentFiltered[currentIndex];
        const isCorrect = val.toLowerCase() === q.answer.toLowerCase();
        if (isCorrect) score++;
        showFeedback(isCorrect);
    }

    function showFeedback(isCorrect) {
        const q = currentFiltered[currentIndex];
        answered.add(q.id);
        document.getElementById('feedback-area').classList.remove('hidden');
        document.getElementById('result-text').innerText = isCorrect ? 'Chính xác! 🎉' : 'Chưa đúng rồi... ✍️';
        document.getElementById('result-text').className = isCorrect ? 'font-bold text-emerald-600' : 'font-bold text-rose-600';
        document.getElementById('explanation-text').innerText = q.explanation;
        updateStats();
    }

    function updateStats() {
        document.getElementById('practice-progress').innerText = `${answered.size}/${allQuestions.length}`;
        document.getElementById('practice-correct').innerText = score;
    }

    function nextQuestion() { if (currentIndex < currentFiltered.length - 1) { currentIndex++; renderQuestion(); } }
    function prevQuestion() { if (currentIndex > 0) { currentIndex--; renderQuestion(); } }

    function filterPractice(type) {
        currentIndex = 0;
        currentFiltered = type === 'all' ? [...allQuestions] : allQuestions.filter(q => q.type === type);
        document.querySelectorAll('.cat-btn').forEach(btn => btn.classList.toggle('active', btn.innerText.includes(type) || (type==='all' && btn.innerText==='Tất cả')));
        renderQuestion();
    }
</script>
"""

def inject_practice_to_html(html_content, all_questions):
    import json
    practice_data_js = f"let allQuestions = {json.dumps(all_questions, ensure_ascii=False)};"
    practice_ui = PRACTICE_UI_TEMPLATE.replace('let allQuestions = [];', practice_data_js)
    
    # Mode Switcher Logic
    if 'id="theory-section"' not in html_content:
        nav_end_marker = '</nav>'
        tabs_html = """
        <!-- Mode Switcher -->
        <div class="flex justify-center gap-4 mb-12 sticky top-6 z-50">
            <button onclick="switchMode('theory')" id="btn-theory" class="px-8 py-3 rounded-2xl bg-slate-900 text-white font-bold shadow-xl border border-white/10 transition-all flex items-center gap-2">
                <i data-lucide="book-open" class="w-5 h-5"></i> Lý thuyết
            </button>
            <button onclick="switchMode('practice')" id="btn-practice" class="px-8 py-3 rounded-2xl bg-white text-slate-900 font-bold shadow-lg border border-slate-100 transition-all flex items-center gap-2">
                <i data-lucide="edit-3" class="w-5 h-5"></i> Luyện tập (200 câu)
                <span class="bg-red-500 text-white text-[10px] px-2 py-0.5 rounded-full animate-pulse">HOT</span>
            </button>
        </div>
        <div id="theory-section" class="mode-section animate-fade-in">
        """
        html_content = html_content.replace(nav_end_marker, nav_end_marker + tabs_html)
        html_content = html_content.replace('<footer', '</div> <!-- End Theory Section -->\n<footer')

    practice_wrapper = f"""
    <!-- Practice Section -->
    <div id="practice-section" class="mode-section hidden animate-fade-in pb-20">
        {practice_ui}
    </div>
    """
    if 'id="practice-section"' in html_content:
        import re
        html_content = re.sub(r'<!-- Practice Section -->.*?</div> <!-- End Practice -->', practice_wrapper, html_content, flags=re.DOTALL)
    else:
        html_content = html_content.replace('</div> <!-- End Theory Section -->', '</div> <!-- End Theory Section -->\n' + practice_wrapper)

    js_switch = """
    <script>
        function switchMode(mode) {
            const theory = document.getElementById('theory-section');
            const practice = document.getElementById('practice-section');
            const btnTheory = document.getElementById('btn-theory');
            const btnPractice = document.getElementById('btn-practice');
            if (mode === 'theory') {
                theory.classList.remove('hidden'); practice.classList.add('hidden');
                btnTheory.className = btnTheory.className.replace('bg-white', 'bg-slate-900').replace('text-slate-900', 'text-white');
                btnPractice.className = btnPractice.className.replace('bg-slate-900', 'bg-white').replace('text-white', 'text-slate-900');
            } else {
                theory.classList.add('hidden'); practice.classList.remove('hidden');
                btnPractice.className = btnPractice.className.replace('bg-white', 'bg-slate-900').replace('text-slate-900', 'text-white');
                btnTheory.className = btnTheory.className.replace('bg-slate-900', 'bg-white').replace('text-white', 'text-slate-900');
                if (typeof allQuestions !== 'undefined' && allQuestions.length > 0 && document.getElementById('question-container').innerHTML.trim() === "") initPractice(allQuestions);
            }
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    </script>
    """
    if 'function switchMode' not in html_content:
        html_content = html_content.replace('</body>', js_switch + '\n</body>')
    return html_content

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
        print_and_flush(f"[CACHE ERROR] {e}")


def load_cookies(cookie_file: str) -> tuple[str, str, str]:
    with open(cookie_file, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    cookie_map = {c["name"]: c["value"] for c in cookies if "name" in c}
    psid   = cookie_map.get("__Secure-1PSID", "")
    psidts = cookie_map.get("__Secure-1PSIDTS", "")
    psidcc = cookie_map.get("__Secure-1PSIDCC", "")
    if not psid or not psidts:
        raise ValueError("Không tìm thấy cookie __Secure-1PSID hoặc __Secure-1PSIDTS!")
    return psid, psidts, psidcc


async def _init_gemini_client(cookie_file: str, label: str, use_pro_model: bool = False):
    """Generic initializer. Returns (client, chat) or raises."""
    from gemini_webapi.constants import Model
    psid, psidts, psidcc = load_cookies(cookie_file)
    client = GeminiClient(psid=psid, psidts=psidts, psidcc=psidcc)
    await client.init(timeout=60, auto_refresh=True)

    available = [name for name, m in client._model_registry.items() if m.is_available]
    print_and_flush(f"[{label}] Status: {client.account_status} | Models: {len(available)} ({', '.join(available[:3])})")

    # Start a new chat (always fresh — no resume for dual mode to avoid cross-account issues)
    if use_pro_model:
        try:
            chat = client.start_chat(model=Model.BASIC_PRO)
            print_and_flush(f"[{label}] Using model: Gemini Pro (BASIC_PRO)")
        except Exception:
            chat = client.start_chat()
            print_and_flush(f"[{label}] Fallback to Flash")
    else:
        chat = client.start_chat()
        print_and_flush(f"[{label}] Using model: Gemini Flash (BASIC_FLASH)")

    return client, chat


async def init_gemini():
    """Initialize both Pro and Free Gemini sessions in parallel."""
    global gemini_client_pro, gemini_chat_pro, gemini_client_free, gemini_chat_free
    global gemini_client, gemini_chat  # legacy aliases

    # Apply network binding patch if configured
    patch_gemini_interface(BIND_4G_INTERFACE)

    results = await asyncio.gather(
        _init_gemini_client(COOKIE_FILE_PRO,  "GEMINI-PRO",  use_pro_model=True),
        _init_gemini_client(COOKIE_FILE_FREE, "GEMINI-FREE", use_pro_model=False),
        return_exceptions=True
    )

    pro_result, free_result = results

    if isinstance(pro_result, Exception):
        print_and_flush(f"[GEMINI-PRO] Init FAILED: {pro_result}")
    else:
        gemini_client_pro, gemini_chat_pro = pro_result
        gemini_client = gemini_client_pro
        gemini_chat   = gemini_chat_pro
        print_and_flush("[GEMINI-PRO] Ready ✓")

    if isinstance(free_result, Exception):
        print_and_flush(f"[GEMINI-FREE] Init FAILED: {free_result} (will use Pro as fallback)")
    else:
        gemini_client_free, gemini_chat_free = free_result
        print_and_flush("[GEMINI-FREE] Ready ✓")

    if gemini_chat_pro is None and gemini_chat_free is None:
        raise RuntimeError("Both Gemini accounts failed to initialize!")

    print_and_flush("[OK] Gemini đã sẵn sàng! (Pro + Free)")


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
        print_and_flush(f"[JSON QUEUE ERROR] {e}")

def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        print_and_flush(f"[DB ERROR] Connection failed: {e}")
        return None

def init_db():
    print_and_flush("[DB] Initializing database...")
    sys.stdout.flush()
    try:
        # Connect without database to create it
        temp_config = DB_CONFIG.copy()
        db_name = temp_config.pop("database")
        print_and_flush(f"[DB] Connecting to MySQL at {temp_config['host']}...")
        sys.stdout.flush()
        conn = mysql.connector.connect(**temp_config)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute(f"USE {db_name}")
        print_and_flush(f"[DB] Using database {db_name}")
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
        print_and_flush("[DB OK] Database and tables initialized.")
    except Error as e:
        print_and_flush(f"[DB ERROR] Initialization failed: {e}")

def add_to_queue(task_type, data):
    # Create hash to avoid duplicates
    hash_str = f"{task_type}_{json.dumps(data, sort_keys=True)}"
    task_hash = hashlib.sha256(hash_str.encode()).hexdigest()
    
    conn = get_db_connection()
    if not conn:
        print_and_flush(f"[QUEUE] DB Connection failed. Using JSON fallback for {task_type}.")
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
                print_and_flush(f"[QUEUE] Task already exists with status: pending. Skipping.")
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
                    print_and_flush(f"[QUEUE] Task already exists with status: success and file exists. Skipping.")
                    return {"status": "success"}
                else:
                    print_and_flush(f"[QUEUE] Task marked as success but file missing. Re-queuing...")
        
        # Insert new task
        sql = "INSERT INTO ai_tasks (task_hash, task_type, task_data, status) VALUES (%s, %s, %s, 'pending')"
        cursor.execute(sql, (task_hash, task_type, json.dumps(data)))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "enqueued"}
    except Error as e:
        print_and_flush(f"[DB ERROR] Add to queue failed: {e}. Using JSON fallback.")
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

async def _run_pro_worker():
    """PRO worker: handles all content tasks (vocab, quiz, writing, etc.)"""
    print_and_flush(f"[WORKER-PRO] Started. Handling: {', '.join(PRO_TYPES)}...")
    _consecutive_429 = 0
    while True:
        try:
            await _process_loop_step(worker_type="PRO")
            _consecutive_429 = 0
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or isinstance(e, asyncio.TimeoutError):
                _consecutive_429 += 1
                wait = min(300, 60 * _consecutive_429)
                print_and_flush(f"[WORKER-PRO] Rate-limit #{_consecutive_429}. Waiting {wait}s...")
                await asyncio.sleep(wait)
            elif "unauthenticated" in err_str or "expired" in err_str:
                print_and_flush("[WORKER-PRO] Auth error. Reinit in 30s...")
                await asyncio.sleep(30)
                try:
                    await init_gemini()
                except: pass
            else:
                await asyncio.sleep(10)

async def _run_free_worker():
    """FREE worker: handles ONLY image tasks."""
    print_and_flush(f"[WORKER-FREE] Started. Handling: {', '.join(FREE_TYPES)}...")
    _consecutive_429 = 0
    while True:
        try:
            await _process_loop_step(worker_type="FREE")
            _consecutive_429 = 0
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or isinstance(e, asyncio.TimeoutError):
                _consecutive_429 += 1
                wait = min(300, 60 * _consecutive_429)
                print_and_flush(f"[WORKER-FREE] Rate-limit #{_consecutive_429}. Waiting {wait}s...")
                await asyncio.sleep(wait)
            elif "unauthenticated" in err_str or "expired" in err_str:
                print_and_flush("[WORKER-FREE] Auth error. Reinit in 30s...")
                await asyncio.sleep(30)
                try:
                    await init_gemini()
                except: pass
            else:
                await asyncio.sleep(10)

async def process_queue_worker():
    global gemini_chat
    print_and_flush("[WORKER] MySQL Queue worker started.")

    
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
                print_and_flush(f"[WORKER] Found previous chat session: {row[0]}")
            cursor.close()
            conn.close()
    except Exception as e:
        print_and_flush(f"[WORKER] Recovery error: {e}")

    _consecutive_429 = 0

    while True:
        try:
            await _process_loop_step()
            _consecutive_429 = 0  # reset on success
        except Exception as e:
            import traceback
            err_str = str(e).lower()
            print_and_flush(f"[WORKER CRITICAL ERROR] {type(e).__name__}: {e}")
            print_and_flush(f"[WORKER CRITICAL TRACEBACK]\n{traceback.format_exc()}")
            sys.stdout.flush()
            if "429" in err_str or isinstance(e, asyncio.TimeoutError):
                _consecutive_429 += 1
                wait = min(300, 60 * _consecutive_429)  # 60s, 120s, 180s... max 5min
                print_and_flush(f"[WORKER] Rate-limit/Timeout (#{_consecutive_429}). Waiting {wait}s WITHOUT reinit...")
                await asyncio.sleep(wait)
            elif "unauthenticated" in err_str or "expired" in err_str:
                print_and_flush("[WORKER] Auth error detected. Reinitializing Gemini in 30s...")
                await asyncio.sleep(30)
                try:
                    await init_gemini()
                    print_and_flush("[WORKER] Gemini reinitialized successfully.")
                except Exception as reinit_err:
                    print_and_flush(f"[WORKER] Reinit failed: {reinit_err}")
            else:
                await asyncio.sleep(10)

async def _process_loop_step(worker_type: str = "PRO"):
    global gemini_chat
    conn = get_db_connection()
    if not conn:
        print_and_flush(f"[WORKER-{worker_type}] DB connection failed. Sleeping 5s...")
        await asyncio.sleep(5)
        return
    
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

        # Increased pacing to 10s per user request to avoid "Ban/429"
        print_and_flush(f"[WORKER-{worker_type}] Pacing... waiting 10s before request.")
        await asyncio.sleep(10)

        # Set task filter based on worker type for PARALLEL optimization
        if worker_type == "FREE":
            # FREE worker handles lightweight tasks
            task_type_filter = "AND task_type IN ('vocab', 'ielts_quiz')"
            active_chat = gemini_chat_free if gemini_chat_free else gemini_chat_pro
            account_label = "FREE"
        else:  # PRO
            # PRO worker handles heavy content generation
            task_type_filter = "AND task_type IN ('practice_generation', 'writing_sample', 'writing_guide', 'barem', 'task1_chart', 'theory_perfection', 'vocab')"
            active_chat = gemini_chat_pro
            account_label = "PRO"

        if active_chat is None:
            print_and_flush(f"\n[WORKER-{worker_type}] Gemini ({account_label}) not ready. Waiting...")
            cursor.close()
            conn.close()
            await asyncio.sleep(5)
            return

        # Atomically claim a task using worker_id with PRIORITY
        import random as _random
        worker_id = f"{worker_type}_{_random.randint(1000, 9999)}"
        
        # Priority logic: practice_generation > writing_sample > barem > others
        priority_sql = ""
        if worker_type == "PRO":
            priority_sql = """
                ORDER BY 
                    CASE 
                        WHEN task_type = 'practice_generation' THEN 1
                        WHEN task_type = 'writing_sample' THEN 2
                        WHEN task_type = 'writing_guide' THEN 2
                        WHEN task_type = 'barem' THEN 3
                        WHEN task_type = 'ielts_quiz' THEN 4
                        ELSE 5
                    END, 
                    created_at ASC
            """
        else:
            priority_sql = "ORDER BY created_at ASC"

        cursor.execute(f"""
            UPDATE ai_tasks SET status = 'processing', worker_id = %s
            WHERE status = 'pending' {task_type_filter}
            {priority_sql}
            LIMIT 1
        """, (worker_id,))

        conn.commit()

        cursor.execute("SELECT * FROM ai_tasks WHERE worker_id = %s AND status = 'processing' LIMIT 1", (worker_id,))
        task = cursor.fetchone()
        
        if pending > 0:
            print_and_flush(f"\r[PROGRESS] {done}/{total} tasks ({percent:.1f}%) | {pending} pending", end="", flush=True)
        
        if task:
            task_id = task['id']
            task_type = task['task_type']
            data = json.loads(task['task_data'])

            # Super safe title access
            chat_title = "IELTS Session"
            try:
                if hasattr(active_chat, 'title') and active_chat.title:
                    chat_title = str(active_chat.title)
            except:
                pass
            
            print_and_flush(f"\n\n[WORKER] --- PROCESSING TASK #{task_id} [{account_label}] ---")
            print_and_flush(f"[TYPE] {task_type.upper()}")
            print_and_flush(f"[CHAT] {chat_title}")
            
            error_occurred = False
            try:

                if task['task_type'] == "barem":
                    result = await generate_barem_suggestion(data["question"], data["band"], chat=active_chat)
                    save_barem_to_file(data["id"], data["band"], result)
                elif task['task_type'] == "vocab":
                    # Pass the chunk number to ensure diversity
                    chunk_num = data.get("chunk", 1)
                    result_json = await generate_vocab_for_question(
                        data["question"], 
                        data["count"], 
                        data.get("vocab_type", "vocabulary"),
                        chunk=chunk_num,
                        chat=active_chat
                    )
                    save_vocab_to_file(data["id"], result_json, data.get("vocab_type", "vocabulary"))
                elif task['task_type'] == "writing_guide":
                    result = await generate_writing_guide(data["question"], data.get("task_type_num", 2), chat=active_chat)
                    save_writing_guide_to_file(data["id"], result)
                elif task['task_type'] == "writing_sample":
                    result = await generate_writing_sample(data["question"], data.get("task_type_num", 2), data.get("band", 8), chat=active_chat)
                    save_writing_sample_to_file(data["id"], data.get("band", 8), result)
                elif task['task_type'] == "practice_generation":
                    filename = data.get("filename")
                    # Support full path override for lesson files outside THEORY_DIR
                    file_path = data.get("file_path") or os.path.join(THEORY_DIR, filename)
                    if os.path.exists(file_path):
                        with open(file_path, "r", encoding="utf-8") as f:
                            html_content = f.read()
                        all_questions = []
                        
                        # STEP 1: Generate a Master Illustration (Skipped if ENABLE_LESSON_IMAGES is False)
                        if ENABLE_LESSON_IMAGES:
                            try:
                                print_and_flush(f"[WORKER] Generating Master Illustration for {filename}...")
                                img_success = await generate_lesson_illustration(html_content, filename, chat=active_chat)
                            except Exception as img_e:
                                print_and_flush(f"[IMAGE ERROR] {img_e}")
                        else:
                            print_and_flush(f"[WORKER] Skipping Illustration for {filename} (Priority: Content)")

                        # STEP 2: Generate Questions (2 chunks x 50)
                        for i in range(1, 3): 
                            chunk_json = await generate_comprehensive_practice(html_content, filename, i, 50, chat=active_chat)
                            try:
                                chunk_data = json.loads(chunk_json)
                                if isinstance(chunk_data, list): all_questions.extend(chunk_data)
                            except: pass
                        if all_questions:
                            # Use the buffer if generate_lesson_illustration modified it
                            final_html = current_html_buffer if current_html_buffer else html_content
                            updated_html = inject_practice_to_html(final_html, all_questions)
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(updated_html)
                            print_and_flush(f"[WORKER] Injected Illustration and {len(all_questions)} questions into {filename}")
                            # Reset buffer
                            globals()['current_html_buffer'] = ""
                    else:
                        print_and_flush(f"[WORKER] File not found: {file_path}")
                elif task['task_type'] == "task1_chart":
                    result = await generate_task1_chart_data(data["question"], data["sample"], data.get("guide", ""), chat=active_chat)
                    save_chart_to_file(data["id"], result)
                elif task['task_type'] == "theory_perfection":
                    result = await generate_theory_perfection(data["filename"], chat=active_chat)
                    save_theory_to_file(data["filename"], result)
                elif task['task_type'] == "txt_to_html_lesson":
                    result = await generate_txt_to_html_lesson(data["filename"], chat=active_chat)
                    save_lesson_to_file(data["filename"], result)
                elif task['task_type'] == "ielts_quiz":
                    result = await generate_ielts_quiz(data["word"], chat=active_chat)
                    save_quiz_to_file(data["id"], result)

                
                cursor.execute(
                    "UPDATE ai_tasks SET status = 'success', chat_name = %s, completed_at = %s WHERE id = %s",
                    (chat_title, datetime.datetime.now(), task_id)
                )
                conn.commit()
                # Trigger manifest update
                update_ai_data_list()
            except Exception as e:
                import traceback
                error_occurred = True
                err_msg = str(e)
                err_lower = err_msg.lower()
                print_and_flush(f"[ERROR] Task #{task_id} ({task_type}) FAILED: {type(e).__name__}: {err_msg}")
                print_and_flush(f"[ERROR TRACEBACK]\n{traceback.format_exc()}")
                sys.stdout.flush()

                is_rate_limit = "429" in err_msg or "1097" in err_msg or isinstance(e, asyncio.TimeoutError)
                is_auth_error = (
                    "unauthenticated" in err_lower
                    or "expired" in err_lower
                ) and not is_rate_limit

                if is_rate_limit:
                    print_and_flush(f"[!] Rate-limit (429/Timeout) on task #{task_id}. Resetting to pending. Waiting 5 minutes...")
                    cursor.execute(
                        "UPDATE ai_tasks SET status = 'pending' WHERE id = %s",
                        (task_id,)
                    )
                    conn.commit()
                    cursor.close()
                    conn.close()
                    await asyncio.sleep(300)  # Wait 5 minutes, no reinit
                    return
                elif is_auth_error:
                    print_and_flush(f"[!] Auth error on task #{task_id}. Resetting to pending + reinitializing...")
                    cursor.execute(
                        "UPDATE ai_tasks SET status = 'pending' WHERE id = %s",
                        (task_id,)
                    )
                    conn.commit()
                    cursor.close()
                    conn.close()
                    await asyncio.sleep(30)
                    try:
                        await init_gemini()
                        print_and_flush("[WORKER] Gemini reinitialized OK.")
                    except Exception as reinit_err:
                        print_and_flush(f"[WORKER] Reinit failed: {reinit_err}")
                    await asyncio.sleep(10)
                    return
                else:
                    cursor.execute(
                        "UPDATE ai_tasks SET status = 'failed', chat_name = %s, completed_at = %s WHERE id = %s",
                        (chat_title, datetime.datetime.now(), task_id)
                    )
            
            conn.commit()
            # Nghỉ 30s nếu lỗi để tránh bị ban, nghỉ 5s nếu thành công
            wait_time = 30 if error_occurred else 5
            print_and_flush(f"[WORKER] Task #{task_id} finished. Next in {wait_time}s...")
            await asyncio.sleep(wait_time)

        else:
            await asyncio.sleep(2)
        
        cursor.close()
        conn.close()
    except Error as e:
        print_and_flush(f"[WORKER DB ERROR] {e}")
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
                return
            
            print_and_flush(f"\n\n[WORKER-JSON] --- PROCESSING TASK #{task_id} ---")
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
                print_and_flush(f"[WORKER-JSON] Task #{task_id} success.")
            except Exception as ex:
                print_and_flush(f"[WORKER-JSON ERROR] {ex}")
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
    print_and_flush(f"[VOCAB] Saved {len(vocab_list)} words to ai_vocab/{speaking_filename}")
    
    # Also update image prompts
    # Update image prompts (Only for vocabulary)
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
    print_and_flush(f"[THEORY] Saved perfected file: {filename}")

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
        print_and_flush(f"[QUEUE] Enqueued {len(vocab_list)} image tasks.")
    except Exception as e:
        print_and_flush(f"[DB ERROR] Image enqueuing failed: {e}")

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
        print_and_flush(f"[LIST] Updated ai_data_list.json: {len(v_files)} vocab, {len(s_files)} suggestions.")
    except Exception as e:
        print_and_flush(f"[LIST ERROR] {e}")

async def generate_vocab_for_question(question, count, vocab_type="vocabulary", chunk=1, chat=None):
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
    print_and_flush(f"[VOCAB] Gửi prompt tới Gemini (chunk={chunk}, type={vocab_type})...")
    sys.stdout.flush()
    response = await asyncio.wait_for((chat or gemini_chat).send_message(prompt), timeout=120)
    txt = response.text.strip()
    print_and_flush(f"[VOCAB] Phản hồi nhận được ({len(txt)} ký tự): {txt[:200]}...")
    sys.stdout.flush()
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
        response = await asyncio.wait_for((chat or gemini_chat).send_message(prompt), timeout=120)
        
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
        print_and_flush(f"AI Process Error: {e}\nRaw Output: {raw_output[:500]}...")
        return {"error": f"AI Process Error: {str(e)}", "raw": raw_output}


async def lookup_word(word: str) -> dict:
    """Tra cứu thông tin chi tiết của một từ hoặc cụm từ từ Gemini (có cache)."""
    global gemini_chat
    
    word_clean = word.lower().strip()
    cache = load_dictionary_cache()
    if word_clean in cache:
        print_and_flush(f"[CACHE HIT] {word_clean}")
        return cache[word_clean]

    if gemini_chat is None:
        raise RuntimeError("Gemini chưa được khởi tạo!")
    
    print_and_flush(f"[AI LOOKUP] {word_clean} (Querying Gemini...)")
    prompt = f"""Bạn là một từ điển IELTS thông minh. Hãy giải thích từ/cụm từ sau: "{word_clean}"
    
    Yêu cầu trả về định dạng JSON (không có văn bản dẫn nhập) với các trường:
    - word: chính là từ/cụm từ đó
    - ipa: phiên âm chuẩn (US/UK)
    - meaning: nghĩa tiếng Việt ngắn gọn, súc tích
    - example: một câu ví dụ hay, tự nhiên trong ngữ cảnh IELTS
    - context: giải thích ngắn gọn về cách dùng hoặc ngữ cảnh nên dùng từ này (ví dụ: dùng trong formal writing, dùng để nhấn mạnh, v.v.)
    
    Ví dụ: {{ "word": "mitigate", "ipa": "/ˈmɪt.ɪ.ɡeɪt/", "meaning": "giảm thiểu, làm nhẹ bớt", "example": "Government should implement policies to mitigate the effects of climate change.", "context": "Dùng trong formal writing/speaking khi nói về việc giảm bớt hậu quả tiêu cực." }}
    """
    response = await asyncio.wait_for((chat or gemini_chat).send_message(prompt), timeout=120)
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
        print_and_flush(f"[AI ERROR] JSON parsing failed: {e}")
        print_and_flush(f"[RAW RESPONSE] {txt}")
        raise e


async def generate_barem_suggestion(question: str, band: int, chat=None) -> str:
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
    response = await asyncio.wait_for((chat or gemini_chat).send_message(prompt), timeout=120)
    return response.text.strip()


async def generate_writing_guide(question: str, task_type_num: int = 2, chat=None) -> str:
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
    response = await asyncio.wait_for((chat or gemini_chat).send_message(prompt), timeout=120)
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
    response = await asyncio.wait_for((chat or gemini_chat).send_message(prompt), timeout=120)
    return response.text


async def generate_writing_sample(question: str, task_type_num: int = 2, band: int = 8, chat=None) -> str:
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
    response = await asyncio.wait_for((chat or gemini_chat).send_message(prompt), timeout=120)
    return response.text.strip()

async def generate_theory_perfection(filename: str, chat=None) -> str:
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
    response = await asyncio.wait_for((chat or gemini_chat).send_message(prompt), timeout=120)
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



async def generate_comprehensive_practice(theory_html: str, filename: str, chunk_index: int = 1, count: int = 50, chat=None) -> str:
    """Tạo một đợt bài tập (mặc định 50 câu) cho một trang lý thuyết."""
    global gemini_chat
    if gemini_chat is None: raise RuntimeError("Gemini chưa được khởi tạo!")

    types = ["Bài tập Dịch", "Word Box", "Fill in the blank", "Chart Analysis"]
    current_type = types[(chunk_index - 1) % len(types)]

    prompt = f"""Bạn là một chuyên gia khảo thí IELTS. 
Nhiệm vụ: Tạo đợt thứ {chunk_index} (gồm {count} câu hỏi) cho bộ bài tập 200 câu của bài học sau:

FILE: {filename}
DẠNG BÀI TẬP CẦN TẬP TRUNG TRONG ĐỢT NÀY: {current_type}

NỘI DUNG LÝ THUYẾT GỐC:
{theory_html[:3000]}...

YÊU CẦU:
1. Tạo đúng {count} câu hỏi chất lượng cao, bám sát lý thuyết.
2. Định dạng trả về: Chỉ trả về một mảng JSON các đối tượng câu hỏi. 
3. Mỗi đối tượng câu hỏi phải có: 
   - `id`: số thứ tự (từ {(chunk_index-1)*count + 1} đến {chunk_index*count})
   - `type`: "{current_type}"
   - `question`: nội dung câu hỏi
   - `options`: mảng các lựa chọn (nếu là Word Box) hoặc null
   - `answer`: đáp án đúng
   - `hint`: gợi ý
   - `explanation`: giải thích chi tiết tại sao chọn đáp án đó.

CHỈ TRẢ VỀ MẢNG JSON, KHÔNG GIẢI THÍCH GÌ THÊM.
"""
    response = await asyncio.wait_for((chat or gemini_chat).send_message(prompt), timeout=300)
    json_str = response.text.strip()
    
    # Clean JSON
    if "```json" in json_str:
        json_str = json_str.split("```json")[1].split("```")[0].strip()
    elif "```" in json_str:
        json_str = json_str.split("```")[1].split("```")[0].strip()
    
    return json_str

async def generate_image_with_gemini(word: str, original_prompt: str, task_id: str, chat=None) -> bool:
    """Generate and save image using Gemini Pro's native capabilities."""
    global gemini_chat
    active_chat = chat or gemini_chat
    if active_chat is None: return False

    # 1. Meta-Prompting for the image
    educational_prompt = f"""Create a professional, high-quality educational illustration for the IELTS vocabulary word: '{word}'.
Style: Minimalist, clean, modern, white background, vector-like or realistic 3D, suitable for a premium educational platform.
Context: {original_prompt}
Please generate the image now."""

    print_and_flush(f"[IMAGE] Requesting generation for: {word}...")
    try:
        response = await asyncio.wait_for(active_chat.send_message(educational_prompt), timeout=180)
        
        # gemini-webapi response.images is a list of image objects
        if hasattr(response, 'images') and response.images:
            img_obj = response.images[0]
            target_path = os.path.join(IMAGE_DIR, f"{task_id}.jpg")
            
            if hasattr(img_obj, 'save'):
                # Some versions require keyword argument 'filename'
                try:
                    img_obj.save(filename=target_path)
                except:
                    img_obj.save(target_path)
            elif hasattr(img_obj, 'content'):
                with open(target_path, "wb") as f:
                    f.write(img_obj.content)
            elif isinstance(img_obj, bytes):
                with open(target_path, "wb") as f:
                    f.write(img_obj)
            else:
                print_and_flush(f"[IMAGE] Warning: Unsupported image object type: {type(img_obj)}")
                return False
                
            print_and_flush(f"[IMAGE] SUCCESS: Saved to {os.path.abspath(target_path)}")
            return True
        else:
            print_and_flush(f"[IMAGE] FAILED: Gemini did not return an image object for '{word}'.")
            return False
    except Exception as e:
        print_and_flush(f"[IMAGE ERROR] {e}")
        return False

async def generate_lesson_illustration(html_content: str, filename: str, chat=None) -> bool:
    """Generate a high-quality master illustration for the entire lesson and inject it."""
    active_chat = chat or gemini_chat
    if active_chat is None: return False

    # 1. Clean HTML to save tokens for analysis
    text_content = re.sub(r'<[^>]+>', ' ', html_content)[:4000]
    
    prompt = f"""You are a professional educational designer. 
Analyze this IELTS lesson content and create a MASTER ILLUSTRATION that visualizes the core concept.
CONTENT: {text_content}

STYLE: Professional, artistic, high-quality 3D or detailed vector illustration, white/clean background, cinematic lighting.
The image should look like a premium cover or a core infographic banner for a top-tier learning platform.
Please generate the image now."""

    try:
        response = await asyncio.wait_for(active_chat.send_message(prompt), timeout=300)
        if hasattr(response, 'images') and response.images:
            img_obj = response.images[0]
            safe_name = filename.replace(".html", "").replace(" ", "_")
            img_filename = f"lesson_{safe_name}.jpg"
            target_path = os.path.join(IMAGE_DIR, img_filename)
            
            if hasattr(img_obj, 'save'):
                try:
                    img_obj.save(filename=target_path)
                except:
                    img_obj.save(target_path)
            elif hasattr(img_obj, 'content'):
                with open(target_path, "wb") as f:
                    f.write(img_obj.content)
            elif isinstance(img_obj, bytes):
                with open(target_path, "wb") as f:
                    f.write(img_obj)
            
            # 2. Inject into HTML (usually at the start of body or after H1)
            img_tag = f'\n<div class="my-8 text-center"><img src="../../public/image/{img_filename}" alt="Lesson Illustration" class="mx-auto rounded-2xl shadow-2xl border-4 border-white max-w-full lg:max-w-4xl hover:scale-[1.02] transition-transform duration-500"></div>\n'
            
            # Simple injection after <body> or the first <h1>
            updated_html = html_content
            if '</h1>' in updated_html:
                updated_html = updated_html.replace('</h1>', '</h1>' + img_tag, 1)
            elif '<body>' in updated_html:
                updated_html = updated_html.replace('<body>', '<body>' + img_tag, 1)
            
            global current_html_buffer
            current_html_buffer = updated_html 
            
            # Pacing: Pro images are heavy, wait 10s after success
            print_and_flush("[WORKER-PRO] Image generated. Cooling down 10s...")
            await asyncio.sleep(10)
            return True
        return False
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg:
            print_and_flush("[RATE LIMIT] Gemini Pro is tired of making images. Waiting 2 minutes...")
            await asyncio.sleep(120)
        print_and_flush(f"[LESSON IMAGE ERROR] {err_msg}")
        return False

# Global buffer to pass modified HTML between functions in a task
current_html_buffer = ""

async def generate_txt_to_html_lesson(filename: str, chat=None) -> str:

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
    response = await asyncio.wait_for((chat or gemini_chat).send_message(prompt), timeout=120)
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
        (function() {{
            const originalWarn = console.warn;
            console.warn = function(...args) {{
                if (args[0] && typeof args[0] === 'string' && args[0].includes('cdn.tailwindcss.com')) return;
                originalWarn.apply(console, args);
            }};
        }})();
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
    print_and_flush(f"[LESSON] Saved perfected lesson: {output_filename}")

async def generate_task1_chart_data(question: str, sample: str, guide: str = "", chat=None) -> dict:
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
    response = await asyncio.wait_for((chat or gemini_chat).send_message(prompt), timeout=120)
    txt = response.text.strip()
    if "```json" in txt:
        txt = txt.split("```json")[1].split("```")[0].strip()
    elif "```" in txt:
        txt = txt.split("```")[1].split("```")[0].strip()
    
    try:
        return json.loads(txt)
    except Exception as e:
        print_and_flush(f"[AI ERROR] JSON parsing failed: {e}")
        # Return a fallback empty structure
        return {"type": "bar", "labels": [], "datasets": []}


# ============================================================
# HTTP REQUEST HANDLER
# ============================================================
class IELTSHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # In log gọn hơn
        print_and_flush(f"[{self.command}] {self.path} — {args[1] if len(args) > 1 else ''}")

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
        print_and_flush(f"[SERVER] GET: {clean_path} (Full: {self.path})")

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
                
                print_and_flush(f"[SERVER] Found {len(v_files)} vocab, {len(s_files)} suggestions.")
                self._json_response(200, {
                    "ai_vocab": v_files,
                    "ai_suggestions": s_files
                })
            except Exception as e:
                print_and_flush(f"[SERVER] Error: {e}")
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
        path = self.path.split('?')[0].rstrip('/')
        if not path: path = "/"
        
        print_and_flush(f">>> [DEBUG] Nhận yêu cầu POST tại: {self.path} (Path sạch: {path})")
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)
        try:
            data = json.loads(body) if content_len > 0 else {}
        except:
            data = {}

        if path == "/generate_practice":
            try:
                chunk_index = int(data.get("chunk_index", 1))
                count = int(data.get("count", 50))
                
                print_and_flush(f"[PRACTICE] Đang tạo chunk {chunk_index} ({count} câu) cho: {filename}")
                result = asyncio.run_coroutine_threadsafe(
                    generate_comprehensive_practice(html_content, filename, chunk_index, count),
                    _event_loop
                ).result(timeout=300)
                
                self._json_response(200, {"practice_json": result})
            except Exception as e:
                self._json_response(500, {"error": str(e)})
            return

        elif path == "/analyze" or path == "/analyze-voices-txt":
            try:
                recordings = data.get("recordings", [])
                if not recordings and path == "/analyze-voices-txt":
                    # Fallback to voices.txt if empty
                    voices_path = os.path.join(SCRIPT_DIR, "voices.txt")
                    if os.path.exists(voices_path):
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
                
                print_and_flush(f"[ANALYZE] Đang phân tích {len(recordings)} bản ghi...")
                result = asyncio.run_coroutine_threadsafe(analyze_recordings(recordings), _event_loop).result(timeout=180)
                self._json_response(200, result)
            except Exception as e:
                self._json_response(500, {"error": str(e)})
            return

        elif path == "/enqueue_barem":
            try:
                count = int(data.get("count", 1))
                for _ in range(count):
                    add_to_queue("barem", {"id": data.get("id"), "question": data.get("question"), "band": data.get("band", 8)})
                self._json_response(200, {"status": "enqueued", "count": count})
            except Exception as e:
                self._json_response(500, {"error": str(e)})
            return

        elif path == "/enqueue_vocab":
            try:
                add_to_queue("vocab", {"id": data.get("id"), "question": data.get("question"), "count": int(data.get("count", 10)), "vocab_type": data.get("vocab_type", "vocabulary")})
                self._json_response(200, {"status": "enqueued"})
            except Exception as e:
                self._json_response(500, {"error": str(e)})
            return

        elif path == "/enqueue_writing":
            try:
                qid, question = data.get("id"), data.get("question")
                add_to_queue("writing_guide", {"id": qid, "question": question, "task_type_num": int(data.get("task_type_num", 2))})
                add_to_queue("vocab", {"id": qid, "question": question, "count": 10, "vocab_type": "vocabulary"})
                add_to_queue("writing_sample", {"id": qid, "question": question, "task_type_num": int(data.get("task_type_num", 2)), "band": int(data.get("band", 8))})
                self._json_response(200, {"status": "all_enqueued", "id": qid})
            except Exception as e:
                self._json_response(500, {"error": str(e)})
            return

        elif path == "/enqueue_task1_chart":
            try:
                add_to_queue("task1_chart", {"id": data.get("id"), "question": data.get("question"), "sample": data.get("sample"), "guide": data.get("guide", "")})
                self._json_response(200, {"status": "enqueued", "id": data.get("id")})
            except Exception as e:
                self._json_response(500, {"error": str(e)})
            return

        elif path == "/enqueue_theory":
            try:
                filenames = data.get("filenames", [])
                for fname in filenames: add_to_queue("theory_perfection", {"filename": fname})
                self._json_response(200, {"status": "enqueued", "count": len(filenames)})
            except Exception as e:
                self._json_response(500, {"error": str(e)})
            return

        elif path == "/enqueue_lessons":
            try:
                filenames = data.get("filenames", [])
                for fname in filenames: add_to_queue("txt_to_html_lesson", {"filename": fname})
                self._json_response(200, {"status": "enqueued_lessons", "count": len(filenames)})
            except Exception as e:
                self._json_response(500, {"error": str(e)})
            return

        elif path == "/check_draft":
            try:
                result = asyncio.run_coroutine_threadsafe(check_draft(data.get("question"), data.get("draft")), _event_loop).result(timeout=120)
                self._json_response(200, {"feedback": result})
            except Exception as e:
                self._json_response(500, {"error": str(e)})
            return

        elif path == "/enqueue_practice_v2":
            try:
                filenames = data.get("filenames", [])
                for fname in filenames:
                    add_to_queue("practice_generation", {"filename": fname})
                self._json_response(200, {"status": "enqueued", "count": len(filenames)})
            except Exception as e:
                self._json_response(500, {"error": str(e)})
            return

        elif path == "/lookup":
            try:
                result = asyncio.run_coroutine_threadsafe(lookup_word(data.get("word")), _event_loop).result(timeout=60)
                self._json_response(200, result)
            except Exception as e:
                self._json_response(500, {"error": str(e)})
            return

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
    server = HTTPServer(("0.0.0.0", 5680), IELTSHandler)
    print_and_flush("=" * 55)
    print_and_flush("  IELTS AI Proxy Server")
    print_and_flush("  http://localhost:5680")
    print_and_flush("  POST /lookup   — tra cứu từ vựng")
    print_and_flush("  POST /analyze  — phân tích bài viết (V2)")
    print_and_flush("  POST /enqueue_practice_v2 — xếp hàng tạo bài tập 200 câu")
    print_and_flush("  POST /check_draft — chấm nháp cá nhân")
    print_and_flush("  POST /enqueue_barem — yêu cầu tạo barem mới")
    print_and_flush("  GET  /health   — kiểm tra trạng thái")
    print_and_flush("=" * 55)
    server.serve_forever()


async def main():
    global _event_loop
    _event_loop = asyncio.get_event_loop()

    print_and_flush("[1/3] Khởi động HTTP server...")
    sys.stdout.flush()
    import threading
    t_server = threading.Thread(target=run_server, daemon=True)
    t_server.start()

    print_and_flush("[2/3] Khởi tạo Database...")
    sys.stdout.flush()
    init_db()
    update_ai_data_list()  # Rebuild manifest from speaking project on every startup
    
    # Start dual parallel workers: PRO for content, FREE for image tasks
    asyncio.create_task(_run_pro_worker())
    asyncio.create_task(_run_free_worker())


    print_and_flush("[3/3] Kết nối Gemini (chạy ngầm)...")
    sys.stdout.flush()
    try:
        await init_gemini()
    except Exception as e:
        print_and_flush(f"[ERROR] Gemini initialization failed: {e}")
        sys.stdout.flush()

    print_and_flush("\n[READY] Server sẵn sàng.\n")
    sys.stdout.flush()

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print_and_flush("\n[STOP] Server đã dừng.")
        sys.stdout.flush()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
