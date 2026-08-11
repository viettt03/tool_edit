# Vietnamese Video Editor

This CLI creates a long-form video from a Vietnamese narration, optional background music, and short video clips.

Requirements:
- `ffmpeg` installed and on PATH
- Python packages: `pip install -r requirements.txt`

Usage:
1. Edit `src/config.py` to point to your files.
2. Run: `python -m src.main` from the workspace root.

Outputs:
- Final video: as set in `OUTPUT_FILE`.
- Subtitles: `output/subtitles.srt` next to output.
