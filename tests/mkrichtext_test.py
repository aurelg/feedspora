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
