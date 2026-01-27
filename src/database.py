from pathlib import Path
import sql3
import hashlib

cwd = str(Path.cwd())

class initdb(self, url):
	def get_job_id(url):
		unique_id = hashlib.sha256(url.encode('utf-8')).hexdigest()
		storage = cwd + "/" + uniquea_id
		return unique_id, storage
	
	def create_db(url):
		conn = sql3.connet(f"{cwd}/db/jobs.db")
		cursor = conn.cursor()
		cursor.execute('''
			CREATE TABLE IF NOT EXIST jobs_table(
				id INTEGER,
				video_url TEXT,
				statas TEXT,
				folder_path TEXT DEFAULT,
				created_at DATETIME DEFAULT CURRENT_TIME
			)
		
		''')
		cursor.commit()
		cursor.close()
		
	def create_job(url):
		job_id, job_folder = get_job_id(url)
		job_path = Path(job_folder)
		job_path.mkdir( parents=True, exist_ok=True)
		
		conn = sql3.connect(f"{cwd}/db/jobs.db")
		cursor = conn.connect()
		
		sql_insert = """
			INSERT INTO jobs_table (id, video_url, status, folder_path) VALUES (?,?,?,?)
		"""
		
		cursor,excute(sql_insert, (job_id, url, "PENDING", job_path))
		
		cursor.commit()
		cursor.close()
		conn.close()
	def update_job(url, status):
		conn sql3.connect(f"{cwd}/db/jobs.db")
		cursor = conn.cursor()
		cursor.excute("UPDATE status = ? WHERE id = ?", (job_id, status))
