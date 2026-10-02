#!/usr/bin/env python3

import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any
import getopt
import re

import yaml

import audiopts

VALID_PHASES = set("mset")
DEFAULT_PHASES = set("mset")
CATEGORY_DIR_SUFFIX = {
    "extras": "Extras",
    "trailers": "Trailers",
}


def parse_phases(value):
    phases = set(value)
    unknown = phases - VALID_PHASES
    if unknown:
        raise ValueError(f"unknown phase code(s): {''.join(sorted(unknown))}")
    return phases


def should_rip_category(category, phases):
    if category == "feature":
        return True
    if category == "extras":
        return "e" in phases
    if category == "trailers":
        return "t" in phases
    return True


def should_run_main_rip(category, phases):
    return category != "feature" or "m" in phases


def should_extract_subtitles(track, phases):
    return bool(track.get("subtitle")) and "s" in phases


def merged_tracks(config):
    defaults = config.get("defaults", {})
    for track in config.get("tracks", []):
        yield defaults | track


def get_output_path(config, track):
    category = track.get("category", "")
    main_title: str = config.get("title", "")

    if category == "feature":
        track_title = track.get("name", main_title)
        track_title += ".mp4"
        return Path(config.get("dest", "")) / track_title

    if category not in CATEGORY_DIR_SUFFIX:
        raise ValueError(f"unknown category {category} for title!")

    track_title: str = track.get("name", "title" + str(track.get("title", 0)))
    track_title += ".mp4"
    category_dir = main_title + CATEGORY_DIR_SUFFIX[category]
    return Path(config.get("dest", "")) / category_dir / track_title


def build_handbrake_command(dest, config, track):
    source = config.get("location", "")
    title = track.get("title", None)
    preset = track.get("preset", None)
    audio = track.get("audio", None)

    cmd = ["HandBrakeCLI"]
    if source:
        cmd.extend(["-i", source])
    if title:
        cmd.extend(["-t", str(title)])
    if preset:
        cmd.extend(["--preset-import-gui", "-Z", preset])
    if audio:
        cmd.extend(audiopts.audio_options(audio))
    cmd.extend(["--subtitle", "none"])
    if dest:
        cmd.extend(["-o", str(dest)])

    return cmd


def build_subtitle_command(dest, config, track):
    source = config.get("location", "")
    title = track.get("title", None)
    subtitle = track.get("subtitle", None)
    subtitle_index = track.get("subtitlenum", None)
    subtitle_file = f"{dest.stem}.{subtitle}.mkv"
    subtitle_dir = config.get("subtitledest", None)
    subtitle_dest = Path(subtitle_dir) / subtitle_file

    cmd = [
        "HandBrakeCLI",
        "-i",
        source,
        "-t",
        str(title),
        "-l",
        "100",
        "-w",
        "100",
        "-audio",
        "none",
        "--encoder-preset",
        "ultrafast",
        "-o",
        str(subtitle_dest),
    ]
    if subtitle_index is not None:
        cmd.extend(["--subtitle", str(subtitle_index)])
    else:
        cmd.extend(["--subtitle", "1"])

    return cmd


def do_post_subtitles(dest, config, track):
    subtitle = track.get("subtitle", None)
    subtitle_file = f"{dest.stem}.{subtitle}.mkv"
    subtitle_dir = config.get("subtitledest", None)
    subtitle_dest = Path(subtitle_dir) / subtitle_file

    print(f"{dest} -> {subtitle_dest}")

    pth = Path(subtitle_dest)

    if (not pth.is_file()) or pth.stat().st_size <= 0:
        print("Error! Subtitle mkv not found!")
        return 1

    result = subprocess.run(
        ["mkvmerge", "-i", str(pth)], capture_output=True, text=True
    )

    if result.returncode != 0:
        print("Couldn't read mkv file!")
        return result.returncode

    for line in result.stdout.splitlines():
        if match := re.search(r"^Track ID (\d+): subtitles \((.*)\)", line):
            tracknum = match[1]
            subtype = match[2]
            if "PGS" in subtype:
                ext = ".sup"
            elif "VobSub" in subtype:
                ext = ".sub"
            else:
                print("Error! Unknown subtype")
                return 1

            dest = pth.with_suffix(ext)
            print(f"Found {match[2]} subtitles with stream id {match[1]}")
            cmd = ["mkvextract", "tracks", str(pth), f"{tracknum}:{dest}"]
            print(shlex.join(cmd))
            res = subprocess.run(cmd)
            if res.returncode == 0:
                pth.unlink()
            return res.returncode

    print("Error! No subtitle track found!")
    return 1


def run_command(cmd):
    print(shlex.join(cmd))
    res = subprocess.run(cmd)
    return res.returncode

def rip_track(dest, config, track, phases):
    category = track.get("category", "")

    status = []
    
    dest.parent.mkdir(parents=True, exist_ok=True)

    if should_run_main_rip(category, phases):
        exitcode = run_command(build_handbrake_command(dest, config, track))
        if exitcode == 0:
            status.append("encoding success")
        else:
            status.append("encoding failed")
            
    if should_extract_subtitles(track, phases):
        subtitle_dir = config.get("subtitledest")
        if not isinstance(subtitle_dir, str) or not subtitle_dir.strip():
            print("Error! Set subtitledest in the YAML configuration")
            status.append("subtitle extract failed")
            return "; ".join(status)
        Path(subtitle_dir).mkdir(parents=True, exist_ok=True)
        exitcode = run_command(build_subtitle_command(dest, config, track))
        if exitcode == 0:
            exitcode = do_post_subtitles(dest, config, track)
        if exitcode == 0:
            status.append("subtitle extract success")
        else:
            status.append("subtitle extract failed")

    return "; ".join(status)

def main(conf: str, phases):
    config: None | Any = None
    with open(conf, "rb") as fp:
        config = yaml.safe_load(fp)

    summaries = {}
    
    for track in merged_tracks(config):
        category = track.get("category", "")
        if not should_rip_category(category, phases):
            print(f"Skipping {category}; phase disabled")
            continue

        try:
            path = get_output_path(config, track)
        except ValueError as err:
            print(f"error: {err}")
            continue

        print(f"Ripping track to {path}")
        result = rip_track(path, config, track, phases)
        summaries[track.get("title")]  = result

    for trackid in sorted(summaries.keys()):
        print(f"Track {trackid}: {summaries[trackid]}")
        

if __name__ == "__main__":
    phases = DEFAULT_PHASES
    optlist, args = getopt.getopt(sys.argv[1:], "p:")
    if len(optlist) != 0:
        arg, val = optlist[-1]
        try:
            phases = parse_phases(val)
        except ValueError as err:
            print(f"error: {err}")
            exit(1)

    if len(args) != 1:
        print(f"Usage: {sys.argv[0]} [ -p mset ] file.yml")
        exit(1)

    main(args[0], phases)
