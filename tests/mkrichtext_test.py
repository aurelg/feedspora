#!/usr/bin/env python

import random
import string
from feedspora.feedspora_runner import mkrichtext


TBD = 'tests/'


def test_mkrichtext():

    def make_fake_keyword():
        length = random.randint(3, 10)
        return ''.join([random.choice(string.ascii_lowercase)
                        for i in range(length)])

    def make_fake_keywords():
        number = random.randint(2, 5)
        return [make_fake_keyword() for i in range(number)]

    def real_len(text):
        return len(text.encode('utf-8'))

    testcases = {}

    with open(TBD+'phrases') as f:
        for l in [l.strip() for l in f]:
            words = [x for x in l.split(' ') if len(x) > 3]
            if len(words) < 3:
                continue
            keywords = random.sample(words, random.randrange(1,
                                     int(len(words)/3)+1))
            testcases[l] = keywords + make_fake_keywords()

    # print("Loaded {} testcases".format(len(testcases)))

    for (text, keywords) in testcases.items():
        for maxlen in range(30, 260, 10):
            output = mkrichtext(text, keywords, maxlen)

            # print("Text: {}\n Maxlength: {}\n Keywords:{}\n Output: {}\n\n"
            #       .format(text, maxlen, keywords, output))

            assert not real_len(output) > maxlen, "{} > {}" \
                .format(real_len(output))
