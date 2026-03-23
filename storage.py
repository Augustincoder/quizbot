import json
import os
from scraper import fetch_all_questions

DATA_DIR = "data"

def init_storage() -> dict:
    """Checks for existing data, scrapes if missing, and loads into memory."""
    os.makedirs(DATA_DIR, exist_ok=True)
    existing_files = [f for f in os.listdir(DATA_DIR) if f.startswith("test_") and f.endswith(".json")]
    
    # 1. Scrape and save if no files exist
    if not existing_files:
        print("First run detected. Initiating scraper...")
        raw_questions = fetch_all_questions()
        
        if not raw_questions:
            print("Failed to scrape any data!")
            return {}

        # Group into blocks of 25
        chunk_size = 25
        for i in range(0, len(raw_questions), chunk_size):
            chunk = raw_questions[i:i + chunk_size]
            test_id = (i // chunk_size) + 1
            range_str = f"{i + 1}-{i + len(chunk)}"
            
            test_data = {
                "test_id": test_id,
                "range": range_str,
                "questions": chunk
            }
            
            filepath = os.path.join(DATA_DIR, f"test_{test_id}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(test_data, f, ensure_ascii=False, indent=4)
        print(f"Data saved into {len(raw_questions)//chunk_size + 1} blocks.")

    # 2. Load all JSON blocks into memory
    memory_db = {}
    for filename in os.listdir(DATA_DIR):
        if filename.startswith("test_") and filename.endswith(".json"):
            with open(os.path.join(DATA_DIR, filename), "r", encoding="utf-8") as f:
                data = json.load(f)
                memory_db[data["test_id"]] = data
                
    print(f"Successfully loaded {len(memory_db)} tests into memory.")
    return memory_db
