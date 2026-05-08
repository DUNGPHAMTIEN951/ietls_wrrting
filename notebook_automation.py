import os
import subprocess
import time
import json
import re

NLM_PATH = r"C:\Users\ahhh\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts\nlm.exe"
NOTEBOOK_ID = "ielts_expert"
IMAGE_DIR = r"d:\ietls_wrrting\public\image"
LESSONS_DIR = r"d:\ietls_wrrting\pages\lessons"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def run_nlm(args):
    cmd = [NLM_PATH] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return None
    except Exception as e:
        print(f"Error running nlm: {e}")
        return None

def get_sources():
    print("Fetching sources from NotebookLM...")
    output = run_nlm(["source", "list", NOTEBOOK_ID, "--json"])
    if output:
        try:
            return json.loads(output)
        except:
            return []
    return []

def get_artifacts():
    output = run_nlm(["studio", "status", NOTEBOOK_ID, "--full", "--json"])
    if output:
        try:
            return json.loads(output)
        except:
            return []
    return []

MAPPING_FILE = os.path.join(SCRIPT_DIR, "infographic_mapping.json")

def load_mapping():
    if os.path.exists(MAPPING_FILE):
        try:
            with open(MAPPING_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_mapping(mapping):
    with open(MAPPING_FILE, "w") as f:
        json.dump(mapping, f, indent=2)

def automate():
    sources = get_sources()
    if not sources:
        print("No sources found.")
        return

    mapping = load_mapping()
    artifacts = get_artifacts()
    artifact_status = {a['id']: a['status'] for a in artifacts}

    print(f"Status: {len(sources)} sources, {len(mapping)} tracked in mapping, {len(artifacts)} in studio.")

    for s in sources:
        source_id = s['id']
        title = s['title']
        
        target_filename = f"infographic_{title}.png"
        target_path = os.path.join(IMAGE_DIR, target_filename)

        if os.path.exists(target_path):
            continue

        if title in mapping:
            art_id = mapping[title]
            status = artifact_status.get(art_id, "unknown")
            
            if status == "completed":
                print(f"  - {title}: Completed. Downloading...")
                run_nlm(["download", "infographic", NOTEBOOK_ID, "--id", art_id, "--output", target_path])
            elif status == "unknown":
                print(f"  - {title}: Artifact lost or deleted. Retriggering...")
                del mapping[title]
                save_mapping(mapping)
            else:
                print(f"  - {title}: Still in progress ({status})...")
        else:
            print(f"  - {title}: Triggering generation...")
            output = run_nlm(["infographic", "create", NOTEBOOK_ID, "--source-ids", source_id, "--style", "professional", "--confirm"])
            if output:
                # Extract Artifact ID: Artifact ID: 16bcaceb-5282-49d7-9ee7-e9b6462106c2
                match = re.search(r"Artifact ID:\s*([a-f0-9\-]+)", output)
                if match:
                    art_id = match.group(1)
                    mapping[title] = art_id
                    save_mapping(mapping)
                    print(f"    -> Tracked Artifact ID: {art_id}")
                else:
                    print(f"    -> FAILED to capture ID. Output: {output}")
            
            time.sleep(4) # Pacing

    print("Automation cycle finished.")

if __name__ == "__main__":
    automate()
