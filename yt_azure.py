#!/usr/bin/env python3
"""
yt-azure: Download videos with yt-dlp and upload to Azure Blob Storage
Cross-platform CLI tool (Windows, Linux, macOS)
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    print("Error: yt-dlp not installed. Run: pip install yt-dlp")
    sys.exit(1)

try:
    from azure.storage.blob import BlobServiceClient
except ImportError:
    print("Error: azure-storage-blob not installed. Run: pip install azure-storage-blob")
    sys.exit(1)

try:
    import gradio as gr
    HAS_GRADIO = True
except ImportError:
    HAS_GRADIO = False

SCRIPT_DIR = Path(__file__).parent.resolve()


def get_config_path(custom_path=None):
    """Get config file path (defaults to same folder as script)"""
    if custom_path:
        return Path(custom_path)
    return SCRIPT_DIR / "yt-azure.json"


def resolve_path(path_str):
    """Resolve path to absolute, using script directory as base for relative paths"""
    path = Path(path_str)
    if path.is_absolute():
        return path
    return SCRIPT_DIR / path


def get_history_path():
    """Get history file path (same folder as script)"""
    return SCRIPT_DIR / "history.json"


def parse_time(time_str):
    """Parse time string (MM:SS or HH:MM:SS or seconds) to seconds"""
    if not time_str:
        return None
    
    time_str = str(time_str).strip()
    
    # Already a number
    try:
        return float(time_str)
    except ValueError:
        pass
    
    # Parse MM:SS or HH:MM:SS
    parts = time_str.split(":")
    try:
        if len(parts) == 2:
            minutes, seconds = map(float, parts)
            return minutes * 60 + seconds
        elif len(parts) == 3:
            hours, minutes, seconds = map(float, parts)
            return hours * 3600 + minutes * 60 + seconds
    except ValueError:
        pass
    
    return None


def format_time_for_filename(seconds):
    """Format seconds to MM-SS or HH-MM-SS for filename"""
    if seconds is None:
        return ""
    
    seconds = int(seconds)
    if seconds >= 3600:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}-{m:02d}-{s:02d}"
    else:
        m = seconds // 60
        s = seconds % 60
        return f"{m:02d}-{s:02d}"


def get_logs_path():
    """Get logs file path (same folder as script)"""
    return SCRIPT_DIR / "yt-azure.log"


def setup_logging():
    """Setup logging to file"""
    log_path = get_logs_path()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger("yt-azure")


logger = setup_logging()


def log(message, level="info"):
    """Log message and print to console"""
    getattr(logger, level)(message)
    print(message)


def load_history():
    """Load download history"""
    history_path = get_history_path()
    if history_path.exists():
        try:
            with open(history_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"entries": [], "position": -1}


def save_history(history):
    """Save download history"""
    history_path = get_history_path()
    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)


def add_to_history(entry):
    """Add entry to history and save"""
    history = load_history()
    history["entries"].append(entry)
    history["position"] = len(history["entries"]) - 1
    save_history(history)
    return history


def load_config(config_path=None):
    """Load config from JSON file"""
    config_file = get_config_path(config_path)
    
    default_config = {
        "azure": {
            "connection_string": "",
            "container_name": "",
            "blob_folder": ""
        },
        "download": {
            "output_path": "./downloads",
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        }
    }
    
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                saved_config = json.load(f)
                # Merge with defaults
                for key in default_config:
                    if key in saved_config:
                        default_config[key].update(saved_config[key])
                return default_config
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load config: {e}")
    
    return default_config


def save_config(config, config_path=None):
    """Save config to JSON file"""
    config_file = get_config_path(config_path)
    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)
    print(f"\n✅ Config saved to: {config_file}")


def prompt_input(prompt, default=None, secret=False):
    """Prompt user for input with optional default"""
    if default:
        display = "*" * 10 if secret and default else default
        prompt = f"{prompt} [{display}]: "
    else:
        prompt = f"{prompt}: "
    
    value = input(prompt).strip()
    return value if value else default


def configure(config_path=None):
    """Interactive config setup"""
    print("\n🔧 yt-azure Configuration\n")
    
    config = load_config(config_path)
    
    print("── Azure Settings ──")
    config["azure"]["connection_string"] = prompt_input(
        "Connection string",
        config["azure"].get("connection_string"),
        secret=True
    )
    config["azure"]["container_name"] = prompt_input(
        "Container name",
        config["azure"].get("container_name")
    )
    config["azure"]["blob_folder"] = prompt_input(
        "Blob folder (e.g., videos/subfolder)",
        config["azure"].get("blob_folder")
    )
    
    print("\n── Download Settings ──")
    config["download"]["output_path"] = prompt_input(
        "Local output path",
        config["download"].get("output_path", "./downloads")
    )
    config["download"]["format"] = prompt_input(
        "Video format",
        config["download"].get("format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best")
    )
    
    save_config(config, config_path)


def show_config(config_path=None):
    """Display current config"""
    config = load_config(config_path)
    config_file = get_config_path(config_path)
    
    print(f"\n📄 Config file: {config_file}\n")
    
    # Mask connection string
    display_config = json.loads(json.dumps(config))
    if display_config["azure"].get("connection_string"):
        display_config["azure"]["connection_string"] = "*" * 20
    
    print(json.dumps(display_config, indent=2))


def download_video(url, start_time=None, end_time=None, config=None, custom_name=None):
    """Download video using yt-dlp"""
    if config is None:
        config = load_config()

    has_time_range = start_time is not None and end_time is not None

    # Resolve output path (handles relative paths cross-platform)
    output_path = resolve_path(config["download"]["output_path"])
    os.makedirs(output_path, exist_ok=True)

    # Build output template with time range and timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Use custom name if provided, otherwise use video title
    if custom_name and custom_name.strip():
        base_name = custom_name.strip()
    else:
        base_name = "%(title)s"

    if has_time_range:
        start_fmt = format_time_for_filename(start_time)
        end_fmt = format_time_for_filename(end_time)
        output_template = f"{base_name}_{start_fmt}_to_{end_fmt}_{timestamp}.%(ext)s"
    else:
        output_template = f"{base_name}_{timestamp}.%(ext)s"
    
    ydl_opts = {
        "outtmpl": str(output_path / output_template),
        "format": config["download"]["format"],
    }
    
    # Add time range if specified
    if has_time_range:
        ydl_opts["download_ranges"] = yt_dlp.utils.download_range_func(
            None, [(float(start_time), float(end_time))]
        )
        ydl_opts["force_keyframes_at_cuts"] = True
    
    downloaded_file = None
    
    def progress_hook(d):
        nonlocal downloaded_file
        if d["status"] == "finished":
            downloaded_file = d["filename"]
    
    ydl_opts["progress_hooks"] = [progress_hook]

    log(f"\n📥 Downloading: {url}")
    if has_time_range:
        log(f"   Time range: {start_time}s - {end_time}s")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    if downloaded_file:
        log(f"✅ Downloaded: {downloaded_file}")
    
    return downloaded_file


def upload_to_azure(filepath, config=None):
    """Upload file to Azure Blob Storage"""
    if config is None:
        config = load_config()

    azure_config = config["azure"]
    
    if not azure_config.get("connection_string"):
        log("❌ Azure connection string not configured. Run: yt-azure --config", "error")
        return None

    if not azure_config.get("container_name"):
        log("❌ Azure container name not configured. Run: yt-azure --config", "error")
        return None
    
    blob_service_client = BlobServiceClient.from_connection_string(
        azure_config["connection_string"]
    )
    container_client = blob_service_client.get_container_client(
        azure_config["container_name"]
    )
    
    filename = os.path.basename(filepath)
    blob_folder = azure_config.get("blob_folder", "").strip("/")
    blob_path = f"{blob_folder}/{filename}" if blob_folder else filename
    
    log(f"\n☁️  Uploading to Azure: {azure_config['container_name']}/{blob_path}")

    blob_client = container_client.get_blob_client(blob_path)

    with open(filepath, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)

    log(f"✅ Upload complete!")
    log(f"   URL: {blob_client.url}")
    
    return blob_client.url


def interactive_mode(config_path=None):
    """Run in interactive mode - Gradio UI if available, else text prompts"""
    
    if HAS_GRADIO:
        launch_ui(config_path)
    else:
        text_interactive_mode(config_path)


def text_interactive_mode(config_path=None):
    """Fallback text-based interactive mode"""
    print("\n🎬 yt-azure Interactive Mode\n")
    
    url = prompt_input("YouTube URL")
    if not url:
        print("❌ URL is required")
        return
    
    use_time_range = prompt_input("Download specific time range? (y/n)", "n")
    
    start_time = None
    end_time = None
    
    if use_time_range.lower() == "y":
        start_time = prompt_input("Start time (seconds)", "0")
        end_time = prompt_input("End time (seconds)")
        
        if not end_time:
            print("❌ End time is required for time range")
            return
    
    config = load_config(config_path)
    
    # Download
    filepath = download_video(url, start_time, end_time, config)
    
    if not filepath:
        print("❌ Download failed")
        return
    
    # Upload
    upload = prompt_input("Upload to Azure? (y/n)", "y")
    if upload.lower() == "y":
        upload_to_azure(filepath, config)


def launch_ui(config_path=None):
    """Launch Gradio web UI"""
    
    config = load_config(config_path)
    
    def get_youtube_embed_url(url, start_time, end_time):
        """Convert YouTube URL to embed URL with time parameters"""
        if not url:
            return ""
        
        # Extract video ID
        video_id = None
        if "youtube.com/watch?v=" in url:
            video_id = url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            video_id = url.split("youtu.be/")[1].split("?")[0]
        
        if not video_id:
            return ""
        
        # Build embed URL with time parameters
        embed_url = f"https://www.youtube.com/embed/{video_id}?"
        params = []
        
        start_sec = parse_time(start_time)
        end_sec = parse_time(end_time)
        
        if start_sec is not None:
            params.append(f"start={int(start_sec)}")
        if end_sec is not None:
            params.append(f"end={int(end_sec)}")
        
        embed_url += "&".join(params)
        return embed_url
    
    def update_preview(url, start_time, end_time):
        """Generate HTML for YouTube preview"""
        embed_url = get_youtube_embed_url(url, start_time, end_time)
        if not embed_url:
            return "<div style='height:450px;display:flex;align-items:center;justify-content:center;background:#f0f0f0;border-radius:8px;color:#666;'>Enter a YouTube URL to preview</div>"
        
        return f'''<iframe 
            width="100%" 
            height="450" 
            src="{embed_url}" 
            frameborder="0" 
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
            allowfullscreen
            style="border-radius:8px;">
        </iframe>'''
    
    def get_last_entry():
        """Get most recent history entry"""
        h = load_history()
        if h["entries"]:
            return h["entries"][-1], len(h["entries"]) - 1
        return None, -1
    
    def get_history_list():
        """Get formatted history list for display"""
        h = load_history()
        items = []
        for i, entry in enumerate(h["entries"]):
            url = entry.get("url", "")
            # Truncate URL for display
            short_url = url[:40] + "..." if len(url) > 40 else url
            time_info = ""
            if entry.get("start") and entry.get("end"):
                time_info = f" [{entry['start']}-{entry['end']}]"
            items.append(f"{i+1}. {short_url}{time_info}")
        return items
    
    def select_history_item(selected_value):
        """Handle selection of history item from dropdown"""
        if not selected_value:
            return "", "", "", "", "", "", "", update_preview("", "", ""), ""
        
        h = load_history()
        # Extract index from "1. url..." format
        try:
            idx = int(selected_value.split(".")[0]) - 1
        except (ValueError, IndexError):
            return "", "", "", "", "", "", "", update_preview("", "", ""), ""
        
        if 0 <= idx < len(h["entries"]):
            h["position"] = idx
            save_history(h)
            entry = h["entries"][idx]
            
            url = entry.get("url", "")
            start = entry.get("start", "")
            end = entry.get("end", "")
            log = entry.get("log", "")
            
            return (
                url,
                start,
                end,
                entry.get("video_name", ""),
                entry.get("container", ""),
                entry.get("blob_folder", ""),
                entry.get("format", ""),
                update_preview(url, start, end),
                log
            )
        return "", "", "", "", "", "", "", update_preview("", "", ""), ""
    
    def process(url, start_time, end_time, video_name, container, blob_folder, format_str, do_upload):
        if not url:
            return "❌ URL is required", gr.update(choices=get_history_list())

        # Build config with overrides
        run_config = load_config(config_path)
        
        if container:
            run_config["azure"]["container_name"] = container
        if blob_folder:
            run_config["azure"]["blob_folder"] = blob_folder
        if format_str:
            run_config["download"]["format"] = format_str
        
        # Parse times (supports MM:SS format)
        start = parse_time(start_time)
        end = parse_time(end_time)
        
        if (start is not None and end is None) or (start is None and end is not None):
            return "❌ Both start and end time required for partial download", gr.update(choices=get_history_list())
        
        output = []
        
        try:
            filepath = download_video(url, start, end, run_config, video_name)
            if not filepath:
                output.append("❌ Download failed")
            else:
                output.append(f"✅ Downloaded: {filepath}")
        except Exception as e:
            logger.error(f"Download error: {e}")
            output.append(f"❌ Download error: {e}")
            filepath = None
        
        if filepath and do_upload:
            try:
                blob_url = upload_to_azure(filepath, run_config)
                if blob_url:
                    output.append(f"✅ Uploaded: {blob_url}")
                else:
                    output.append("❌ Upload failed - check Azure config")
            except Exception as e:
                logger.error(f"Upload error: {e}")
                output.append(f"❌ Upload error: {e}")
        
        # Save to history with log
        entry = {
            "url": url,
            "start": start_time,
            "end": end_time,
            "video_name": video_name,
            "container": container,
            "blob_folder": blob_folder,
            "format": format_str,
            "log": "\n".join(output),
            "timestamp": datetime.now().isoformat()
        }
        add_to_history(entry)
        logger.info(f"Completed: {url}, start={start_time}, end={end_time}")
        
        return "\n".join(output), gr.update(choices=get_history_list())
    
    # Load last entry for initial values
    last_entry, _ = get_last_entry()
    initial_values = {
        "url": last_entry.get("url", "") if last_entry else "",
        "start": last_entry.get("start", "") if last_entry else "",
        "end": last_entry.get("end", "") if last_entry else "",
        "video_name": last_entry.get("video_name", "") if last_entry else "",
        "container": last_entry.get("container", "") if last_entry else "",
        "blob_folder": last_entry.get("blob_folder", "") if last_entry else "",
        "format": last_entry.get("format", "") if last_entry else "",
    }
    
    with gr.Blocks(title="yt-azure") as app:
        gr.Markdown("# 🎬 yt-azure")
        
        with gr.Row():
            # Left pane - Form (30%)
            with gr.Column(scale=3):
                history_list = gr.Dropdown(
                    choices=get_history_list(),
                    label="History",
                    interactive=True
                )
                
                url_input = gr.Textbox(
                    label="YouTube URL", 
                    placeholder="https://youtube.com/watch?v=...",
                    value=initial_values["url"]
                )
                
                with gr.Row():
                    start_input = gr.Textbox(
                        label="Start (e.g., 3:07)", 
                        placeholder="0:00",
                        value=initial_values["start"]
                    )
                    end_input = gr.Textbox(
                        label="End (e.g., 3:21)", 
                        placeholder="1:30",
                        value=initial_values["end"]
                    )
                
                gr.Markdown("### Overrides")
                video_name_input = gr.Textbox(
                    label="Video Name (optional)",
                    placeholder="Custom filename (without extension)",
                    value=initial_values.get("video_name", "")
                )
                container_input = gr.Textbox(
                    label="Container", 
                    placeholder=config["azure"].get("container_name") or "from config",
                    value=initial_values["container"]
                )
                folder_input = gr.Textbox(
                    label="Blob folder", 
                    placeholder=config["azure"].get("blob_folder") or "from config",
                    value=initial_values["blob_folder"]
                )
                format_input = gr.Textbox(
                    label="Format", 
                    placeholder="from config",
                    value=initial_values["format"]
                )
                
                upload_check = gr.Checkbox(label="Upload to Azure", value=True)
                
                submit_btn = gr.Button("🚀 Download", variant="primary")
            
            # Right pane - Video preview (70%)
            with gr.Column(scale=7):
                preview_html = gr.HTML(
                    value=update_preview(initial_values["url"], initial_values["start"], initial_values["end"])
                )
                output = gr.Textbox(label="Output", lines=4, interactive=False)
        
        # Event handlers
        form_fields = [url_input, start_input, end_input, video_name_input, container_input, folder_input, format_input]
        
        history_list.change(fn=select_history_item, inputs=[history_list], outputs=form_fields + [preview_html, output])
        
        # Update preview when URL or times change
        gr.on(
            triggers=[url_input.change, start_input.change, end_input.change],
            fn=update_preview,
            inputs=[url_input, start_input, end_input],
            outputs=[preview_html]
        )
        
        submit_btn.click(
            fn=process,
            inputs=[url_input, start_input, end_input, video_name_input, container_input, folder_input, format_input, upload_check],
            outputs=[output, history_list]
        )
    
    print("\n🌐 Launching UI at http://localhost:7860\n")
    app.launch(inbrowser=True)


def main():
    parser = argparse.ArgumentParser(
        description="Download videos with yt-dlp and upload to Azure Blob Storage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  yt-azure                                    # Interactive mode / UI
  yt-azure --url "https://..." --start 3:07 --end 3:21
  yt-azure --url "https://..." --start 0 --end 30
  yt-azure --url "https://..." --container my-container --blob-folder videos/
  yt-azure --config                           # Configure settings (default location)
  yt-azure --config /path/to/config.json      # Configure at custom location
  yt-azure --show-config                      # Show current config
        """
    )
    
    parser.add_argument("--url", "-u", help="YouTube video URL")
    parser.add_argument("--start", "-s", help="Start time (seconds or MM:SS)")
    parser.add_argument("--end", "-e", help="End time (seconds or MM:SS)")
    parser.add_argument("--config", "-c", nargs="?", const=True, help="Configure settings (optionally specify config file path)")
    parser.add_argument("--show-config", action="store_true", help="Show current config")
    parser.add_argument("--config-file", help="Path to config file")
    parser.add_argument("--container", help="Azure container name (overrides config)")
    parser.add_argument("--blob-folder", help="Azure blob folder (overrides config)")
    parser.add_argument("--format", "-f", help="Video format (overrides config)")
    parser.add_argument("--no-upload", action="store_true", help="Skip Azure upload")
    
    args = parser.parse_args()
    
    # Determine config path
    config_path = None
    if args.config_file:
        config_path = args.config_file
    elif isinstance(args.config, str):
        config_path = args.config
    
    # Config commands
    if args.config:
        configure(config_path)
        return
    
    if args.show_config:
        show_config(config_path)
        return
    
    # If no URL provided, run interactive mode
    if not args.url:
        interactive_mode(config_path)
        return
    
    # CLI mode with arguments
    config = load_config(config_path)
    
    # Apply CLI overrides
    if args.container:
        config["azure"]["container_name"] = args.container
    if args.blob_folder:
        config["azure"]["blob_folder"] = args.blob_folder
    if args.format:
        config["download"]["format"] = args.format
    
    # Parse times (supports MM:SS format)
    start_time = parse_time(args.start)
    end_time = parse_time(args.end)
    
    filepath = download_video(args.url, start_time, end_time, config)
    
    if filepath and not args.no_upload:
        upload_to_azure(filepath, config)


if __name__ == "__main__":
    main()
