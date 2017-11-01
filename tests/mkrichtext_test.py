#!/usr/bin/env python

import random
import string
from feedspora.feedspora_runner import mkrichtext


TBD = 'tests/'


def make_fake_keyword():
    length = random.randint(3, 10)
    return ''.join([random.choice(string.ascii_lowercase)
                    for i in range(length)])


def make_fake_keywords():
    number = random.randint(2, 5)
    return [make_fake_keyword() for i in range(number)]


def real_len(text):
    return len(text.encode('utf-8'))


TESTCASES = {}

with open(TBD+'phrases') as f:
    for l in [l.strip() for l in f]:
        words = [x for x in l.split(' ') if len(x) > 3]
        if len(words) < 3:
            continue
        keywords = random.sample(words, random.randrange(1,
                                                         int(len(words)/3)+1))
        TESTCASES[l] = keywords + make_fake_keywords()

    # No keywords and short
    statement = ' '.join(make_fake_keywords())
    TESTCASES[statement] = []
    # No keywords and long
    TESTCASES[statement * 30] = []


def test_mkrichtext_length():
    for (text, keywords) in TESTCASES.items():
        for maxlen in range(30, 260, 10):
            output = mkrichtext(text, keywords, maxlen)
            assert not real_len(output) > maxlen, "{} > {}" \
                .format(real_len(output))
            assert not output.endswith('|'), "{} ends with sep".format(output)


def test_mkrichtext_case():
    for (text, keywords) in TESTCASES.items():
        output1 = mkrichtext(text, keywords, 500)
        output2 = mkrichtext(text.upper(), keywords, 500)
        assert output1.upper() == output2.upper()
