#!/usr/bin/env python

from feedspora.feedspora_runner import FeedSpora


TBD = 'tests/'


def test_retrieve_feed_soup():
    # FIXME should also test URLs
    sources = [TBD+'feed.atom', TBD+'feed.rss',
               'https://my.framasoft.org/u/aurelieng/?do=rss',
               'http://aurelien.latitude77.org/feed.atom']
    fs = FeedSpora()
    for s in sources:
        fs.retrieve_feed_soup(s)


def test_atom_parser():
    f = 'feed.atom'
    fs = FeedSpora()
    soup = fs.retrieve_feed_soup(TBD+f)
    gen = fs.parse_atom(soup)
    assert len([_ for _ in gen]) > 0


def test_rss_parser():
    f = 'feed.rss'
    fs = FeedSpora()
    soup = fs.retrieve_feed_soup(TBD+f)
    gen = fs.parse_rss(soup)
    assert len([_ for _ in gen]) > 0
