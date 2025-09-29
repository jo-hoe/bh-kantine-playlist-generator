from datetime import datetime
from enum import Enum
import logging
from cloudscraper import create_scraper
from lxml import html as lxml_html

HOST_URL = "https://www.berghain.berlin"

EVENT_ITEM_XPATH = '//a[starts-with(@href, "/de/event/")]'
ITEM_DETAIL_XPATH = '//span[@class="font-bold"]'


URL_MAPPING = {
    "Kantine": HOST_URL + "/de/program/kantine-am-berghain/",
    "Klub": HOST_URL + "/de/program/"
}


def get_event_date_details_for_url(url: str) -> list[tuple[datetime, str]]:
    scraper = create_scraper()
    page = scraper.get(url)
    tree = lxml_html.fromstring(page.content)
    event_items = tree.xpath(EVENT_ITEM_XPATH)

    result = []
    # first item is the date
    # example '22.09.2025'
    # the following items are the artists performing that day
    # we only consider the artist in case the span has another span containing the text "LIVE" inside the item
    for item in event_items:
        # dot is added to ensure relative (sub)xpath from the current item
        details = item.xpath('.' + ITEM_DETAIL_XPATH)

        if len(details) < 2:
            logging.warning(
                f"No details found for event with url: {url}. Required at least date and one artist and found {len(details)} items.")
            return []

        date_str = details[0].text_content().strip()
        try:
            event_date = datetime.strptime(date_str, "%d.%m.%Y")
        except ValueError as e:
            logging.error(
                f"Error parsing date '{date_str}' from event with url: {item.href}. Error: {e}")
            return []

        for detail in details[1:]:
            # dot is added to ensure relative (sub)xpath from the current item
            spans = detail.xpath('.//span')
            # check if there is a span with text "LIVE" next span with artist name
            # we take this as an indication that this is an actual artist which is performing instead of some other text or event name
            if len(spans) > 1 and any("LIVE" in span.text_content().upper() for span in spans):
                artist_name = spans[0].xpath('normalize-space(text()[1])')
                if artist_name:
                    artist_name = artist_name.strip()
                    result.append((event_date, artist_name))
                else:
                    logging.info(
                        f"Found 'LIVE' tag but no artist name in event with url: {item.href}")

    return result
