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
COOKIE_FILE = os.path.join(SCRIPT_DIR, "cookie.js")
INPUT_DIR = os.path.join(SCRIPT_DIR, "..", "data", "txt_split")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "data", "json_chunks")
os.makedirs(OUTPUT_DIR, exist_ok=True)

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

async def process_chunk(chat, chunk, filename):
    print(f"  Processing {filename}...")
    
    prompt = f"""Phân tích đoạn văn bản IELTS sau và trích xuất dữ liệu chi tiết theo cấu trúc JSON.
Yêu cầu:
1. Vocabulary: 5-8 từ/cụm từ học thuật quan trọng nhất (word, pron, type, meaning_vi, example).
2. Structures: 3-5 cấu trúc ngữ pháp hoặc collocations hay (formula, usage_vi, example_band8).
3. Flashcards: 5 thẻ flashcard để ôn tập (front, back).
4. Exercises: 5 câu hỏi luyện tập (type: "mcq" hoặc "fill", text, options, answer, explanation_vi).

Văn bản:
{chunk}

JSON Format:
{{
  "vocabulary": [ ... ],
  "structures": [ ... ],
  "flashcards": [ ... ],
  "exercises": [ ... ]
}}
"""
    result = await gemini_ask(chat, prompt)
    return result

async def main():
    psid, psidts = load_cookies(COOKIE_FILE)
    client = GeminiClient(psid, psidts)
    await client.init()
    
    target_files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".txt")]
    target_files.sort() # Process in order
    
    chat = client.start_chat(model="gemini-3-pro")
    
    for filename in target_files:
        output_filename = filename.replace(".txt", ".json")
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        if os.path.exists(output_path):
            print(f"Skipping {filename} (already processed).")
            continue
            
        txt_path = os.path.join(INPUT_DIR, filename)
        with open(txt_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        if not content.strip():
            continue
            
        data = await process_chunk(chat, content, filename)
        
        if data:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Successfully processed {filename}.")
        else:
            print(f"Failed to process {filename}.")
            
        await asyncio.sleep(5) # Delay to avoid rate limits

if __name__ == "__main__":
    asyncio.run(main())
