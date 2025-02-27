import os
import ffmpeg
import whisper
import argparse
import warnings
import tempfile
from .utils import filename, str2bool, write_srt
from .ass_generator import AssGenerator


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("video", nargs="+", type=str,
                        help="paths to video files to transcribe")
    parser.add_argument("--model", default="small",
                        choices=whisper.available_models(), help="name of the Whisper model to use")
    parser.add_argument("--output_dir", "-o", type=str,
                        default=".", help="directory to save the outputs")
    parser.add_argument("--subtitle_format", type=str, default="ass",
                        choices=["srt", "ass"], help="subtitle format to generate")
    parser.add_argument("--ass_style", type=str, default="default",
                        choices=["default", "highlight"], help="ASS subtitle style template")
    parser.add_argument("--output_srt", type=str2bool, default=False,
                        help="whether to output the .srt file along with the video files")
    parser.add_argument("--srt_only", type=str2bool, default=False,
                        help="only generate the .srt file and not create overlayed video")
    parser.add_argument("--verbose", type=str2bool, default=False,
                        help="whether to print out the progress and debug messages")

    parser.add_argument("--task", type=str, default="transcribe", choices=[
                        "transcribe", "translate"], help="whether to perform X->X speech recognition ('transcribe') or X->English translation ('translate')")
    parser.add_argument("--language", type=str, default="auto", choices=["auto","af","am","ar","as","az","ba","be","bg","bn","bo","br","bs","ca","cs","cy","da","de","el","en","es","et","eu","fa","fi","fo","fr","gl","gu","ha","haw","he","hi","hr","ht","hu","hy","id","is","it","ja","jw","ka","kk","km","kn","ko","la","lb","ln","lo","lt","lv","mg","mi","mk","ml","mn","mr","ms","mt","my","ne","nl","nn","no","oc","pa","pl","ps","pt","ro","ru","sa","sd","si","sk","sl","sn","so","sq","sr","su","sv","sw","ta","te","tg","th","tk","tl","tr","tt","uk","ur","uz","vi","yi","yo","zh"], 
    help="What is the origin language of the video? If unset, it is detected automatically.")

    args = parser.parse_args().__dict__
    model_name: str = args.pop("model")
    output_dir: str = args.pop("output_dir")
    subtitle_format: str = args.pop("subtitle_format")
    ass_style: str = args.pop("ass_style")
    output_srt: bool = args.pop("output_srt")
    srt_only: bool = args.pop("srt_only")
    language: str = args.pop("language")
    
    os.makedirs(output_dir, exist_ok=True)

    if model_name.endswith(".en"):
        warnings.warn(
            f"{model_name} is an English-only model, forcing English detection.")
        args["language"] = "en"
    # if translate task used and language argument is set, then use it
    elif language != "auto":
        args["language"] = language
    
    args["word_timestamps"] = True
        
    model = whisper.load_model(model_name)
    audios = get_audio(args.pop("video"))
    subtitles = get_subtitles(
        audios, output_srt or srt_only, output_dir, subtitle_format, ass_style,
        lambda audio_path: model.transcribe(audio_path, **args)
    )

    if srt_only:
        return

    for path, sub_path in subtitles.items():
        out_path = os.path.join(output_dir, f"{filename(path)}_subtitled.mp4")

        print(f"Burning subtitles into {filename(path)}...")

        # Get video stream info
        probe = ffmpeg.probe(path)
        video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        width = int(video_info['width'])
        height = int(video_info['height'])

        # Set up ffmpeg inputs
        video = ffmpeg.input(path)
        audio = video.audio

        if subtitle_format == "srt":
            # For SRT, use subtitles filter
            video_with_subs = video.filter('subtitles', sub_path, force_style="OutlineColour=&H40000000,BorderStyle=3")
        else:
            # For ASS, use ass filter which properly handles all styling
            video_with_subs = video.filter('ass', sub_path)

        # Hard encode the subtitles
        try:
            (
                ffmpeg
                .concat(video_with_subs, audio, v=1, a=1)
                .output(
                    out_path,
                    acodec='aac',
                    vcodec='h264',
                    crf=23,  # Adjust quality (18-28 is good range, lower is better)
                    preset='medium'  # Adjust encoding speed/quality trade-off
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            print(f"Successfully saved subtitled video to {os.path.abspath(out_path)}")
        except ffmpeg.Error as e:
            print("An error occurred while encoding the video:")
            print("stdout:", e.stdout.decode('utf8'))
            print("stderr:", e.stderr.decode('utf8'))
            raise e


def get_audio(paths):
    temp_dir = tempfile.gettempdir()

    audio_paths = {}

    for path in paths:
        print(f"Extracting audio from {filename(path)}...")
        output_path = os.path.join(temp_dir, f"{filename(path)}.wav")

        ffmpeg.input(path).output(
            output_path,
            acodec="pcm_s16le", ac=1, ar="16k"
        ).run(quiet=True, overwrite_output=True)

        audio_paths[path] = output_path

    return audio_paths


def get_subtitles(audio_paths: dict, output_srt: bool, output_dir: str, 
                  subtitle_format: str, ass_style: str, transcribe: callable):
    subtitles_path = {}
    ass_generator = AssGenerator()

    for path, audio_path in audio_paths.items():
        # Always save subtitle files in the output directory
        sub_path = os.path.join(output_dir, f"{filename(path)}.{subtitle_format}")
        
        print(
            f"Generating subtitles for {filename(path)}... This might take a while."
        )

        result = transcribe(audio_path)

        if subtitle_format == "srt":
            write_srt(result["segments"], sub_path)
        else:
            with open(sub_path, "w", encoding="utf-8") as f:
                f.write(ass_generator.generate_ass(result["segments"], ass_style))

        subtitles_path[path] = sub_path

        print(f"Saved subtitles to {os.path.abspath(sub_path)}.")

    return subtitles_path


if __name__ == '__main__':
    main()
