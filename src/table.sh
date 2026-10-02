#!/bin/bash

awk '
    found { print; next }

    /^JSON Title Set:/ {
        found = 1
        sub(/^JSON Title Set:[[:space:]]*/, "")
        if (length) print
    }
' |
jq -r '
  def pad2:
    floor
    | tostring
    | if length < 2 then "0" + . else . end;
  (
    [
      "TITLE",
      "MPLS",
      "DURATION",
      "CHAP",
      "AUDIO",
      "SUBS",
      "WIDTH",
      "HEIGHT",
      "LANG"
    ],
  (
    .TitleList[]
    | (
        (.Duration.Hours   // 0) * 3600 +
        (.Duration.Minutes // 0) * 60 +
        (.Duration.Seconds // 0)
      ) as $total
    | (
        (($total / 3600) | pad2) + ":" +
        ((($total % 3600) / 60) | pad2) + ":" +
        (($total % 60) | pad2)
      ) as $duration
    | [
        .Index,
        .Playlist,
        $duration,
        (.ChapterList | length),
        (.AudioList | length),
        (.SubtitleList | length),
        (.Geometry.Width // 0),
        (.Geometry.Height // 0),
        (
          [.AudioList[]?.LanguageCode]
          | map(select(. != null))
          | unique
          | join(",")
        )
      ]))
  | @tsv
'
