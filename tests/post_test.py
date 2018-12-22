import pytest
import requests
import requests_cache

from helpers import check_feed

requests_cache.install_cache()


def test_post_diaspora_basic(capsys):
    """
    Test the basic operation of the Diaspora client
    """
    check_feed(capsys, "diaspora_basic")


def test_post_facebook_basic(capsys):
    """
    Test the basic operation of the Facebook client
    """
    check_feed(capsys, "facebook_basic")


def test_post_linkedin_basic(capsys):
    """
    Test the basic operation of the LinkedIn client
    """
    check_feed(capsys, "linkedin_basic")


def test_post_mastodon_basic(capsys):
    """
    Test the basic operation of the Mastodon client
    """
    check_feed(capsys, "mastodon_basic")


def test_post_shaarpy_basic(capsys):
    """
    Test the basic operation of the Shaarli client
    """
    check_feed(capsys, "shaarpy_basic")


def test_post_tweepy_basic(capsys):
    """
    Test the basic operation of the Twitter client
    """
    check_feed(capsys, "tweepy_basic")


def test_post_wordpress_basic(capsys):
    """
    Test the basic operation of the WordPress client
    """
    check_feed(capsys, "wordpress_basic")


def test_post_diaspora_full(capsys):
    """
    Test the full operation of the Diaspora client
    """
    check_feed(capsys, "diaspora_full")


def test_post_facebook_full(capsys):
    """
    Test the full operation of the Facebook client
    """
    check_feed(capsys, "facebook_full")


def test_post_linkedin_full(capsys):
    """
    Test the full operation of the LinkedIn client
    """
    check_feed(capsys, "linkedin_full")


def test_post_mastodon_full(capsys):
    """
    Test the full operation of the Mastodon client
    """
    check_feed(capsys, "mastodon_full")


def test_post_shaarpy_full(capsys):
    """
    Test the full operation of the Shaarli client
    """
    check_feed(capsys, "shaarpy_full")


def test_post_tweepy_full(capsys):
    """
    Test the full operation of the Twitter client
    """
    check_feed(capsys, "tweepy_full")


def test_post_wordpress_full(capsys):
    """
    Test the full operation of the WordPress client
    """
    check_feed(capsys, "wordpress_full")


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


def test_post_prefix_suffix(capsys):
    """
    Test the client post prefix/suffix implementation
    """
    check_feed(capsys, "prefix_suffix")
