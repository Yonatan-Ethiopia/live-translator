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
import tts
#import tts2
from pathlib import Path
import time
import torch
from silero_vad import load_silero_vad, VADIterator

STOP_SIGNAL = object()

raw_text = []

SAMPLE_RATE = 16000
CHANNELS = 1
BYTES_PER_SAMPLE = 2
CHUNK_SECONDS = 10

CHUNK_LIMIT = SAMPLE_RATE * BYTES_PER_SAMPLE * CHANNELS * CHUNK_SECONDS

OVERLAP_SECONDS = 1.0
OVERLAP_BYTES   = int(OVERLAP_SECONDS * SAMPLE_RATE * BYTES_PER_SAMPLE * CHANNELS)

WINDOW_SIZE_SAMPLE = 512

running_event = threading.Event()
data_available = threading.Event()  # New event to signal when data is available

db = database.initdb()
cwd = str(Path.cwd())

vmodel = load_silero_vad()
vad_iterator = VADIterator(
    vmodel,
    threshold=0.5,
    sampling_rate=SAMPLE_RATE,
    min_silence_duration_ms=500,
    speech_pad_ms=200
)


speech_start = None
speech_accumaltor = []
def full_pipeline(job_id, url, job_folder):
    sub_index = 0
    chunk_index = 0
    
    # Create necessary directories
    os.makedirs(f"{cwd}/storage/{job_id}/subtitles", exist_ok=True)
    os.makedirs(f"{cwd}/storage/{job_id}/audio", exist_ok=True)
    
    def realTranslate(api, text, start, end, ind):
        
        num = ind
        try:
            print("translating here")
            response = requests.get(api, params={
                "text": text,
                "source_language": "en",
                "target_language": "am"
            })
            result = response.json()
            print(f"Status code: {response.status_code}")
            print(f"Response content: {response.text}")
            result = response.json()
            print(f"Full JSON: {result}")
            print(result['translated_text'])
            text = result['translated_text']
            subtitle = {
                "start": float(start),
                "end": float(end),
                "text": text
            }
            with open(f"{cwd}/storage/{job_id}/subtitles/{num}.json", "w", encoding="utf-8") as f:
                json.dump(subtitle, f, ensure_ascii=False, indent=2)
                
            #database.update_status(job_id, f"subtitle_chunk {num} added")
            
            database.update_chunk_table(job_id, "subtitle", num, f"{cwd}/storage/{job_id}/subtitles/{num}.json")
            num += 1
            return text
        except Exception as e:
            print(f"Error in realTranslate: {e}")
            return text
            
        # if i == 1:
            # i = 2
            # return s1
        # return s2
            
        # subtitle = {
            # "start": float(start),
            # "end": float(end),
            # "text": text
        # }
        # with open(f"{cwd}/storage/{job_id}/subtitles/{num}.json", "w", encoding="utf-8") as f:
               # json.dump(subtitle, f, ensure_ascii=False, indent=2)   
        # database.update_chunk_table(job_id, "subtitle", num, f"{cwd}/storage/{job_id}/subtitles/{num}.json")

    def get_stream_url(url):
        yt_output = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(yt_output) as ytdlp:
            info = ytdlp.extract_info(url, download=False)
            return info['url']
    
    stream_url = get_stream_url(url)

    def ffmpeg_thread(process, q):
        nonlocal chunk_index
        running_event.set()
        db.update_status(job_id, "ffmpeg:extracting stream bytes")
        
        audio_buffer = b''           # rolling byte buffer from ffmpeg
        speech_accumulator = []      # list of np.float32 arrays for current speech
        speech_start = None
        chunks_processed = 0
        current_time = 0.0           # absolute time in seconds
        
        print("Starting VAD-based audio processing...")
    
        while True:
            try:
                raw_bytes = process.stdout.read(1024 * 16)   # Read decent size for efficiency
                if not raw_bytes:
                    if process.poll() is not None:           # FFmpeg has finished
                        break
                    continue
    
                audio_buffer += raw_bytes
    
                # Process as many full frames as possible
                while len(audio_buffer) >= WINDOW_SIZE_SAMPLE * 2:
                    # Extract one frame
                    frame_bytes = audio_buffer[:WINDOW_SIZE_SAMPLE * 2]
                    audio_buffer = audio_buffer[WINDOW_SIZE_SAMPLE * 2:]
    
                    # Convert to normalized float32
                    frame_np = np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                    frame_tensor = torch.from_numpy(frame_np)
    
                    # Feed to VAD
                    speech_dict = vad_iterator(frame_tensor, return_seconds=True)
    
                    # Update absolute time
                    frame_duration = WINDOW_SIZE_SAMPLE / SAMPLE_RATE
                    current_time += frame_duration
    
                    # === VAD Logic ===
                    if speech_dict:
                        if 'start' in speech_dict:
                            speech_start = speech_dict['start']
                            speech_accumulator = [frame_np]          # Start new speech
                            print(f"Speech START detected at {speech_start:.2f}s")
    
                        if 'end' in speech_dict:
                            speech_end = speech_dict['end']
                            speech_accumulator.append(frame_np)      # Add current frame
    
                            # Create full speech segment
                            if len(speech_accumulator) > 0:
                                full_speech_np = np.concatenate(speech_accumulator)
    
                                print(f"Speech END at {speech_end:.2f}s | Duration: {speech_end - speech_start:.2f}s "
                                      f"| Samples: {len(full_speech_np)}")
    
                                # Put complete speech chunk into queue
                                q.put({
                                    "audio": full_speech_np,
                                    "start": speech_start,
                                    "end": speech_end,
                                    "duration": speech_end - speech_start
                                })
                                chunks_processed += 1
    
                            # Reset for next speech segment
                            speech_accumulator = []
                            speech_start = None
    
                    else:
                        # No event from VAD
                        if speech_start is not None:
                            # We are inside speech → keep accumulating
                            speech_accumulator.append(frame_np)
    
            except KeyboardInterrupt:
                break
            except Exception as e:
                db.update_status(job_id, "ffmpeg:Error")
                print(f"Error in ffmpeg thread: {e}")
                break
    
        # === End of stream handling ===
        running_event.clear()
        db.update_status(job_id, "ffmpeg:finished reading stream bytes")
        
        # If we were in the middle of speech when stream ended, force finish it
        if speech_start is not None and len(speech_accumulator) > 0:
            speech_end = current_time
            full_speech_np = np.concatenate(speech_accumulator)
            
            print(f"Force ending last speech segment at {speech_end:.2f}s")
            q.put({
                "audio": full_speech_np,
                "start": speech_start,
                "end": speech_end,
                "duration": speech_end - speech_start
            })
            chunks_processed += 1
    
        print(f"FFmpeg thread finished! Processed {chunks_processed} speech chunks")
        q.put("end")
        data_available.set()
        
        process.stdout.close()
        process.wait()
        vad_iterator.reset_states()

    def asr_thread(q, q_text):
        nonlocal sub_index
        db.update_status(job_id, "ASR:transcribing")
        print("Loading Whisper model...")
    
        model = WhisperModel(
            "tiny",                    # you can change to "small" later if needed
            device="cpu",
            compute_type="int8",
            local_files_only=True
        )
    
        print("Whisper model loaded, waiting for audio data...")
    
        if not data_available.wait(timeout=30):
            print("Timeout waiting for audio data")
            db.update_status(job_id, "ASR:Timeout - no audio data")
            q_text.put(STOP_SIGNAL)
            return
    
        print("\n---------Transcription Started---------")
        chunks_processed = 0
    
        while True:
            try:
                data = q.get(timeout=5.0)
                chunks_processed += 1
    
                if data == "end":
                    print("ASR received end signal")
                    break
                if data is None:
                    continue
    
                np_array = data["audio"]
                vad_start = data["start"]      # Absolute time from VAD
                vad_end = data["end"]
    
                print(f"\nProcessing chunk {chunks_processed} | VAD [{vad_start:.2f}s → {vad_end:.2f}s]")
    
                # Transcribe with faster-whisper
                segments, info = model.transcribe(
                    np_array,
                    language="en",
                    beam_size=5,
                    word_timestamps=True          # Enable this for better subtitles
                )
    
                full_text = ""
    
                for segment in segments:
                    segment_text = segment.text.strip()
                    full_text += segment_text + " "
    
                    # Shift Whisper's relative timestamps to absolute using VAD start
                    seg_start_abs = vad_start + segment.start
                    seg_end_abs   = vad_start + segment.end
    
                    print(f"  [{seg_start_abs:.2f}s → {seg_end_abs:.2f}s] {segment_text}")
    
                    # Optional: log word-level timestamps (if you want more precision later)
                    if hasattr(segment, 'words') and segment.words:
                        print("    Words:")
                        for word in segment.words:
                            word_start_abs = vad_start + word.start
                            word_end_abs   = vad_start + word.end
                            print(f"      [{word_start_abs:.2f}s → {word_end_abs:.2f}s] {word.word}")
    
                full_text = full_text.strip()
    
                # Write to rawtext file
                with open(f"{job_folder}/rawtext.txt", "a", encoding="utf-8") as f:
                    f.write(f"[{vad_start:.2f}s → {vad_end:.2f}s] {full_text}\n")
    
                # Send to translation queue (using VAD segment times for ducking)
                ind = sub_index
                translated_text = realTranslate(
                    "https://google-translat-api.proshega1.workers.dev/translate",
                    full_text,
                    vad_start,
                    vad_end,
                    ind
                )
                sub_index += 1
    
                q_text.put((translated_text, vad_start, vad_end))
    
            except queue.Empty:
                if not running_event.is_set() and q.empty():
                    print("ASR: No more data and ffmpeg finished")
                    q_text.put(STOP_SIGNAL)
                    break
                continue
    
            except Exception as e:
                print(f"Error in asr thread: {e}")
                db.update_status(job_id, "ASR:Error")
                q_text.put(STOP_SIGNAL)
                break
    
        db.update_status(job_id, "ASR:Finished")
        print(f"ASR process finished! Processed {chunks_processed} speech chunks")
        
    def tts_thread(q_text):
        print("Starting TTS thread...")
        db.update_status(job_id, "tts")
        number = 0
        chunks_processed = 0
    
        while True:
            try:
                data = q_text.get(timeout=5.0)   # Increase timeout significantly
                if data is STOP_SIGNAL:
                    print("TTS received stop signal")
                    break
    
                text, start, end = data
                print(f"TTS processing chunk {chunks_processed + 1}: {start:.2f}s → {end:.2f}s | Text: {text[:100]}...")
                tts.hasab(text, start, end, job_id, number)
                number += 1
                chunks_processed += 1
    
            except queue.Empty:
                # Only exit on empty if ffmpeg is done AND asr has already sent STOP
                if not running_event.is_set():
                    print("TTS: ffmpeg finished, waiting a bit longer for remaining ASR items...")
                    # Optional: sleep a little or check q_text.empty() again after delay
                    time.sleep(2.0)
                    if q_text.empty():
                        print("TTS: still empty after extra wait → assuming done")
                        break
                continue
            except Exception as e:
                print(f"Error in tts_thread: {e}")
                break
    
        db.update_status(job_id, "TTS:Finished")
        print(f"TTS process finished! Processed {chunks_processed} chunks")

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
    
    # ffmpeg_cmd = [
        # "ffmpeg",
        # "-i", stream_url,      # local file instead of stream
        # "-f", "s16le",
        # "-ac", "1",
        # "-ar", "16000",
        # "-"
    # ]
    print("Starting FFmpeg process...")
    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    q = queue.Queue()
    q_text = queue.Queue()

    # Clear the data_available event before starting
    data_available.clear()
    
    thread_ffmpeg = threading.Thread(target=ffmpeg_thread, args=(process, q))
    thread_asr = threading.Thread(target=asr_thread, args=(q, q_text))
    #thread_tts = threading.Thread(target=tts_thread, args=(q_text,))

    # Start all threads
    print("Starting threads...")
    thread_ffmpeg.start()
    # Give ffmpeg a moment to start producing data
    time.sleep(2)
    thread_asr.start()
    #thread_tts.start()

    # Wait for all threads to complete
    thread_ffmpeg.join()
    thread_asr.join()
    #thread_tts.join()
    
    db.update_status(job_id, "Pipeline completed successfully")
    print("All threads completed!")
