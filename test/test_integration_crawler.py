
import unittest
from app.crawler import get_all_event_date_urls, get_event_date_details


class TestIntegrationCrawler(unittest.TestCase):

    def test_get_all_event_date_urls(self):
        items = get_all_event_date_urls()

        assert len(items) > 2, "Expected more than 2 event URLs"
        assert len(items) == len(
            set(items)), "Expected all event URLs to be unique"

    def test_get_event_date_details(self):
        items = get_all_event_date_urls()
        for item in items:
            event_details = get_event_date_details(item)
            if len(event_details) > 0:
                assert len(
                    event_details) > 0, f"Expected at least one artist name for event URL: {item}"
                return  # return if we found at least one event with artist names

        self.fail("No event URL with artist names found")
