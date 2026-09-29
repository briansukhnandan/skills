---
name: psx-to-psp
description: "Build PSP EBOOT.PBP packages from PlayStation 1 images, preferring pop-fe and using PSXPackager only when explicitly requested or carefully device-tested."
---

# PSX to PSP

Create PSP-compatible `EBOOT.PBP` packages from user-provided PlayStation 1
disc images. Select the converter from the input format rather than forcing
every image through one tool.

## Choose the converter

Use **pop-fe** as the first choice for PSP packages. It accepts `.cue`,
CloneCD `.ccd`, and single-track raw `.bin` or `.img` inputs. For a CCD it
creates a temporary CUE itself; for a direct BIN or IMG it creates a
single-track temporary CUE. Do not reject a valid CCD merely because it has
no separate CUE.

Prefer the original CUE whenever one is valid, since it carries the table of
contents needed for CD-audio tracks. Do not replace a valid multi-track CUE
with a direct BIN or IMG input. For ECM input, decode to a temporary raw image
beside an unchanged CUE, confirm the CUE reference now exists, and pass that
CUE to pop-fe. A direct BIN or IMG is suitable only when it is known to be a
single data track; use the CCD or CUE when the disc has additional tracks.

Use **PSXPackager** only when the user explicitly selects it or when a
pop-fe-compatible route has been exhausted and the user accepts a device test
before deployment. It supports raw IMG, BIN/CUE, ISO, CHD, supported archives,
and M3U playlists, but its EBOOTs have failed to boot on this PSP in real
tests. Do not automatically choose it merely because the input is CCD, raw
BIN, raw IMG, or ECM-restored.

If PSXPackager is explicitly chosen, prefer raw BIN/CUE or IMG to a cooked
ISO: cooked ISOs cannot preserve XA subheaders and may lose streaming audio or
FMV. PSXPackager can read standard CHD metadata directly; do not expand a CHD
merely to convert it.

Never overwrite an existing `EBOOT.PBP` or delete an existing destination to
make room. Preserve the user's disc order.

## pop-fe workflow

Resolve pop-fe from an explicitly supplied directory first; otherwise use
`$POP_FE_DIR`. The chosen directory must contain `pop-fe.py`. Run from that
directory because pop-fe uses repository-relative resources. Do not clone,
install, or modify pop-fe to compensate for a missing directory.

1. For a CUE, confirm every referenced BIN, WAV, or other track file exists
   beside it. For a CCD, keep its IMG and SUB sidecars together. For a direct
   BIN or IMG, use it only after confirming it represents one data track.
   Pass every ordered disc input in one command.
2. Create the destination directory, then run:

   ```bash
   python3 pop-fe.py --psp-dir <destination> <disc-1> [<disc-2> ...]
   ```

3. pop-fe normally writes `<destination>/<game-id>/EBOOT.PBP`. Move its
   package files, including `EBOOT.PBP` and any `DOCUMENT.DAT` or memory-card
   files, into the destination root; remove the game-ID directory only when
   it is empty.

## PSXPackager workflow

Resolve a runnable PSXPackager CLI from an explicitly supplied path or
`$PSXPACKAGER_BIN`. The source repository is expected at
`/home/brian/Git/PSXPackager`, but a source clone is not a substitute for a
built or released `psxpackager` executable. Do not silently download or
install a runtime; request direction if no runnable CLI is available.

1. Stage repaired or decompressed inputs and the output in a temporary
   directory. Do not alter the original disc files, replace a working PSP
   package, or copy the candidate to the PSP before the user approves a
   device test.
2. For a single disc, invoke:

   ```bash
   psxpackager -i <cue-or-supported-image> -o <temporary-output-directory>
   ```

   Use the default compression level unless the user selects another level.
3. For a multi-disc game, create a temporary `.m3u` listing the disc inputs
   in the user-supplied order and pass that playlist to `-i`.
4. Locate the non-empty generated `.pbp`, move it to the requested game
   directory as `EBOOT.PBP`, and retain any user-supplied embedded resources
   only when they were explicitly imported.

## Verify and report

Verify the final PBP exists, is non-empty, and starts with the PBP magic bytes
`00 50 42 50`. When copying to a PSP, compare the staged and destination
checksums before reporting success. Report the final path, size, converter,
primary game ID when detected, and any warnings that materially affect the
build. Do not claim artwork, manuals, PSP configs, or CD audio were included
unless the selected converter's output confirms it.
