#!/usr/bin/env python3

from collections import defaultdict
import argparse
import sys
import subprocess
import json
import ast
from typing import cast

type FieldValue = int | str
type TrackInfo = dict[str, FieldValue]
type TracksById = dict[str, TrackInfo]
type TitleInfo = dict[str, FieldValue | TracksById]

ATTRIBS = [
    "unknown", "type", "name", "langCode", "language",
    "codecId", "codec", "codecDesc",
    "chapters", "duration", "discSize", "discBytes",
    "streamTypeExt", "bitrate", "channels", "angles", "sourceFile",
    "sampleRate", "sampleSize", "videoSize", "aspect",
    "framerate", "streamFlags", "date", "originalTitleId",
    "numSegments", "segments", "outputFile",
    "languageCode", "languageName",
    "treeInfo", "panelTitle", "volumeName", "orderWeight",
    "outputFormat", "outputFormatDesc",
    "seamless", "panelText", "mkvFlags", "mkvFlagsText",
    "audioLayoutName", "outputCodec", "outputConversionType",
    "outputSampleRate", "outputSampleSize", "outputChannels",
    "outputChannelLayoutName", "outputChannelLayout", "audioMixDescription",
    "comment"
]
INTFIELDS = {"chapters", "discBytes", "numSegments", "orderWeight"}

def attrForId(raw_id: str) -> str:
    attr_id = int(raw_id)
    if attr_id < len(ATTRIBS):
        return ATTRIBS[attr_id]
    return f"unknown_{attr_id}"

def parseValue(attr: str, raw_value: str) -> FieldValue:
    try:
        val: str | int = cast(str, ast.literal_eval(raw_value))
    except (SyntaxError, ValueError):
        val = raw_value

    if attr in INTFIELDS:
        try:
            return int(val)
        except (TypeError, ValueError):
            return cast(FieldValue, val)

    return cast(FieldValue, val)

def plain(obj: object) -> object:
    if isinstance(obj, dict):
        return {k: plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [plain(v) for v in obj]
    return obj

def getTracks(title: TitleInfo) -> TracksById:
    tracks = title.get("tracks")
    if tracks is None:
        tracks = {}
        title["tracks"] = tracks
    return cast(TracksById, tracks)

def displayField(title: TitleInfo, key: str) -> FieldValue | str:
    value = title.get(key)
    if isinstance(value, dict) or value is None:
        return ""
    return value

def countTracks(tracks: dict[str, TrackInfo]) -> tuple[int, int]:
    audio = 0
    subs = 0
    for value in tracks.values():
        if value.get('type') == 'Audio':
            audio += 1
        elif value.get('type') == 'Subtitles':
            subs += 1
    return (audio, subs,)

def sortedTitleItems(titles: dict[str, TitleInfo]) -> list[tuple[str, TitleInfo]]:
    return sorted(titles.items(), key=lambda item: int(item[0]))

def yamlScalar(value: FieldValue | str) -> str:
    if value == "":
        return ""
    return json.dumps(str(value))

def firstDiscTitle(titles: dict[str, TitleInfo]) -> str:
    for _, title_info in sortedTitleItems(titles):
        value = displayField(title_info, "volumeName")
        if value != "":
            return str(value)
    return ""

def printTemplate(titles: dict[str, TitleInfo]) -> None:
    print("---")
    print(f"title: {yamlScalar(firstDiscTitle(titles))}")
    print("location:")
    print("dest:")
    print("subtitledest:")
    print("defaults:")
    print('  preset: "General/Fast 1080p30"')
    print('  audio: "1:stereomix"')
    print("tracks:")
    for key, title_info in sortedTitleItems(titles):
        print(f" - title: {key}")
        print("   category:")
        print("   audio:")
        print(f"   mpls: {yamlScalar(displayField(title_info, 'sourceFile'))}")
        print("   subtitle: en")
        print(f"   runtime: {yamlScalar(displayField(title_info, 'duration'))}")
        print(f"   mkv: {yamlScalar(displayField(title_info, 'outputFile'))}")
        print("   name:")

def main(args: list[str]) -> None:
    parser = argparse.ArgumentParser(
        description="Summarize MakeMKV disc title information."
    )
    output = parser.add_mutually_exclusive_group()
    output.add_argument(
        "--table",
        action="store_true",
        help="print a compact title table (default)",
    )
    output.add_argument(
        "--json",
        action="store_true",
        help="print the parsed MakeMKV title/track data as pretty JSON",
    )
    output.add_argument(
        "--template",
        action="store_true",
        help="print a starter YAML ingestion template",
    )
    parser.add_argument("source", nargs="*", help="arguments passed to makemkvcon info")
    parsed = parser.parse_args(args)

    cmd = ["makemkvcon", "-r", "--minlength=0", "info"]
    cmd.extend(parsed.source)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, end="", file=sys.stderr)
        raise SystemExit(result.returncode)

    titles: dict[str, TitleInfo] = defaultdict(dict)
    
    for line in result.stdout.splitlines():
        if line.startswith("TINFO:"):
            (title, id, _, raw_value) = line.removeprefix("TINFO:").split(",", 3)
            attr = attrForId(id)
            titles[title][attr] = parseValue(attr, raw_value)
        elif line.startswith("SINFO:"):
            (title, track, id, _, raw_value) = line.removeprefix("SINFO:").split(",", 4)
            attr = attrForId(id)
            tracks = getTracks(titles[title])
            tracks.setdefault(track, {})[attr] = parseValue(attr, raw_value)

    if parsed.json:
        json.dump(plain(titles), sys.stdout, indent=2)
        print()
        return

    if parsed.template:
        printTemplate(titles)
        return
    
    print("TITLE\tTIME\tCHAP\tAUDIO\tSUBS\tFILENAME")
    for key, title_info in sortedTitleItems(titles):
        (audio, subs) = countTracks(getTracks(title_info))
        print(
            f"{key}\t"
            f"{displayField(title_info, 'duration')}\t"
            f"{displayField(title_info, 'chapters')}\t"
            f"{audio}\t{subs}\t"
            f"{displayField(title_info, 'outputFile')}"
        )
if __name__ == '__main__':
    main(sys.argv[1:])
