def build_video_filter(
    count: int,
    width: int,
    height: int,
    fps: int,
    output_label: str = "video",
) -> str:
    """Normalize and concatenate video inputs in a single filter graph."""
    if count < 1:
        raise ValueError("At least one video is required.")

    filters: list[str] = []
    for index in range(count):
        filters.append(
            f"[{index}:v]"
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},fps={fps},setsar=1,format=yuv420p,"
            f"setpts=PTS-STARTPTS[v{index}]"
        )

    concat_inputs = "".join(f"[v{index}]" for index in range(count))
    filters.append(f"{concat_inputs}concat=n={count}:v=1:a=0[{output_label}]")
    return ";".join(filters)
