"""
Mastodon client
"""

import json
import time

from mastodon import Mastodon

from feedspora.generic_client import GenericClient


class MastodonClient(GenericClient):
    ''' The MastodonClient handles the connection to Mastodon. '''
    _mastodon = None

    def __init__(self, account, testing):
        '''
        Initialize
        :param account:
        :param testing:
        '''
        client_id = account['client_id']
        client_secret = account['client_secret']
        access_token = account['access_token']
        api_base_url = account['url']

        if not testing:
            self._mastodon = Mastodon(
                client_id=client_id,
                client_secret=client_secret,
                access_token=access_token,
                api_base_url=api_base_url)
        self._delay = 0 if 'delay' not in account else account['delay']
        self._visibility = 'unlisted' if 'visibility' not in account or \
            account['visibility'] not in ['public', 'unlisted', 'private'] \
            else account['visibility']

    def test_output(self, **kwargs):
        '''
        Print output for testing purposes
        :param kwargs:
        '''
        print(
            json.dumps({
                "client": self.get_name(),
                "delay": self._delay,
                "visibility": self._visibility,
                "content": kwargs['text']
            },
                       indent=4))

        return True

    def post(self, entry):
        '''
        Post entry to Mastadon
        :param entry:
        '''
        maxlen = 500 - len(entry.link) - 1
        text = self._mkrichtext(entry.title, entry.keywords, maxlen=maxlen)
        text += ' ' + entry.link

        to_return = False

        if self.is_testing():
            to_return = self.test_output(text=text)
        else:
            if self._delay > 0:
                time.sleep(self._delay)

            to_return = self._mastodon.status_post(
                text, visibility=self._visibility)

        return to_return
