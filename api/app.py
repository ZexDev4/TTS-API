# api/app.py
import requests
import json
import base64
import random
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

# ======================
# Config
# ======================
MAX_CHARS = 1000  # Maximum character limit

# Random User-Agent
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 11; SM-A207F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:116.0) Gecko/20100101 Firefox/116.0"
]

# Endpoint ElevenLabs
url = "https://api.elevenlabs.io/v1/text-to-speech/1k39YpzqXZn52BgyLyGO/stream/with-timestamps?allow_unauthenticated=1"

headers = {
    "accept": "*/*",
    "content-type": "application/json",
    "user-agent": random.choice(user_agents)
}

# Serve index.html from static folder
@app.route('/')
def serve_index():
    return send_from_directory('../static', 'index.html')

@app.route('/tts', methods=['GET'])
def text_to_speech():
    # Get text from query parameter
    text = request.args.get('text', '').strip()

    # Validate text
    if not text:
        return jsonify({"error": "Parameter 'text' adalah wajib"}), 400
    if len(text) > MAX_CHARS:
        return jsonify({"error": f"Teks terlalu panjang ({len(text)} huruf). Maksimal {MAX_CHARS}."}), 400

    # Prepare data for ElevenLabs API
    data = {
        "text": text,
        "model_id": "eleven_v3",
        "voice_settings": {"speed": 1}
    }

    try:
        # Send request to ElevenLabs
        response = requests.post(url, headers=headers, json=data, stream=True)
        response.raise_for_status()

        # Check content type
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type and "text/event-stream" not in content_type:
            return jsonify({"error": f"Unexpected content type: {content_type}"}), 500

        # Parse audio response
        audio_chunks = []
        raw_response = response.text
        for line in raw_response.splitlines():
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    obj = json.loads(line)
                    if "audio_base64" in obj:
                        # Validate base64 string
                        try:
                            base64.b64decode(obj["audio_base64"], validate=True)
                            audio_chunks.append(obj["audio_base64"])
                        except base64.binascii.Error:
                            continue  # Skip invalid base64
                except json.JSONDecodeError:
                    continue

        # Check if audio was generated
        if audio_chunks:
            # Join base64 chunks
            audio_base64 = "".join(audio_chunks)
            # Verify the joined base64 string
            try:
                base64.b64decode(audio_base64, validate=True)
            except base64.binascii.Error:
                return jsonify({"error": "Invalid base64 audio data"}), 500

            return jsonify({
                "status": "success",
                "audio_base64": audio_base64
            }), 200
        else:
            return jsonify({"error": "Tidak ada audio_base64 valid ditemukan di response.", "raw_response": raw_response[:1000]}), 500

    except requests.RequestException as e:
        return jsonify({"error": f"Gagal mengirim request: {str(e)}", "raw_response": response.text[:1000] if 'response' in locals() else ""}), 500

if __name__ == '__main__':
    app.run(debug=True)
