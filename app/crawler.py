from datetime import datetime
from enum import Enum
import logging
from cloudscraper import create_scraper
from lxml import html as lxml_html

HOST_URL = "https://www.berghain.berlin"
PAGE_MODIFIER = "?page="

EVENT_ITEM_XPATH = '//a[starts-with(@href, "/de/event/")]'
ITEM_DETAIL_XPATH = '//span[@class="font-bold"]'


URL_MAPPING = {
    "kantine": HOST_URL + "/de/program/kantine-am-berghain/",
    "klub": HOST_URL + "/de/program/"
}


def get_event_date_details_for_url(url: str) -> list[tuple[datetime, str]]:
    page_number = 1
    all_events = list[tuple[datetime, str]]()

    while True:
        old_events_count = len(all_events)

        events_from_page = parse_page_page(f"{url}{PAGE_MODIFIER}{page_number}")
        page_number += 1
        if not events_from_page or len(events_from_page) == 0:
            break

        # only add new items which are not already in the list
        for event in events_from_page:
            if event not in all_events:
                all_events.append(event)

        # break if no new items were added
        if len(all_events) == old_events_count:
            break

        if page_number > 99:
            logging.warning(
                f"More than 99 pages found for URL: {url}. Stopping further processing to avoid excessive load.")
            break

    return all_events


def parse_page_page(url: str) -> list[tuple[datetime, str]]:
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
                f"Insufficient details found for event with url: {get_link(item)}. Required at least date and one artist but found {len(details)} items.")
            continue

        date_str = details[0].text_content().strip()
        try:
            event_date = datetime.strptime(date_str, "%d.%m.%Y")
        except ValueError as e:
            logging.error(
                f"Error parsing date '{date_str}' from event with url: {get_link(item)}. Error: {e}")
            continue

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
                        f"Found 'LIVE' tag but no artist name in event with url: {get_link(item)}")

    return result


def get_link(item) -> str:
    result = "N/A"
    link_path = item.xpath("./@href")

    if len(link_path) > 0:
        result = f"{HOST_URL}{link_path[0]}"

    return result
