from flask import Flask, request, jsonify
import requests
import json
import random

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
    """Validate text length and content."""
    if not text:
        raise ValueError("Teks tidak boleh kosong.")
    if len(text) > MAX_CHARS:
        raise ValueError(f"Teks terlalu panjang ({len(text)} karakter). Maksimal {MAX_CHARS} karakter.")
    return text

def send_request(text):
    """Send request to ElevenLabs API."""
    data = {
        "text": text,
        "model_id": "eleven_v3",
        "voice_settings": {"speed": 1}
    }
    try:
        response = requests.post(ELEVENLABS_URL, headers=get_headers(), json=data, stream=True)
        response.raise_for_status()
        return response
    except requests.RequestException as re:
        print(f"ElevenLabs request failed: {re}")  # Logging ke stdout
        raise

def parse_audio_chunks(response):
    """Parse audio_base64 from streaming response."""
    audio_chunks = []
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8').strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    obj = json.loads(line)
                    if "audio_base64" in obj:
                        audio_chunks.append(obj["audio_base64"])
                except json.JSONDecodeError as e:
                    print(f"Failed to parse JSON line: {line}, error: {e}")  # Logging ke stdout
                    continue
    return audio_chunks

@app.route('/text-to-speech', methods=['GET'])
def text_to_speech():
    """Endpoint to convert text to audio and return base64."""
    try:
        # Ambil teks dari query parameter
        input_text = request.args.get('text')
        if not input_text:
            return jsonify({"error": "Parameter 'text' diperlukan dalam query string."}), 400

        # Validasi teks
        validated_text = validate_text(input_text)

        # Kirim request ke ElevenLabs
        response = send_request(validated_text)

        # Parse audio chunks
        audio_chunks = parse_audio_chunks(response)

        # Gabungkan chunks dan kembalikan sebagai base64
        if audio_chunks:
            combined_base64 = "".join(audio_chunks)
            print(f"Processed text-to-speech for text length: {len(validated_text)}")  # Logging ke stdout
            return jsonify({
                "status": "success",
                "audio_base64": combined_base64,
                "audio_format": "mp3"
            }), 200
        else:
            print("No audio_base64 found in response")  # Logging ke stdout
            return jsonify({"error": "Tidak ada audio_base64 ditemukan di response."}), 500

    except ValueError as ve:
        print(f"Validation error: {ve}")  # Logging ke stdout
        return jsonify({"error": str(ve)}), 400
    except requests.RequestException as re:
        return jsonify({"error": f"Gagal mengirim request ke ElevenLabs: {re}"}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")  # Logging ke stdout
        return jsonify({"error": f"Terjadi kesalahan: {e}"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)
