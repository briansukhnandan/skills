---
name: torrent-media-formatting
description: Clean and normalize movie or TV-show torrents in place, including media, subtitle, season, and junk-artifact handling. Use when a downloaded media directory needs library-ready names.
---

# Torrent Media Formatting

Normalize only the user-supplied torrent directory and work in place.

## Inspect first

- Recursively inventory media, subtitle, external-audio, and non-media files.
- Derive title, year, series, season, episode, and language from the release names and directory structure. Use embedded media metadata when it resolves ambiguity. If the identity, year, or episode mapping is not reliable, show the ambiguous items and ask rather than guessing.
- Before changing anything, preflight every destination for duplicate names, case-only collisions, and a file-versus-directory conflict. Preserve containers and extensions.

## Movies

- A standalone movie is `Title (Year).extension`; strip release groups, resolution, codec, source, edition tags, and site names. Example: `Back to the Future I (1985).mkv`.
- If a movie has external subtitles, place its video and subtitles in a `Title (Year)` directory. Name the video `Title (Year).extension`.
- Name a single subtitle `Title (Year).language.extension` when its language is known. For multiple revisions, use stable, human-readable labels such as `Title (Year) - English 1.srt`, `Title (Year) - English 2.srt`, and `Title (Year) - Spanish 1.srt`. Retain meaningful labels such as `SDH`.
- Do not create a folder for a movie that has no external subtitle merely because the torrent originally contained a folder. Keep the standalone video at the target root; remove empty release folders after moving it.

## TV series

- Use a clean series directory. Preserve a meaningful season/book/specials hierarchy when one exists; normalize only release-noise in its folder names. A conventional season folder is `Season N` unless the source structure has a meaningful alternate grouping such as `Book One - Water` or `Specials`.
- For episodic files with reliable numbering, name videos `Series Name S01E01 Episode Title.extension` when a title is known, otherwise `Series Name S01E01.extension`. Keep season/episode identifiers zero-padded. Name paired subtitles from the same episode base and append language/revision labels as needed.
- For any flat series release where episode files are directly in the series folder, retain that flat layout. This is common with anime but is not anime-specific. Clean publisher/resolution/hash noise and use `Series Name - 01.extension` when only an episode number is reliable. Do not invent season numbers or episode titles.
- Preserve multi-episode markers (for example, `S01E01-E02`) instead of splitting media files.

## Keep playback essentials; remove torrent junk

- Keep video files, common subtitles (`.srt`, `.ass`, `.ssa`, `.vtt`, `.sub` with its `.idx`, `.sup`), and separate audio tracks (`.mka`, `.ac3`, `.aac`, `.dts`, `.flac`). Keep any file whose purpose is uncertain and could be needed for playback.
- Delete only clear uploader artifacts: release advertisements, download notices, text files that are plainly promotional, covers/posters (`.jpg`, `.jpeg`, `.png`), `.nfo` files, and empty directories left by their removal. Do not delete user-created artwork or documentation when its purpose is unclear.
- Do not delete archives, disc structures, checksums, or nonstandard companions without first explaining why they are unnecessary and getting confirmation.

## Execute and verify

- When the user asks to format the supplied directory, that authorizes the scoped in-place renames and removal of clear torrent junk. Keep a concise record of moves and removals while working.
- Use collision-safe renames. Do not overwrite an existing file; stop and ask how to resolve a collision.
- Afterward, list the retained playable files and subtitles, check that subtitle files have a corresponding video, and report any uncertain files left untouched.
