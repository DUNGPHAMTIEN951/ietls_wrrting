import os
import json

def aggregate_data(json_dir, output_file):
    all_data = {
        "vocabulary": [],
        "structures": [],
        "flashcards": [],
        "exercises": []
    }
    
    files = [f for f in os.listdir(json_dir) if f.endswith(".json")]
    
    for filename in files:
        file_path = os.path.join(json_dir, filename)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # Add metadata about source
            source = filename.replace(".json", "")
            
            for item in data.get("vocabulary", []):
                item["source"] = source
                all_data["vocabulary"].append(item)
            
            for item in data.get("structures", []):
                item["source"] = source
                all_data["structures"].append(item)
                
            for item in data.get("flashcards", []):
                item["source"] = source
                all_data["flashcards"].append(item)
                
            for item in data.get("exercises", []):
                item["source"] = source
                all_data["exercises"].append(item)
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    
    print(f"Aggregated {len(files)} files into {output_file}")

if __name__ == "__main__":
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    json_directory = os.path.join(SCRIPT_DIR, "..", "data", "json_chunks")
    output_path = os.path.join(SCRIPT_DIR, "..", "data", "master_data.json")
    aggregate_data(json_directory, output_path)
