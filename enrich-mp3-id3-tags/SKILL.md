---
name: enrich-mp3-id3-tags
description: Match MP3 files to their correct releases and embed portable artist, title, album, track, year, genre, provenance, and front-cover ID3 metadata. Use for untagged or poorly tagged music libraries; do not use for filename-only cleanup or assume a search engine's first result is correct.
---

# Enrich MP3 ID3 Tags

Given a user-supplied directory of MP3 files, enrich their ID3 tags and rename
each successfully matched file to its song title only. Artist information belongs
in `TPE1`/album-artist ID3 tags, not in the filename. Do not change audio streams.
Treat filenames and existing tags as search clues, not authoritative metadata.

## Build a reviewable plan

Inventory the input directory first. Record file count, existing tag coverage,
audio duration, and the artist/title interpretation of each file. Prefer useful
existing `TPE1` and `TIT2` values; otherwise interpret an `Artist - Title`
filename. If neither provides a reliable match, hold the file for review.

Use `scripts/apply_metadata.py` when its dependencies (`requests`, `mutagen`,
and Pillow) are available:

```bash
python3 scripts/apply_metadata.py plan <audio-directory> \
  --output <metadata-plan.json> --country US
```

The planner queries the public Apple iTunes Search API, scores artist/title and
duration agreement, penalizes likely compilations and unintended alternate
versions, and records the top candidates. Its score is a shortlist signal, not
proof. Review every unresolved record and audit all automatically approved
records by album group before changing files. Also review the planned title-only
output names and resolve duplicate titles before applying anything.

Prefer release evidence in this order:

1. An exact official catalog match with compatible title, artist, duration,
   track position, and release context.
2. MusicBrainz release/recording data with Cover Art Archive front art.
3. An official artist, label, Bandcamp, SoundCloud, or YouTube release page.

Use secondary pages only to corroborate ambiguous facts. Do not attach artwork
merely because it depicts the artist. Match the specific release. Prefer the
original studio album over compilations, deluxe editions, remasters, or singles
only when the audio is the same recording. Preserve the alternate edition when
duration or other evidence identifies an edit, remix, exclusive, live, or
acoustic version.

For manual resolutions, edit the plan's `selected` object with title, artist,
album, album artist, year, track/disc numbers and counts, genre, artwork URL,
source URL, and source identifiers. Set `approved` to true only after reviewing
the evidence. Keep a short `review_note` for non-obvious decisions. The apply
command refuses to run while any record is unresolved.

## Apply portable tags

Once the whole plan is approved, run:

```bash
python3 scripts/apply_metadata.py apply <metadata-plan.json>
```

This writes ID3v2.3 tags for broad standalone-player compatibility. It embeds
title (`TIT2`), artist (`TPE1`), album artist (`TPE2`), album (`TALB`), year,
track/disc positions, genre, ISRC when available, source provenance, and an
`APIC` front cover. Artwork is converted to a non-progressive RGB JPEG no
larger than 600×600. After every file is tagged, it renames it to
`<ID3 title>.mp3`, removing any artist prefix. It refuses duplicate destination
names or an existing unrelated destination; resolve those in the plan before
retrying. The script leaves audio frames alone.

Do not apply a plan to a different directory or a changed collection without
rebuilding and reviewing it. If files already contain useful tags, inspect the
proposed overwrite and preserve data the user wants to keep.

## Verify before reporting success

Run:

```bash
python3 scripts/apply_metadata.py verify <metadata-plan.json>
```

Also confirm that every target has the planned title-only filename and is
readable as MP3, the tag version is `(2, 3, 0)`, required text frames exist,
the ID3 title and artist match the plan, every embedded picture decodes, and
each audio duration still matches the pre-write plan. Report unresolved or
questionable matches explicitly; never hide them behind a completion count.
