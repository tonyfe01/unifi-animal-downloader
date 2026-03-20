#!/usr/bin/env python3
"""
UniFi Protect Animal Footage Downloader

Downloads historical video clips of animal detection events from a
UniFi Protect NVR. Supports filtering by date range, camera, and
animal type.

Requires: Python 3.10+, UniFi Protect firmware v6.0+
Install:  pip install -r requirements.txt
Setup:    cp .env.example .env  (then fill in your NVR credentials)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from uiprotect import ProtectApiClient
from uiprotect.data import Camera, Event, SmartDetectObjectType

# Animal-related smart detection types
ANIMAL_TYPES: set[SmartDetectObjectType] = {
    SmartDetectObjectType.ANIMAL,
    SmartDetectObjectType.PET,
}

# Human-readable labels for display
ANIMAL_TYPE_LABELS: dict[str, str] = {
    "animal": "Animal",
    "pet": "Pet",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download animal detection footage from UniFi Protect",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s                              # Last 24 hours, all cameras
  %(prog)s --start 2026-03-01           # Since March 1st
  %(prog)s --start 2026-03-01 --end 2026-03-15
  %(prog)s --camera "Backyard"          # Specific camera only
  %(prog)s --list-cameras               # Show available cameras
  %(prog)s --dry-run                    # Preview without downloading
  %(prog)s --days 7                     # Last 7 days
        """,
    )

    parser.add_argument(
        "--host",
        default=os.getenv("PROTECT_HOST"),
        help="NVR IP address (or set PROTECT_HOST in .env)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PROTECT_PORT", "443")),
        help="NVR port (default: 443)",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("PROTECT_USERNAME"),
        help="NVR username (or set PROTECT_USERNAME in .env)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("PROTECT_PASSWORD"),
        help="NVR password (or set PROTECT_PASSWORD in .env)",
    )

    parser.add_argument(
        "--list-cameras",
        action="store_true",
        help="List available cameras and exit",
    )
    parser.add_argument(
        "--camera",
        help="Filter events to a specific camera (by name, case-insensitive)",
    )

    time_group = parser.add_argument_group("time range")
    time_group.add_argument(
        "--start",
        help="Start date (YYYY-MM-DD or YYYY-MM-DD HH:MM)",
    )
    time_group.add_argument(
        "--end",
        help="End date (YYYY-MM-DD or YYYY-MM-DD HH:MM, default: now)",
    )
    time_group.add_argument(
        "--days",
        type=int,
        default=1,
        help="Look back N days from now (default: 1, ignored if --start is set)",
    )

    parser.add_argument(
        "--output-dir",
        default="./downloads",
        help="Output directory (default: ./downloads)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without downloading",
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Re-download files even if they already exist",
    )

    return parser.parse_args()


def parse_datetime(value: str) -> datetime:
    """Parse a date or datetime string into a timezone-aware datetime."""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(
        f"Invalid date format: '{value}'. Use YYYY-MM-DD or YYYY-MM-DD HH:MM"
    )


def get_time_range(args: argparse.Namespace) -> tuple[datetime, datetime]:
    """Determine the start and end times from CLI arguments."""
    now = datetime.now(tz=timezone.utc)

    if args.start:
        start = parse_datetime(args.start)
    else:
        start = now - timedelta(days=args.days)

    if args.end:
        end = parse_datetime(args.end)
    else:
        end = now

    if start >= end:
        print(f"Error: start ({start}) must be before end ({end})")
        sys.exit(1)

    return start, end


def make_filename(event: Event, camera: Camera | None) -> str:
    """Build a human-readable filename for an event clip."""
    ts = event.start.strftime("%Y-%m-%d_%H-%M-%S")
    types = "_".join(
        sorted(t.value for t in (event.smart_detect_types or []) if t in ANIMAL_TYPES)
    )
    if not types:
        types = "animal"
    return f"{ts}_{types}.mp4"


def make_output_path(
    base_dir: Path, event: Event, camera: Camera | None
) -> Path:
    """Build the full output path: base_dir/camera_name/date/filename."""
    cam_name = (camera.name if camera else "unknown_camera").replace("/", "_").replace(" ", "_")
    date_dir = event.start.strftime("%Y-%m-%d")
    filename = make_filename(event, camera)
    return base_dir / cam_name / date_dir / filename


async def connect_nvr(args: argparse.Namespace) -> ProtectApiClient:
    """Connect to the UniFi Protect NVR."""
    if not args.host:
        print("Error: NVR host is required. Set PROTECT_HOST in .env or use --host")
        sys.exit(1)
    if not args.username or not args.password:
        print("Error: Username and password are required. Set them in .env or use --username / --password")
        sys.exit(1)

    print(f"Connecting to NVR at {args.host}:{args.port}...")

    api = ProtectApiClient(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        verify_ssl=False,
    )

    try:
        await api.update()
    except Exception as e:
        print(f"Error: Could not connect to NVR: {e}")
        sys.exit(1)

    nvr = api.bootstrap.nvr
    print(f"Connected to: {nvr.name} (firmware {nvr.version})")
    return api


async def list_cameras(api: ProtectApiClient) -> None:
    """Print all cameras the user has access to."""
    cameras = api.bootstrap.cameras
    if not cameras:
        print("No cameras found.")
        return

    print(f"\nFound {len(cameras)} camera(s):\n")
    print(f"  {'Name':<30} {'ID':<26} {'Model':<20} {'Smart Detect Types'}")
    print(f"  {'-'*30} {'-'*26} {'-'*20} {'-'*30}")
    for cam in sorted(cameras.values(), key=lambda c: c.name):
        detect_types = ", ".join(t.value for t in (cam.feature_flags.smart_detect_types or []))
        print(f"  {cam.name:<30} {cam.id:<26} {cam.type:<20} {detect_types}")


def find_camera_by_name(
    cameras: dict[str, Camera], name: str
) -> Camera | None:
    """Find a camera by name (case-insensitive partial match)."""
    name_lower = name.lower()
    for cam in cameras.values():
        if name_lower in cam.name.lower():
            return cam
    return None


async def get_animal_events(
    api: ProtectApiClient,
    start: datetime,
    end: datetime,
    camera_id: str | None = None,
) -> list[Event]:
    """Query the NVR for animal smart detection events."""
    events = await api.get_events(
        start=start,
        end=end,
        smart_detect_types=list(ANIMAL_TYPES),
    )

    # Filter to specific camera if requested
    if camera_id:
        events = [e for e in events if e.camera_id == camera_id]

    return events


async def download_event_clip(
    api: ProtectApiClient,
    event: Event,
    output_path: Path,
) -> bool:
    """Download the video clip for a single event. Returns True on success."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        await api.get_camera_video(
            camera_id=event.camera_id,
            start=event.start,
            end=event.end,
            output_file=output_path,
        )
        return True
    except Exception as e:
        # Retry once
        try:
            await api.get_camera_video(
                camera_id=event.camera_id,
                start=event.start,
                end=event.end,
                output_file=output_path,
            )
            return True
        except Exception:
            print(f"    ⚠ Failed to download: {e}")
            # Clean up partial file
            if output_path.exists():
                output_path.unlink()
            return False


async def main() -> None:
    load_dotenv()
    args = parse_args()

    api = await connect_nvr(args)

    try:
        # --list-cameras mode
        if args.list_cameras:
            await list_cameras(api)
            return

        cameras = api.bootstrap.cameras

        # Resolve camera filter
        camera_id: str | None = None
        if args.camera:
            cam = find_camera_by_name(cameras, args.camera)
            if not cam:
                print(f"Error: No camera matching '{args.camera}' found.")
                print("Use --list-cameras to see available cameras.")
                sys.exit(1)
            camera_id = cam.id
            print(f"Filtering to camera: {cam.name}")

        # Determine time range
        start, end = get_time_range(args)
        print(f"Searching for animal events from {start:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M} UTC...")

        # Query events
        events = await get_animal_events(api, start, end, camera_id)

        if not events:
            print("\nNo animal detection events found for the given criteria.")
            return

        # Summarize findings
        type_counts: dict[str, int] = {}
        cam_counts: dict[str, int] = {}
        for ev in events:
            for t in (ev.smart_detect_types or []):
                if t in ANIMAL_TYPES:
                    label = ANIMAL_TYPE_LABELS.get(t.value, t.value)
                    type_counts[label] = type_counts.get(label, 0) + 1
            cam = cameras.get(ev.camera_id)
            cam_name = cam.name if cam else "Unknown"
            cam_counts[cam_name] = cam_counts.get(cam_name, 0) + 1

        print(f"\nFound {len(events)} animal event(s):")
        for label, count in sorted(type_counts.items()):
            print(f"  {label}: {count}")
        for cam_name, count in sorted(cam_counts.items()):
            print(f"  📷 {cam_name}: {count} event(s)")

        if args.dry_run:
            print("\n[DRY RUN] Would download the following clips:\n")
            for i, ev in enumerate(events, 1):
                cam = cameras.get(ev.camera_id)
                path = make_output_path(Path(args.output_dir), ev, cam)
                duration = (ev.end - ev.start).total_seconds()
                types_str = ", ".join(t.value for t in (ev.smart_detect_types or []) if t in ANIMAL_TYPES)
                print(f"  {i:>4}. {path}")
                print(f"        {ev.start:%Y-%m-%d %H:%M:%S} ({duration:.0f}s) [{types_str}]")
            return

        # Download clips
        output_dir = Path(args.output_dir)
        print(f"\nDownloading {len(events)} clip(s) to {output_dir}/...\n")

        downloaded = 0
        skipped = 0
        failed = 0

        for i, ev in enumerate(events, 1):
            cam = cameras.get(ev.camera_id)
            path = make_output_path(output_dir, ev, cam)
            cam_name = cam.name if cam else "Unknown"
            duration = (ev.end - ev.start).total_seconds()
            types_str = ", ".join(t.value for t in (ev.smart_detect_types or []) if t in ANIMAL_TYPES)

            # Skip existing
            if path.exists() and not args.no_skip:
                size_mb = path.stat().st_size / (1024 * 1024)
                print(f"  [{i}/{len(events)}] ⏭ Already exists ({size_mb:.1f} MB): {path.name}")
                skipped += 1
                continue

            print(f"  [{i}/{len(events)}] ⬇ {cam_name} | {ev.start:%H:%M:%S} ({duration:.0f}s) [{types_str}]")

            success = await download_event_clip(api, ev, path)
            if success:
                size_mb = path.stat().st_size / (1024 * 1024)
                print(f"           ✅ Saved ({size_mb:.1f} MB): {path.name}")
                downloaded += 1
            else:
                failed += 1

        # Summary
        print(f"\nDone! Downloaded: {downloaded}, Skipped: {skipped}, Failed: {failed}")
        if downloaded > 0:
            print(f"Files saved to: {output_dir.resolve()}")

    finally:
        await api.async_disconnect()


if __name__ == "__main__":
    asyncio.run(main())
