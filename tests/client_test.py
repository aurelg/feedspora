#!/usr/bin/env python

from feedspora.feedspora_runner import FeedSpora
from feedspora.feedspora_runner import DiaspyClient
from feedspora.feedspora_runner import TweepyClient
from feedspora.feedspora_runner import FacebookClient
from feedspora.feedspora_runner import MastodonClient
from feedspora.feedspora_runner import ShaarpyClient
from feedspora.feedspora_runner import LinkedInClient

TBD = 'tests/'


def generator():
    f = 'feed.atom'
    fs = FeedSpora()
    soup = fs.retrieve_feed_soup(TBD+f)
    return fs.parse_atom(soup)


expected = [{'title': 'Atom-Powered Robots Run Amok',
             'url': 'http://example.org/2003/12/13/atom03',
             'keywords': ['vegetable', 'mineral', 'animal']}]


def check(client, check_entry):
    entries = [x for x in generator()]
    assert len(entries) > 0
    assert len(entries) == len(expected)
    for entry, expect in zip(entries, expected):
        returned = client.post(entry)
        check_entry(returned, expect)


def test_DiaspyClient():

    def new_init(obj):
        class fake_provider():
            def post(self, text, aspect_ids=None, provider_display_name=None):
                return {'text': text,
                        'aspect_ids': aspect_ids,
                        'provider_display_name': provider_display_name}
        obj.stream = fake_provider()
        obj.keywords = []

    def check_entry(returned, expect):
        assert returned is not None
        assert returned['aspect_ids'] == 'public'
        assert returned['provider_display_name'] == 'FeedSpora'
        assert returned['text'].startswith("[{}]({})".format(expect['title'],
                                                             expect['url']))
        for i in ['#{}'.format(k) for k in expect['keywords']]:
            assert returned['text'].index(i) > -1

    DiaspyClient.__init__ = new_init
    check(DiaspyClient(), check_entry)


def test_TweepyClient():

    def new_init(obj):
        class fake_provider():
            def update_status(self, text):
                return {'text': text}
        obj._api = fake_provider()

    def check_entry(returned, expected):
        assert returned is not None
        assert returned['text'].index(expected['title'].encode('utf-8')) > -1
        assert returned['text'].index(expected['url'].encode('utf-8')) > -1
        assert not len(returned['text']) > 140
        for k in expected['keywords']:
            target = ' #{}'.format(k).encode('utf-8')
            assert returned['text'].index(target) > -1

    TweepyClient.__init__ = new_init
    check(TweepyClient(), check_entry)


def test_MastodonClient():

    def new_init(obj):
        class fake_provider():
            def status_post(self, text, visibility=None):
                return {'text': text, 'visibility': visibility}
        obj._mastodon = fake_provider()
        obj._visibility = 'public'
        obj._delay = 0

    def check_entry(returned, expected):
        assert returned is not None
        assert returned['text'].index(expected['title']) > -1
        assert returned['text'].index(expected['url']) > -1
        assert not len(returned['text']) > 500
        for k in expected['keywords']:
            assert returned['text'].index(' #{}'.format(k)) > -1

    MastodonClient.__init__ = new_init
    check(MastodonClient(), check_entry)


def test_LinkedInClient():

    def new_init(obj):
        class fake_provider():
            def submit_share(self, comment, title, description, submitted_url):
                return {'comment': comment,
                        'title': title,
                        'description': description,
                        'submitted_url': submitted_url}
        obj._linkedin = fake_provider()

    def check_entry(returned, expected):
        assert returned is not None
        assert returned['comment'].index(expected['title']) > -1
        assert returned['title'].index(expected['title']) > -1
        assert returned['description'].index(expected['title']) > -1
        assert returned['submitted_url'].index(expected['url']) > -1
        for k in expected['keywords']:
            assert returned['comment'].index(' #{}'.format(k)) > -1

    LinkedInClient.__init__ = new_init
    check(LinkedInClient(), check_entry)


def test_ShaarpyClient():

    def new_init(obj):
        class fake_provider():
            def post_link(self, link, keywords, title=None, desc=None):
                return {'link': link, 'keywords': keywords, 'title': title,
                        'desc': desc}
        obj._shaarpy = fake_provider()

    def check_entry(returned, expected):
        assert returned is not None
        assert returned['title'].index(expected['title']) > -1
        assert returned['link'].index(expected['url']) > -1
        assert set(expected['keywords']) == set(returned['keywords'])

    ShaarpyClient.__init__ = new_init
    check(ShaarpyClient(), check_entry)


def test_FacebookClient():

    def new_init(obj):
        class fake_provider():
            def put_wall_post(self, text, attachment, post_as):
                return {'text': text, 'attachment': attachment, 'post_as':
                        post_as}
        obj._graph = fake_provider()
        obj._post_as = 'me'

    def check_entry(returned, expected):
        assert returned is not None
        assert returned['text'].startswith(expected['title'])
        assert returned['attachment']['name'].index(expected['title']) > -1
        assert returned['attachment']['link'].index(expected['url']) > -1
        for k in expected['keywords']:
            assert returned['text'].index(' #{}'.format(k)) > -1, \
                "{} not found in {}".format(' #{}'.format(k), returned['text'])

    FacebookClient.__init__ = new_init
    check(FacebookClient(), check_entry)
