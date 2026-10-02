#!/usr/bin/env python3

import json
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
        print(main_title, track_title)
        track_title += ".mp4"
        return Path(config.get("dest", "")) / track_title

    if category not in CATEGORY_DIR_SUFFIX:
        raise ValueError(f"unknown category {category} for title!")

    track_title: str = track.get("name", "title" + str(track.get("title", 0)))
    track_title += ".mp4"
    category_dir = main_title + CATEGORY_DIR_SUFFIX[category]
    return Path(config.get("dest", "")) / category_dir / track_title

def build_makemkv_command(dest, config, track):
    source = config.get("location", "")
    title = track.get("title", "")
    
    cmd = ["makemkvcon", "--minlength=0", "mkv"]

    if source is not None:
        cmd.append(source)
    if title is not None:
        cmd.append(str(title))
    cmd.append(str(dest))

    print(cmd)

    return cmd

def build_handbrake_command(dest, config, track, mkv_file):
    title = track.get("title", None)
    preset = track.get("preset", config.get("defaults", {}).get("preset"))
    audio = track.get("audio", None)

    cmd = ["HandBrakeCLI"]
    if mkv_file:
        cmd.extend(["-i", str(mkv_file)])
    # Title not required for single mkv file
    #if title:
    #    cmd.extend(["-t", str(title)])
    if preset:
        cmd.extend(["--preset-import-gui", "-Z", preset])
    if audio:
        cmd.extend(audiopts.audio_options(audio))
    cmd.extend(["--subtitle", "none"])
    if dest:
        cmd.extend(["-o", str(dest)])

    return cmd

def get_subtitles(mkv_file):
    subtitles = []
    cmd = ["mediainfo", "--Output=JSON", mkv_file]
    out = subprocess.run(cmd, capture_output=True, text=True)
    info = json.loads(out.stdout)
    for track in info["media"]["track"]:
        if track["@type"] == "Text":
            subtitles.append((
                int(track.get("ID")) -1,
                track.get("Format"),
                track.get("Language"),))

    return subtitles

def do_post_subtitles(dest, config, track, mkv_file):
    subtitle_dir = config.get("subtitledest")
    if not isinstance(subtitle_dir, str) or not subtitle_dir.strip():
        print("Error! Set subtitledest in the YAML configuration")
        return 1
    subtitle = track.get("subtitle", None)
    subtitlenum = track.get("subtitlenum", None)
    # Add .mkv so that with_suffix replaces the right thing
    subtitle_file = f"{dest.stem}.{subtitle}.mkv" 
    
    print(f"{mkv_file} -> {subtitle_file}")

    if (not mkv_file.is_file()) or mkv_file.stat().st_size <= 0:
        print("Error! Subtitle mkv not found!")
        return

    sub_tracks = get_subtitles(mkv_file)

    for sub_track in sub_tracks:
        (subidx, subtype, sublang) = sub_track
        if ((subtitlenum is not None and subidx == subtitlenum) or
            (subtitlenum is None and sublang == subtitle)):
            if "PGS" in subtype:
                ext = ".sup"
            elif "VobSub" in subtype:
                ext = ".sub"
            else:
                print("Error! Unknown subtype")
                return

            dest = Path(subtitle_dir).expanduser() / subtitle_file
            dest = dest.with_suffix(ext)
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            print(f"Found {sublang} subtitles with stream id {subidx}")
            cmd = ["mkvextract", "tracks", str(mkv_file), f"{subidx}:{dest}"]

            res = run_command(cmd)

            return res

def run_command(cmd):
    print(shlex.join(cmd))
    res = subprocess.run(cmd)
    return res.returncode

def rip_track(dest, config, track, phases):
    category = track.get("category", "")
    main_title = config.get("title", "")
    temp_dir = Path(config.get("dest", "")) / (main_title + "Temp")
    
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    exitcode = run_command(build_makemkv_command(temp_dir, config, track))
    if exitcode != 0:
        print("Failed to rip mkv file")
        return
    
    # Where the output from the above should have landed
    mkv_file = temp_dir / track.get("mkv", "")
    if not mkv_file.is_file() or mkv_file.stat().st_size == 0:
        print("Error! Failed to extact mkv_file!")
        return "MKV extract failed"

    status = []
    
    if should_run_main_rip(category, phases):
        exitcode = run_command(build_handbrake_command(dest, config, track, mkv_file))
        if exitcode == 0:
            status.append("encoding success")
        else:
            status.append("encoding failed")
        
    if should_extract_subtitles(track, phases):
        exitcode = do_post_subtitles(dest, config, track, mkv_file)
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
            summaries[track.get("title")] = "skipped"
            continue

        try:
            path = get_output_path(config, track)
        except ValueError as err:
            print(f"error: {err}")
            summaries[track.get("title")] = "Failed to set path"
            continue

        print(f"Ripping track to {path}")
        result = rip_track(path, config, track, phases)
        summaries[track.get("title")] = result

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
