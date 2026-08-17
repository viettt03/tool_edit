from __future__ import annotations

import argparse
import json
from pathlib import Path

from .collector import DouyinPageCollector
from .downloader import (
    DouyinDownloader,
    format_result,
    read_url_list,
    result_as_dict,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download public Douyin videos for the video editor. "
            "Provide URLs copied from Douyin."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--video-url",
        "--url",
        dest="video_urls",
        action="append",
        help="A public Douyin video URL. Downloads one per URL.",
    )
    source.add_argument(
        "--urls",
        type=Path,
        help="Text file containing one public Douyin URL per line.",
    )
    source.add_argument(
        "--user-url",
        help="A public Douyin user URL; collect videos from that user.",
    )
    source.add_argument(
        "--keyword",
        help="Search Douyin video pages by keyword and collect results.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum videos for --user-url or --keyword (default: 10).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("input/videos"),
        help="Directory for downloaded videos (default: input/videos).",
    )
    parser.add_argument(
        "--cookies",
        type=Path,
        help=(
            "Optional Netscape-format cookies file from your own browser "
            "session, if the public URL requires it."
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional JSON report path for download results.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        if args.video_urls:
            urls = args.video_urls
        elif args.urls:
            urls = read_url_list(args.urls)
        else:
            collector = DouyinPageCollector(args.cookies)
            if args.user_url:
                urls = collector.collect_user(args.user_url, args.limit)
            else:
                urls = collector.search(args.keyword, args.limit)

            print(f"Collected {len(urls)} video URLs")

        results = DouyinDownloader(
            output_directory=args.output,
            cookies_file=args.cookies,
        ).download(urls)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}")
        return 1

    for result in results:
        print(format_result(result))

    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(
                [result_as_dict(result) for result in results],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Report: {args.report}")

    failed = sum(result.status == "failed" for result in results)
    print(f"Downloaded: {len(results) - failed}, failed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
