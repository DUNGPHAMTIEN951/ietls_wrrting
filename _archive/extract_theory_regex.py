import json
import re

def extract_theory_regex(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    sections = []
    current_section = None
    
    # regex for headings: <h[34] ... id='theory-(\d+)'>([^<]+)</h[34]>
    h_pattern = re.compile(r"<h([34]).*?id='(theory-\d+)'>([^<]+)</h[34]>")
    
    for line in lines:
        h_match = h_pattern.search(line)
        if h_match:
            # Save previous section
            if current_section:
                sections.append(current_section)
            
            level = int(h_match.group(1))
            section_id = h_match.group(2)
            title = h_match.group(3).strip()
            
            current_section = {
                "id": section_id,
                "title": title,
                "level": level - 2, # 1 for h3, 2 for h4
                "content": ""
            }
        elif current_section:
            # Clean up line (remove <br>, etc.)
            clean_line = line.strip().replace('<br>', '')
            if clean_line:
                current_section["content"] += clean_line
    
    if current_section:
        sections.append(current_section)
        
    return sections

def main():
    legacy_file = 'd:/writing/part_1_legacy.html'
    theory_data = extract_theory_regex(legacy_file)
    
    if theory_data:
        with open('d:/writing/data/task1_theory_data.js', 'w', encoding='utf-8') as f:
            f.write("const TASK1_THEORY_DATA = " + json.dumps(theory_data, ensure_ascii=False, indent=2) + ";")
        print(f"Extracted {len(theory_data)} theory sections using Regex.")
    else:
        print("Failed to extract theory sections.")

if __name__ == "__main__":
    main()
