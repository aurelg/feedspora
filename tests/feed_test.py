import pytest

from helpers import check_feed


def test_feed_atom(capsys):
    """
    Test the atom configuration / feed
    """
    check_feed(capsys, "atom")


def test_feed_rss(capsys):
    """
    Test the RSS configuration / feed
    """
    check_feed(capsys, "rss")


def test_feed_opts(capsys):
    """
    Test the feed option functionality
    """
    check_feed(capsys, "feed_opts")
