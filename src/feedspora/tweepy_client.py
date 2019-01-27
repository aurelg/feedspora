"""
Twitter client based on tweepy.
"""

import re
import tweepy

from feedspora.generic_client import GenericClient


class TweepyClient(GenericClient):
    ''' The TweepyClient handles the connection to Twitter. '''
    _api = None

    def __init__(self, config, testing):
        '''
        Initialize
        :param config:
        :param testing:
        '''
        self._config = config

        # handle auth
        # See https://tweepy.readthedocs.org/en/v3.2.0/auth_tutorial.html
        # #auth-tutorial
        auth = None

        if not testing:
            auth = tweepy.OAuthHandler(config['consumer_token'],
                                       config['consumer_secret'])
            auth.set_access_token(config['access_token'],
                                  config['access_token_secret'])
        self._link_cost = 23
        self._max_len = 280
        self._api = tweepy.API(auth)

        self.set_common_opts(config)

    def get_dict_output(self, **kwargs):
        '''
        Return dict output for testing purposes
        :param kwargs:
        '''

        return {
            "client": self._config['name'],
            "content": kwargs['text'],
            "media": kwargs['media_path'] if kwargs['media_path'] else None
        }

    def post(self, feed, entry):
        '''
        Post entry to Twitter.
        :param entry:
        '''

        putative_urls = re.findall(r'[a-zA-Z0-9]+\.[a-zA-Z]{2,3}', entry.title)
        # Infer the 'inner links' Twitter may charge length for
        adjust_with_inner_links = self._link_cost + \
            sum([self._link_cost - len(u) for u in putative_urls])
        maxlen = self._max_len - adjust_with_inner_links - 1  # for last ' '

        # Let's build our tweet!  Apply optional prefix
        text = self.resolve_option(feed, 'post_prefix')

        # Process contents
        raw_contents = entry.title

        stripped_html = self.strip_html(feed, entry.content) \
                        if entry.content else None
        if self.resolve_option(feed, 'post_include_content') and stripped_html:
            raw_contents += ": " + stripped_html
        text += self._mkrichtext(raw_contents, self.filter_tags(feed, entry),
                                 maxlen=maxlen)

        # Apply optional suffix
        text += self.resolve_option(feed, 'post_suffix')

        # Shorten the link URL if configured/possible
        text += " " + self.shorten_url(feed, entry.link)

        # Finally ready to post.  Let's find out how (media/text)
        media_path = None
        if self.resolve_option(feed, 'post_include_media') and entry.media_url:
            # Need to download image from that URL in order to post it!
            media_path = self.download_media(entry.media_url)

        to_return = False
        if self.is_testing():
            self.accumulate_testing_output(
                self.get_dict_output(text=text, media_path=media_path))
        elif media_path:
            to_return = self._api.update_with_media(media_path, text)
        else:
            to_return = self._api.update_status(text)

        return to_return
