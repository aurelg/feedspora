"""
Shaarpy client
"""
import copy

import logging

from bs4 import BeautifulSoup

from feedspora.generic_client import GenericClient
from shaarpy.shaarpy import Shaarpy


class ShaarpyClient(GenericClient):
    ''' The ShaarpyClient handles the connection to Shaarli. '''
    _shaarpy = None

    def __init__(self, account, testing):
        '''
        Initialize
        :param account:
        :param testing:
        '''
        self._account = copy.deepcopy(account)

        if not testing:
            self._shaarpy = Shaarpy()
            self._shaarpy.login(account['username'], account['password'],
                                account['url'])
        self.set_common_opts(account)

    def get_dict_output(self, **kwargs):
        '''
        Return dict output for testing purposes
        :param kwargs:
        '''

        return {
            "client": self._account['name'],
            "title": self._account['post_prefix'] + \
                     kwargs['entry'].title+self._account['post_suffix'],
            "link": self.shorten_url(kwargs['entry'].link),
            "tags": self.filter_tags(kwargs['entry']),
            "content": kwargs['content']
        }

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

        content = self.remove_ending_tags(content)

        to_return = False

        if self.is_testing():
            to_return = self.accumulate_testing_output(
                self.get_dict_output(content=content, entry=entry))
        else:
            title = self._account['post_prefix'] + \
                    entry.title+self._account['post_suffix']
            try:
                to_return = self._shaarpy.post_link(
                    self.shorten_url(entry.link),
                    self.filter_tags(entry),
                    title=title,
                    desc=content) or True
                # pylint: enable=assignment-from-no-return
            except Exception as e:
                logging.error(str(e), exc_info=True)

        return to_return
