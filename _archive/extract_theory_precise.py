import json
import re

def extract_content(file_path, ids):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    results = []
    # Find positions of all relevant H tags
    positions = []
    for id_val in ids:
        pattern = rf"<h[34].*?id='{id_val}'>.*?</h[34]>"
        match = re.search(pattern, content)
        if match:
            positions.append((id_val, match.start(), match.end()))
    
    # Sort positions by their appearance
    positions.sort(key=lambda x: x[1])
    
    for i in range(len(positions)):
        id_val, start, end = positions[i]
        # Content is between end of current tag and start of next tag
        next_start = positions[i+1][1] if i+1 < len(positions) else content.find('</main>', end)
        
        raw_content = content[end:next_start]
        # Clean up <br>, excessive whitespace, etc.
        clean_content = raw_content.replace('\n', '').replace('<br>', '').replace('  ', ' ')
        
        results.append({
            "id": id_val,
            "content": clean_content.strip()
        })
        
    return results

def main():
    legacy_file = 'd:/writing/part_1_legacy.html'
    ids = [
        "theory-128", "theory-290", "theory-1610", "theory-3404", "theory-4442",
        "theory-5602", "theory-6219", "theory-7400", "theory-8453", "theory-9220",
        "theory-10162", "theory-11013", "theory-14836", "theory-16317",
        "theory-28046", "theory-28204", "theory-40697", "theory-42520", "theory-45769",
        "theory-49653", "theory-51256", "theory-52098", "theory-55432", "theory-56853",
        "theory-58242", "theory-60578", "theory-63848", "theory-68250", "theory-73775",
        "theory-89121", "theory-110048"
    ]
    
    theory_data = extract_content(legacy_file, ids)
    
    if theory_data:
        with open('d:/writing/data/task1_theory_content.js', 'w', encoding='utf-8') as f:
            f.write("const TASK1_THEORY_CONTENT = " + json.dumps(theory_data, ensure_ascii=False, indent=2) + ";")
        print(f"Extracted {len(theory_data)} theory content blocks.")
    else:
        print("Failed to extract content.")

if __name__ == "__main__":
    main()
