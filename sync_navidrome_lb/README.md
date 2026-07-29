# Navidrome to ListenBrainz Playlist Synchronizer

A Python script that synchronizes playlists from your self-hosted Navidrome music server to ListenBrainz. Playlists are converted to JSPF (JSON Serialization Format for Playlists) format and created on your ListenBrainz account.

Once your playlists are on ListenBrainz, you can use ListenBrainz's native sync features to push them to Spotify, Qobuz, and other services.

## Features

- ✅ Sync all Navidrome playlists or specific ones by name
- ✅ Automatic MusicBrainz ID detection from track metadata
- ✅ Fallback database lookup if MBIDs aren't in API response
- ✅ Detailed logging and sync reports
- ✅ JSPF format for maximum compatibility
- ✅ Error handling and retry logic
- ✅ JSON sync log for tracking

## Requirements

- Python 3.7+
- Access to Navidrome server (URL, username, password)
- ListenBrainz account with API token
- Navidrome database should contain MusicBrainz Recording IDs (mbz_recording_id)

## Installation

### 1. Clone or download the script files

```bash
# If downloading files individually, ensure you have:
# - navidrome_to_listenbrainz.py
# - .env.example
# - requirements.txt
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
# Copy the example configuration
cp .env.example .env

# Edit .env with your credentials
nano .env
```

#### Configuration Guide

**NAVIDROME_URL**
- Your Navidrome server URL (e.g., `http://localhost:4533` or `https://music.example.com`)

**NAVIDROME_USER**
- Your Navidrome username

**NAVIDROME_PASSWORD**
- Your Navidrome password

**NAVIDROME_DB_PATH** (Optional)
- Path to Navidrome's SQLite database file (e.g., `/data/navidrome.db`)
- Used as fallback if tracks don't have MBID in API response
- If not set, script will only use API data

**LISTENBRAINZ_TOKEN**
- Your ListenBrainz API token
- Get it from: https://listenbrainz.org/settings/

**SYNC_PLAYLISTS** (Optional)
- Comma-separated list of playlist names to sync
- Leave empty to sync all playlists
- Example: `SYNC_PLAYLISTS=Favorites,Workout Mix,Study Music`

## Usage

### Sync all playlists

```bash
python navidrome_to_listenbrainz.py
```

### Sync specific playlists only

Edit `.env` and set:

```
SYNC_PLAYLISTS=Favorites,My Playlist,Another Playlist
```

Then run:

```bash
python navidrome_to_listenbrainz.py
```

### View logs

The script creates detailed logs:

```bash
# View real-time output
python navidrome_to_listenbrainz.py 2>&1 | tee sync.log

# Check sync results
cat sync_log.json
```

## Output

### Console Output

```
2024-01-15 14:23:45,123 - INFO - Starting playlist sync from Navidrome to ListenBrainz
2024-01-15 14:23:45,234 - INFO - Found 5 playlists to sync
2024-01-15 14:23:45,345 - INFO - Syncing playlist: My Favorites (ID: abc123)
2024-01-15 14:23:45,456 - INFO - Building JSPF for playlist: My Favorites
2024-01-15 14:23:45,567 - INFO - Converted 45 tracks (skipped 2)
...
============================================================
SYNC SUMMARY
============================================================
✓ My Favorites
  ListenBrainz ID: 12345678-1234-5678-1234-567812345678
✓ Workout Mix
  ListenBrainz ID: 87654321-4321-8765-4321-876543218765
✗ Empty Playlist
============================================================
```

### Sync Log (sync_log.json)

```json
[
  {
    "navidrome_id": "abc123",
    "navidrome_name": "My Favorites",
    "listenbrainz_id": "12345678-1234-5678-1234-567812345678",
    "timestamp": "2024-01-15T14:23:45.678901",
    "status": "success"
  },
  {
    "navidrome_id": "xyz789",
    "navidrome_name": "Empty Playlist",
    "timestamp": "2024-01-15T14:23:50.123456",
    "status": "failed"
  }
]
```

## Workflow: From Navidrome to Spotify/Qobuz

Once playlists are on ListenBrainz, complete the sync chain:

1. **Navidrome** → (this script) → **ListenBrainz**
2. **ListenBrainz** → (ListenBrainz native sync or Soundiiz) → **Spotify/Qobuz**

To sync from ListenBrainz to Spotify/Qobuz:

### Free Option (One-time transfer)
- Go to your ListenBrainz playlist
- Use the "Export" feature to copy the playlist URL
- Manual import or use open-source tools

### Premium Option (Automatic sync)
- Use **Soundiiz** (free tier available for basic syncs)
- Set up automatic ListenBrainz → Spotify/Qobuz sync

## Troubleshooting

### Error: "Missing required environment variables"

**Solution:** Ensure `.env` file exists and has all required fields filled in.

```bash
cat .env
```

### Error: "Navidrome API error" or connection failed

**Solution:** 
- Check Navidrome URL is correct (include protocol: `http://` or `https://`)
- Verify credentials are correct
- Ensure Navidrome server is running and accessible
- Check firewall rules if accessing remotely

### Tracks skipped with "no MusicBrainz ID"

This is normal if:
- Tracks in Navidrome don't have MBIDs embedded
- API response doesn't include `mbzRecordingId`
- Database path not configured for fallback lookup

**Solution:**
- Set `NAVIDROME_DB_PATH` in `.env` for fallback lookup
- Or enrich track metadata in Navidrome with MBIDs

### "Failed to create playlist on ListenBrainz"

**Solution:**
- Verify ListenBrainz token is valid: https://listenbrainz.org/settings/
- Check ListenBrainz API status: https://listenbrainz.org/
- Ensure playlist name is not already taken (ListenBrainz allows duplicates but may have limits)

### Playlist created but tracks not showing

**Possible causes:**
- Tracks don't have valid MusicBrainz IDs
- Track metadata format issues
- ListenBrainz database doesn't recognize recording IDs

**Debug:**
- Check `sync_log.json` for skipped track count
- Enable debug logging (modify script to add `logger.setLevel(logging.DEBUG)`)
- Verify tracks exist in MusicBrainz: https://musicbrainz.org/

## Advanced: Running on Schedule

### Linux/Mac (cron)

```bash
# Open crontab
crontab -e

# Add entry to sync daily at 2 AM
0 2 * * * cd /path/to/script && python navidrome_to_listenbrainz.py >> sync.log 2>&1
```

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install -r requirements.txt

ENV NAVIDROME_URL=http://navidrome:4533
ENV NAVIDROME_USER=user
ENV NAVIDROME_PASSWORD=pass
ENV LISTENBRAINZ_TOKEN=token

CMD ["python", "navidrome_to_listenbrainz.py"]
```

Run:
```bash
docker build -t navidrome-lb-sync .
docker run --env-file .env navidrome-lb-sync
```

## How It Works

1. **Fetch playlists** from Navidrome via Subsonic API
2. **Get playlist tracks** for each playlist
3. **Extract MusicBrainz IDs** from track metadata or database
4. **Build JSPF format** playlist data
5. **Create on ListenBrainz** using ListenBrainz API
6. **Log results** to JSON file for tracking

## JSPF Format

Playlists are created in JSPF (JSON Serialization Format for Playlists) format, which includes:

- Playlist title and description
- Track metadata with MusicBrainz Recording IDs
- Creation timestamp
- Source metadata (marked as "navidrome")

Example JSPF structure:
```json
{
  "playlist": {
    "title": "My Favorites",
    "description": "Synced from Navidrome on 2024-01-15T14:23:45.123456",
    "public": true,
    "track": [
      {
        "title": "Song Title",
        "identifier": "https://musicbrainz.org/recording/12345678-1234-5678-1234-567812345678",
        "creator": "Artist Name",
        "duration": 240000,
        "album": "Album Name"
      }
    ],
    "extension": {
      "https://listenbrainz.org/ns/0.1": {
        "additional_metadata": {
          "source": "navidrome"
        }
      }
    }
  }
}
```

## Limitations

- Requires MusicBrainz Recording IDs in Navidrome
- ListenBrainz has rate limits (handled gracefully)
- Playlist descriptions are auto-generated with sync timestamp
- Doesn't support private playlists (all synced playlists are public on ListenBrainz)

## Privacy & Security

- API tokens are stored locally in `.env` - keep this file secret
- Never commit `.env` to version control
- Add to `.gitignore`:
  ```
  .env
  sync_log.json
  ```

## Support & Contributing

- Check logs for detailed error messages
- Review `sync_log.json` for failed playlists
- ListenBrainz API docs: https://listenbrainz.readthedocs.io/
- Navidrome documentation: https://www.navidrome.org/docs/

## License

This script is provided as-is for personal use.

## Next Steps

1. After syncing playlists to ListenBrainz
2. Use ListenBrainz's built-in sync to push to Spotify/Qobuz
3. Or use Soundiiz for automatic scheduled syncs
