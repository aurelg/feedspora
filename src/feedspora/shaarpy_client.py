"""
Shaarpy client
"""

import json

from bs4 import BeautifulSoup
from shaarpy.shaarpy import Shaarpy

from feedspora.generic_client import GenericClient


class ShaarpyClient(GenericClient):
    ''' The ShaarpyClient handles the connection to Shaarli. '''
    _shaarpy = None

    def __init__(self, account, testing):
        '''
        Initialize
        :param account:
        :param testing:
        '''

        if not testing:
            self._shaarpy = Shaarpy()
            self._shaarpy.login(account['username'], account['password'],
                                account['url'])

    def test_output(self, **kwargs):
        '''
        Print output for testing purposes
        :param kwargs:
        '''
        print(
            json.dumps({
                "client": self.get_name(),
                "title": kwargs['entry'].title,
                "link": kwargs['entry'].link,
                "keywords": kwargs['entry'].keywords,
                "content": kwargs['text']
            },
                       indent=4))

        return True

    def post(self, entry):
        '''
        Post entry to Shaarli
        :param entry:
        '''
        content = entry.content
        # pylint: disable=broad-except
        try:
            soup = BeautifulSoup(entry.content, 'html.parser')
            content = soup.text
        except Exception:
            pass
        # pylint: enable=broad-except

        # Note non-boolean return type!
        to_return = {}

        if self.is_testing():
            to_return = self.test_output(text=content, entry=entry)
        else:
            # For some reasons, this pylint directive is ignored?
            # pylint: disable=assignment-from-no-return
            to_return = self._shaarpy.post_link(
                entry.link, entry.keywords, title=entry.title, desc=content)
            # pylint: enable=assignment-from-no-return

        return to_return
