from datetime import datetime
import logging
import re
from cloudscraper import create_scraper
from lxml import html as lxml_html

HOST_URL = "https://www.berghain.berlin"
BASE_URL = HOST_URL + "/de/program/kantine-am-berghain/"

# xpath to href of /a elements which start with /de/event/*
EVENT_ITEM_XPATH = '//a[starts-with(@href, "/de/event/")]/@href'
ITEM_DETAIL_XPATH = '//span[@class="font-bold"]'


def get_all_event_date_urls() -> list[str]:
    scraper = create_scraper()
    page = scraper.get(BASE_URL)
    tree = lxml_html.fromstring(page.content)
    event_urls = tree.xpath(EVENT_ITEM_XPATH)
    full_event_urls = [HOST_URL + url for url in event_urls]
    return full_event_urls


def get_event_date_details(event_url: str) -> list[tuple[datetime, str]]:
    # returns list of (datetime, artist_name)
    # date is the date when the artist performs
    # and event date can have multiple artists performing

    scraper = create_scraper()
    page = scraper.get(event_url)

    tree = lxml_html.fromstring(page.content)
    # first item is the date
    # example '22.09.2025'
    # the following items are the artists performing that day
    # we only consider the artist in case the span has another span containing the text "LIVE" inside the item
    details = tree.xpath(ITEM_DETAIL_XPATH)

    if len(details) < 2:
        logging.warning(
            f"No details found for event URL: {event_url}. Required at least date and one artist and found {len(details)} items.")
        return []

    date_str = details[0].text_content().strip()
    try:
        event_date = datetime.strptime(date_str, "%d.%m.%Y")
    except ValueError as e:
        logging.error(
            f"Error parsing date '{date_str}' from event URL: {event_url}. Error: {e}")
        return []

    result = []
    for detail in details[1:]:
        # check if there is a span with text "LIVE" inside
        if detail.xpath('.//span[contains(translate(., "abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXYZ"), "LIVE")]'):
            artist_name = detail.xpath('normalize-space(text()[1])')
            if artist_name:
                artist_name = artist_name.strip()
                result.append((event_date, artist_name))
            else:
                logging.info(
                    f"Found 'LIVE' tag but no artist name in event URL: {event_url}")

    return result
