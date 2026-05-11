from pathlib import Path
import sqlite3 as sql3
import hashlib
import disk_mgr as mgr

cwd = str(Path.cwd())

class initdb:
	def get_job_id(self,url):
		unique_id = hashlib.sha256(url.encode('utf-8')).hexdigest()
		return unique_id
	
	def __init__(self):
		mgr.get_db()
		conn = sql3.connect(f"{cwd}/db/jobs.db")
		cursor = conn.cursor()
		cursor.execute('''
			CREATE TABLE IF NOT EXISTS jobs_table(                
				id TEXT PRIMARY KEY,
				video_url TEXT,
				status TEXT,
				folder_path TEXT,
				created_at DATETIME DEFAULT CURRENT_TIMESTAMP
			)
		
		''')
		conn.commit()
		cursor.close()
		conn.close()
		
		conn = sql3.connect(f"{cwd}/db/chunkmeta.db")
		cursor = conn.cursor()
		cursor.execute('''
			CREATE TABLE IF NOT EXISTS chunks_meta(
				id TEXT,
				chunk_index INTEGER,
				chunk_type TEXT,
				path TEXT 
			)
		''')
		conn.commit()
		cursor.close()
		conn.close()
		
	def create_job(self,url):
		job_id = self.get_job_id(url)
		if mgr.is_workspace(job_id):
			return job_id
		job_folder = mgr.get_workspace(job_id)
		conn = sql3.connect(f"{cwd}/db/jobs.db")
		cursor = conn.cursor()
		
		sql_insert = """
			INSERT INTO jobs_table (id, video_url, status, folder_path) VALUES (?,?,?,?)
		"""
		
		cursor.execute(sql_insert, (job_id, url, "PENDING", job_folder))
		
		conn.commit()
		cursor.close()
		conn.close()
		return job_id
	def update_status(self,job_id, status):
		print(f"Status: {status}")
		conn = sql3.connect(f"{cwd}/db/jobs.db")
		cursor = conn.cursor()
		cursor.execute("UPDATE jobs_table SET status = ? WHERE id = ?", (status, job_id))
		conn.commit()
		cursor.close()
		conn.close()
		print("Updated")


def claim_next_job(db_path):
    conn = sql3.connect(f"{cwd}/db/jobs.db")
    # This allows us to access columns by name like job['id']
    conn.row_factory = sql3.Row 
    cursor = conn.cursor()
    query = """
    UPDATE jobs_table 
    SET status = 'PROCESSING'
    WHERE id = (
        SELECT id FROM jobs_table WHERE status = 'PENDING' 
        ORDER BY created_at ASC LIMIT 1
    )
    RETURNING id, video_url, folder_path;
    """
    
    try:
        cursor.execute(query)
        job = cursor.fetchone()
        conn.commit()
        id = job['id']
        print(f"Jon {id} found!")
        return job 
    except Exception as e:
        return None
    finally:
        conn.close()
        
def get_sub_path(job_id, chunk):
	conn = sql3.connect(f"{cwd}/db/chunkmeta.db")
	conn.row_factory = sql3.Row
	cursor = conn.cursor()
	query = """
		SELECT path FROM chunks_meta
		WHERE id=? AND chunk_index=? AND chunk_type='subtitle'
	"""
	try:
		cursor.execute(query,(job_id, chunk))
		record = cursor.fetchone()
		if record:
			return record['path'] 
		else:
			print("NO data found!")
			return None
	except Exception as e:
		print(f"Error is:\n {e}")
		return None
	finally:
		conn.close()
def get_audio_path(job_id, chunk):
	conn = sql3.connect(f"{cwd}/db/chunkmeta.db")
	conn.row_factory = sql3.Row
	cursor = conn.cursor()
	query = """
		SELECT path FROM chunks_meta
		WHERE job_id=? AND chunk_index=? AND type='audio'
	"""
	try:
		cursor.execute(query,(job_id, chunk))
		record = cursor.fetchone()
		if record:
			return record['path'] 
		else:
			return None
	except Exception as e:
		return None
	finally:
		conn.close()
def update_chunk_table(job_id, chunk_type, chunk_index, chunk_path):
	conn = sql3.connect(f"{cwd}/db/chunkmeta.db")
	cursor = conn.cursor()
	cursor.execute(" INSERT INTO chunks_meta (id, chunk_index, chunk_type, path) VALUES (?,?,?,?)", (job_id, chunk_index, chunk_type, chunk_path))
	conn.commit()
	cursor.close()
	conn.close()
