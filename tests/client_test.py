#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import pytest
import json

from feedspora.feedspora_runner import FeedSpora
from feedspora.feedspora_runner import DiaspyClient
from feedspora.feedspora_runner import TweepyClient
from feedspora.feedspora_runner import FacebookClient
from feedspora.feedspora_runner import MastodonClient
from feedspora.feedspora_runner import ShaarpyClient
from feedspora.feedspora_runner import LinkedInClient

TBD = 'tests/'


@pytest.fixture
def entry_generator():
    f = 'feed.atom'
    fs = FeedSpora()
    soup = fs.retrieve_feed_soup(TBD+f)
    return fs.parse_atom(soup)


@pytest.fixture
def expected():
    with open('tests/expected.json') as f:
        return json.load(f)


def check(client, entry_generator, expected, check_entry):

    entries = [x for x in entry_generator][::-1]
    assert len(entries) > 0
    assert len(entries) == len(expected)
    for entry, expect in zip(entries, expected):
        # Check that items in the feed read from disk and the expected
        # datastructure are the same
        source = expect['source']
        assert entry.title == source['title']
        assert entry.link == source['link']
        assert set(entry.keywords) == set(source['keywords'])
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
                return {'text': text,
                        'aspect_ids': aspect_ids,
                        'provider_display_name': provider_display_name}
        obj.stream = fake_provider()
        obj.keywords = []

    def check_entry(returned, expect):
        assert returned['aspect_ids'] == 'public'
        assert returned['provider_display_name'] == 'FeedSpora'
        assert returned['text'].startswith("[{}]({})".format(expect['title'],
                                                             expect['link']))
        for i in ['#{}'.format(k) for k in expect['keywords']]:
            assert returned['text'].index(i) > -1

    DiaspyClient.__init__ = new_init
    check(DiaspyClient(), entry_generator, expected, check_entry)


def test_TweepyClient(entry_generator, expected):

    def new_init(obj):
        class fake_provider():
            def update_status(self, text):
                return {'text': text}
        obj._api = fake_provider()
        obj._link_cost = 22
        obj._max_len = 140

    def check_entry(returned, expected):
        assert returned['text'].startswith(expected['title'])
        assert returned['text'].endswith(expected['link'])
        # Check the length of the text - link + 22 (twitter cost)
        returned_text = returned['text'][:returned['text'].rfind(' ')]
        putative_urls = re.findall('[a-zA-Z0-9]+\.[a-zA-Z]{2,3}',
                                   returned_text)
        # Infer the 'inner links' Twitter may charge length for
        adjust_with_inner_links = 0
        if len(putative_urls) > 0:
            adjust_with_inner_links = sum([22 - len(u) for u in putative_urls])
        detected_length = len(returned_text) + 22 + adjust_with_inner_links
        assert not detected_length > 140
        for k in expected['keywords']:
            target = ' #{}'.format(k)
            assert returned['text'].index(target) > -1

    TweepyClient.__init__ = new_init
    check(TweepyClient(), entry_generator, expected, check_entry)


def test_MastodonClient(entry_generator, expected):

    def new_init(obj):
        class fake_provider():
            def status_post(self, text, visibility=None):
                return {'text': text, 'visibility': visibility}
        obj._mastodon = fake_provider()
        obj._visibility = 'public'
        obj._delay = 0

    def check_entry(returned, expected):
        assert returned['text'].index(expected['title']) > -1
        assert returned['text'].index(expected['link']) > -1
        assert not len(returned['text']) > 500
        for k in expected['keywords']:
            assert returned['text'].index(' #{}'.format(k)) > -1

    MastodonClient.__init__ = new_init
    check(MastodonClient(), entry_generator, expected, check_entry)


def test_LinkedInClient(entry_generator, expected):

    def new_init(obj):
        class fake_provider():
            def submit_share(self, comment, title, description, submitted_url):
                return {'comment': comment,
                        'title': title,
                        'description': description,
                        'submitted_url': submitted_url}
        obj._linkedin = fake_provider()

    def check_entry(returned, expected):
        assert returned['comment'].index(expected['title']) > -1
        assert returned['title'].index(expected['title']) > -1
        assert returned['description'].index(expected['title']) > -1
        assert returned['submitted_url'].index(expected['link']) > -1
        for k in expected['keywords']:
            assert returned['comment'].index(' #{}'.format(k)) > -1

    LinkedInClient.__init__ = new_init
    check(LinkedInClient(), entry_generator, expected, check_entry)


def test_ShaarpyClient(entry_generator, expected):

    def new_init(obj):
        class fake_provider():
            def post_link(self, link, keywords, title=None, desc=None):
                return {'link': link, 'keywords': keywords, 'title': title,
                        'desc': desc}
        obj._shaarpy = fake_provider()

    def check_entry(returned, expected):
        assert returned['title'].index(expected['title']) > -1
        assert returned['link'].index(expected['link']) > -1
        assert set(expected['keywords']) == set(returned['keywords'])

    ShaarpyClient.__init__ = new_init
    check(ShaarpyClient(), entry_generator, expected, check_entry)


def test_FacebookClient(entry_generator, expected):

    def new_init(obj):
        class fake_provider():
            def put_wall_post(self, text, attachment, post_as):
                return {'text': text, 'attachment': attachment, 'post_as':
                        post_as}
        obj._graph = fake_provider()
        obj._post_as = 'me'

    def check_entry(returned, expected):
        assert returned['text'].startswith(expected['title'])
        assert returned['attachment']['name'].index(expected['title']) > -1
        assert returned['attachment']['link'].index(expected['link']) > -1
        for k in expected['keywords']:
            assert returned['text'].index(' #{}'.format(k)) > -1, \
                "{} not found in {}".format(' #{}'.format(k), returned['text'])

    FacebookClient.__init__ = new_init
    check(FacebookClient(), entry_generator, expected, check_entry)
