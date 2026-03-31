import json
import re

def extract_array(file_path, var_name):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Try to find the start and end of the array
    # This is a bit tricky with complex nested objects, so we'll look for the match
    pattern = rf'const {var_name} = \[(.*?)\];'
    # Use re.DOTALL to match across lines
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1)
    return None

def extract_object(file_path, var_name):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    pattern = rf'const {var_name} = \{{(.*?)\}};'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1)
    return None

def main():
    legacy_file = 'd:/writing/part_1_legacy.html'
    
    # Extract exerciseDatabase
    exercises = extract_array(legacy_file, 'exerciseDatabase')
    if exercises:
        with open('d:/writing/data/task1_exercises.js', 'w', encoding='utf-8') as f:
            f.write(f"const TASK1_EXERCISES = [{exercises}];")
        print("Extracted TASK1_EXERCISES")

    # Extract translationDatabase
    translations = extract_array(legacy_file, 'translationDatabase')
    if translations:
        with open('d:/writing/data/task1_translations.js', 'w', encoding='utf-8') as f:
            f.write(f"const TASK1_TRANSLATIONS = [{translations}];")
        print("Extracted TASK1_TRANSLATIONS")

    # Extract flashcardData
    flashcards = extract_object(legacy_file, 'flashcardData')
    if flashcards:
        with open('d:/writing/data/task1_flashcards.js', 'w', encoding='utf-8') as f:
            f.write(f"const TASK1_FLASHCARDS = {{{flashcards}}};")
        print("Extracted TASK1_FLASHCARDS")

if __name__ == "__main__":
    main()
