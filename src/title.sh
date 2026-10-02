#!/bin/bash

# Ensure an argument was passed to the terminal
if [ -z "$1" ]; then
    echo "Usage: $0 <track_number | mpls_filename>" >&2
    exit 1
fi

# Convert the search target to lowercase instantly to normalize the search input
TARGET=$(echo "$1" | tr '[:upper:]' '[:lower:]')

# Read the raw scan log from stdin, extract the hidden JSON, and filter via jq
awk '
found { print; next }
/^JSON Title Set:/ { found = 1; sub(/^JSON Title Set:[[:space:]]*/, ""); if (length) print }
' | jq -c --arg target "$TARGET" '
  # Helper function to pad single digit times to standard 00:00:00 layout
  def pad2: floor | tostring | if length < 2 then "0" + . else . end;

  # Walk through the master Title list
  .TitleList[] 
  # Strict type-checking rules protect the string engine from dropping an explode crash
  | select(
      (.Index | tostring) == $target or 
      (.Playlist | type == "string" and (.Playlist | ascii_downcase) == $target)
    )
  | ( (.Duration.Hours // 0) * 3600 + (.Duration.Minutes // 0) * 60 + (.Duration.Seconds // 0) ) as $total 

  | ( (($total / 3600) | pad2) + ":" + ((($total % 3600) / 60) | pad2) + ":" + (($total % 60) | pad2) ) as $duration
  | {
      title: .Index,
      mpls: .Playlist,
      duration: $duration,
      format: (
        ((.Geometry.Width * .Geometry.PAR.Num / .Geometry.PAR.Den)
          / .Geometry.Height) as $dar
        |
        if (($dar - 1.333333) | fabs) < 0.05 then "4x3"
        elif (($dar - 1.777778) | fabs) < 0.05 then "widescreen"
        else ($dar | tostring)
        end
      ),
      resolution: "\(.Geometry.Width // 0)x\(.Geometry.Height // 0)",
      chapters: (.ChapterList | length),
      audio: [
        .AudioList[]? | "Track \(.TrackNumber) [\(.LanguageCode // "und")]: \(.ChannelTitle // "Unknown") \(.Description // "")"
      ],
      subtitles: [
        .SubtitleList[]? | "Track \(.TrackNumber) [\(.LanguageCode // "und")]: \(.Description // "")"
      ]
    }
'
