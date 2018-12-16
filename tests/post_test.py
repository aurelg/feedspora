import pytest
import requests
import requests_cache

from helpers import check_feed

requests_cache.install_cache()


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


def test_post_tag_opts(capsys):
    """
    Test the tag options implementation
    """
    check_feed(capsys, "tag_opts")


def test_post_content_tags(capsys):
    """
    Test the content_tags implementation
    """
    check_feed(capsys, "content_tags")


def test_post_client_shorteners(capsys):
    """
    Test the client URL shortening implementation
    """
    check_feed(capsys, "client_shorteners")
