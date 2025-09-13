import requests
import json
import base64
import random
import uuid
from flask import Flask, request, jsonify, Response
from io import BytesIO
import time
from pathlib import Path

app = Flask(__name__)

# ======================
# Config
# ======================
MAX_CHARS = 1000
OUTPUT_DIR = Path("output_audio")
OUTPUT_DIR.mkdir(exist_ok=True)

user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 11; SM-A207F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:116.0) Gecko/20100101 Firefox/116.0"
]

ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/1k39YpzqXZn52BgyLyGO/stream/with-timestamps?allow_unauthenticated=1"

headers = {
    "accept": "*/*",
    "content-type": "application/json",
    "user-agent": random.choice(user_agents)
}

# ======================
# Helper Function: Call ElevenLabs API
# ======================
def call_elevenlabs_api(text, model_id="eleven_v3", speed=1.0):
    """Call ElevenLabs API to convert text to speech."""
    data = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {"speed": speed}
    }
    
    start_time = time.time()
    response = requests.post(ELEVENLABS_URL, headers=headers, json=data)
    if response.status_code != 200:
        raise ValueError(f"API request failed: {response.status_code} - {response.text}")
    
    audio_chunks = []
    for line in response.iter_lines():
        if line:
            try:
                obj = json.loads(line.decode('utf-8'))
                if "audio_base64" in obj:
                    audio_chunks.append(obj["audio_base64"])
            except json.JSONDecodeError:
                continue
    
    if not audio_chunks:
        raise ValueError("No audio_base64 found in response.")
    
    audio_bytes = b""
    for chunk in audio_chunks:
        try:
            audio_bytes += base64.b64decode(chunk)
        except base64.binascii.Error as e:
            print(f"Invalid base64 chunk: {e}")
            continue
    
    elapsed_time = time.time() - start_time
    return audio_bytes, elapsed_time

# ======================
# API Endpoint: Generate Audio
# ======================
@app.route('/generate-audio', methods=['POST'])
def generate_audio():
    """Generate audio from text using ElevenLabs API."""
    try:
        # Validate input
        input_data = request.json
        if not input_data or 'text' not in input_data:
            return jsonify({"error": "Missing 'text' in request body"}), 400
        
        text_data = input_data['text'].strip()
        model_id = input_data.get('model_id', 'eleven_v3')
        speed = float(input_data.get('speed', 1.0))
        
        # Validate text length
        if len(text_data) > MAX_CHARS:
            return jsonify({"error": f"Text too long ({len(text_data)} characters). Maximum is {MAX_CHARS}."}), 400
        
        # Call API and get audio
        audio_bytes, elapsed_time = call_elevenlabs_api(text_data, model_id, speed)
        
        # Save response for debugging (optional)
        response_filename = OUTPUT_DIR / f"response_{uuid.uuid4()}.txt"
        with open(response_filename, "w", encoding="utf-8") as f:
            f.write(json.dumps({"text": text_data, "model_id": model_id, "speed": speed}))
        
        # Return audio as streamed response
        return Response(
            audio_bytes,
            mimetype='audio/mpeg',
            headers={"X-Processing-Time": f"{elapsed_time:.2f}"}
        )
    
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 500
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

# ======================
# Health Check Endpoint
# ======================
@app.route('/health', methods=['GET'])
def health():
    """Check API health."""
    return jsonify({"status": "healthy", "timestamp": time.strftime("%Y-%m-%d %H:%M:%S WIB")}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
