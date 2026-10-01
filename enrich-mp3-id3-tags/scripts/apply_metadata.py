#!/usr/bin/env python3
"""Plan, review, and apply portable ID3 metadata to MP3 files."""

from __future__ import annotations

import argparse
import io
import json
import re
import time
import unicodedata
import uuid
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import requests
from mutagen.id3 import (
    APIC,
    COMM,
    TALB,
    TCON,
    TDRC,
    TIT2,
    TPE1,
    TPE2,
    TPOS,
    TRCK,
    TSRC,
    TXXX,
)
from mutagen.mp3 import MP3
from PIL import Image


ITUNES_SEARCH = "https://itunes.apple.com/search"
USER_AGENT = "enrich-mp3-id3-tags/1.0"
ALBUM_PENALTIES = {
    "greatest hits": 0.12,
    "best of": 0.12,
    "deluxe": 0.05,
    "expanded": 0.05,
    "anniversary": 0.05,
    "remaster": 0.04,
    "karaoke": 0.35,
    "tribute": 0.35,
    "live": 0.15,
    "single": 0.04,
}
VERSION_WORDS = ("live", "remix", "acoustic", "instrumental", "karaoke")
ARTIST_ALIASES = {
    "tupac shakur": ("2pac",),
}


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold().replace("&", " and ")
    return "".join(char for char in value if char.isalnum())


def search_title(value: str, artist: str) -> str:
    value = re.sub(rf"\s+-\s+{re.escape(artist)}\s*\([^)]*\)\s*$", "", value, flags=re.I)
    value = re.sub(r"\s+[\[(](official (audio|video)|lyrics?|hq)[\])]\s*$", "", value, flags=re.I)
    return value.strip()


def comparable_title(value: str) -> str:
    value = re.sub(
        r"\s*[\[(](official (audio|video)|lyrics?|hq|remaster(ed)?( \d{4})?)[\])]\s*$",
        "",
        value,
        flags=re.I,
    )
    value = re.sub(r"\s*[-–]\s*(remaster(ed)?( \d{4})?)\s*$", "", value, flags=re.I)
    return value.strip()


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalized(left), normalized(right)).ratio()


def artist_similarity(expected: str, actual: str) -> float:
    options = (expected, *ARTIST_ALIASES.get(expected.casefold(), ()))
    scores = []
    actual_norm = normalized(actual)
    for option in options:
        option_norm = normalized(option)
        score = similarity(option, actual)
        if option_norm and (option_norm in actual_norm or actual_norm in option_norm):
            score = max(score, 0.96)
        scores.append(score)
    return max(scores)


def score_candidate(artist: str, title: str, duration_ms: int, item: dict[str, Any]) -> tuple[float, dict[str, float]]:
    candidate_title = str(item.get("trackName", ""))
    candidate_artist = str(item.get("artistName", ""))
    title_score = similarity(comparable_title(title), comparable_title(candidate_title))
    artist_score = artist_similarity(artist, candidate_artist)
    candidate_duration = int(item.get("trackTimeMillis") or 0)
    difference = abs(duration_ms - candidate_duration) if candidate_duration else 999_999
    duration_score = max(0.0, 1.0 - difference / 20_000)
    score = 0.55 * title_score + 0.27 * artist_score + 0.18 * duration_score

    expected_lower = title.casefold()
    candidate_lower = candidate_title.casefold()
    for word in VERSION_WORDS:
        if word in candidate_lower and word not in expected_lower:
            score -= 0.12
    album_lower = str(item.get("collectionName", "")).casefold()
    for marker, penalty in ALBUM_PENALTIES.items():
        if marker in album_lower:
            score -= penalty
    return score, {
        "title": round(title_score, 4),
        "artist": round(artist_score, 4),
        "duration": round(duration_score, 4),
        "duration_difference_ms": difference,
    }


def artwork_url(item: dict[str, Any], size: int = 600) -> str:
    url = str(item.get("artworkUrl100", ""))
    return re.sub(r"/\d+x\d+bb\.", f"/{size}x{size}bb.", url)


def metadata_from_item(item: dict[str, Any]) -> dict[str, Any]:
    release_date = str(item.get("releaseDate", ""))
    return {
        "title": item.get("trackName", ""),
        "artist": item.get("artistName", ""),
        "album": item.get("collectionName", ""),
        "album_artist": item.get("collectionArtistName") or item.get("artistName", ""),
        "year": release_date[:4],
        "track_number": item.get("trackNumber"),
        "track_count": item.get("trackCount"),
        "disc_number": item.get("discNumber"),
        "disc_count": item.get("discCount"),
        "genre": item.get("primaryGenreName", ""),
        "isrc": item.get("isrc", ""),
        "copyright": item.get("copyright", ""),
        "itunes_track_id": item.get("trackId"),
        "itunes_collection_id": item.get("collectionId"),
        "artwork_url": artwork_url(item),
        "source_url": item.get("trackViewUrl", ""),
    }


def query_itunes(session: requests.Session, term: str, country: str, limit: int = 200) -> list[dict[str, Any]]:
    for attempt in range(6):
        response = session.get(
            ITUNES_SEARCH,
            params={"term": term, "entity": "song", "limit": limit, "country": country},
            timeout=30,
        )
        if response.status_code != 429:
            response.raise_for_status()
            time.sleep(0.35)
            return list(response.json().get("results", []))
        retry_after = float(response.headers.get("Retry-After", 0) or 0)
        time.sleep(max(retry_after, min(20.0, 2.0 ** attempt)))
    response.raise_for_status()
    return []


def build_plan(folder: Path, output: Path, country: str) -> None:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    records = []
    artist_cache: dict[str, list[dict[str, Any]]] = {}
    paths = sorted(folder.glob("*.mp3"), key=lambda path: path.name.casefold())
    for index, path in enumerate(paths, 1):
        existing_tags = MP3(path).tags
        existing_artist = existing_tags.get("TPE1") if existing_tags else None
        existing_title = existing_tags.get("TIT2") if existing_tags else None
        if existing_artist and existing_title:
            artist = str(existing_artist.text[0]).strip()
            title = str(existing_title.text[0]).strip()
        else:
            artist, separator, raw_title = path.stem.partition(" - ")
            if not separator:
                records.append(
                    {
                        "file": path.name,
                        "approved": False,
                        "reason": "needs existing Artist/Title tags or an Artist - Title filename",
                    }
                )
                continue
            title = search_title(raw_title, artist)
        duration_ms = round(MP3(path).info.length * 1000)
        if artist not in artist_cache:
            artist_cache[artist] = query_itunes(session, artist, country)
        candidates = artist_cache[artist]
        best_catalog_title = max(
            (similarity(comparable_title(title), comparable_title(str(item.get("trackName", "")))) for item in candidates),
            default=0.0,
        )
        if best_catalog_title < 0.76:
            candidates = candidates + query_itunes(session, f"{artist} {title}", country, limit=50)
        ranked = []
        for item in candidates:
            score, components = score_candidate(artist, title, duration_ms, item)
            ranked.append((score, components, item))
        ranked.sort(key=lambda entry: entry[0], reverse=True)
        top = ranked[:5]
        selected = metadata_from_item(top[0][2]) if top else None
        approved = bool(
            top
            and top[0][0] >= 0.82
            and top[0][1]["title"] >= 0.78
            and top[0][1]["artist"] >= 0.72
            and top[0][1]["duration"] >= 0.30
        )
        records.append(
            {
                "file": path.name,
                "output_file": title_filename(selected["title"]) + ".mp3" if selected else None,
                "parsed_artist": artist,
                "parsed_title": title,
                "duration_ms": duration_ms,
                "approved": approved,
                "score": round(top[0][0], 4) if top else None,
                "score_components": top[0][1] if top else None,
                "selected": selected,
                "candidates": [
                    {
                        "score": round(score, 4),
                        "score_components": components,
                        "metadata": metadata_from_item(item),
                    }
                    for score, components, item in top
                ],
            }
        )
        print(f"[{index:3}/{len(paths)}] {'OK' if approved else 'REVIEW':6} {path.name}", flush=True)
    payload = {
        "schema_version": 1,
        "source": "Apple iTunes Search API",
        "country": country,
        "folder": str(folder),
        "files": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    name_errors = output_name_errors(records)
    if name_errors:
        duplicate_names = {message.removeprefix("duplicate title-only filename: ") for message in name_errors}
        for record in records:
            if record.get("output_file") in duplicate_names:
                record["approved"] = False
                record["reason"] = "duplicate title-only filename"
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    approved_count = sum(bool(record.get("approved")) for record in records)
    if name_errors:
        print("Plan requires review: " + "; ".join(name_errors))
    print(f"Plan: {approved_count} approved, {len(records) - approved_count} require review -> {output}")


def number_text(number: Any, total: Any) -> str:
    if not number:
        return ""
    return f"{number}/{total}" if total else str(number)


def title_filename(title: str) -> str:
    """Return a title-only filename stem without changing ordinary punctuation."""
    name = re.sub(r"[\x00/]", " ", title).strip()
    name = re.sub(r"\s+", " ", name)
    if not name or name in {".", ".."}:
        raise ValueError(f"cannot create a filename from title {title!r}")
    return name


def output_name_errors(records: list[dict[str, Any]]) -> list[str]:
    names = [record.get("output_file") for record in records if record.get("output_file")]
    duplicates = sorted({name for name in names if names.count(name) > 1}, key=str.casefold)
    return [f"duplicate title-only filename: {name}" for name in duplicates]


def path_for_record(folder: Path, record: dict[str, Any]) -> Path:
    original = folder / record["file"]
    renamed = folder / record.get("output_file", record["file"])
    if original.exists():
        return original
    if renamed.exists():
        return renamed
    raise FileNotFoundError(f"neither planned path exists: {original.name} or {renamed.name}")


def validate_rename(folder: Path, records: list[dict[str, Any]]) -> None:
    errors = output_name_errors(records)
    if errors:
        raise SystemExit("Refusing to rename: " + "; ".join(errors))
    sources = {path_for_record(folder, record) for record in records}
    for record in records:
        source = path_for_record(folder, record)
        target = folder / record["output_file"]
        if source != target and target.exists() and target not in sources:
            raise SystemExit(f"Refusing to rename: destination already exists: {target.name}")


def rename_to_titles(folder: Path, records: list[dict[str, Any]]) -> None:
    validate_rename(folder, records)
    operations = []
    for record in records:
        source = path_for_record(folder, record)
        target = folder / record["output_file"]
        if source != target:
            temp = folder / f".id3-rename-{uuid.uuid4().hex}.mp3"
            operations.append((source, temp, target))
    try:
        for source, temp, _ in operations:
            source.rename(temp)
        for _, temp, target in operations:
            temp.rename(target)
    except Exception:
        for source, temp, target in reversed(operations):
            if target.exists() and not temp.exists():
                target.rename(temp)
            if temp.exists():
                temp.rename(source)
        raise


def prepare_cover(session: requests.Session, url: str) -> bytes:
    for attempt in range(4):
        response = session.get(url, timeout=30)
        if response.ok:
            break
        if attempt == 3:
            response.raise_for_status()
        time.sleep(1.5 * (attempt + 1))
    with Image.open(io.BytesIO(response.content)) as image:
        image = image.convert("RGB")
        image.thumbnail((600, 600), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=90, optimize=True, progressive=False)
        return output.getvalue()


def apply_plan(plan_path: Path) -> None:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    folder = Path(plan["folder"])
    unresolved = [record["file"] for record in plan["files"] if not record.get("approved") or not record.get("selected")]
    if unresolved:
        raise SystemExit("Refusing to apply: unresolved files remain:\n" + "\n".join(unresolved))
    validate_rename(folder, plan["files"])

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    cover_cache: dict[str, bytes] = {}
    for index, record in enumerate(plan["files"], 1):
        path = path_for_record(folder, record)
        metadata = record["selected"]
        cover_url = metadata["artwork_url"]
        if cover_url not in cover_cache:
            cover_cache[cover_url] = prepare_cover(session, cover_url)
        cover = cover_cache[cover_url]
        audio = MP3(path)
        if audio.tags is None:
            audio.add_tags()
        tags = audio.tags
        for frame_id in ("TIT2", "TPE1", "TPE2", "TALB", "TDRC", "TRCK", "TPOS", "TCON", "TSRC", "APIC", "COMM"):
            tags.delall(frame_id)
        for description in ("Metadata source", "iTunes Track ID", "iTunes Collection ID", "MusicBrainz Release ID"):
            tags.delall(f"TXXX:{description}")
        tags.add(TIT2(encoding=3, text=[metadata["title"]]))
        tags.add(TPE1(encoding=3, text=[metadata["artist"]]))
        tags.add(TPE2(encoding=3, text=[metadata["album_artist"]]))
        tags.add(TALB(encoding=3, text=[metadata["album"]]))
        if metadata.get("year"):
            tags.add(TDRC(encoding=3, text=[metadata["year"]]))
        track = number_text(metadata.get("track_number"), metadata.get("track_count"))
        disc = number_text(metadata.get("disc_number"), metadata.get("disc_count"))
        if track:
            tags.add(TRCK(encoding=3, text=[track]))
        if disc:
            tags.add(TPOS(encoding=3, text=[disc]))
        if metadata.get("genre"):
            tags.add(TCON(encoding=3, text=[metadata["genre"]]))
        if metadata.get("isrc"):
            tags.add(TSRC(encoding=3, text=[metadata["isrc"]]))
        source_name = metadata.get("metadata_source") or plan["source"]
        tags.add(TXXX(encoding=3, desc="Metadata source", text=[metadata.get("source_url") or source_name]))
        if metadata.get("itunes_track_id"):
            tags.add(TXXX(encoding=3, desc="iTunes Track ID", text=[str(metadata["itunes_track_id"])]))
        if metadata.get("itunes_collection_id"):
            tags.add(TXXX(encoding=3, desc="iTunes Collection ID", text=[str(metadata["itunes_collection_id"])]))
        if metadata.get("musicbrainz_release_id"):
            tags.add(TXXX(encoding=3, desc="MusicBrainz Release ID", text=[metadata["musicbrainz_release_id"]]))
        tags.add(COMM(encoding=3, lang="eng", desc="Metadata source", text=[source_name]))
        tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Front cover", data=cover))
        audio.save(v2_version=3, v1=0)
        print(f"[{index:3}/{len(plan['files'])}] TAGGED {path.name}", flush=True)
    rename_to_titles(folder, plan["files"])
    print(f"Renamed {len(plan['files'])} MP3 file(s) to title-only names.")


def verify_plan(plan_path: Path) -> None:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    folder = Path(plan["folder"])
    failures = []
    for record in plan["files"]:
        expected_name = record.get("output_file", record["file"])
        path = folder / expected_name
        try:
            if not path.exists():
                raise FileNotFoundError(f"expected title-only filename {expected_name}")
            audio = MP3(path)
            tags = audio.tags
            if not tags or tags.version != (2, 3, 0):
                failures.append(f"{path.name}: expected ID3v2.3, found {getattr(tags, 'version', None)}")
                continue
            required = ("TIT2", "TPE1", "TALB", "TPE2", "TDRC", "TRCK")
            missing = [frame for frame in required if not tags or not tags.get(frame)]
            if not tags or not tags.getall("APIC"):
                missing.append("APIC")
            if missing:
                failures.append(f"{path.name}: missing {', '.join(missing)}")
                continue
            if str(tags.get("TIT2")) != record["selected"]["title"]:
                failures.append(f"{path.name}: ID3 title does not match plan")
                continue
            if str(tags.get("TPE1")) != record["selected"]["artist"]:
                failures.append(f"{path.name}: ID3 artist does not match plan")
                continue
            for picture in tags.getall("APIC"):
                with Image.open(io.BytesIO(picture.data)) as image:
                    image.verify()
        except Exception as error:
            failures.append(f"{path.name}: {error}")
    if failures:
        raise SystemExit("Verification failed:\n" + "\n".join(failures))
    print(f"Verified {len(plan['files'])} title-only MP3 filenames with ID3v2.3 tags and decodable embedded cover art.")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("folder", type=Path)
    plan_parser.add_argument("--output", type=Path, required=True)
    plan_parser.add_argument("--country", default="US")
    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("plan", type=Path)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("plan", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "plan":
        build_plan(arguments.folder, arguments.output, arguments.country)
    elif arguments.command == "apply":
        apply_plan(arguments.plan)
    else:
        verify_plan(arguments.plan)


if __name__ == "__main__":
    main()
