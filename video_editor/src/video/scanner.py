from pathlib import Path


VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
}


def scan_videos(
    directory: Path,
) -> list[Path]:

    if not directory.exists():

        raise FileNotFoundError(
            f"Video directory not found: "
            f"{directory}"
        )

    videos = [
        file
        for file in directory.iterdir()
        if (
            file.is_file()
            and file.suffix.lower()
            in VIDEO_EXTENSIONS
        )
    ]

    if not videos:

        raise ValueError(
            f"No videos found in {directory}"
        )

    return sorted(videos)
