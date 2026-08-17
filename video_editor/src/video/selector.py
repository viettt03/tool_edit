import random
from pathlib import Path

from ..ffmpeg.executor import get_video_duration


def select_videos(
    videos: list[Path],
    target_duration: float,
    randomize: bool = True,
    avoid_consecutive_duplicate: bool = True,
) -> list[Path]:

    if not videos:
        raise ValueError(
            "Video list is empty."
        )

    pool = videos.copy()

    if randomize:
        random.shuffle(pool)

    selected = []
    total_duration = 0.0
    index = 0
    duration_cache: dict[Path, float] = {}

    while total_duration < target_duration:

        video = pool[index % len(pool)]

        if (
            avoid_consecutive_duplicate
            and selected
            and selected[-1] == video
            and len(pool) > 1
        ):
            index += 1
            continue

        duration = duration_cache.get(video)
        if duration is None:
            duration = get_video_duration(video)
            if duration <= 0:
                raise ValueError(f"Video has no usable duration: {video}")
            duration_cache[video] = duration

        selected.append(video)

        total_duration += duration

        index += 1

        # Khi đi hết pool thì shuffle lại
        if index % len(pool) == 0:

            if randomize:
                random.shuffle(pool)

    return selected
