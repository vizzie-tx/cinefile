# CineFile: Scripts for archiving and filing movies

CineFile is a collection of personal scripts for archiving movies from discs
and organizing them for a Jellyfin library.

This is an early release of tools developed for the author's workflow.
Configuration files require manual editing, and error handling is still
incomplete. The scripts are intended for a Linux command-line environment.

## Requirements

Install the dependencies for the scripts you plan to use. External commands
must be available on your `PATH`, and Python packages must be available to the
`python3` interpreter used by the scripts.

| Component | Required by |
| --- | --- |
| Python (developed with 3.14) | All Python scripts; `mkvdiscinfo.py` uses syntax requiring Python 3.12 or newer |
| PyYAML | `ripit.py`, `mkvripit.py`, `filemovies` |
| requests | `filemovies` |
| HandBrakeCLI | `ripit.py`, `mkvripit.py` |
| MakeMKV (`makemkvcon`) | `mkvripit.py`, `mkvdiscinfo.py` |
| MediaInfo (`mediainfo`) | `mkvripit.py` subtitle extraction |
| MKVToolNix (`mkvextract`, `mkvmerge`) | Subtitle processing (`mkvripit.py` uses `mkvextract`; `ripit.py` uses both) |
| Bash, awk, jq | `table.sh`, `title.sh` |

## Installation

Copy the contents of `src` to a directory on your `PATH`. Keep `audiopts.py`
beside `ripit.py` and `mkvripit.py`, which import it as a library.

## Scripts

### ripit.py, mkvripit.py

These YAML-driven scripts produce MP4 files and extract VobSub or PGS subtitles
into separate files. `ripit.py` uses HandBrakeCLI directly. `mkvripit.py` first
extracts MKV files with MakeMKV, then converts them with HandBrakeCLI.

### mkvdiscinfo.py

Scans a source with MakeMKV and prints a table of titles and tracks by default.
Use `--json` for the parsed scan data or `--template` for a starter YAML file.
Source arguments are passed to `makemkvcon info`.

### audiopts.py

Converts a compact audio-track specification into HandBrakeCLI options. For
example:

```bash
audiopts.py '1:stereomix,2:dc'
```

The track-type definitions in the script can be extended for other audio
configurations.

### filemovies

Looks up movie filenames using The Movie Database (TMDB), then moves and renames
files into a Jellyfin-compatible directory structure. Ambiguous searches display
a menu for selecting a match.

### table.sh, title.sh

Read HandBrakeCLI scan output containing a `JSON Title Set:` marker from standard
input. `table.sh` produces a table; `title.sh` selects a title by number or MPLS
filename and produces JSON. See the current playlist-filter limitation below.

## Ripping workflow

Start with a copy of [config/template.yml](config/template.yml), or generate a
MakeMKV-based template:

```bash
mkvdiscinfo.py --template disc:0 > movie.yml
# Edit movie.yml before running:
mkvripit.py movie.yml
```

For the direct HandBrake workflow, edit a copy of the static template and run:

```bash
ripit.py movie.yml
```

Templates are starting points, not ready-to-rip configurations. Fill in required
fields, remove unwanted tracks, and fill in or remove optional blank fields.
A blank YAML value becomes null; it does not inherit a default. In particular,
remove blank track-level `audio:` entries to use `defaults.audio`, and remove
blank `name:` entries to use the generated filename fallback.

| Setting | Meaning |
| --- | --- |
| `title` | Movie name used for output filenames and directories |
| `location` | Source accepted by the selected backend: HandBrakeCLI for `ripit.py`, MakeMKV for `mkvripit.py` |
| `dest` | Directory for video output |
| `subtitledest` | Directory for extracted subtitles; required when extracting subtitles |
| `defaults` | Track settings such as `preset` and `audio`, overridden by individual track entries |
| `tracks` | List of titles to process |

Each track needs a backend-appropriate `title` number and a `category` of
`feature`, `extras`, or `trailers`. An optional `name` controls its output name.
For `mkvripit.py`, each track also needs `mkv`, the filename produced by MakeMKV;
the generated template includes this field, but the static template does not.
`mpls` and `runtime` are reference information, not inputs used to select a title.

The sample preset is `General/Fast 1080p30`. Set `subtitle` to the desired language
when extracting subtitles, or remove it to disable subtitle extraction for that
track. In `ripit.py`, `subtitlenum` selects the HandBrake subtitle track (default:
1), and `subtitle` labels the output. In `mkvripit.py`, `subtitlenum` selects the
extraction track index; when omitted, the script matches the subtitle language.

Both ripping scripts accept `-p` followed by any combination of these letters:

| Letter | Enables |
| --- | --- |
| `m` | Feature video encoding |
| `s` | Subtitle extraction for selected tracks with a `subtitle` setting |
| `e` | Extras processing |
| `t` | Trailers processing |

All four are enabled by default (`-p mset`). For example, `ripit.py -p m movie.yml`
encodes the feature without extracting subtitles or processing extras and trailers.
Disabling `m` does not disable encoding of selected extras or trailers.
`mkvripit.py` still runs MakeMKV for selected tracks when feature encoding is
disabled; it does not simply reuse an existing MKV file.

## Filing movies

Copy [config/filemoviesrc](config/filemoviesrc) to one of the following locations.
The first existing file in this order is used:

1. `~/.filemoviesrc`
2. `~/filemoviesrc`
3. `filemoviesrc` beside the installed script

Set `destination` to the movie library directory and `tmbdurl` to the TMDB movie
search URL. Preserve the spelling `tmbdurl` used in the sample. Both settings are
required. Put your TMDB bearer token alone in `~/.tmdbtoken`.

Preview the moves, then run without `--dry-run` to apply them:

```bash
filemovies --dry-run --input /movies/incoming
filemovies --input /movies/incoming
```

`--output` overrides the configured destination. If `--input` is omitted, the
output directory is also used as the input directory. Only direct children are
considered; the script does not recursively scan the input tree. Normal execution
moves files and refuses to overwrite an existing destination.

## Known limitations

- Configuration validation and error handling are incomplete. Templates require
  manual editing before use, and invalid values can produce tracebacks.
- `title.sh` currently has a playlist-filter bug that can cause jq errors for MPLS
  searches and when a numeric search encounters a different title.
- `filemovies` does not currently recognize `.sup` subtitles, although the ripping
  scripts can produce them. Those files are skipped and need separate handling.
- Subtitle files and extras are only filed when the destination movie directory
  already exists. Input ordering can therefore leave them for a later run.
