#!/usr/bin/env python3
"""
Generate a detailed music taste profile from listening history.
Output is optimized for a Claude research agent to find local concerts.
"""

import sys
import os
import json
import math
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional, Any
from loguru import logger
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.database import DatabaseManager
from shared.models import PlayHistory, Track, Artist
from sqlalchemy import func, extract, desc


class TasteProfileGenerator:
    """Generates a comprehensive music taste profile from listening history."""

    def __init__(self, output_path: str = "data/taste_profile.md"):
        load_dotenv()
        self.db = DatabaseManager()
        self.output_path = output_path
        self._spotify = None

    @property
    def spotify(self) -> spotipy.Spotify:
        """Lazy-load Spotify client."""
        if self._spotify is None:
            self._spotify = spotipy.Spotify(auth_manager=SpotifyOAuth(
                scope="user-library-read",
                cache_path="data/cache/.spotify_cache"
            ))
        return self._spotify

    def generate(self) -> str:
        """Generate the complete taste profile and write to markdown."""
        logger.info("Starting taste profile generation...")

        # Step 1: Get comprehensive artist data
        logger.info("Fetching artist play data...")
        artist_data = self._get_comprehensive_artist_data()

        # Step 2: Enrich with genre data from Spotify
        logger.info("Enriching with Spotify genre data...")
        artist_data = self._enrich_genres(artist_data)

        # Step 3: Calculate tiers
        logger.info("Calculating artist tiers...")
        tiers = self._calculate_artist_tiers(artist_data)

        # Step 4: Build genre profile
        logger.info("Building genre profile...")
        genre_profile = self._build_genre_profile(tiers)

        # Step 5: Analyze listening patterns
        logger.info("Analyzing listening patterns...")
        patterns = self._analyze_listening_patterns(artist_data)

        # Step 6: Get stats summary
        stats = self._get_stats_summary()

        # Step 7: Generate markdown
        logger.info("Generating markdown profile...")
        markdown = self._generate_markdown(stats, tiers, genre_profile, patterns)

        # Write to file
        with open(self.output_path, 'w') as f:
            f.write(markdown)

        logger.info(f"Profile written to {self.output_path}")
        return self.output_path

    def _get_comprehensive_artist_data(self) -> List[Dict[str, Any]]:
        """Get detailed play data for all artists."""
        with self.db.session_scope() as session:
            # Get all artists with play counts
            artist_plays = session.query(
                Artist,
                func.count(PlayHistory.id).label('total_plays'),
                func.min(PlayHistory.played_at).label('first_play'),
                func.max(PlayHistory.played_at).label('last_play')
            ).select_from(PlayHistory)\
             .join(Artist, PlayHistory.artist_id == Artist.id)\
             .group_by(Artist.id)\
             .order_by(desc('total_plays'))\
             .all()

            artist_data = []
            for artist, total_plays, first_play, last_play in artist_plays:
                # Get years with plays
                years_query = session.query(
                    extract('year', PlayHistory.played_at).label('year'),
                    func.count(PlayHistory.id).label('plays')
                ).filter(PlayHistory.artist_id == artist.id)\
                 .group_by('year')\
                 .all()

                years_active = len(years_query)
                plays_by_year = {int(y): p for y, p in years_query}

                # Get peak month
                peak_month_query = session.query(
                    func.strftime('%Y-%m', PlayHistory.played_at).label('month'),
                    func.count(PlayHistory.id).label('plays')
                ).filter(PlayHistory.artist_id == artist.id)\
                 .group_by('month')\
                 .order_by(desc('plays'))\
                 .first()

                peak_month = peak_month_query[0] if peak_month_query else None
                peak_month_plays = peak_month_query[1] if peak_month_query else 0

                days_since_last = (datetime.utcnow() - last_play).days if last_play else 9999

                artist_data.append({
                    'id': artist.id,
                    'name': artist.name,
                    'spotify_id': artist.spotify_id,
                    'genres': json.loads(artist.genres) if artist.genres else [],
                    'total_plays': total_plays,
                    'first_play': first_play,
                    'last_play': last_play,
                    'years_active': years_active,
                    'plays_by_year': plays_by_year,
                    'peak_month': peak_month,
                    'peak_month_plays': peak_month_plays,
                    'days_since_last_play': days_since_last
                })

            return artist_data

    def _enrich_genres(self, artist_data: List[Dict], max_artists: int = 200) -> List[Dict]:
        """Enrich top artists with genre data from Spotify API."""
        artists_needing_genres = [
            a for a in artist_data[:max_artists]
            if not a['genres']
        ]

        if not artists_needing_genres:
            logger.info("All top artists already have genre data")
            return artist_data

        logger.info(f"Fetching genres for {len(artists_needing_genres)} artists...")

        updated_count = 0
        with self.db.session_scope() as session:
            for artist_info in artists_needing_genres:
                try:
                    genres = self._fetch_artist_genres(artist_info)
                    if genres:
                        artist_info['genres'] = genres
                        # Update database
                        artist = session.get(Artist, artist_info['id'])
                        if artist:
                            artist.genres = json.dumps(genres)
                        updated_count += 1
                except Exception as e:
                    logger.warning(f"Failed to get genres for {artist_info['name']}: {e}")

        logger.info(f"Updated genres for {updated_count} artists")
        return artist_data

    def _fetch_artist_genres(self, artist_info: Dict) -> List[str]:
        """Fetch genres for a single artist from Spotify."""
        # Try by Spotify ID first
        if artist_info['spotify_id']:
            try:
                result = self.spotify.artist(artist_info['spotify_id'])
                if result and result.get('genres'):
                    return result['genres']
            except Exception:
                pass

        # Fall back to search
        try:
            results = self.spotify.search(q=artist_info['name'], type='artist', limit=1)
            if results['artists']['items']:
                artist = results['artists']['items'][0]
                # Verify name matches reasonably
                if artist_info['name'].lower() in artist['name'].lower() or \
                   artist['name'].lower() in artist_info['name'].lower():
                    return artist.get('genres', [])
        except Exception:
            pass

        return []

    def _calculate_artist_tiers(self, artist_data: List[Dict]) -> Dict[str, List[Dict]]:
        """Assign artists to tiers based on weighted scoring."""
        if not artist_data:
            return {'tier_1': [], 'tier_2': [], 'tier_3': [], 'tier_4': []}

        max_plays = max(a['total_plays'] for a in artist_data)
        max_peak = max(a['peak_month_plays'] for a in artist_data) if artist_data else 1
        max_years = 7  # Data spans 7 years

        for artist in artist_data:
            # Weighted scoring formula
            play_score = (math.log1p(artist['total_plays']) / math.log1p(max_plays)) * 100
            consistency_score = (artist['years_active'] / max_years) * 100
            intensity_score = (artist['peak_month_plays'] / max_peak) * 100 if max_peak > 0 else 0
            recency_score = 100 if artist['days_since_last_play'] < 180 else 50

            artist['tier_score'] = (
                play_score * 0.40 +
                consistency_score * 0.25 +
                intensity_score * 0.20 +
                recency_score * 0.15
            )

        # Sort by tier score
        sorted_artists = sorted(artist_data, key=lambda x: x['tier_score'], reverse=True)

        return {
            'tier_1': sorted_artists[:20],      # Must-see
            'tier_2': sorted_artists[20:70],    # Would definitely enjoy
            'tier_3': sorted_artists[70:170],   # Would likely enjoy
            'tier_4': sorted_artists[170:300]   # Casual interest
        }

    def _build_genre_profile(self, tiers: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """Aggregate genre preferences weighted by tier and play count."""
        genre_weights = defaultdict(float)
        genre_artists = defaultdict(list)

        tier_multipliers = {'tier_1': 4.0, 'tier_2': 2.0, 'tier_3': 1.0, 'tier_4': 0.5}

        for tier_name, artists in tiers.items():
            multiplier = tier_multipliers[tier_name]
            for artist in artists:
                if artist['genres']:
                    for genre in artist['genres']:
                        weight = artist['total_plays'] * multiplier
                        genre_weights[genre] += weight
                        if artist['name'] not in genre_artists[genre]:
                            genre_artists[genre].append(artist['name'])

        # Normalize and sort
        total_weight = sum(genre_weights.values()) or 1
        genre_distribution = []
        for genre, weight in sorted(genre_weights.items(), key=lambda x: x[1], reverse=True):
            genre_distribution.append({
                'genre': genre,
                'percentage': (weight / total_weight) * 100,
                'artists': genre_artists[genre][:5]  # Top 5 artists per genre
            })

        # Build genre clusters
        clusters = self._cluster_genres(genre_distribution[:30])

        return {
            'distribution': genre_distribution[:25],  # Top 25 genres
            'clusters': clusters
        }

    def _cluster_genres(self, genre_list: List[Dict]) -> List[Dict]:
        """Group related genres into clusters."""
        # Define genre family mappings
        genre_families = {
            'indie folk': ['indie folk', 'folk', 'acoustic', 'singer-songwriter', 'folk-pop', 'stomp and holler', 'new americana'],
            'indie/alternative': ['indie', 'indie pop', 'indie rock', 'alternative', 'alt rock', 'modern rock'],
            'pop': ['pop', 'dance pop', 'electropop', 'art pop', 'bedroom pop', 'chamber pop'],
            'country/americana': ['country', 'americana', 'country pop', 'country rock', 'bluegrass', 'folk rock'],
            'rock': ['rock', 'classic rock', 'soft rock', 'adult alternative', 'heartland rock'],
            'r&b/soul': ['r&b', 'soul', 'neo soul', 'contemporary r&b'],
            'electronic': ['electronic', 'edm', 'house', 'synth', 'chillwave', 'indietronica']
        }

        clusters = []
        used_genres = set()

        for family_name, family_genres in genre_families.items():
            cluster_genres = []
            cluster_percentage = 0
            cluster_artists = set()

            for genre_info in genre_list:
                genre = genre_info['genre'].lower()
                # Check if genre belongs to this family
                if any(fg in genre for fg in family_genres) and genre not in used_genres:
                    cluster_genres.append(genre_info['genre'])
                    cluster_percentage += genre_info['percentage']
                    cluster_artists.update(genre_info['artists'][:3])
                    used_genres.add(genre)

            if cluster_genres and cluster_percentage >= 2:  # At least 2% to be included
                clusters.append({
                    'name': family_name,
                    'genres': cluster_genres[:5],
                    'percentage': cluster_percentage,
                    'artists': list(cluster_artists)[:5]
                })

        return sorted(clusters, key=lambda x: x['percentage'], reverse=True)

    def _analyze_listening_patterns(self, artist_data: List[Dict]) -> Dict[str, Any]:
        """Analyze listening behavior patterns."""
        with self.db.session_scope() as session:
            # Total stats
            total_plays = session.query(func.count(PlayHistory.id)).scalar()
            total_artists = len(artist_data)

            # Calculate loyalty index (top 10 artists % of total)
            top_10_plays = sum(a['total_plays'] for a in artist_data[:10])
            loyalty_index = (top_10_plays / total_plays * 100) if total_plays > 0 else 0

            # Calculate discovery rate (unique artists per year)
            artists_per_year = defaultdict(set)
            plays_query = session.query(
                PlayHistory.artist_id,
                extract('year', PlayHistory.played_at).label('year')
            ).all()

            for artist_id, year in plays_query:
                artists_per_year[int(year)].add(artist_id)

            # Count new artists discovered each year
            all_artists = set()
            new_per_year = {}
            for year in sorted(artists_per_year.keys()):
                new_artists = artists_per_year[year] - all_artists
                new_per_year[year] = len(new_artists)
                all_artists.update(artists_per_year[year])

            avg_new_per_year = sum(new_per_year.values()) / len(new_per_year) if new_per_year else 0

            # Discovery openness score (0-100)
            # Higher if discovering many new artists relative to repeating old ones
            repeat_rate = total_plays / total_artists if total_artists > 0 else 0
            discovery_score = min(100, (avg_new_per_year / 50) * 100)  # 50 new artists/year = 100

            # Year-over-year genre consistency
            years = sorted(artist_data[0]['plays_by_year'].keys()) if artist_data and artist_data[0]['plays_by_year'] else []

            return {
                'loyalty_index': loyalty_index,
                'discovery_openness': discovery_score,
                'avg_new_artists_per_year': avg_new_per_year,
                'repeat_rate': repeat_rate,
                'years_covered': years,
                'new_artists_per_year': new_per_year
            }

    def _get_stats_summary(self) -> Dict[str, Any]:
        """Get overall listening statistics."""
        with self.db.session_scope() as session:
            total_plays = session.query(func.count(PlayHistory.id)).scalar()
            total_artists = session.query(func.count(Artist.id)).scalar()
            total_tracks = session.query(func.count(Track.id)).scalar()

            first_play = session.query(func.min(PlayHistory.played_at)).scalar()
            last_play = session.query(func.max(PlayHistory.played_at)).scalar()

            return {
                'total_plays': total_plays,
                'total_artists': total_artists,
                'total_tracks': total_tracks,
                'first_play': first_play,
                'last_play': last_play,
                'data_span_years': (last_play - first_play).days / 365.25 if first_play and last_play else 0
            }

    def _generate_markdown(self, stats: Dict, tiers: Dict, genre_profile: Dict, patterns: Dict) -> str:
        """Generate the markdown profile document."""
        lines = []

        # Header
        lines.append("# Music Taste Profile")
        lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d')} | "
                    f"{stats['total_plays']:,} plays across {stats['data_span_years']:.1f} years | "
                    f"{stats['total_artists']:,} artists*")
        lines.append("")

        # Executive Summary
        lines.append("## Executive Summary")
        lines.append("")
        summary = self._generate_summary(tiers, genre_profile, patterns)
        lines.append(summary)
        lines.append("")

        # Artist Tiers
        lines.append("## Artist Tiers")
        lines.append("")

        # Tier 1
        lines.append("### Tier 1: Must-See Artists")
        lines.append("*Automatic concert recommendations - these are your core artists*")
        lines.append("")
        if tiers['tier_1']:
            lines.append("| Rank | Artist | Plays | Years Active | Peak Period | Genres |")
            lines.append("|------|--------|-------|--------------|-------------|--------|")
            for i, artist in enumerate(tiers['tier_1'], 1):
                genres_str = ', '.join(artist['genres'][:3]) if artist['genres'] else 'Unknown'
                peak = artist['peak_month'] or 'N/A'
                lines.append(f"| {i} | {artist['name']} | {artist['total_plays']:,} | "
                           f"{artist['years_active']}/7 | {peak} | {genres_str} |")
        lines.append("")

        # Tier 2
        lines.append("### Tier 2: Would Definitely Enjoy")
        lines.append("*High-confidence concert recommendations*")
        lines.append("")
        if tiers['tier_2']:
            lines.append("| Artist | Plays | Consistency | Genres |")
            lines.append("|--------|-------|-------------|--------|")
            for artist in tiers['tier_2'][:30]:  # Show top 30
                genres_str = ', '.join(artist['genres'][:3]) if artist['genres'] else 'Unknown'
                lines.append(f"| {artist['name']} | {artist['total_plays']:,} | "
                           f"{artist['years_active']}/7 years | {genres_str} |")
        lines.append("")

        # Tier 3 (condensed)
        lines.append("### Tier 3: Would Likely Enjoy")
        lines.append("*Good matches based on listening patterns*")
        lines.append("")
        if tiers['tier_3']:
            tier3_names = [a['name'] for a in tiers['tier_3'][:50]]
            lines.append(', '.join(tier3_names))
        lines.append("")

        # Genre Profile
        lines.append("## Genre Profile")
        lines.append("")

        lines.append("### Primary Genres")
        lines.append("| Genre | % of Listening | Top Artists |")
        lines.append("|-------|----------------|-------------|")
        for genre in genre_profile['distribution'][:15]:
            artists_str = ', '.join(genre['artists'][:3])
            lines.append(f"| {genre['genre']} | {genre['percentage']:.1f}% | {artists_str} |")
        lines.append("")

        lines.append("### Genre Clusters")
        lines.append("*Related genres grouped together*")
        lines.append("")
        for i, cluster in enumerate(genre_profile['clusters'][:6], 1):
            genres_str = ' + '.join(cluster['genres'][:4])
            artists_str = ', '.join(cluster['artists'][:4])
            lines.append(f"{i}. **{cluster['name'].title()}** ({cluster['percentage']:.0f}%): {genres_str}")
            lines.append(f"   - Artists: {artists_str}")
        lines.append("")

        # Listening Patterns
        lines.append("## Listening Patterns")
        lines.append("")

        lines.append(f"### Loyalty Index: {patterns['loyalty_index']:.0f}/100")
        lines.append(f"Top 10 artists account for {patterns['loyalty_index']:.1f}% of all listening. "
                    f"{'Very loyal listener with deep attachment to favorites.' if patterns['loyalty_index'] > 30 else 'Diverse listener who spreads attention broadly.'}")
        lines.append("")

        lines.append(f"### Discovery Openness: {patterns['discovery_openness']:.0f}/100")
        lines.append(f"Average of {patterns['avg_new_artists_per_year']:.0f} new artists discovered per year. "
                    f"{'Active explorer of new music.' if patterns['discovery_openness'] > 50 else 'Tends to stick with known favorites.'}")
        lines.append("")

        # Concert Recommendation Guidelines
        lines.append("## Concert Recommendation Guidelines")
        lines.append("")
        lines.append("**Instructions for the concert-finding agent:**")
        lines.append("")
        lines.append("1. **Priority 1 - Direct Matches**: Search for any Tier 1 artists touring. These are automatic recommendations regardless of venue size or ticket price.")
        lines.append("")
        lines.append("2. **Priority 2 - Strong Matches**: Tier 2 artists are high-confidence recommendations, especially those with recent listening activity (check last_play dates).")
        lines.append("")

        # Genre-based recommendations
        top_genres = [g['genre'] for g in genre_profile['distribution'][:5]]
        lines.append(f"3. **Priority 3 - Genre Matches**: Search for artists in these genres even if not in the database: {', '.join(top_genres)}")
        lines.append("")

        # Similar artist suggestions
        lines.append("4. **Similar Artists to Search**: Based on the taste profile, these similar artists would likely be enjoyed:")
        similar_artists = self._suggest_similar_artists(tiers, genre_profile)
        lines.append(f"   {', '.join(similar_artists)}")
        lines.append("")

        lines.append("5. **Festival Strategy**: Multi-day festivals with 2+ Tier 1-2 artists are high value. Look for folk/indie/acoustic-focused festivals.")
        lines.append("")

        # Genres to avoid
        lines.append("6. **Lower Priority**: Heavy metal, hard rock, EDM, and hip-hop are underrepresented in listening history. Only recommend if featuring a known artist.")
        lines.append("")

        lines.append("---")
        lines.append("*Profile generated by spotify_sync taste profiler*")

        return '\n'.join(lines)

    def _generate_summary(self, tiers: Dict, genre_profile: Dict, patterns: Dict) -> str:
        """Generate the executive summary paragraph."""
        top_artists = [a['name'] for a in tiers['tier_1'][:5]]
        top_clusters = [c['name'] for c in genre_profile['clusters'][:3]]

        loyalty_desc = "deeply committed" if patterns['loyalty_index'] > 35 else "moderately loyal"
        discovery_desc = "actively discovering new music" if patterns['discovery_openness'] > 50 else "preferring familiar favorites"

        summary = (
            f"You are a {loyalty_desc} listener with strong preferences for "
            f"{', '.join(top_clusters[:2])} music. Your core artists include "
            f"{', '.join(top_artists[:3])}, who have been consistent favorites. "
            f"You show a pattern of {discovery_desc} while maintaining deep engagement "
            f"with artists that resonate with you. Your musical preference centers on "
            f"acoustic, emotionally resonant music with introspective qualities."
        )

        return summary

    def _suggest_similar_artists(self, tiers: Dict, genre_profile: Dict) -> List[str]:
        """Suggest similar artists not in the user's library."""
        # Based on common genre patterns, suggest similar artists
        suggestions = []

        top_genres = [g['genre'].lower() for g in genre_profile['distribution'][:10]]

        # Genre-based suggestions
        similar_artist_map = {
            'indie folk': ['Iron & Wine', 'Fleet Foxes', 'Gregory Alan Isakov', 'The Tallest Man on Earth', 'Lord Huron'],
            'singer-songwriter': ['Phoebe Bridgers', 'Julien Baker', 'Lucy Dacus', 'Adrianne Lenker', 'Maggie Rogers'],
            'folk': ['The Lumineers', 'First Aid Kit', 'Vance Joy', 'Ben Howard', 'Jose Gonzalez'],
            'alternative': ['Hozier', 'Mt. Joy', 'Caamp', 'Rainbow Kitten Surprise', 'Novo Amor'],
            'acoustic': ['City and Colour', 'Passenger', 'Angus & Julia Stone', 'The Paper Kites', 'Dustin Tebbutt'],
            'country': ['Kacey Musgraves', 'Sturgill Simpson', 'Tyler Childers', 'Colter Wall', 'Chris Stapleton'],
            'pop': ['Lorde', 'HAIM', 'Bleachers', 'The 1975', 'Vampire Weekend']
        }

        # Get existing artist names to filter out
        existing = set(a['name'].lower() for a in tiers['tier_1'] + tiers['tier_2'])

        for genre, artists in similar_artist_map.items():
            if any(genre in g for g in top_genres):
                for artist in artists:
                    if artist.lower() not in existing and artist not in suggestions:
                        suggestions.append(artist)

        return suggestions[:15]


def main():
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

    generator = TasteProfileGenerator()
    output_path = generator.generate()

    logger.info(f"\nProfile complete! Written to: {output_path}")
    logger.info("You can now share this profile with a Claude research agent to find concerts.")


if __name__ == "__main__":
    main()
