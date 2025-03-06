# Automatic subtitles in your videos

This repository uses `ffmpeg` and [OpenAI's Whisper API](https://platform.openai.com/docs/guides/speech-to-text) to automatically generate and overlay subtitles on any video.

## Installation

To get started, you'll need Python 3.7 or newer. Install the binary by running the following command:

    pip install git+https://github.com/m1guelpf/auto-subtitle.git

You'll also need to install [`ffmpeg`](https://ffmpeg.org/), which is available from most package managers:

```bash
# on Ubuntu or Debian
sudo apt update && sudo apt install ffmpeg

# on MacOS using Homebrew (https://brew.sh/)
brew install ffmpeg

# on Windows using Chocolatey (https://chocolatey.org/)
choco install ffmpeg
```

## Usage

The following command will generate a `subtitled/video.mp4` file contained the input video with overlayed subtitles.

    auto_subtitle /path/to/video.mp4 -o subtitled/

The default setting uses OpenAI's `whisper-1` model, which works well for transcribing in multiple languages.

    auto_subtitle /path/to/video.mp4 --model whisper-1

Adding `--task translate` will translate the subtitles into English:

    auto_subtitle /path/to/video.mp4 --task translate

Run the following to view all available options:

    auto_subtitle --help

Run the higlight caption task: 

    python3.11 -m auto_subtitle.cli ./fresh-market-demo.mp4 --model whisper-1 --subtitle_format ass -o .

## Flask API

You can also use this service as a Flask web application with an API endpoint:

```bash
# Start the Flask server
python app.py
```

This will start a web server at http://localhost:5000 with the following features:

- Web interface at http://localhost:5000/ for uploading videos and generating subtitles
- API endpoint at http://localhost:5000/subtitle for programmatic access

### API Usage Example

```bash
# Using curl to send a request to the API
curl -X POST -F "video=@/path/to/video.mp4" -F "model=whisper-1" -F "subtitle_format=ass" http://localhost:5000/subtitle -o subtitled_video.mp4
```

Available parameters:
- `video`: The video file to process (required)
- `model`: Whisper model to use (default: whisper-1)
- `subtitle_format`: Format of subtitles, 'srt' or 'ass' (default: ass)
- `ass_style`: Style for ASS subtitles, 'default' or 'highlight' (default: default)
- `task`: 'transcribe' or 'translate' (default: transcribe)
- `language`: Language code or 'auto' for auto-detection (default: auto)
- `srt_only`: 'true' to get only subtitle file, 'false' to get video with subtitles (default: false)

## OpenAI API Key

This application uses the OpenAI API for speech-to-text transcription. You need to set your OpenAI API key in the `.env` file:

```
OPENAI_API_KEY=your_openai_api_key_here
```

You can obtain an API key by signing up at [OpenAI's platform](https://platform.openai.com/).

## Deployment to Railway

This application is configured for easy deployment to [Railway](https://railway.app/). The following files are included for deployment:

- `Procfile`: Specifies the start command for the web server
- `runtime.txt`: Specifies Python 3.11 as the required runtime
- `railway.json`: Contains Railway-specific configuration
- `Dockerfile`: Provides container configuration with ffmpeg

### Deployment Steps

1. Install the Railway CLI:
   ```bash
   npm i -g @railway/cli
   ```

2. Login to your Railway account:
   ```bash
   railway login
   ```

3. Initialize your project:
   ```bash
   railway init
   ```

4. Deploy your application:
   ```bash
   railway up
   ```

5. Open your deployed application:
   ```bash
   railway open
   ```

The application will automatically use Python 3.11 as specified in the `runtime.txt` file, and the start command is defined in both the `Procfile` and `railway.json` files.

### Environment Variables

The following environment variables can be configured in Railway:

- `PORT`: The port on which the application will run (default: 5000)
- `PYTHONUNBUFFERED`: Set to 1 to ensure unbuffered Python output
- `OPENAI_API_KEY`: Your OpenAI API key (required)

You can set these variables in the Railway dashboard under your project's "Variables" tab.

### Handling Long Processing Times

When processing longer videos, the default timeout of 30 seconds in Gunicorn might not be sufficient. The application is configured with a 300-second (5-minute) timeout to handle longer processing times. If your videos require even more processing time, you can adjust the timeout in the following files:

1. **Dockerfile**:
   ```
   CMD gunicorn app:app --bind 0.0.0.0:$PORT --timeout 300
   ```

2. **railway.json**:
   ```json
   "startCommand": "gunicorn app:app --timeout 300"
   ```

If you need to increase memory allocation for processing larger videos or using more complex models, you can adjust the resources in the Railway dashboard:

1. Go to your project in the Railway dashboard
2. Select your service
3. Click on "Settings"
4. Under "Resource Usage", increase the memory allocation as needed

## License

This script is open-source and licensed under the MIT License. For more details, check the [LICENSE](LICENSE) file.
