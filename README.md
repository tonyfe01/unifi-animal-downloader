# 🐾 UniFi Protect Animal Footage Downloader

A Python CLI tool that downloads video clips of **animal detection events** from your UniFi Protect NVR. Perfect for reviewing wildlife activity captured by your cameras!

## What It Does

- Connects to your local UniFi Protect NVR
- Queries historical **smart detection events** filtered to animal types
- Downloads the video clips as MP4 files
- Organizes files by camera and date

## Requirements

- **Python 3.10+**
- **UniFi Protect firmware v6.0+** (for animal smart detection)
- A camera with smart detection support (G4, G5, or AI series)
- Local network access to the NVR
- NVR account credentials with camera access

## Setup

### 1. Clone / copy this folder

```bash
cd unifi-animal-downloader
```

### 2. Create a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate   # On Mac/Linux
# venv\Scripts\activate    # On Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure your NVR credentials

```bash
cp .env.example .env
```

Edit `.env` with your NVR details:

```
PROTECT_HOST=192.168.1.1       # Your NVR's IP address
PROTECT_PORT=443               # Usually 443
PROTECT_USERNAME=your-username # Your NVR login
PROTECT_PASSWORD=your-password # Your NVR password
```

> **Tip:** To find your NVR's IP, check the UniFi app or your router's device list.

## Usage

### List your cameras

```bash
python animal_downloader.py --list-cameras
```

### Download animal events (last 24 hours)

```bash
python animal_downloader.py
```

### Download from a specific date range

```bash
python animal_downloader.py --start 2026-03-01 --end 2026-03-15
```

### Download from the last 7 days

```bash
python animal_downloader.py --days 7
```

### Filter to a specific camera

```bash
python animal_downloader.py --camera "Backyard"
```

### Preview without downloading (dry run)

```bash
python animal_downloader.py --dry-run --days 3
```

### Save to a custom directory

```bash
python animal_downloader.py --output-dir ~/Videos/animals
```

## Output Structure

Downloaded clips are organized like this:

```
downloads/
├── Backyard_Camera/
│   ├── 2026-03-19/
│   │   ├── 2026-03-19_08-15-30_animal.mp4
│   │   └── 2026-03-19_14-22-10_animal.mp4
│   └── 2026-03-20/
│       └── 2026-03-20_06-45-00_animal.mp4
└── Front_Door/
    └── 2026-03-20/
        └── 2026-03-20_11-30-15_animal.mp4
```

## All Options

```
usage: animal_downloader.py [-h] [--host HOST] [--port PORT]
                            [--username USERNAME] [--password PASSWORD]
                            [--list-cameras] [--camera CAMERA]
                            [--start START] [--end END] [--days DAYS]
                            [--output-dir OUTPUT_DIR] [--dry-run] [--no-skip]

options:
  --host HOST           NVR IP address (or set PROTECT_HOST in .env)
  --port PORT           NVR port (default: 443)
  --username USERNAME   NVR username (or set PROTECT_USERNAME in .env)
  --password PASSWORD   NVR password (or set PROTECT_PASSWORD in .env)
  --list-cameras        List available cameras and exit
  --camera CAMERA       Filter events to a specific camera (by name)
  --start START         Start date (YYYY-MM-DD or YYYY-MM-DD HH:MM)
  --end END             End date (default: now)
  --days DAYS           Look back N days (default: 1)
  --output-dir DIR      Output directory (default: ./downloads)
  --dry-run             Show what would be downloaded without downloading
  --no-skip             Re-download files even if they already exist
```

## Troubleshooting

### "Could not connect to NVR"
- Check that the NVR IP address is correct and reachable (`ping 192.168.1.1`)
- Make sure you're on the same local network as the NVR
- Verify your username and password work in the UniFi Protect web UI

### "No animal detection events found"
- Make sure your camera supports smart detection (G4/G5/AI series)
- Check that animal detection is **enabled** in UniFi Protect settings for that camera
- Try a wider date range with `--days 7` or `--days 30`

### "SSL certificate" warnings
- This is normal — the tool disables SSL verification since NVRs use self-signed certificates

### Large downloads are slow
- Video clips are downloaded directly from the NVR over your local network
- Very long events produce larger files — this is expected
- The tool downloads one clip at a time to avoid overloading the NVR

## How It Works

1. **Connects** to your NVR using the `uiprotect` Python library
2. **Queries** the events API with `smart_detect_types=["animal", "pet"]`
3. **Filters** by your specified camera and date range
4. **Downloads** the video clip for each event using the NVR's recording API
5. **Saves** files in an organized folder structure

## Credits

Built with [uiprotect](https://github.com/uilibs/uiprotect) — an unofficial Python API for UniFi Protect.
