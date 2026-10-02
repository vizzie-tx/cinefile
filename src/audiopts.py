#!/usr/bin/env python3

import shlex

TRACKTYPES = {
    "dts":       ("auto",   "copy:dts",   "auto", "DTS 5.1 Surround"),
    "dtshd":     ("auto",   "copy:dtshd", "auto", "DTS-HD MA 5.1"),
    "dd":        ("auto",   "copy:ac3",   "auto", "Dolby Digital 5.1 Surround"),
    "dpl":       ("auto",   "copy:ac3",   "auto", "Dolby Pro Logic II"),
    "stereo":    ("auto",   "copy:ac3",   "auto", "Stereo"),
    "stereomix": ("stereo", "av_aac",     "160",  "Stereo Mixdown"),
    "mono":      ("mono",   "av_aac",     "128",  "Mono"),
    "dc":        ("stereo", "av_aac",     "128",  "Director's Commentary"),
}


def audio_options(spec: str) -> list[str]:
    tracks: list[str] = []
    encoders: list[str] = []
    bitrates: list[str] = []
    mixdowns: list[str] = []
    names: list[str] = []

    for item in spec.split(","):
        track, sep, remainder = item.strip().partition(":")
        track_type, _, track_name = remainder.partition(":")

        if not sep or not track or not track_type:
            raise ValueError(f"Invalid audio specification: {item!r}")

        mixdown, encoder, bitrate, name = TRACKTYPES[track_type]
        if track_name:
            name = track_name

        tracks.append(track)
        encoders.append(encoder)
        bitrates.append(bitrate)
        mixdowns.append(mixdown)
        names.append(name)

    return [
        "-a", ",".join(tracks),
        "-E", ",".join(encoders),
        "-B", ",".join(bitrates),
        "-6", ",".join(mixdowns),
        "-A", ",".join(names),
    ]


def main() -> None:
    import sys

    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {sys.argv[0]} TRACK:TYPE[,TRACK:TYPE...]")

    print(shlex.join(audio_options(sys.argv[1])))


if __name__ == "__main__":
    main()
