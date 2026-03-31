import json
import re
from bs4 import BeautifulSoup

def extract_theory(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # The theory is in the .theory-content div (from line 263 approx)
    content_div = soup.find(class_='theory-content')
    if not content_div:
        # Fallback: search for elements with id start with theory-
        sections = []
        # Find all h3 (Main sections A, B) and h4 (Subsections A1, A2...)
        headings = soup.find_all(['h3', 'h4'], id=re.compile('theory-'))
        
        for h in headings:
            section_id = h.get('id')
            title = h.get_text(strip=True)
            level = 1 if h.name == 'h3' else 2
            
            # Content is everything until the next heading
            content_parts = []
            curr = h.next_sibling
            while curr and not (curr.name in ['h3', 'h4'] and curr.get('id', '').startswith('theory-')):
                if hasattr(curr, 'outerHTML'):
                    # Simplify: only keep useful tags or just text
                    # For Task 1, there are many <p> and <strong> tags
                    content_parts.append(str(curr))
                elif isinstance(curr, str) and curr.strip():
                    content_parts.append(f"<p>{curr.strip()}</p>")
                curr = curr.next_sibling
            
            sections.append({
                "id": section_id,
                "title": title,
                "level": level,
                "content": "".join(content_parts).replace('\n', '').replace('  ', ' ')
            })
        return sections
    return []

def main():
    legacy_file = 'd:/writing/part_1_legacy.html'
    theory_data = extract_theory(legacy_file)
    
    if theory_data:
        # Save as JS
        with open('d:/writing/data/task1_theory_data.js', 'w', encoding='utf-8') as f:
            f.write("const TASK1_THEORY_DATA = " + json.dumps(theory_data, ensure_ascii=False, indent=2) + ";")
        print(f"Extracted {len(theory_data)} theory sections.")

if __name__ == "__main__":
    main()
