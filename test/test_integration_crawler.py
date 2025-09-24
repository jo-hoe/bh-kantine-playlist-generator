
import unittest
from app.crawler import get_event_date_details_for_url, KANTINE_PROGRAM_URL


class TestIntegrationCrawler(unittest.TestCase):

    def test_get_event_date_details_for_url(self):
        items = get_event_date_details_for_url(KANTINE_PROGRAM_URL)

        assert len(
            items) > 0, f"Expected at least one artist name for event URL: {KANTINE_PROGRAM_URL}"
