import pytest

from helpers import check_feed


def test_post_basic(capsys):
    """
    Test the atom configuration / feed
    """
    check_feed(capsys, "basic")


def test_post_full(capsys):
    """
    Test the RSS configuration / feed
    """
    check_feed(capsys, "full")


def test_post_title_tags(capsys):
    """
    Test the RSS configuration / feed
    """
    check_feed(capsys, "title_tags")
