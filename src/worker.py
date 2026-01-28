import time
import database
import engine
from pathlib import Path
import sqlite3

cwd = str(Path.cwd())
db = database.initdb()
DB_FILE = f"{cwd}/db/jobs.db"

def start_worker():
    print("Worker started. Monitoring database...")
    
    while True:
        # 1. Try to grab a job
        job = database.claim_next_job(DB_FILE)
        
        if job:
            job_id = job['id']
            url = job['video_url']
            path = job['folder_path']
            
            print(f"[*] Found Job {job_id}. Starting Engine...")
            
            try:
                # 2. Call your Engine (The heavy lifting)
                # Pass the job_id so the engine can update statuses itself
                engine.full_pipeline(job_id, url, path)
                
                # 3. Final update
                db.update_status(job_id, 'COMPLETED')
                print(f"[+] Job {job_id} Finished.")
                
            except Exception as e:
                print(f"[!] Job {job_id} Failed: {e}")
                db.update_status(job_id, 'FAILED')
        
        else:
            # 4. No jobs? Rest for a bit.
            time.sleep(5)

if __name__ == "__main__":
    start_worker()
