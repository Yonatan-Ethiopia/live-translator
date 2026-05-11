import sys
import database as db

table = db.initdb()
if len(sys.argv) > 1:
	url = sys.argv[1]
	job_id = table.create_job(url)
	print(f"job_id: {job_id}")
