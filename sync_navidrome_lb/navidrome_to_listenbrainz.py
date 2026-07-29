#!/usr/bin/env python3
"""
Navidrome to ListenBrainz Playlist Synchronizer

Syncs playlists from a Navidrome music server to ListenBrainz using the ListenBrainz API.
Requires MusicBrainz Recording IDs to be present in Navidrome database.
"""

import os
import sys
import json
import logging
import sqlite3
import requests
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


@dataclass
class Track:
    """Represents a track in JSPF format"""
    title: str
    identifier: str  # MusicBrainz Recording ID URI
    creator: str  # Artist name
    duration: int  # milliseconds
    album: Optional[str] = None
    
    def to_jspf(self) -> Dict:
        """Convert to JSPF track object"""
        track = {
            "title": self.title,
            "identifier": self.identifier,
            "creator": self.creator,
            "duration": self.duration,
        }
        if self.album:
            track["album"] = self.album
        return track


@dataclass
class PlaylistMetadata:
    """JSPF Playlist metadata"""
    title: str
    description: Optional[str] = None
    public: bool = True
    
    def to_jspf(self) -> Dict:
        """Convert to JSPF metadata"""
        metadata = {
            "title": self.title,
            "public": self.public,
        }
        if self.description:
            metadata["description"] = self.description
        return metadata


class NavidromeClient:
    """Client for interacting with Navidrome via Subsonic API"""
    
    def __init__(self, url: str, username: str, password: str):
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.db_path = os.getenv('NAVIDROME_DB_PATH', None)
        
    def get_playlists(self) -> List[Dict]:
        """Get all playlists from Navidrome via API"""
        try:
            params = {
                'u': self.username,
                'p': self.password,
                'c': 'navidrome-listenbrainz-sync',
                'f': 'json'
            }
            response = requests.get(
                f"{self.url}/rest/getPlaylists.view",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('subsonic-response', {}).get('status') == 'ok':
                playlists = data.get('subsonic-response', {}).get('playlists', {}).get('playlist', [])
                # Handle single playlist case
                if isinstance(playlists, dict):
                    playlists = [playlists]
                return playlists
            else:
                logger.error("Navidrome API error")
                return []
        except Exception as e:
            logger.error(f"Failed to get playlists from Navidrome: {e}")
            return []
    
    def get_playlist_tracks(self, playlist_id: str) -> List[Dict]:
        """Get tracks for a specific playlist from Navidrome API"""
        try:
            params = {
                'u': self.username,
                'p': self.password,
                'c': 'navidrome-listenbrainz-sync',
                'f': 'json',
                'id': playlist_id
            }
            response = requests.get(
                f"{self.url}/rest/getPlaylist.view",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('subsonic-response', {}).get('status') == 'ok':
                playlist = data.get('subsonic-response', {}).get('playlist', {})
                tracks = playlist.get('entry', [])
                # Handle single track case
                if isinstance(tracks, dict):
                    tracks = [tracks]
                return tracks
            else:
                logger.error(f"Failed to get playlist {playlist_id}")
                return []
        except Exception as e:
            logger.error(f"Failed to get playlist tracks: {e}")
            return []
    
    def get_track_mbid(self, track_id: str) -> Optional[str]:
        """Get MusicBrainz Recording ID from Navidrome database"""
        if not self.db_path or not os.path.exists(self.db_path):
            logger.warning("Navidrome database path not configured, skipping direct DB lookup")
            return None
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT mbz_recording_id FROM media_file WHERE id = ?",
                (track_id,)
            )
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result and result[0] else None
        except Exception as e:
            logger.warning(f"Failed to query database for track {track_id}: {e}")
            return None


class ListenBrainzClient:
    """Client for interacting with ListenBrainz API"""
    
    BASE_URL = "https://listenbrainz.org/api/v1"
    
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            'Authorization': f'Token {token}',
            'Content-Type': 'application/json'
        }
    
    def create_playlist(self, playlist_jspf: Dict) -> Optional[str]:
        """Create a playlist on ListenBrainz and return its ID"""
        try:
            response = requests.post(
                f"{self.BASE_URL}/playlist/create",
                headers=self.headers,
                json=playlist_jspf
            )
            response.raise_for_status()
            data = response.json()
            
            playlist_id = data.get('playlist_mbid')
            if playlist_id:
                logger.info(f"Created playlist on ListenBrainz: {playlist_id}")
                return playlist_id
            else:
                logger.error(f"No playlist ID in response: {data}")
                return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to create playlist on ListenBrainz: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to create playlist on ListenBrainz: {e}")
            return None


class PlaylistSynchronizer:
    """Orchestrates playlist synchronization from Navidrome to ListenBrainz"""
    
    def __init__(self, navidrome_url: str, navidrome_user: str, navidrome_pass: str, 
                 listenbrainz_token: str):
        self.navidrome = NavidromeClient(navidrome_url, navidrome_user, navidrome_pass)
        self.listenbrainz = ListenBrainzClient(listenbrainz_token)
        self.sync_log = []
    
    def build_jspf_playlist(self, playlist_name: str, playlist_id: str, 
                           description: Optional[str] = None) -> Optional[Dict]:
        """Build a JSPF playlist from Navidrome playlist data"""
        logger.info(f"Building JSPF for playlist: {playlist_name}")
        
        # Get tracks from Navidrome
        tracks_data = self.navidrome.get_playlist_tracks(playlist_id)
        
        if not tracks_data:
            logger.warning(f"No tracks found in playlist {playlist_name}")
            return None
        
        # Convert tracks to JSPF format
        jspf_tracks = []
        skipped_count = 0
        
        for track_data in tracks_data:
            mbid = track_data.get('mbzRecordingId') or self.navidrome.get_track_mbid(
                track_data.get('id')
            )
            
            if not mbid:
                logger.warning(
                    f"Skipping track '{track_data.get('title')}' - no MusicBrainz ID"
                )
                skipped_count += 1
                continue
            
            # Ensure MBID is in URI format
            if not mbid.startswith('https://'):
                mbid = f"https://musicbrainz.org/recording/{mbid}"
            
            track = Track(
                title=track_data.get('title', 'Unknown'),
                identifier=mbid,
                creator=track_data.get('artist', 'Unknown'),
                duration=int(track_data.get('duration', 0) * 1000),  # Convert to ms
                album=track_data.get('album')
            )
            jspf_tracks.append(track.to_jspf())
        
        if not jspf_tracks:
            logger.error(f"No valid tracks with MBIDs in playlist {playlist_name}")
            return None
        
        logger.info(f"Converted {len(jspf_tracks)} tracks (skipped {skipped_count})")
        
        # Build JSPF playlist
        metadata = PlaylistMetadata(
            title=playlist_name,
            description=description or f"Synced from Navidrome on {datetime.now().isoformat()}",
            public=True
        )
        
        jspf_playlist = {
            "playlist": {
                "title": metadata.title,
                "description": metadata.description,
                "public": metadata.public,
                "track": jspf_tracks,
                "extension": {
                    "https://listenbrainz.org/ns/0.1": {
                        "additional_metadata": {
                            "source": "navidrome"
                        }
                    }
                }
            }
        }
        
        return jspf_playlist
    
    def sync_playlist(self, playlist_id: str, playlist_name: str, 
                     description: Optional[str] = None) -> bool:
        """Sync a single playlist from Navidrome to ListenBrainz"""
        logger.info(f"Syncing playlist: {playlist_name} (ID: {playlist_id})")
        
        jspf_playlist = self.build_jspf_playlist(playlist_name, playlist_id, description)
        
        if not jspf_playlist:
            logger.error(f"Failed to build JSPF for playlist {playlist_name}")
            return False
        
        # Create on ListenBrainz
        result_id = self.listenbrainz.create_playlist(jspf_playlist)
        
        if result_id:
            self.sync_log.append({
                'navidrome_id': playlist_id,
                'navidrome_name': playlist_name,
                'listenbrainz_id': result_id,
                'timestamp': datetime.now().isoformat(),
                'status': 'success'
            })
            return True
        else:
            self.sync_log.append({
                'navidrome_id': playlist_id,
                'navidrome_name': playlist_name,
                'timestamp': datetime.now().isoformat(),
                'status': 'failed'
            })
            return False
    
    def sync_all_playlists(self) -> None:
        """Sync all playlists from Navidrome to ListenBrainz"""
        logger.info("Starting playlist sync from Navidrome to ListenBrainz")
        
        playlists = self.navidrome.get_playlists()
        
        if not playlists:
            logger.error("No playlists found in Navidrome")
            return
        
        logger.info(f"Found {len(playlists)} playlists to sync")
        
        successful = 0
        failed = 0
        
        for playlist in playlists:
            playlist_id = playlist.get('id')
            playlist_name = playlist.get('name')
            
            if self.sync_playlist(playlist_id, playlist_name):
                successful += 1
            else:
                failed += 1
        
        logger.info(f"Sync complete: {successful} succeeded, {failed} failed")
        self.print_summary()
    
    def sync_playlists_by_name(self, playlist_names: List[str]) -> None:
        """Sync specific playlists by name"""
        logger.info(f"Syncing specific playlists: {playlist_names}")
        
        playlists = self.navidrome.get_playlists()
        
        if not playlists:
            logger.error("No playlists found in Navidrome")
            return
        
        successful = 0
        failed = 0
        
        for playlist in playlists:
            if playlist.get('name') in playlist_names:
                playlist_id = playlist.get('id')
                playlist_name = playlist.get('name')
                
                if self.sync_playlist(playlist_id, playlist_name):
                    successful += 1
                else:
                    failed += 1
        
        logger.info(f"Sync complete: {successful} succeeded, {failed} failed")
        self.print_summary()
    
    def print_summary(self) -> None:
        """Print sync summary"""
        if not self.sync_log:
            return
        
        print("\n" + "="*60)
        print("SYNC SUMMARY")
        print("="*60)
        
        for entry in self.sync_log:
            status = "✓" if entry['status'] == 'success' else "✗"
            print(f"{status} {entry['navidrome_name']}")
            if entry['status'] == 'success':
                print(f"  ListenBrainz ID: {entry['listenbrainz_id']}")
        
        print("="*60 + "\n")
    
    def save_sync_log(self, filepath: str = "sync_log.json") -> None:
        """Save sync log to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.sync_log, f, indent=2)
        logger.info(f"Sync log saved to {filepath}")


def main():
    """Main entry point"""
    # Load configuration
    navidrome_url = os.getenv('NAVIDROME_URL')
    navidrome_user = os.getenv('NAVIDROME_USER')
    navidrome_pass = os.getenv('NAVIDROME_PASSWORD')
    listenbrainz_token = os.getenv('LISTENBRAINZ_TOKEN')
    
    # Validate configuration
    if not all([navidrome_url, navidrome_user, navidrome_pass, listenbrainz_token]):
        logger.error("Missing required environment variables. Please check .env file.")
        sys.exit(1)
    
    # Initialize synchronizer
    sync = PlaylistSynchronizer(
        navidrome_url=navidrome_url,
        navidrome_user=navidrome_user,
        navidrome_pass=navidrome_pass,
        listenbrainz_token=listenbrainz_token
    )
    
    # Check if specific playlists requested
    playlist_names = os.getenv('SYNC_PLAYLISTS', '').strip()
    
    if playlist_names:
        # Sync specific playlists
        names_list = [name.strip() for name in playlist_names.split(',')]
        sync.sync_playlists_by_name(names_list)
    else:
        # Sync all playlists
        sync.sync_all_playlists()
    
    # Save log
    sync.save_sync_log()


if __name__ == '__main__':
    main()
