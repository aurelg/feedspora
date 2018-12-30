#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import re

import pytest

from feedspora.diaspora_client import DiaspyClient
from feedspora.facebook_client import FacebookClient
from feedspora.feedspora_runner import FeedSpora
from feedspora.linkedin_client import LinkedInClient
from feedspora.mastodon_client import MastodonClient
from feedspora.shaarpy_client import ShaarpyClient
from feedspora.tweepy_client import TweepyClient
from feedspora.wordpress_client import WPClient


@pytest.fixture
def entry_generator():
    f = 'feed.atom'
    fs = FeedSpora()
    soup = fs.retrieve_feed_soup(f)

    return fs.parse_atom(soup)


@pytest.fixture
def expected():
    with open('expected.json') as f:
        return json.load(f)


def check(client, entry_generator, expected, check_entry):

    entries = [x for x in entry_generator][::-1]
    assert len(entries) > 0
    assert len(entries) == len(expected)

    for entry, expect in zip(entries, expected):
        # Check that items in the feed read from disk and the expected
        # datastructure are the same
        expect_source = expect['source']
        assert entry.title == expect_source['title']
        assert entry.link == expect_source['link']
        # Important to test these in a list context, as ordering matters
        assert entry.tags['title'] == expect_source['tags']['title']
        assert entry.tags['content'] == expect_source['tags']['content']
        assert entry.tags['category'] == expect_source['tags']['category']
        client_key = str(type(client)).split('.')[-1][:-2]
        # Check that expected values are defined for 'title' and 'link'
        expect_key = client_key if client_key in expect else 'source'
        assert expect[expect_key]['title'] != ''
        assert expect[expect_key]['link'] != ''
        # Test the client post return
        returned = client.post(entry)
        assert returned is not None
        check_entry(returned, expect[expect_key])


def test_DiaspyClient(entry_generator, expected):
    def new_init(obj):
        class fake_provider():
            def post(self, text, aspect_ids=None, provider_display_name=None):
                return {
                    'text': text,
                    'aspect_ids': aspect_ids,
                    'provider_display_name': provider_display_name
                }

        obj.stream = fake_provider()
        obj.set_common_opts({})

    def check_entry(returned, expect):
        assert returned['aspect_ids'] == 'public'
        assert returned['provider_display_name'] == 'FeedSpora'
        assert returned['text'].startswith("[{}]({})".format(
            expect['title'], expect['link']))

        for i in ['#{}'.format(k) for k in expect['tags']['title'] + \
                                           expect['tags']['content'] + \
                                           expect['tags']['category']]:
            assert returned['text'].index(i) > -1

    old_init = DiaspyClient.__init__
    DiaspyClient.__init__ = new_init
    check(DiaspyClient(), entry_generator, expected, check_entry)
    DiaspyClient.__init__ = old_init


def test_TweepyClient(entry_generator, expected):
    def new_init(obj):
        class fake_provider():
            def update_status(self, text):
                return {'text': text}

        obj._api = fake_provider()
        obj._link_cost = 23
        obj._max_len = 280
        obj.set_common_opts({})

    def check_entry(returned, expected):
        # Check the length of the text - link + 22 (twitter cost)
        returned_text = returned['text'][:returned['text'].rfind(' ')]
        putative_urls = re.findall(r'[a-zA-Z0-9]+\.[a-zA-Z]{2,3}',
                                   returned_text)
        # Infer the 'inner links' Twitter may charge length for
        adjust_with_inner_links = 23 + \
            sum([23 - len(u) for u in putative_urls])
        detected_length = len(returned_text) + adjust_with_inner_links
        assert not detected_length > 280

        # Subtract additional 4 for the potential '... ' separator
        title_length = 280 - len(expected['link']) - \
                       adjust_with_inner_links - 4
        title_start = expected['title'][:title_length]
        title_start = title_start[:title_start.rfind(' ')]
        assert returned['text'].startswith(title_start)
        assert returned['text'].endswith(expected['link'])

        for k in expected['tags']['title'] + \
                 expected['tags']['content'] + \
                 expected['tags']['category']:
            target = ' #{}'.format(k)
            assert returned['text'].index(target) > -1

    old_init = TweepyClient.__init__
    TweepyClient.__init__ = new_init
    check(TweepyClient(), entry_generator, expected, check_entry)
    TweepyClient.__init__ = old_init


def test_MastodonClient(entry_generator, expected):
    def new_init(obj):
        class fake_provider():
            def status_post(self, text, visibility=None):
                return {'text': text, 'visibility': visibility}

        obj._mastodon = fake_provider()
        obj._visibility = 'public'
        obj._delay = 0
        obj.set_common_opts({})

    def check_entry(returned, expected):
        assert returned['text'].index(expected['title']) > -1
        assert returned['text'].index(expected['link']) > -1
        assert not len(returned['text']) > 500

        for k in expected['tags']['title'] + \
                 expected['tags']['content'] + \
                 expected['tags']['category']:
            assert returned['text'].index(' #{}'.format(k)) > -1

    old_init = MastodonClient.__init__
    MastodonClient.__init__ = new_init
    check(MastodonClient(), entry_generator, expected, check_entry)
    MastodonClient.__init__ = old_init


def test_LinkedInClient(entry_generator, expected):
    def new_init(obj):
        class fake_provider():
            def submit_share(self, **kwargs):

                return {
                    'updateUrl': 'http://www.bogus.com/fakeyResponse',
                    'comment': kwargs['comment'],
                    'title': kwargs['title'],
                    'description': kwargs['description'],
                    'submitted_url': kwargs['submitted_url']
                }

        obj._linkedin = fake_provider()
        obj.set_common_opts({})

    def check_entry(returned, expected):
        assert returned['comment'].index(expected['title']) > -1
        assert returned['title'].index(expected['title']) > -1
        assert returned['description'].index(expected['title']) > -1
        assert returned['submitted_url'].index(expected['link']) > -1

        for k in expected['tags']['title'] + \
                 expected['tags']['content'] + \
                 expected['tags']['category']:
            assert returned['comment'].index(' #{}'.format(k)) > -1

    old_init = LinkedInClient.__init__
    LinkedInClient.__init__ = new_init
    check(LinkedInClient(), entry_generator, expected, check_entry)
    LinkedInClient.__init__ = old_init


def test_ShaarpyClient(entry_generator, expected):
    def new_init(obj):
        class fake_provider():
            def post_link(self, link, tags, title=None, desc=None):
                return {
                    'link': link,
                    'tags': tags,
                    'title': title,
                    'desc': desc
                }

        obj._shaarpy = fake_provider()
        obj.set_common_opts({})

    def check_entry(returned, expected):
        assert returned['title'].index(expected['title']) > -1
        assert returned['link'].index(expected['link']) > -1
        assert returned['tags'] == expected['tags']['title'] + \
                                   expected['tags']['content'] + \
                                   expected['tags']['category']

    old_init = ShaarpyClient.__init__
    ShaarpyClient.__init__ = new_init
    check(ShaarpyClient(), entry_generator, expected, check_entry)
    ShaarpyClient.__init__ = old_init


def test_FacebookClient(entry_generator, expected):
    def new_init(obj):
        class fake_provider():
            def put_object(self, post_id, area, **attachment):
                return {
                    'id': post_id,
                    'link': attachment['link'],
                    'message': attachment['message']
                }

        obj._graph = fake_provider()
        obj.set_common_opts({'post_to_id': '411'})

    def check_entry(returned, expected):
        assert returned['message'].index(expected['title']) > -1
        assert returned['message'].index(expected['link']) > -1

        for k in expected['tags']['title'] + \
                 expected['tags']['content'] + \
                 expected['tags']['category']:
            assert returned['message'].index(' #{}'.format(k)) > -1, \
                "{} not found in {}".format(' #{}'.format(k), returned['message'])

    old_init = FacebookClient.__init__
    FacebookClient.__init__ = new_init
    check(FacebookClient(), entry_generator, expected, check_entry)
    FacebookClient.__init__ = old_init
