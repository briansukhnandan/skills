---
name: ps1-to-psp-pop-fe
description: "Build PSP EBOOT.PBP packages from user-provided PlayStation 1 BIN/CUE game images with pop-fe, including ordered multi-disc games."
---

# PS1 to PSP with pop-fe

Convert user-provided PS1 disc images to a PSP-compatible `EBOOT.PBP`. Use
pop-fe; do not substitute another converter unless the user directs it.

## Resolve pop-fe

Use an explicitly supplied pop-fe directory first; otherwise use `$POP_FE_DIR`.
The chosen directory must contain `pop-fe.py`. Run the build from that
directory because pop-fe uses repository-relative resources.

If neither source resolves to a usable directory, stop safely. Tell the user
to provide the directory or set, for example,

```bash
export POP_FE_DIR=/path/to/pop-fe
```

Do not clone, install, or modify pop-fe to compensate for a missing directory.

## Inputs and destination

- Accept one game directory or ordered game directories for a multi-disc game.
- Use the `.cue` file for every disc; do not feed a `.bin` directly. Confirm
  each cue's referenced files are present beside it before building.
- Preserve the user-supplied disc order. If the order or intended cue is
  ambiguous, ask before building.
- A cue may reference several BIN, WAV, or other track files. Leave those
  files together and pass the cue unchanged so pop-fe can retain the complete
  disc layout.
- Honor an explicit output directory. Otherwise create a sibling of the first
  input directory named `<clean game name> (PS1)`. Derive the clean name by
  removing only clear trailing region, language, revision, and disc labels;
  ask if the name remains ambiguous.
- Never overwrite an existing `EBOOT.PBP` or delete an existing output
  directory to make room.

## Build and verify

1. Create the destination directory before invoking pop-fe; pop-fe does not
   create a missing destination parent.
2. Run `python3 pop-fe.py --psp-dir <destination> <cue-1> [<cue-2> ...]` from
   the resolved pop-fe directory. Pass every ordered disc cue in one command.
3. On success, pop-fe normally writes `<destination>/<game-id>/EBOOT.PBP`.
   Move the produced package files, including `EBOOT.PBP` and any companion
   `DOCUMENT.DAT` or memory-card files, into the destination root. Remove the
   game-ID directory only if it is empty. The final path is
   `<destination>/EBOOT.PBP`.
4. Verify that the final PBP exists and is non-empty. Report its path, size,
   detected primary game ID, and whether optional artwork or manual retrieval
   failed. Manual-download failures do not prevent a playable build.

Do not claim that artwork, manuals, or a game-specific PSP config was applied
unless the pop-fe output confirms it.
