import os
import subprocess
import time
import re

NLM_PATH = r"C:\Users\ahhh\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts\nlm.exe"
NOTEBOOK_ID = "ielts_expert"
LESSONS_DIR = r"d:\ietls_wrrting\pages\lessons"

def clean_html(raw_html):
    # Remove script and style elements
    clean = re.sub(r'<(script|style).*?>.*?</\1>', '', raw_html, flags=re.DOTALL)
    # Remove other tags
    clean = re.sub(r'<[^>]+>', ' ', clean)
    # Collapse whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

def upload_files():
    files = [f for f in os.listdir(LESSONS_DIR) if f.endswith(".html")]
    total = len(files)
    print(f"Found {total} HTML files to process.")

    for i, fname in enumerate(files):
        file_path = os.path.join(LESSONS_DIR, fname)
        print(f"[{i+1}/{total}] Processing: {fname}...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            text_content = clean_html(content)
            title = fname.replace(".html", "")
            
            # Use --text flag
            cmd = [NLM_PATH, "source", "add", NOTEBOOK_ID, "--text", text_content, "--title", title]
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            if result.returncode == 0:
                print("  SUCCESS")
            else:
                print(f"  FAILED: {result.stderr}")
        except Exception as e:
            print(f"  CRITICAL ERROR: {e}")
        
        time.sleep(1.5) # Increased delay for stability

if __name__ == "__main__":
    upload_files()
