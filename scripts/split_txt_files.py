import os
import sys

# Reconfigure stdout for UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def split_files(input_dir, output_dir, n=20):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    files = [f for f in os.listdir(input_dir) if f.endswith('.txt')]
    
    for filename in files:
        file_path = os.path.join(input_dir, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        lines_per_chunk = max(1, total_lines // n)
        
        base_name = os.path.splitext(filename)[0]
        
        for i in range(n):
            start = i * lines_per_chunk
            # For the last chunk, take everything remaining
            end = (i + 1) * lines_per_chunk if i < n - 1 else total_lines
            
            chunk_content = lines[start:end]
            if not chunk_content:
                continue
            
            output_filename = f"{base_name}_part{i+1:02d}.txt"
            output_path = os.path.join(output_dir, output_filename)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.writelines(chunk_content)
            
        print(f"Split {filename} into {n} parts.")

if __name__ == "__main__":
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    input_directory = os.path.join(SCRIPT_DIR, "..", "data", "txt")
    output_directory = os.path.join(SCRIPT_DIR, "..", "data", "txt_split")
    split_files(input_directory, output_directory)
