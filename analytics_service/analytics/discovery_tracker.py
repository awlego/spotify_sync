"""
Track music discovery patterns and build artist relationship networks
"""
from typing import Dict, List, Tuple, Optional, Any, Set
import networkx as nx
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import numpy as np
from loguru import logger
import sys
from pathlib import Path
import json

# Import shared components
sys.path.append(str(Path(__file__).parent.parent.parent))
from shared import DatabaseManager, Track, Artist, PlayHistory
from sqlalchemy import func, and_


class DiscoveryTracker:
    """Analyzes music discovery patterns and artist relationships"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.graph = nx.Graph()
        
    def build_discovery_network(self, user_id: Optional[int] = None,
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Build a network graph of artist discoveries and relationships
        """
        with self.db.session_scope() as session:
            # Get all plays in chronological order
            query = session.query(PlayHistory).join(Track).join(Artist)
            
            if user_id:
                query = query.filter(PlayHistory.user_id == user_id)
            
            if start_date:
                query = query.filter(PlayHistory.played_at >= start_date)
            else:
                # Default to last year
                start_date = datetime.now() - timedelta(days=365)
                query = query.filter(PlayHistory.played_at >= start_date)
            
            if end_date:
                query = query.filter(PlayHistory.played_at <= end_date)
            
            plays = query.order_by(PlayHistory.played_at).all()
            
            # Build discovery timeline and relationships
            artist_discoveries = {}  # artist_id -> first_play_date
            artist_plays = defaultdict(list)  # artist_id -> list of play times
            artist_info = {}  # artist_id -> artist details
            
            # Track discoveries
            for play in plays:
                artist_id = play.track.artist.id
                artist_name = play.track.artist.name
                
                if artist_id not in artist_discoveries:
                    artist_discoveries[artist_id] = play.played_at
                    artist_info[artist_id] = {
                        'id': artist_id,
                        'name': artist_name,
                        'discovered': play.played_at.isoformat(),
                        'first_track': play.track.name
                    }
                
                artist_plays[artist_id].append(play.played_at)
            
            # Calculate artist metrics
            nodes = []
            for artist_id, info in artist_info.items():
                play_dates = artist_plays[artist_id]
                
                # Calculate engagement metrics
                total_plays = len(play_dates)
                days_active = (play_dates[-1] - play_dates[0]).days + 1
                play_density = total_plays / max(days_active, 1)
                
                # Calculate "importance" using PageRank-like metric
                importance = min(1.0, total_plays / 100.0)  # Normalize to 0-1
                
                nodes.append({
                    'id': str(artist_id),
                    'name': info['name'],
                    'discovered': info['discovered'],
                    'first_track': info['first_track'],
                    'play_count': total_plays,
                    'days_active': days_active,
                    'play_density': round(play_density, 2),
                    'importance': round(importance, 3),
                    'size': max(5, min(50, total_plays))  # Node size based on plays
                })
            
            # Build relationships
            edges = self._build_artist_relationships(plays, artist_discoveries)
            
            # Find discovery paths
            discovery_chains = self._find_discovery_chains(plays, artist_discoveries)
            
            # Calculate network statistics
            stats = self._calculate_network_stats(nodes, edges)
            
            return {
                'nodes': nodes,
                'edges': edges,
                'discovery_chains': discovery_chains,
                'stats': stats
            }
    
    def _build_artist_relationships(self, plays: List[PlayHistory], 
                                   discoveries: Dict[int, datetime]) -> List[Dict[str, Any]]:
        """
        Build relationships between artists based on listening patterns
        """
        edges = []
        edge_weights = defaultdict(lambda: defaultdict(float))
        
        # Time-based relationships (played in same session)
        session_window = timedelta(hours=2)  # 2-hour session window
        
        for i in range(len(plays) - 1):
            current_play = plays[i]
            next_play = plays[i + 1]
            
            # Check if plays are in same session
            time_diff = next_play.played_at - current_play.played_at
            if time_diff <= session_window:
                artist1_id = current_play.track.artist.id
                artist2_id = next_play.track.artist.id
                
                if artist1_id != artist2_id:
                    # Weight based on time proximity
                    weight = 1.0 - (time_diff.total_seconds() / session_window.total_seconds())
                    edge_weights[artist1_id][artist2_id] += weight
        
        # Discovery relationships (one artist led to another)
        discovery_window = timedelta(days=7)  # 7-day window for discovery influence
        
        artist_list = sorted(discoveries.items(), key=lambda x: x[1])  # Sort by discovery date
        
        for i in range(len(artist_list) - 1):
            current_artist_id, current_date = artist_list[i]
            
            for j in range(i + 1, min(i + 10, len(artist_list))):  # Check next 10 discoveries
                next_artist_id, next_date = artist_list[j]
                
                time_diff = next_date - current_date
                if time_diff <= discovery_window:
                    # Discovery relationship weight
                    weight = 1.0 - (time_diff.total_seconds() / discovery_window.total_seconds())
                    edge_weights[current_artist_id][next_artist_id] += weight * 0.5
        
        # Convert to edge list
        for artist1_id, connections in edge_weights.items():
            for artist2_id, weight in connections.items():
                if weight > 0.1:  # Threshold for meaningful connections
                    edges.append({
                        'source': str(artist1_id),
                        'target': str(artist2_id),
                        'weight': round(weight, 3),
                        'type': 'discovery' if weight < 1.0 else 'session'
                    })
        
        return edges
    
    def _find_discovery_chains(self, plays: List[PlayHistory],
                              discoveries: Dict[int, datetime]) -> List[Dict[str, Any]]:
        """
        Find chains of artist discoveries (A led to B led to C)
        """
        chains = []
        
        # Build a graph for path finding
        G = nx.DiGraph()
        
        # Add nodes with discovery dates
        for artist_id, discovery_date in discoveries.items():
            G.add_node(artist_id, discovered=discovery_date)
        
        # Add edges based on discovery order and time proximity
        discovery_window = timedelta(days=14)
        artist_list = sorted(discoveries.items(), key=lambda x: x[1])
        
        for i in range(len(artist_list) - 1):
            current_id, current_date = artist_list[i]
            
            for j in range(i + 1, min(i + 5, len(artist_list))):
                next_id, next_date = artist_list[j]
                
                if next_date - current_date <= discovery_window:
                    G.add_edge(current_id, next_id)
        
        # Find interesting paths
        if len(G.nodes) > 2:
            # Find longest paths (discovery journeys)
            for node in G.nodes:
                if G.out_degree(node) == 0:  # End nodes
                    # Find all paths to this node
                    for start_node in G.nodes:
                        if G.in_degree(start_node) == 0 and start_node != node:  # Start nodes
                            try:
                                paths = list(nx.all_simple_paths(G, start_node, node, cutoff=5))
                                for path in paths:
                                    if len(path) >= 3:  # At least 3 artists in chain
                                        chain_info = []
                                        for artist_id in path:
                                            artist = next(p.track.artist for p in plays 
                                                        if p.track.artist.id == artist_id)
                                            chain_info.append({
                                                'id': artist_id,
                                                'name': artist.name,
                                                'discovered': discoveries[artist_id].isoformat()
                                            })
                                        
                                        chains.append({
                                            'length': len(path),
                                            'artists': chain_info
                                        })
                            except nx.NetworkXNoPath:
                                continue
        
        # Sort by chain length and return top chains
        chains.sort(key=lambda x: x['length'], reverse=True)
        return chains[:10]  # Return top 10 chains
    
    def _calculate_network_stats(self, nodes: List[Dict[str, Any]], 
                                edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate network statistics and insights
        """
        # Build NetworkX graph for analysis
        G = nx.Graph()
        
        for node in nodes:
            G.add_node(node['id'], **node)
        
        for edge in edges:
            G.add_edge(edge['source'], edge['target'], weight=edge['weight'])
        
        stats = {
            'total_artists': len(nodes),
            'total_connections': len(edges),
            'network_density': round(nx.density(G), 3) if len(nodes) > 1 else 0,
            'discovery_rate': self._calculate_discovery_rate(nodes),
            'exploration_score': self._calculate_exploration_score(nodes, edges)
        }
        
        # Find most connected artists (hubs)
        if len(nodes) > 0:
            degree_centrality = nx.degree_centrality(G)
            top_hubs = sorted(degree_centrality.items(), key=lambda x: x[1], reverse=True)[:5]
            stats['discovery_hubs'] = [
                {
                    'artist': next(n['name'] for n in nodes if n['id'] == hub[0]),
                    'centrality': round(hub[1], 3)
                }
                for hub in top_hubs
            ]
        
        # Find isolated artists (unique discoveries)
        isolated = [n for n in G.nodes() if G.degree(n) == 0]
        stats['unique_discoveries'] = len(isolated)
        
        return stats
    
    def _calculate_discovery_rate(self, nodes: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Calculate how discovery rate changes over time
        """
        if not nodes:
            return {'average': 0, 'trend': 'stable'}
        
        # Sort by discovery date
        sorted_nodes = sorted(nodes, key=lambda x: x['discovered'])
        
        # Calculate monthly discovery rate
        monthly_discoveries = defaultdict(int)
        for node in sorted_nodes:
            month = datetime.fromisoformat(node['discovered']).strftime('%Y-%m')
            monthly_discoveries[month] += 1
        
        rates = list(monthly_discoveries.values())
        avg_rate = sum(rates) / len(rates) if rates else 0
        
        # Determine trend
        if len(rates) >= 3:
            recent_avg = sum(rates[-3:]) / 3
            older_avg = sum(rates[:-3]) / max(len(rates) - 3, 1)
            
            if recent_avg > older_avg * 1.2:
                trend = 'increasing'
            elif recent_avg < older_avg * 0.8:
                trend = 'decreasing'
            else:
                trend = 'stable'
        else:
            trend = 'insufficient_data'
        
        return {
            'average': round(avg_rate, 1),
            'trend': trend,
            'monthly_rates': dict(monthly_discoveries)
        }
    
    def _calculate_exploration_score(self, nodes: List[Dict[str, Any]], 
                                   edges: List[Dict[str, Any]]) -> float:
        """
        Calculate a score representing musical exploration diversity
        """
        if not nodes:
            return 0.0
        
        # Factors for exploration score
        artist_diversity = min(len(nodes) / 100.0, 1.0)  # More artists = higher score
        
        # Connection diversity (not too sparse, not too dense)
        if len(nodes) > 1:
            actual_edges = len(edges)
            possible_edges = len(nodes) * (len(nodes) - 1) / 2
            edge_ratio = actual_edges / possible_edges if possible_edges > 0 else 0
            # Optimal is around 0.3 (not too sparse, not too dense)
            connection_score = 1.0 - abs(0.3 - edge_ratio) / 0.3
        else:
            connection_score = 0.0
        
        # Discovery consistency (regular discoveries vs. bursts)
        discovery_dates = [datetime.fromisoformat(n['discovered']) for n in nodes]
        if len(discovery_dates) > 1:
            time_span = (discovery_dates[-1] - discovery_dates[0]).days
            avg_gap = time_span / len(discovery_dates)
            # Calculate variance in discovery gaps
            gaps = [(discovery_dates[i+1] - discovery_dates[i]).days 
                   for i in range(len(discovery_dates)-1)]
            if gaps:
                gap_variance = np.var(gaps)
                consistency_score = 1.0 / (1.0 + gap_variance / 100.0)  # Lower variance = higher score
            else:
                consistency_score = 0.5
        else:
            consistency_score = 0.5
        
        # Combine scores
        exploration_score = (artist_diversity * 0.4 + 
                           connection_score * 0.3 + 
                           consistency_score * 0.3)
        
        return round(exploration_score * 100, 1)  # Return as percentage
    
    def get_artist_discovery_path(self, artist1_name: str, artist2_name: str,
                                 user_id: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Find the discovery path between two artists
        """
        with self.db.session_scope() as session:
            # Get artist IDs
            artist1 = session.query(Artist).filter_by(name=artist1_name).first()
            artist2 = session.query(Artist).filter_by(name=artist2_name).first()
            
            if not artist1 or not artist2:
                return None
            
            # Build network
            network_data = self.build_discovery_network(user_id)
            
            # Create graph
            G = nx.Graph()
            for edge in network_data['edges']:
                G.add_edge(edge['source'], edge['target'], weight=edge['weight'])
            
            # Find shortest path
            try:
                path = nx.shortest_path(G, str(artist1.id), str(artist2.id))
                
                # Get details for each artist in path
                path_details = []
                for artist_id in path:
                    node = next(n for n in network_data['nodes'] if n['id'] == artist_id)
                    path_details.append(node)
                
                return path_details
            except nx.NetworkXNoPath:
                return None