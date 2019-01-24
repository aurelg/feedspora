"""
Mastodon client
"""

import logging
import time

from mastodon import Mastodon
from mastodon.Mastodon import MastodonIllegalArgumentError, MastodonAPIError

from feedspora.generic_client import GenericClient


class MastodonClient(GenericClient):
    ''' The MastodonClient handles the connection to Mastodon. '''
    _mastodon = None
    _invoke_delay = False

    def __init__(self, config, testing):
        '''
        Initialize
        :param config:
        :param testing:
        '''
        self._config = config

        client_id = config['client_id']
        client_secret = config['client_secret']
        access_token = config['access_token']
        api_base_url = config['url']

        if not testing:
            self._mastodon = Mastodon(
                client_id=client_id,
                client_secret=client_secret,
                access_token=access_token,
                api_base_url=api_base_url)
        self._delay = 0 if 'delay' not in config else config['delay']
        self._visibility = 'unlisted' if 'visibility' not in config or \
            config['visibility'] not in ['public', 'unlisted', 'private'] \
            else config['visibility']
        self.set_common_opts(config)

    def get_dict_output(self, **kwargs):
        '''
        Return dict output for testing purposes
        :param kwargs:
        '''

        return {
            "client": self._config['name'],
            "delay": self._delay,
            "visibility": self._visibility,
            "content": kwargs['text'],
            "media": kwargs['media_path']
        }

    def post(self, feed, entry):
        '''
        Post entry to Mastodon
        :param feed:
        :param entry:
        '''
        use_link = self.shorten_url(feed, entry.link)
        maxlen = 500 - len(use_link) - \
                 len(self.resolve_option(feed, 'post_prefix')) - \
                 len(self.resolve_option(feed, 'post_suffix')) - 1
        text = self.resolve_option(feed, 'post_prefix')

        # Process contents (title and perhaps stripped item entry contents)
        raw_contents = entry.title
        stripped_html = self.strip_html(feed, entry.content) \
                        if entry.content else None
        if self.resolve_option(feed, 'post_include_content') and stripped_html:
            raw_contents += ": " + stripped_html
        text += self._mkrichtext(raw_contents, self.filter_tags(feed, entry),
                                 maxlen=maxlen)

        # Apply optional suffix
        text += self.resolve_option(feed, 'post_suffix')

        # Finally, add the (potentially shortened) link
        text += " " + use_link

        # Add media if appropriate
        media_path = None
        if self.resolve_option(feed, 'post_include_media') and entry.media_url:
            # Need to download image from that URL in order to post it!
            media_path = self.download_media(entry.media_url)

        to_return = False
        if self.is_testing():
            self.accumulate_testing_output(
                self.get_dict_output(text=text,
                                     media_path=media_path))
        else:
            if self._delay > 0 and self._invoke_delay:
                logging.info("Delaying post for %d seconds...", self._delay)
                time.sleep(self._delay)

            # Post media first (if appropriate)
            media_id = 0
            if media_path:
                try:
                    media_result = self._mastodon.media_post(media_path)
                    if 'id' in media_result:
                        # Successfully posted - get the ID
                        media_id = media_result['id']
                except (MastodonIllegalArgumentError,
                        MastodonAPIError) as exception:
                    logging.info("Error encountered while posting %s: %s",
                                 media_path, str(exception))

            to_return = self._mastodon.status_post(
                text, media_ids=([media_id] if media_id else None),
                visibility=self._visibility)

        if to_return and 'id' in to_return:
            # Enable the posting delay for the next post attempt
            self._invoke_delay = True

        return to_return
