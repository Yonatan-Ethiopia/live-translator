import subprocess
import os
import argparse

def pocket(job_id, text, number):
	try:
		audio_dir = f"{os.getcwd()}/storage/{job_id}/audio"
		os.makedirs(audio_dir, exist_ok=True)
		final_filename = f"{audio_dir}/{number}.mp3"
		pocket_cmd = [
			"/home/yonatan/pocket-tts/venv/bin/pocket-tts"
			'generate',
			'--text', text,
			'--voice', '/home/yonatan/Downloads/bmo2.wav',
			'--output-path', final_filename 
		]
		process = subprocess.run(pocket_cmd, stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
	except Exception as e:
		print(f"Error on chunk number:{number} Error: {e}")
parser = argparse.ArgumentParser(description="TTS")
parser.add_argument("--job_id", type=str, required=True, help="Job identifier")
parser.add_argument("--text", type=str, required=True, help="Text")
parser.add_argument("--number", type=int, required=True, help="Number")

args = parser.parse_args()
pocket(args.job_id, args.text, args.number)

