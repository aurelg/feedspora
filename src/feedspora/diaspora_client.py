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

    def __init__(self, config, testing):
        '''
        Initialize
        :param config:
        :param testing:
        '''
        self._config = config

        if not testing:
            self.connection = diaspy.connection.Connection(
                pod=config['pod'],
                username=config['username'],
                password=config['password'])
            self.connection.login()
            try:
                self.stream = diaspy.streams.Stream(self.connection,
                                                    'stream.json')
            except diaspy.errors.PostError as exception:
                logging.error("Cannot get diaspy stream: %s", str(exception))
                self.stream = None
        self.set_common_opts(config)

    def get_dict_output(self, **kwargs):
        '''
        Return dict output for testing purposes
        :param kwargs:
        '''

        return {
            "client": self._config['name'],
            "content": kwargs['text'],
            "media": kwargs['photo']
        }

    def post(self, feed, entry):
        '''
        Post entry to Diaspora.
        :param feed:
        :param entry:
        '''

        text = self.resolve_option(feed, 'post_prefix') + \
               '['+entry.title +']('+self.shorten_url(feed, entry.link)+')'
        stripped_html = self.strip_html(feed, entry.content) \
                        if entry.content else None
        if self.resolve_option(feed, 'post_include_content') and stripped_html:
            text += ": " + stripped_html
        text += self.resolve_option(feed, 'post_suffix')
        post_tags = ''.join([" #{}".format(k)
                             for k in self.filter_tags(feed, entry)])
        if post_tags:
            text += ' |'+post_tags

        media_path = None
        if self.resolve_option(feed, 'post_include_media') and entry.media_url:
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
