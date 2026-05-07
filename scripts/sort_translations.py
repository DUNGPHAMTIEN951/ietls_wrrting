import os
import json

# Current sentences
translations_path = r"d:\ietls_wrrting\data\task1_translations.js"
input_dir = r"d:\ietls_wrrting\data\txt_split"

# Read current translations
with open(translations_path, "r", encoding="utf-8") as f:
    content = f.read()
    # Extract the array content
    start = content.find("[")
    end = content.rfind("]") + 1
    translations_json = content[start:end]
    # Simple cleanup to make it JSON-like (might be tricky due to JS syntax)
    # Actually, I'll just use a regex to find all objects
    import re
    items = re.findall(r'\{ id: (.*?), vietnamese: (.*?), english: (.*?), hint: (.*?) , category: (.*?) \}', content)
    # The format might vary. Let's try a safer regex.
    items = re.findall(r'\{.*?id:\s*\'(.*?)\'.*?vietnamese:\s*"(.*?)".*?english:\s*"(.*?)".*?\}', content, re.DOTALL)

print(f"Read {len(items)} items from JS.")

# Read all text files
all_text = ""
file_order = sorted([f for f in os.listdir(input_dir) if "WRITING 1A" in f or "WRITING 1B" in f or "WRITING 21" in f])
for filename in file_order:
    with open(os.path.join(input_dir, filename), "r", encoding="utf-8") as f:
        all_text += f.read() + "\n"

# For each item, find its position in the total text
results = []
for id, vi, en in items:
    pos = all_text.find(vi)
    results.append({
        "id": id,
        "vi": vi,
        "en": en,
        "pos": pos if pos != -1 else 9999999
    })

# Sort by position
results.sort(key=lambda x: x["pos"])

print("Sorted order:")
for r in results[:10]:
    print(f"{r['id']}: {r['vi'][:50]}... (pos: {r['pos']})")

# Write out the new order?
# No, let's just show the user first.
