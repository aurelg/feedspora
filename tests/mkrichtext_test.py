#!/usr/bin/env python

import random
import string

import pytest

from feedspora.feedspora_runner import mkrichtext

TBD = 'tests/'


@pytest.fixture
def testcases():
    def make_fake_keyword():
        length = random.randint(3, 10)
        return ''.join(
            [random.choice(string.ascii_lowercase) for i in range(length)])

    def make_fake_keywords():
        number = random.randint(2, 5)
        return [make_fake_keyword() for i in range(number)]

    to_return = {}
    with open(TBD + 'phrases') as f:
        for l in [l.strip() for l in f]:
            words = [x for x in l.split(' ') if len(x) > 3]
            if len(words) < 3:
                continue
            keywords = random.sample(
                words, random.randrange(1,
                                        int(len(words) / 3) + 1))
            to_return[l] = keywords + make_fake_keywords()

        # No keywords and short
        statement = ' '.join(make_fake_keywords())
        to_return[statement] = []
        # No keywords and long
        to_return[statement * 30] = []
    return to_return


def test_mkrichtext_length(testcases):
    for (text, keywords) in testcases.items():
        for maxlen in range(30, 260, 10):
            output = mkrichtext(text, keywords, maxlen)
            assert not len(output) > maxlen, "{} > {}" \
                .format(len(output))
            assert not output.endswith('|'), "{} ends with sep".format(output)


def test_mkrichtext_case(testcases):
    for (text, keywords) in testcases.items():
        output1 = mkrichtext(text, keywords, 500)
        output2 = mkrichtext(text.upper(), keywords, 500)
        assert output1.upper() == output2.upper()

def test_mkrichtext_tags():
    '''
    Test the proper handling and application of hashtags
    '''
    testcases = {
                     'No Tags, No Keywords': {
                         'keywords': [],
                         'expected': 'No Tags, No Keywords'
                     },
                     'One #Tag, No Keywords': {
                         'keywords': [],
                         'expected': 'One #Tag, No Keywords'
                     },
                     'One #Tag, Unrelated Keyword': {
                         'keywords': ['appended'],
                         'expected': 'One #Tag, Unrelated Keyword | #appended'
                     },
                     'One #Tag, Duplicate Keyword': {
                         'keywords': ['tag'],
                         'expected': 'One #Tag, Duplicate Keyword'
                     },
                     'One #Tag, Keyword In Title': {
                         'keywords': ['keyword'],
                         'expected': 'One #Tag, #Keyword In Title'
                     },
                     'tag-text-embedded In Title': {
                         'keywords': ['tag', 'embedded'],
                         'expected': 'tag-text-embedded In Title | #tag #embedded'
                     },
                     'Tags at beginning and end': {
                         'keywords': ['tags', 'end'],
                         'expected': '#Tags at beginning and #end'
                     },
                     'Tags within "quotes" and parens (tricky)': {
                         'keywords': ['quotes', 'tricky'],
                         'expected': 'Tags within "#quotes" and parens (#tricky)'
                     },
                     'Tags in red/white/blue': {
                         'keywords': ['red', 'white', 'blue'],
                         'expected': 'Tags in #red/#white/#blue'
                     },
                     'Tag before comma, before period.': {
                         'keywords': ['comma', 'period'],
                         'expected': 'Tag before #comma, before #period.'
                     },
                     '#Bad-tag retained (not bad, eh?)': {
                         'keywords': ['bad', 'eh'],
                         'expected': '#Bad-tag retained (not #bad, #eh?)'
                     },
                }
    for input in testcases:
        keywords = testcases[input]['keywords']
        expected = testcases[input]['expected']
        output = mkrichtext(input, keywords, 500)
        assert output == expected
