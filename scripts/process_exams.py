import os
import json
import asyncio
import sys
import re
from gemini_webapi import GeminiClient

# Reconfigure stdout for UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(os.path.dirname(SCRIPT_DIR), "cookie.js")
EXAMS_DIR = r"d:\notebookllm\de_thi_nam_khanh"
OUTPUT_DIR = os.path.join(EXAMS_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TEMPLATE_FILE = r"d:\notebookllm\master_template.html"

def load_cookies(cookie_file):
    with open(cookie_file, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    cookie_map = {c["name"]: c["value"] for c in cookies if "name" in c}
    psid   = cookie_map.get("__Secure-1PSID", "")
    psidts = cookie_map.get("__Secure-1PSIDTS", "")
    return psid, psidts

def extract_json(txt):
    match = re.search(r"```json\s*(.*?)\s*```", txt, re.DOTALL)
    if match: txt = match.group(1)
    else:
        match = re.search(r"```.*?\s*(.*?)\s*```", txt, re.DOTALL)
        if match: txt = match.group(1)
    txt = re.sub(r"^[^{[]*", "", txt)
    txt = re.sub(r"[^}\]]*$", "", txt)
    return txt

async def gemini_ask(chat, prompt):
    print(f"    Sending request to Gemini...")
    try:
        response = await chat.send_message(prompt)
        txt = extract_json(response.text.strip())
        return json.loads(txt)
    except Exception as e:
        print(f"    Error parsing Gemini response: {e}")
        return None

def split_text(text, n=10):
    lines = text.splitlines()
    avg = len(lines) // n
    chunks = []
    last = 0
    for i in range(n-1):
        chunks.append("\n".join(lines[last:last+avg]))
        last += avg
    chunks.append("\n".join(lines[last:]))
    return chunks

async def process_chunk(chat, chunk, chunk_idx, total_chunks, start_q_id, start_ex_id):
    print(f"  Processing chunk {chunk_idx+1}/{total_chunks}...")
    
    # 1. Extract Questions
    prompt_q = f"""Trích xuất TOÀN BỘ câu hỏi từ đoạn văn bản đề thi sau đây. 
Yêu cầu: Không bỏ sót bất kỳ câu nào. Trả về JSON array.

Văn bản:
{chunk}

JSON:
[
  {{
    "id": {start_q_id} + index,
    "type": "mcq" hoặc "text",
    "text": "nội dung câu hỏi",
    "options": {{ "A": "...", "B": "...", "C": "...", "D": "..." }},
    "answer": "đáp án",
    "explanation": "giải thích chi tiết (tiếng Việt)"
  }}
]
"""
    questions = await gemini_ask(chat, prompt_q)
    if not isinstance(questions, list): questions = []
    
    # 2. Extract Vocab (5-8 words per chunk to reach 50-80 total)
    prompt_v = f"""Liệt kê 6-8 từ vựng/cấu trúc quan trọng nhất từ đoạn văn bản trên.
JSON:
[
  {{ "word": "...", "pron": "...", "type": "...", "meaning": "...", "example": "..." }}
]
"""
    vocab = await gemini_ask(chat, prompt_v)
    if not isinstance(vocab, list): vocab = []
    
    # 3. Generate Vocab Exercises (10-12 questions per chunk to reach 100+ total)
    prompt_e = f"""Dựa trên từ vựng trong đoạn văn bản trên, hãy tạo 10-12 câu bài tập ôn tập từ vựng đa dạng (trắc nghiệm, điền từ, word form).
JSON:
[
  {{
    "id": {start_ex_id} + index,
    "type": "mcq" hoặc "text",
    "text": "...",
    "options": {{...}},
    "answer": "...",
    "explanation": "..."
  }}
]
"""
    exercises = await gemini_ask(chat, prompt_e)
    if not isinstance(exercises, list): exercises = []
    
    return questions, vocab, exercises

async def process_exam_split(client, filename, template_content):
    txt_path = os.path.join(EXAMS_DIR, filename)
    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    exam_id_match = re.search(r"\d+", filename)
    exam_id = exam_id_match.group() if exam_id_match else "unknown"
    print(f"\n>>> PROCESSING EXAM {exam_id} (SPLIT INTO 10 PARTS) <<<")
    
    chunks = split_text(content, 10)
    all_questions = []
    all_vocab = []
    all_exercises = []
    
    chat = client.start_chat(model="gemini-3-pro")
    
    for i, chunk in enumerate(chunks):
        if not chunk.strip(): continue
        
        qs, vs, exs = await process_chunk(chat, chunk, i, len(chunks), len(all_questions)+1, len(all_exercises)+1)
        
        # Update IDs and merge
        for idx, q in enumerate(qs):
            q["id"] = len(all_questions) + 1
            all_questions.append(q)
        
        all_vocab.extend(vs)
        
        for idx, ex in enumerate(exs):
            ex["id"] = len(all_exercises) + 1
            all_exercises.append(ex)
            
        await asyncio.sleep(2) # Stability delay

    final_data = {
        "questions": all_questions,
        "vocab": all_vocab,
        "exercises": all_exercises
    }
    
    # Save JSON
    json_path = os.path.join(OUTPUT_DIR, f"data_{exam_id}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    
    # Generate HTML
    html_content = template_content.replace("{{EXAM_ID}}", str(exam_id))
    html_content = html_content.replace("{{DATABASE}}", json.dumps({str(exam_id): final_data}, ensure_ascii=False))
    output_path = os.path.join(OUTPUT_DIR, f"de_{exam_id}.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"DONE EXAM {exam_id}: {len(all_questions)} questions, {len(all_vocab)} vocab, {len(all_exercises)} exercises.")
    return exam_id

async def main():
    psid, psidts = load_cookies(COOKIE_FILE)
    client = GeminiClient(psid, psidts)
    await client.init()
    
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        template_content = f.read()
    
    target_files = [f for f in os.listdir(EXAMS_DIR) if f.endswith(".txt")]
    target_files = sorted(target_files, key=lambda x: int(re.search(r"\d+", x).group()) if re.search(r"\d+", x) else 0)
    
    processed_exams = []
    
    # Process one by one
    for filename in target_files:
        try:
            exam_id = await process_exam_split(client, filename, template_content)
            processed_exams.append({"id": exam_id, "title": f"English Practice {exam_id}", "filename": f"de_{exam_id}.html"})
            
            # Incremental index update
            index_html = f"""
            <!DOCTYPE html>
            <html lang="vi">
            <head>
                <meta charset="UTF-8"><title>Hệ Thống Luyện Thi English</title>
                <script src="https://cdn.tailwindcss.com"></script>
                <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
            </head>
            <body class="bg-gray-100 p-10"><div class="max-w-6xl mx-auto">
                <h1 class="text-4xl font-black mb-10 text-center text-blue-800 uppercase">Hệ Thống Luyện Thi English</h1>
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            """
            for exam in sorted(processed_exams, key=lambda x: int(x["id"]) if x["id"].isdigit() else 999):
                index_html += f"""
                    <a href="{exam['filename']}" class="bg-white p-6 rounded-2xl shadow hover:shadow-xl transition border border-gray-100 h-40 flex flex-col justify-between">
                        <h2 class="text-xl font-bold">{exam['title']}</h2>
                        <div class="text-blue-600 font-bold">Luyện tập ngay <i class="fa-solid fa-arrow-right ml-1"></i></div>
                    </a>
                """
            index_html += "</div></div></body></html>"
            with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
                f.write(index_html)
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
