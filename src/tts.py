import requests
import json
import base64
import os
import database 

url = "https://api.addisassistant.com/api/v1/audio"
api = "sk_f5700499-76ca-4f38-8237-64f9d85b4710_837390792eadaefac10f14680de8959ca38a4f648ba14d18f821fb981d0f3ccb"

Header = {
	"Content-Type": "application/json",
	"X-API-KEY":api,
}

def hasab(text, start, end, job_id, number):
	try:
		body = {
			"text": text,
			"language": "am",
			"voice_id": "male-1",
			"output_format": "mp3",
		}
		
		print(f"Sending TTS request for text: {text[:50]}...")
		response = requests.post(url, headers=Header, json=body)
		data = response.json()
		
		if "audio" in data and data["audio"]:
			audio_str = data["audio"]
			
			# Debug info
			print(f"First 50 chars: {audio_str[:50]}")
			print(f"Length: {len(audio_str)}")
			
			# Create directory
			audio_dir = f"{os.getcwd()}/storage/{job_id}/audio"
			os.makedirs(audio_dir, exist_ok=True)
			
			final_filename = f"{audio_dir}/{number}.mp3"
			
			# Try different approaches
			approaches = [
				("raw", audio_str),
				("no_prefix", audio_str[2:] if audio_str.startswith('//') else audio_str),
			]
			
			saved_successfully = False
			decoded_data = None
			
			# First, try to decode using different approaches
			for name, content in approaches:
				try:
					# Add padding
					missing = len(content) % 4
					if missing:
						content += '=' * (4 - missing)
					
					# Decode
					decoded = base64.b64decode(content)
					print(f"✓ Successfully decoded using '{name}' approach ({len(decoded)} bytes)")
					decoded_data = decoded
					saved_successfully = True
					break  # Exit loop once decoding succeeds
					
				except Exception as e:
					print(f"✗ Failed {name} approach: {e}")
					continue
			
			if saved_successfully and decoded_data:
				# Save the file ONCE with the successful decode
				with open(final_filename, "wb") as f:
					f.write(decoded_data)
				print(f"✓ Saved {final_filename} ({len(decoded_data)} bytes)")
				
				# Update database - handle potential UNIQUE constraint
				try:
					database.update_chunk_table(job_id, "audio", number, final_filename)
					print(f"✓ Database updated successfully for chunk {number}")
				except Exception as db_error:
					if "UNIQUE constraint failed" in str(db_error):
						print(f"! Chunk {number} already exists in database (this might be normal if reprocessing)")
						# Consider if you need to UPDATE instead of INSERT here
					else:
						print(f"✗ Database error: {db_error}")
			else:
				print(f"❌ Failed to decode audio for chunk {number} using any approach")
		else:
			print(f"Error: No audio data received. Response: {data}")
			
	except Exception as e:
		print(f"Error at tts.py: {e}")
		import traceback
		traceback.print_exc()
