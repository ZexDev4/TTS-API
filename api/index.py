from flask import Flask, request, jsonify
import requests
import json
import random
import re
import base64

app = Flask(__name__)

# Configuration (hardcoded variables)
MAX_CHARS = 1000
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/1k39YpzqXZn52BgyLyGO/stream/with-timestamps?allow_unauthenticated=1"
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 11; SM-A207F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:116.0) Gecko/20100101 Firefox/116.0"
]

def get_headers():
    """Generate headers with random user-agent."""
    return {
        "accept": "*/*",
        "content-type": "application/json",
        "user-agent": random.choice(USER_AGENTS)
    }

def validate_text(text):
    """Validate and sanitize text."""
    if not text:
        raise ValueError("Teks tidak boleh kosong.")
    if len(text) > MAX_CHARS:
        raise ValueError(f"Teks terlalu panjang ({len(text)} karakter). Maksimal {MAX_CHARS} karakter.")
    # Sanitize: keep alphanumeric, spaces, and common punctuation; replace ellipses
    text = re.sub(r'\.{2,}|…', '.', text)  # Replace ... or … with .
    text = re.sub(r'[^\w\s.,!?\'"-]', '', text)  # Remove other non-standard characters
    return text

def is_valid_base64(s):
    """Check if string is valid base64."""
    try:
        if not re.match(r'^[A-Za-z0-9+/=]+$', s):
            return False
        base64.b64decode(s, validate=True)
        return True
    except Exception:
        return False

def send_request(text):
    """Send request to ElevenLabs API."""
    data = {
        "text": text,
        "model_id": "eleven_v3",
        "voice_settings": {"speed": 1}
    }
    try:
        response = requests.post(ELEVENLABS_URL, headers=get_headers(), json=data, stream=True)
        print(f"ElevenLabs response status: {response.status_code}")
        if response.status_code != 200:
            print(f"ElevenLabs response content: {response.text[:500]}")
        response.raise_for_status()
        return response
    except requests.RequestException as re:
        print(f"ElevenLabs request failed: {re}")
        raise

def parse_audio_chunks(response):
    """Parse audio_base64 from streaming response."""
    audio_chunks = []
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8').strip()
            print(f"Raw response line: {line[:100]}...")
            if line.startswith("{") and line.endswith("}"):
                try:
                    obj = json.loads(line)
                    if "audio_base64" in obj:
                        chunk = obj["audio_base64"]
                        if is_valid_base64(chunk):
                            audio_chunks.append(chunk)
                        else:
                            print(f"Invalid base64 chunk skipped: {chunk[:50]}...")
                except json.JSONDecodeError as e:
                    print(f"Failed to parse JSON line: {line[:50]}..., error: {e}")
                    continue
    print(f"Valid audio chunks collected: {len(audio_chunks)}")
    return audio_chunks

@app.route('/text-to-speech', methods=['GET'])
def text_to_speech():
    """Endpoint to convert text to audio and return base64."""
    try:
        input_text = request.args.get('text', '').strip()
        if not input_text:
            return jsonify({"error": "Parameter 'text' diperlukan dalam query string."}), 400

        validated_text = validate_text(input_text)
        print(f"Sanitized text: {validated_text}")
        response = send_request(validated_text)
        audio_chunks = parse_audio_chunks(response)

        if audio_chunks:
            combined_base64 = "".join(audio_chunks)
            if not is_valid_base64(combined_base64):
                print(f"Invalid combined base64: {combined_base64[:50]}...")
                return jsonify({"error": "Invalid base64 audio data from API. Try simpler text (e.g., avoid ellipses)."}), 500
            print(f"Processed text-to-speech for text length: {len(validated_text)}")
            return jsonify({
                "status": "success",
                "audio_base64": combined_base64,
                "audio_format": "mp3"
            }), 200
        else:
            print("No valid audio_base64 found in response")
            return jsonify({"error": "No valid audio data received from API. Try simpler text (e.g., avoid ellipses)."}), 500

    except ValueError as ve:
        print(f"Validation error: {ve}")
        return jsonify({"error": str(ve)}), 400
    except requests.RequestException as re:
        return jsonify({"error": f"Failed to process request to ElevenLabs: {re}. Try simpler text."}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": f"Internal server error: {e}. Try simpler text."}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)
