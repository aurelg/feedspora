"""
Diaspora client.
"""
import logging

import diaspy.connection
import diaspy.models
import diaspy.streams

from feedspora.generic_client import GenericClient


class DiaspyClient(GenericClient):
    ''' The DiaspyClient handles the connection to Diaspora. '''
    stream = None
    connection = None

    def __init__(self, account, testing):
        '''
        Initialize
        :param account:
        :param testing:
        '''
        self._account = account

        if not testing:
            self.connection = diaspy.connection.Connection(
                pod=account['pod'],
                username=account['username'],
                password=account['password'])
            self.connection.login()
            try:
                self.stream = diaspy.streams.Stream(self.connection,
                                                    'stream.json')
            except diaspy.errors.PostError as exception:
                logging.error("Cannot get diaspy stream: %s", str(exception))
                self.stream = None
        self.set_common_opts(account)

    def get_dict_output(self, **kwargs):
        '''
        Return dict output for testing purposes
        :param kwargs:
        '''

        return {
            "client": self._account['name'],
            "content": kwargs['text'],
            "media": kwargs['photo']
        }

    def post(self, entry):
        '''
        Post entry to Diaspora.
        :param entry:
        '''

        text = self._account['post_prefix'] + \
               '['+entry.title +']('+self.shorten_url(entry.link)+')'
        stripped_html = self.strip_html(entry.content) \
                        if entry.content else None
        if self._account['post_include_content'] and stripped_html:
            text += ": " + stripped_html
        text += self._account['post_suffix']
        post_tags = ''.join([" #{}".format(k) for k in self.filter_tags(entry)])
        if post_tags:
            text += ' |'+post_tags

        media_path = None
        if self._account['post_include_media'] and entry.media_url:
            # Need to download image from that URL in order to post it!
            media_path = self.download_media(entry.media_url)

        post_params = {'text': text,
                       'photo': media_path,
                       'aspect_ids': 'public',
                       'provider_display_name': 'FeedSpora'
                       }

        to_return = False
        if self.stream:
            to_return = self.stream.post(**post_params)
        elif self.is_testing():
            self.accumulate_testing_output(self.get_dict_output(**post_params))
        else:
            logging.info("Diaspy stream is None, not posting anything")

        return to_return
