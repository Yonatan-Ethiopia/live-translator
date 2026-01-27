import sys
import database as db
#import processors

table = db.initdb()
if len(sys.argv) > 1:
	url = sys.argv[1]
	job_id = table.create_job(url)

