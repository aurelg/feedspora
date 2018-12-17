"""
Test Atom/RSS feed retrieval and parsing
"""

import responses

from feedspora.feedspora_runner import FeedSpora


# pylint: disable=no-member
@responses.activate
# pylint: enable=no-member
def test_retrieve_feed_soup():
    """
    Test file/url retrieval
    """
    req2file_mapping = {
        "https://my.framasoft.org/u/aurelieng/?do=rss": "feed.rss",
        "http://aurelien.latitude77.org/feed.atom": "feed.atom",
    }

    for req, filename in req2file_mapping.items():
        with open(filename) as fhandler:
            responses.add(responses.GET, req, body=fhandler.read(), status=200)

    sources = [
        "feed.atom", "feed.rss",
        "https://my.framasoft.org/u/aurelieng/?do=rss",
        "http://aurelien.latitude77.org/feed.atom"
    ]
    feedspora = FeedSpora()

    for source in sources:
        feedspora.retrieve_feed_soup(source)


def test_atom_parser():
    """
    Test atom parsing
    """
    filename = "feed.atom"
    feedspora = FeedSpora()
    soup = feedspora.retrieve_feed_soup(filename)
    gen = feedspora.parse_atom(soup)
    assert [_ for _ in gen]


def test_rss_parser():
    """
    test RSS parsing
    """
    filename = "feed.rss"
    feedspora = FeedSpora()
    soup = feedspora.retrieve_feed_soup(filename)
    gen = feedspora.parse_rss(soup)
    assert [_ for _ in gen]
