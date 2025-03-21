import os
import tempfile
import ffmpeg
import gc
from flask import Flask, request, jsonify, send_file, url_for, render_template
from werkzeug.utils import secure_filename
from auto_subtitle.utils import filename, write_srt
from auto_subtitle.ass_generator import AssGenerator
import openai
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Set OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(tempfile.gettempdir(), 'auto_subtitle_uploads')
app.config['OUTPUT_FOLDER'] = os.path.join(tempfile.gettempdir(), 'auto_subtitle_outputs')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload size

# Create necessary directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# List of allowed file extensions
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_audio(video_path):
    """Extract audio from video file"""
    temp_dir = tempfile.gettempdir()
    output_path = os.path.join(temp_dir, f"{filename(video_path)}.wav")

    ffmpeg.input(video_path).output(
        output_path,
        acodec="pcm_s16le", ac=1, ar="16k"
    ).run(quiet=True, overwrite_output=True)

    return output_path

def get_subtitles(video_path, audio_path, output_dir, subtitle_format, ass_style, transcribe_func):
    """Generate subtitles for the video"""
    # Save subtitle file in the output directory
    sub_path = os.path.join(output_dir, f"{filename(video_path)}.{subtitle_format}")
    
    result = transcribe_func(audio_path)

    if subtitle_format == "srt":
        with open(sub_path, "w", encoding="utf-8") as f:
            write_srt(result["segments"], f)
    else:
        ass_generator = AssGenerator()
        with open(sub_path, "w", encoding="utf-8") as f:
            f.write(ass_generator.generate_ass(result["segments"], ass_style))

    return sub_path

def create_subtitled_video(video_path, sub_path, output_dir, subtitle_format):
    """Burn subtitles into video"""
    out_path = os.path.join(output_dir, f"{filename(video_path)}_subtitled.mp4")

    # Get video stream info
    probe = ffmpeg.probe(video_path)
    video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')

    # Set up ffmpeg inputs
    video = ffmpeg.input(video_path)
    audio = video.audio

    if subtitle_format == "srt":
        # For SRT, use subtitles filter
        video_with_subs = video.filter('subtitles', sub_path, force_style="OutlineColour=&H40000000,BorderStyle=3")
    else:
        # For ASS, use ass filter which properly handles all styling
        video_with_subs = video.filter('ass', sub_path)

    # Hard encode the subtitles
    (
        ffmpeg
        .concat(video_with_subs, audio, v=1, a=1)
        .output(
            out_path,
            acodec='aac',
            vcodec='h264',
            crf=23,
            preset='medium'
        )
        .overwrite_output()
        .run(capture_stdout=True, capture_stderr=True)
    )

    return out_path

def transcribe_with_openai_api(audio_path, model_name="whisper-1", task="transcribe", language="auto"):
    """Transcribe audio using OpenAI's Whisper API"""
    try:
        # Prepare parameters for API call
        params = {
            "model": model_name,
            "response_format": "verbose_json"
        }
        
        # Add language if specified and not auto
        if language != "auto":
            params["language"] = language
        
        # Set task (translate or transcribe)
        if task == "translate":
            # For translation, we always translate to English
            params["response_format"] = "verbose_json"
        
        # Open the audio file
        with open(audio_path, "rb") as audio_file:
            # Call the OpenAI API
            if task == "transcribe":
                response = openai.audio.transcriptions.create(
                    file=audio_file,
                    **params
                )
            else:  # translate
                response = openai.audio.translations.create(
                    file=audio_file,
                    **params
                )
        
        # Convert response to dictionary if it's not already
        if not isinstance(response, dict):
            response = response.model_dump()
        
        # Process the response to match the format expected by our subtitle generator
        # OpenAI API returns segments with start and end times
        segments = []
        
        if "segments" in response:
            # If the API already returns segments in the format we need
            segments = response["segments"]
        else:
            # If we need to create segments from the response
            # This is a simplified version - in a real implementation, 
            # you might want to split the text into sentences or use other logic
            segments = [
                {
                    "start": 0,
                    "end": 10,  # Default duration if not provided
                    "text": response.get("text", "")
                }
            ]
        
        # Return in the format expected by get_subtitles
        return {
            "segments": segments,
            "text": response.get("text", "")
        }
    
    except Exception as e:
        print(f"Error in OpenAI API transcription: {str(e)}")
        raise

@app.route('/subtitle', methods=['POST'])
def subtitle_video():
    # Check if a file was uploaded
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    file = request.files['video']
    
    # Check if the file is valid
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
    
    # Get parameters from request
    model_name = request.form.get('model', 'whisper-1')  # Default to OpenAI's whisper-1 model
    subtitle_format = request.form.get('subtitle_format', 'ass')
    ass_style = request.form.get('ass_style', 'default')
    task = request.form.get('task', 'transcribe')
    language = request.form.get('language', 'auto')
    srt_only = request.form.get('srt_only', 'false').lower() == 'true'
    
    # Validate parameters
    if subtitle_format not in ['srt', 'ass']:
        return jsonify({'error': 'Invalid subtitle format. Use "srt" or "ass"'}), 400
    
    if ass_style not in ['default', 'highlight']:
        return jsonify({'error': 'Invalid ASS style. Use "default" or "highlight"'}), 400
    
    if task not in ['transcribe', 'translate']:
        return jsonify({'error': 'Invalid task. Use "transcribe" or "translate"'}), 400
    
    # Save the uploaded file
    video_filename = secure_filename(file.filename)
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
    file.save(video_path)
    
    try:
        # Extract audio
        audio_path = get_audio(video_path)
        
        # Generate subtitles using OpenAI's Whisper API
        sub_path = get_subtitles(
            video_path, 
            audio_path, 
            app.config['OUTPUT_FOLDER'], 
            subtitle_format, 
            ass_style,
            lambda audio_path: transcribe_with_openai_api(audio_path, model_name, task, language)
        )
        
        # If srt_only is True, return the subtitle file
        if srt_only:
            return send_file(
                sub_path,
                as_attachment=True,
                download_name=f"{filename(video_filename)}.{subtitle_format}"
            )
        
        # Create subtitled video
        output_video_path = create_subtitled_video(
            video_path, 
            sub_path, 
            app.config['OUTPUT_FOLDER'], 
            subtitle_format
        )
        
        # Return the subtitled video
        return send_file(
            output_video_path,
            as_attachment=True,
            download_name=f"{filename(video_filename)}_subtitled.mp4"
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        # Clean up temporary files
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
        # Force garbage collection to free memory
        gc.collect()

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5123))
    app.run(host='0.0.0.0', port=port, debug=False)
