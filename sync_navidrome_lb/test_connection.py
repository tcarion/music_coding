#!/usr/bin/env python3
"""
Test connection script for Navidrome and ListenBrainz

Run this before doing the full sync to verify your configuration is correct.
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def test_navidrome():
    """Test connection to Navidrome"""
    print("\n" + "="*60)
    print("Testing Navidrome Connection")
    print("="*60)
    
    url = os.getenv('NAVIDROME_URL')
    user = os.getenv('NAVIDROME_USER')
    password = os.getenv('NAVIDROME_PASSWORD')
    
    if not all([url, user, password]):
        print("❌ Missing Navidrome configuration")
        print("   Required: NAVIDROME_URL, NAVIDROME_USER, NAVIDROME_PASSWORD")
        return False
    
    print(f"URL: {url}")
    print(f"User: {user}")
    
    try:
        # Test basic connectivity
        response = requests.get(url, timeout=5)
        print(f"✓ Server responds (HTTP {response.status_code})")
    except Exception as e:
        print(f"❌ Cannot connect to Navidrome: {e}")
        return False
    
    try:
        # Test API authentication
        params = {
            'u': user,
            'p': password,
            'c': 'test-client',
            'f': 'json'
        }
        response = requests.get(
            f"{url}/rest/ping.view",
            params=params,
            timeout=5
        )
        response.raise_for_status()
        
        data = response.json()
        if data.get('subsonic-response', {}).get('status') == 'ok':
            print("✓ Authentication successful")
            
            # Get playlists count
            response = requests.get(
                f"{url}/rest/getPlaylists.view",
                params=params,
                timeout=5
            )
            response.raise_for_status()
            
            playlists = response.json().get('subsonic-response', {}).get('playlists', {}).get('playlist', [])
            if isinstance(playlists, dict):
                playlists = [playlists]
            
            print(f"✓ Found {len(playlists)} playlists")
            
            if playlists:
                print("\n  Available playlists:")
                for p in playlists[:5]:  # Show first 5
                    print(f"    - {p.get('name')} ({p.get('songCount', 0)} tracks)")
                if len(playlists) > 5:
                    print(f"    ... and {len(playlists) - 5} more")
            
            return True
        else:
            print("❌ Authentication failed")
            return False
    except Exception as e:
        print(f"❌ API error: {e}")
        return False


def test_listenbrainz():
    """Test connection to ListenBrainz"""
    print("\n" + "="*60)
    print("Testing ListenBrainz Connection")
    print("="*60)
    
    token = os.getenv('LISTENBRAINZ_TOKEN')
    
    if not token:
        print("❌ Missing ListenBrainz configuration")
        print("   Required: LISTENBRAINZ_TOKEN")
        return False
    
    print(f"Token: {token[:20]}..." if len(token) > 20 else token)
    
    try:
        headers = {
            'Authorization': f'Token {token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            "https://listenbrainz.org/api/v1/validate-token",
            headers=headers,
            timeout=5
        )
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('valid'):
            username = data.get('user_name', 'Unknown')
            print(f"✓ Token is valid")
            print(f"✓ Logged in as: {username}")
            return True
        else:
            print(f"❌ Token is invalid")
            return False
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("❌ Token is invalid or expired")
        else:
            print(f"❌ API error: {e.response.text}")
        return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


def test_mbid_support():
    """Test if Navidrome has tracks with MBIDs"""
    print("\n" + "="*60)
    print("Testing MusicBrainz ID Support")
    print("="*60)
    
    url = os.getenv('NAVIDROME_URL')
    user = os.getenv('NAVIDROME_USER')
    password = os.getenv('NAVIDROME_PASSWORD')
    
    if not all([url, user, password]):
        print("⚠ Navidrome not configured, skipping")
        return True
    
    try:
        params = {
            'u': user,
            'p': password,
            'c': 'test-client',
            'f': 'json'
        }
        
        # Get all songs
        response = requests.get(
            f"{url}/rest/getSongs.view",
            params={**params, 'size': 10},
            timeout=10
        )
        response.raise_for_status()
        
        songs = response.json().get('subsonic-response', {}).get('songs', {}).get('song', [])
        if isinstance(songs, dict):
            songs = [songs]
        
        if not songs:
            print("⚠ No songs found in library")
            return True
        
        print(f"Checking {len(songs)} sample songs for MBIDs...")
        
        with_mbid = 0
        without_mbid = 0
        
        for song in songs:
            if song.get('mbzRecordingId'):
                with_mbid += 1
            else:
                without_mbid += 1
        
        percentage = int((with_mbid / len(songs)) * 100) if songs else 0
        print(f"✓ {with_mbid}/{len(songs)} tracks have MBIDs ({percentage}%)")
        
        if with_mbid == 0:
            print("⚠ WARNING: No tracks have MusicBrainz IDs!")
            print("   Playlists will be empty or need fallback database lookup")
            print("   Configure NAVIDROME_DB_PATH in .env if available")
        elif percentage < 50:
            print("⚠ WARNING: Only {percentage}% of tracks have MBIDs")
            print("   Many tracks will be skipped during sync")
        else:
            print("✓ Good MBID coverage")
        
        return True
    except Exception as e:
        print(f"⚠ Could not check MBID support: {e}")
        return True  # Don't fail if we can't check


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("Navidrome to ListenBrainz - Connection Test")
    print("="*60)
    
    # Check if .env exists
    if not os.path.exists('.env'):
        print("\n❌ .env file not found!")
        print("   Please copy .env.example to .env and configure it:")
        print("   $ cp .env.example .env")
        sys.exit(1)
    
    results = []
    
    # Run tests
    results.append(("Navidrome", test_navidrome()))
    results.append(("ListenBrainz", test_listenbrainz()))
    results.append(("MusicBrainz IDs", test_mbid_support()))
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    for name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n✓ All tests passed!")
        print("\nYou can now run the full sync:")
        print("  $ python navidrome_to_listenbrainz.py")
    else:
        print("\n❌ Some tests failed. Please fix the issues above.")
        sys.exit(1)


if __name__ == '__main__':
    main()
