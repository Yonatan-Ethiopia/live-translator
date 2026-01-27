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
	def update_job(self,job_id, status):
		conn + sql3.connect(f"{cwd}/db/jobs.db")
		cursor = conn.cursor()
		cursor.execute("UPDATE status = ? WHERE id = ?", (job_id, status))
