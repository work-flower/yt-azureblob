# yt-azure

Download YouTube videos (full or partial) and upload to Azure Blob Storage. Features a web UI and CLI.

## Prerequisites

**ffmpeg** is required for partial video downloads.

```bash
# Windows (Command Prompt or PowerShell)
winget install ffmpeg

# Linux (Debian/Ubuntu)
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

**Node.js** is required for YouTube's JavaScript challenge solving.

```bash
# Windows (Command Prompt or PowerShell)
winget install OpenJS.NodeJS

# Linux (Debian/Ubuntu)
sudo apt install nodejs

# macOS
brew install node
```

## Installation

```bash
pip install yt-dlp azure-storage-blob gradio
```

Or install from setup:
```bash
pip install -e .
```

## Quick Start

```bash
# Launch web UI
python yt_azure.py

# Or use CLI
python yt_azure.py --url "https://youtube.com/watch?v=..." --start 3:07 --end 3:21
```

## Configuration

```bash
python yt_azure.py --config
```

Edit `yt-azure.json` in the same folder:

```json
{
  "azure": {
    "connection_string": "your-connection-string",
    "container_name": "my-container",
    "blob_folder": "videos/"
  },
  "download": {
    "output_path": "./downloads",
    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
  }
}
```

## Web UI

Launches at http://localhost:7860 with:
- YouTube video preview (updates with time range)
- Time input as `MM:SS` or seconds
- Optional custom filename
- Download history dropdown
- Azure upload toggle

## CLI Options

| Option | Description |
|--------|-------------|
| `--url`, `-u` | YouTube URL |
| `--start`, `-s` | Start time (e.g., `3:07` or `187`) |
| `--end`, `-e` | End time |
| `--container` | Override Azure container |
| `--blob-folder` | Override blob folder |
| `--format`, `-f` | Override video format |
| `--no-upload` | Skip Azure upload |
| `--config` | Edit configuration |
| `--show-config` | Display current config |

## Files

| File | Purpose |
|------|---------|
| `yt_azure.py` | Main script |
| `yt-azure.json` | Configuration |
| `history.json` | Download history (auto-created) |
| `yt-azure.log` | Logs (auto-created) |

## Authors

- **Aylin** — Creator
- **Claude (Anthropic)** — Co-author

## License

MIT
