import yt_dlp
import ffmpeg
import subprocess
import threading
import queue
import numpy as np
import os
import soundfile as sf
import requests
import json
from faster_whisper import WhisperModel
import database
from pathlib import Path

#url = 'https://youtu.be/ZU0f8_C5Pm0?si=SXM6XmhZ334oaR20'

raw_text = []

SAMPLE_RATE = 16000
CHANNELS = 1
BYTES_PER_SAMPLE = 2
CHUNK_SECONDS = 5

CHUNK_LIMIT = SAMPLE_RATE * BYTES_PER_SAMPLE * CHANNELS * CHUNK_SECONDS

running_event = threading.Event()

db = database.initdb()
cwd = str(Path.cwd())
#job_id = "70a1a763719e8f657a02db8ce750aaba21bccc6815835c17435f93763361fa17"
def full_pipeline(job_id, url, job_folder): 
	def realTranslate(api, text):
		try:
			response = requests.get( api, params = {
				"text": text,
				"source_language" : "en",
				"target_language" : "am"
			})
			result = response.json()
			print(result["translated_text"])
			text = result["translated_text"]
			with open(f"{cwd}/storage/{job_id}/translatedtext.txt", "a", encoding = "utf-8") as f:
				f.write(f"{text}\n")
			db.update_status(job_id, "translation:finished reading stream bytes")
		except Exception as e:
			print(f"Error in realTranslate: {e}")



	def get_stream_url(url):
		yt_output = {
			'format':'bestaudio/best',
			'quiet': True,
			'no_warnings': True,
		}
		with yt_dlp.YoutubeDL(yt_output) as ytdlp:
			info = ytdlp.extract_info(url, download=False)
			return info['url']
	stream_url = get_stream_url(url)
	def listen_to_error(process):
		if process.stderr:
			print(f"Error in process ffmpeg {process.stderr.read().decode}")

	def ffmpeg_thread(process, q):
		running_event.set()
		db.update_status(job_id, "ffmpeg:extracting stream bytes") 
		buffer = b''
		print("reading bytes...")
		while True:
			try:
				raw_bytes = process.stdout.read(1024*16)
				if not raw_bytes:
					if process.poll() is not None:
						break
					else:
						continue
				buffer += raw_bytes
				while len(buffer) >= CHUNK_LIMIT:
					chunk = buffer[:CHUNK_LIMIT]
					buffer = buffer[CHUNK_LIMIT:]
					np_array = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
					q.put(np_array)
					if process.poll() is not None:
						break
					#print(np_array)
			except KeyboardInterrupt:
				break
			except Exception as e:
				db.update_status(job_id, "ffmpeg:Error")
				print(f"Error in ffmpeg thread: {e}")
				
		running_event.clear()
		db.update_status(job_id, "ffmpeg:finished reading stream bytes")
		print("ffmpeg exited and done!")
		process.stdout.close()
		process.wait()


	def asr_thread(q):
		db.update_status(job_id, "ASR:transcribing") 
		model = WhisperModel(
			"tiny",
			device="cpu",
			compute_type="int8"
		) 
		print("\n---------Transcription Result---------") 
		while True:
			try:
				data = q.get(timeout=0.1)
				if data is None:
					
					continue
				#print("Data found..")
				sf.write(
					"chunk_01.wav",
					data,
					samplerate=16000,
					subtype="PCM_16"
				)
				#print(">WAV formed...")
				# files = {
					# "file": ("chunk_01.wav", open("chunk_01.wav", "rb"), "audio/wav"),
					# "config": (None, json.dumps(config))
				# }
				
				segments, info = model.transcribe(
					data,
					language="en",
					beam_size=5,
					word_timestamps=True
				)
				for segment in segments:
					segment_text = segment.text
					start_time = segment.start
					end_time = segment.end
					print(f"[{start_time:.2f}s -> {end_time:.2f}s] {segment_text} ")
					with open(f"{job_folder}/rawtext.txt", "a", encoding = "utf-8") as f:
						f.write(f"[{start_time:.2f}s -> {end_time:.2f}s] {segment_text}\n")
					realTranslate("https://google-translat-api.proshega1.workers.dev/translate", f"[{start_time:.2f}s -> {end_time:.2f}s] {segment_text}")

			except KeyboardInterrupt:
				break
			except queue.Empty:
				if not running_event.is_set() or q.empty():
					print("asr is done too!")
					break			
			except Exception as e:
				print(f"Error in asr thread: {e}")
		db.update_status(job_id, "ASR:Finished")
		print("process finished!")
		return True

	ffmpeg_cmd = [
		'ffmpeg',
		'-reconnect', '1',
		'-reconnect_streamed', '1',
		'-reconnect_delay_max', '5',
		'-i', stream_url,
		'-f', 's16le',
		'-ac', '1',
		'-ar', '16000',
		'-'
	]

	process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	q = queue.Queue()
	is_running = True
	thread_ffmpeg = threading.Thread(target=ffmpeg_thread, args=(process, q))
	thread_asr = threading.Thread(target=asr_thread, args=(q,))

	thread_ffmpeg.start()
	thread_asr.start()
	thread_ffmpeg.join()
	thread_asr.join()

