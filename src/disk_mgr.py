from pathlib import Path

cwd = str(Path.cwd())
def is_workspace(job_id):
	job_folder = cwd + "/" + "storage/" + job_id
	if Path(job_folder).is_dir():
		return True
	return False
def get_workspace(job_id):
	job_folder = cwd + "/" + "storage/" + job_id
	if Path(job_folder).is_dir():
		return 
	else: 
		Path(job_folder).mkdir()
		return job_folder

def get_db():
	db_folder = cwd + "/" + "db"
	if Path(db_folder).exists():
		return
	else:
		Path(db_folder).mkdir(parents=True, exist_ok=True)
		return
