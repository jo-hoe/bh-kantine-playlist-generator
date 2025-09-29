
import unittest
from app.crawler import get_event_date_details_for_url, URL_MAPPING


class TestIntegrationCrawler(unittest.TestCase):

    def test_get_event_date_details_for_kantine(self):
        self.get_event_date_details_for_url("Kantine")

    def test_get_event_date_details_for_klub(self):
        self.get_event_date_details_for_url("Klub")

    def get_event_date_details_for_url(self, key: str):
        items = get_event_date_details_for_url(URL_MAPPING[key])

        assert len(
            items) > 0, f"Expected at least one artist name for event URL: {URL_MAPPING[key]}"
