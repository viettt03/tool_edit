# Vietnamese Video Editor

This CLI creates a Vietnamese narrated video from short clips, optional background music, and styled ASS subtitles. The final video is rendered in one FFmpeg pass, so it does not create and re-encode an intermediate `video.mp4`.

## Setup

1. Install FFmpeg and make sure `ffmpeg` and `ffprobe` are on `PATH`.
2. From `video_editor`, install Python packages:

   ```powershell
   pip install -r requirements.txt
   ```

3. Put files in `input/` and edit `src/config.py`.
4. Run from `video_editor`:

   ```powershell
   python -m src.main
   ```

   For a vertical TikTok render, run:

   ```powershell
   python -m src.main_tiktok
   ```

## Quality and speed

- The default `libx264`, `crf=22`, and `preset="veryfast"` is a good CPU quality/speed balance.
- For faster subtitle generation on CPU, change `whisper_model` from `"small"` to `"base"`. Keep `small` when subtitle accuracy matters more.
- If an NVIDIA GPU and compatible CTranslate2/CUDA setup are available, set `whisper_device="cuda"`, `whisper_compute_type="float16"`, and `video_codec="h264_nvenc"`. The renderer automatically uses NVENC quality options instead of x264 CRF options.
- Set `audio_speed` above `1.0` only when you want a faster voice. At `1.0`, the source audio is reused without creating a WAV intermediate.

## Output

- Final video: `output/final.mp4`
- Styled subtitles: `output/subtitles.ass`
- TikTok video: `output/tiktok_final.mp4`
- TikTok subtitles: `output/tiktok_subtitles.ass`
