from pathlib import Path

cwd = str(Path.cwd())
def is_workspace(job_id):
	job_folder = cwd + "/" + "storage/" + job_id
	if Path(job_folder).is_dir():
		return True
	return False
def get_workspace(job_id):
	job_folder = cwd + "/" + "storage/" + job_id
	audio_folder = job_folder + "/audio"
	subtitle_folder = job_folder + "/subtitles"
	if Path(job_folder).is_dir() and Path(audio_folder).is_dir() and Path(subtitle_folder).is_dir():
		return 
	else: 
		Path(job_folder).mkdir(parents=True, exist_ok=True)
		Path(audio_folder).mkdir(parents=True, exist_ok=True)
		Path(subtitle_folder).mkdir(parents=True, exist_ok=True)
		return job_folder

def get_db():
	db_folder = cwd + "/" + "db"
	if Path(db_folder).exists():
		return
	else:
		Path(db_folder).mkdir(parents=True, exist_ok=True)
		return
