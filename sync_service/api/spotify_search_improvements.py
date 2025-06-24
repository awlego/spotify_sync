"""
Improved Spotify search strategies based on notebook analysis
"""
from typing import Optional, Dict, Any
from loguru import logger
import re


class ImprovedSpotifySearch:
    """Enhanced search strategies for finding Spotify tracks"""
    
    @staticmethod
    def normalize_string(s: str) -> str:
        """Normalize string for better matching"""
        # Remove special characters and extra spaces
        s = re.sub(r'[^\w\s-]', ' ', s)
        s = re.sub(r'\s+', ' ', s)
        return s.strip().lower()
    
    @staticmethod
    def truncate_for_search(text: str, max_length: int = 30) -> str:
        """Truncate text for search, avoiding cutoff in middle of words"""
        if len(text) <= max_length:
            return text
        
        # Try to cut at a space
        truncated = text[:max_length]
        last_space = truncated.rfind(' ')
        if last_space > max_length * 0.6:  # Only if space is reasonably far
            return truncated[:last_space]
        return truncated
    
    def search_track_flexible(self, sp, track_name: str, artist_name: str, 
                             album_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Flexible track search using multiple strategies
        Based on the notebook's proven approach
        """
        # Strategy 1: Simple concatenated search (notebook style)
        # This often works better than the structured query
        try:
            # Truncate long names to avoid issues
            track_search = self.truncate_for_search(track_name)
            artist_search = self.truncate_for_search(artist_name, 20)
            
            # Build query similar to notebook
            query_parts = [track_search, artist_search]
            if album_name and len(album_name) < 50:
                album_search = self.truncate_for_search(album_name, 20)
                query_parts.append(album_search)
            
            query = ' '.join(query_parts)
            results = sp.search(q=query, type='track', limit=10)
            
            if results['tracks']['items']:
                # Find best match
                normalized_artist = self.normalize_string(artist_name)
                normalized_track = self.normalize_string(track_name)
                
                for track in results['tracks']['items']:
                    # Check artist match
                    track_artists = [self.normalize_string(a['name']) for a in track['artists']]
                    artist_match = any(normalized_artist in artist or artist in normalized_artist 
                                     for artist in track_artists)
                    
                    # Check track name match
                    track_name_match = self.normalize_string(track['name'])
                    name_match = (normalized_track in track_name_match or 
                                track_name_match in normalized_track)
                    
                    if artist_match and name_match:
                        return track
                
                # If no perfect match, return first result with artist match
                for track in results['tracks']['items']:
                    track_artists = [self.normalize_string(a['name']) for a in track['artists']]
                    if any(normalized_artist in artist or artist in normalized_artist 
                          for artist in track_artists):
                        return track
        
        except Exception as e:
            logger.debug(f"Flexible search failed: {e}")
        
        # Strategy 2: Try without album
        if album_name:
            try:
                query = f'{track_search} {artist_search}'
                results = sp.search(q=query, type='track', limit=5)
                
                if results['tracks']['items']:
                    normalized_artist = self.normalize_string(artist_name)
                    for track in results['tracks']['items']:
                        track_artists = [self.normalize_string(a['name']) for a in track['artists']]
                        if any(normalized_artist in artist or artist in normalized_artist 
                              for artist in track_artists):
                            return track
            
            except Exception as e:
                logger.debug(f"No-album search failed: {e}")
        
        # Strategy 3: Try with normalized/cleaned names
        try:
            # Remove common suffixes that might cause issues
            clean_track = re.sub(r'\s*\(feat\..*?\)|\s*\[.*?\]|\s*-\s*(Remix|Edit|Version).*$', '', track_name, flags=re.IGNORECASE)
            clean_track = self.truncate_for_search(clean_track)
            
            query = f'{clean_track} {artist_search}'
            results = sp.search(q=query, type='track', limit=5)
            
            if results['tracks']['items']:
                normalized_artist = self.normalize_string(artist_name)
                for track in results['tracks']['items']:
                    track_artists = [self.normalize_string(a['name']) for a in track['artists']]
                    if any(normalized_artist in artist or artist in normalized_artist 
                          for artist in track_artists):
                        return track
        
        except Exception as e:
            logger.debug(f"Cleaned search failed: {e}")
        
        return None
    
    def find_alternative_versions(self, sp, track_name: str, artist_name: str) -> Optional[Dict[str, Any]]:
        """
        Find alternative versions of a track (live, acoustic, remix, etc.)
        when the exact version isn't available
        """
        base_track_name = re.sub(r'\s*\(.*?\)|\s*\[.*?\]', '', track_name)
        base_track_name = self.truncate_for_search(base_track_name)
        
        try:
            query = f'{base_track_name} {artist_name}'
            results = sp.search(q=query, type='track', limit=20)
            
            if results['tracks']['items']:
                normalized_artist = self.normalize_string(artist_name)
                
                # Score each result
                scored_results = []
                for track in results['tracks']['items']:
                    track_artists = [self.normalize_string(a['name']) for a in track['artists']]
                    if any(normalized_artist in artist or artist in normalized_artist 
                          for artist in track_artists):
                        
                        # Calculate similarity score
                        track_name_norm = self.normalize_string(track['name'])
                        base_name_norm = self.normalize_string(base_track_name)
                        
                        # Prefer exact matches, then versions that contain the base name
                        if track_name_norm == base_name_norm:
                            score = 100
                        elif base_name_norm in track_name_norm:
                            score = 80
                        else:
                            # Partial match score based on common words
                            base_words = set(base_name_norm.split())
                            track_words = set(track_name_norm.split())
                            common_words = base_words.intersection(track_words)
                            score = len(common_words) / len(base_words) * 60 if base_words else 0
                        
                        if score > 40:  # Reasonable threshold
                            scored_results.append((score, track))
                
                # Return best match
                if scored_results:
                    scored_results.sort(key=lambda x: x[0], reverse=True)
                    return scored_results[0][1]
        
        except Exception as e:
            logger.debug(f"Alternative version search failed: {e}")
        
        return None