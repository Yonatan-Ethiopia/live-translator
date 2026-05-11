import sys
import os
import database as db
from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
#import processors

app = Flask(__name__)
CORS(app)
table = db.initdb()

@app.route('/addvid', methods=['POST'])
def add_job():
	vid_link = request.form.get('link')
	if vid_link:
		job_id = table.create_job(vid_link)
		return jsonify({"message":"job added", "job_id":job_id}), 200
	else:
		return jsonify({"message":"unsupported link error"}),400 

@app.route('/getsubtitle/<job_id>/<chunk>')
def get_subs(job_id, chunk):
	chunk_path = db.get_sub_path(job_id, chunk)
	print(f"Job id is: {job_id}")
	print(f"Chunk is: {chunk}")
	print(f"Chunk path is: {chunk_path}")
	if chunk_path is None:
		return jsonify({"message":"processing chunk"}), 202
	elif chunk_path is not None:
		dir_path = os.path.dirname(chunk_path)
		file_name = os.path.basename(chunk_path)
		return send_from_directory(
			dir_path,
			file_name,
			as_attachment=False), 200

	else:
		return jsonify({"message": "server error"}), 500

@app.route('/getaudio/<job_id>/<chunk>')
def get_audios(job_id, chunk):
	chunk_path = get_audio_path(job_id, chunk)
	if chunk_path is None:
		return jsonify({"message":"processing chunk"}), 202
	elif chunk_path is not None:
		dir_path = os.path.dirname(chunk_path)
		file_name = os.path.dirname(chunk_path)
		return send_from_directory(
			dir_path,
			file_name,
			as_attachment=False), 200
	else:
		return jsonify({"message":" server error"}),500

if __name__=="__main__":
    app.run(port=5000, debug=True)
# if len(sys.argv) > 1:
	# url = sys.argv[1]
	# job_id = table.create_job(url)

