#!/usr/bin/env python

import random
import string

import pytest

from feedspora.generic_client import GenericClient


@pytest.fixture
def testcases():
    def make_fake_tag():
        length = random.randint(3, 10)

        return ''.join(
            [random.choice(string.ascii_lowercase) for i in range(length)])

    def make_fake_tags():
        number = random.randint(2, 5)

        return [make_fake_tag() for i in range(number)]

    to_return = {}
    with open('phrases') as f:
        for l in [l.strip() for l in f]:
            words = [x for x in l.split(' ') if len(x) > 3]

            if len(words) < 3:
                continue
            tags = random.sample(
                words, random.randrange(1,
                                        int(len(words) / 3) + 1))
            to_return[l] = tags + make_fake_tags()

        # No tags and short
        statement = ' '.join(make_fake_tags())
        to_return[statement] = []
        # No tags and long
        to_return[statement * 30] = []

    return to_return


def test_mkrichtext_length(testcases):
    for (text, tags) in testcases.items():
        for maxlen in range(30, 260, 10):
            output = GenericClient()._mkrichtext(text, tags, maxlen)
            assert not len(output) > maxlen, "{} > {}" \
                .format(len(output))
            assert not output.endswith('|'), "{} ends with sep".format(output)


def test_mkrichtext_case(testcases):
    for (text, tags) in testcases.items():
        output1 = GenericClient()._mkrichtext(text, tags, 500)
        output2 = GenericClient()._mkrichtext(text.upper(), tags, 500)
        assert output1.upper() == output2.upper()


def test_mkrichtext_tags():
    '''
    Test the proper handling and application of hashtags
    '''
    testcases = {
        'No Hashtags, No Tags': {
            'tags': [],
            'expected': 'No Hashtags, No Tags'
        },
        'One #Hashtag, No Tags': {
            'tags': [],
            'expected': 'One #Hashtag, No Tags'
        },
        'One #Hashtag, Unrelated Tag': {
            'tags': ['appended'],
            'expected': 'One #Hashtag, Unrelated Tag | #appended'
        },
        'One #Hashtag, Duplicate Tag': {
            'tags': ['hashtag'],
            'expected': 'One #Hashtag, Duplicate Tag'
        },
        'One #Hashtag, Tag In Title': {
            'tags': ['tag'],
            'expected': 'One #Hashtag, #Tag In Title'
        },
        'tag-text-embedded In Title': {
            'tags': ['tag', 'embedded'],
            'expected': 'tag-text-embedded In Title | #tag #embedded'
        },
        'Tags at beginning and end': {
            'tags': ['tags', 'end'],
            'expected': '#Tags at beginning and #end'
        },
        'Tags within "quotes" and parens (tricky)': {
            'tags': ['quotes', 'tricky'],
            'expected': 'Tags within "#quotes" and parens (#tricky)'
        },
        'Tags in red/white/blue': {
            'tags': ['red', 'white', 'blue'],
            'expected': 'Tags in #red/#white/#blue'
        },
        'Tag before comma, before period.': {
            'tags': ['comma', 'period'],
            'expected': 'Tag before #comma, before #period.'
        },
        '#Bad-tag retained (not bad, eh?)': {
            'tags': ['bad', 'eh'],
            'expected': '#Bad-tag retained (not #bad, #eh?)'
        },
    }

    for input in testcases:
        tags = testcases[input]['tags']
        expected = testcases[input]['expected']
        output = GenericClient()._mkrichtext(input, tags, 500)
        assert output == expected
