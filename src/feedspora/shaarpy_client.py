"""
Shaarpy client
"""

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
        self.set_common_opts(account)

    def get_dict_output(self, **kwargs):
        '''
        Return dict output for testing purposes
        :param kwargs:
        '''

        return {
            "client": self.get_name(),
            "title": self._post_prefix+kwargs['entry'].title+self._post_suffix
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

        # Note non-boolean return type!
        to_return = {}

        if self.is_testing():
            self.accumulate_testing_output(
                self.get_dict_output(content=content, entry=entry))
        else:
            title = self._post_prefix+entry.title+self._post_suffix
            # For some reasons, this pylint directive is ignored?
            # pylint: disable=assignment-from-no-return
            to_return = self._shaarpy.post_link(
                self.shorten_url(entry.link), self.filter_tags(entry),
                title=title, desc=content)
            # pylint: enable=assignment-from-no-return

        return to_return
