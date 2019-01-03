"""
Shaarpy client
"""

import logging

from bs4 import BeautifulSoup
from shaarpy.shaarpy import Shaarpy
from feedspora.generic_client import GenericClient


class ShaarpyClient(GenericClient):
    ''' The ShaarpyClient handles the connection to Shaarli. '''
    _shaarpy = None
    _post_private = False

    def __init__(self, account, testing):
        '''
        Initialize
        :param account:
        :param testing:
        '''
        self._account = account
        if 'post_audience' in account and \
           account['post_audience'].lower() == 'private':
            self._post_private = True

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
            "link": kwargs['link'],
            "tags": kwargs['tags'],
            "title": kwargs['title'],
            "content": kwargs['content'],
            "audience": kwargs['audience']
        }

    def post(self, entry):
        '''
        Post entry to Shaarli
        :param entry:
        '''
        title = self._account['post_prefix'] + \
                entry.title+self._account['post_suffix']
        link = self.shorten_url(entry.link)
        tags = self.filter_tags(entry)
        content = ''
        if self._account['post_include_content'] and entry.content:
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
            post_args = {'link': link,
                         'tags': tags,
                         'title': title,
                         'content': content,
                         'audience': 'private' if self._post_private else \
                                     'public'
                         }
            self.accumulate_testing_output(self.get_dict_output(**post_args))
        else:
            # pylint: disable=broad-except
            try:
                to_return = self._shaarpy.post_link(link, tags,
                                                    title=title, desc=content,
                                                    private=self._post_private)
            except Exception as broad_exception:
                logging.error(str(broad_exception), exc_info=True)
            # pylint: enable=broad-except

        return to_return
