import unittest
from unittest.mock import Mock, patch
from datetime import datetime
from app.playlist.abstract_playlist_generator import AbstractPlaylistGenerator


class MockPlaylistGenerator(AbstractPlaylistGenerator):
    """Mock implementation for testing"""
    
    def __init__(self, playlist_name: str, maximum_tracks_per_artist: int):
        super().__init__(playlist_name, maximum_tracks_per_artist)
        self.playlist_id = "test_playlist_id"
        self.track_ids_by_artist = {}
        self.updated_track_ids = None
        
    def get_playlist_id_by_name(self, playlist_name: str) -> str | None:
        return self.playlist_id
    
    def get_top_tracks_for_artist(self, artist_name: str, maximum_tracks_per_artist: int) -> list[str]:
        return self.track_ids_by_artist.get(artist_name, [])
    
    def update_playlist(self, playlist_id: str, list_of_track_ids: list[str]) -> bool:
        self.updated_track_ids = list_of_track_ids
        return True
    
    def generate_playlist(self, playlist_name: str) -> bool:
        return True


class TestPlaylistGenerator(unittest.TestCase):
    
    def test_process_filters_duplicate_tracks(self):
        """Test that duplicate track IDs are filtered out"""
        generator = MockPlaylistGenerator("Test Playlist", 3)
        
        # Set up artists with some duplicate tracks
        generator.track_ids_by_artist = {
            "Artist 1": ["track1", "track2", "track3"],
            "Artist 2": ["track2", "track4", "track5"],  # track2 is duplicate
            "Artist 3": ["track1", "track6", "track7"],  # track1 is duplicate
        }
        
        artists_performance_dates = [
            (datetime(2025, 1, 1), "Artist 1"),
            (datetime(2025, 1, 2), "Artist 2"),
            (datetime(2025, 1, 3), "Artist 3"),
        ]
        
        result = generator.process(artists_performance_dates)
        
        self.assertTrue(result)
        self.assertIsNotNone(generator.updated_track_ids)
        
        # Should have 7 unique tracks (track1, track2 appear twice but should only be included once)
        expected_tracks = ["track1", "track2", "track3", "track4", "track5", "track6", "track7"]
        self.assertEqual(len(generator.updated_track_ids), len(expected_tracks))
        self.assertEqual(set(generator.updated_track_ids), set(expected_tracks))
        
    def test_process_preserves_order_with_duplicates(self):
        """Test that the order is preserved when filtering duplicates"""
        generator = MockPlaylistGenerator("Test Playlist", 2)
        
        # Set up artists where duplicates appear later
        generator.track_ids_by_artist = {
            "Artist 1": ["track1", "track2"],
            "Artist 2": ["track3", "track1"],  # track1 appears again
            "Artist 3": ["track4", "track2"],  # track2 appears again
        }
        
        artists_performance_dates = [
            (datetime(2025, 1, 1), "Artist 1"),
            (datetime(2025, 1, 2), "Artist 2"),
            (datetime(2025, 1, 3), "Artist 3"),
        ]
        
        result = generator.process(artists_performance_dates)
        
        self.assertTrue(result)
        # First occurrence should be kept, preserving order
        # Expected: track1, track2, track3, track4
        expected_tracks = ["track1", "track2", "track3", "track4"]
        self.assertEqual(generator.updated_track_ids, expected_tracks)
        
    def test_process_no_duplicates(self):
        """Test that processing works correctly when there are no duplicates"""
        generator = MockPlaylistGenerator("Test Playlist", 3)
        
        generator.track_ids_by_artist = {
            "Artist 1": ["track1", "track2", "track3"],
            "Artist 2": ["track4", "track5", "track6"],
        }
        
        artists_performance_dates = [
            (datetime(2025, 1, 1), "Artist 1"),
            (datetime(2025, 1, 2), "Artist 2"),
        ]
        
        result = generator.process(artists_performance_dates)
        
        self.assertTrue(result)
        expected_tracks = ["track1", "track2", "track3", "track4", "track5", "track6"]
        self.assertEqual(generator.updated_track_ids, expected_tracks)
        
    def test_process_all_duplicates(self):
        """Test processing when all artists have the same tracks"""
        generator = MockPlaylistGenerator("Test Playlist", 2)
        
        generator.track_ids_by_artist = {
            "Artist 1": ["track1", "track2"],
            "Artist 2": ["track1", "track2"],
            "Artist 3": ["track1", "track2"],
        }
        
        artists_performance_dates = [
            (datetime(2025, 1, 1), "Artist 1"),
            (datetime(2025, 1, 2), "Artist 2"),
            (datetime(2025, 1, 3), "Artist 3"),
        ]
        
        result = generator.process(artists_performance_dates)
        
        self.assertTrue(result)
        # Should only have 2 tracks despite 3 artists
        expected_tracks = ["track1", "track2"]
        self.assertEqual(generator.updated_track_ids, expected_tracks)


if __name__ == '__main__':
    unittest.main()
