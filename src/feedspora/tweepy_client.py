"""
Twitter client based on tweepy.
"""

import logging
import os
import re

import lxml.html
import requests
import tweepy

from feedspora.generic_client import GenericClient


class TweepyClient(GenericClient):
    ''' The TweepyClient handles the connection to Twitter. '''
    _api = None

    def __init__(self, account, testing):
        '''
        Initialize
        :param account:
        :param testing:
        '''
        # handle auth
        # See https://tweepy.readthedocs.org/en/v3.2.0/auth_tutorial.html
        # #auth-tutorial
        auth = None

        if not testing:
            auth = tweepy.OAuthHandler(account['consumer_token'],
                                       account['consumer_secret'])
            auth.set_access_token(account['access_token'],
                                  account['access_token_secret'])
        self._link_cost = 23
        self._max_len = 280
        self._api = tweepy.API(auth)

        self.set_common_opts(account)

    def get_dict_output(self, **kwargs):
        '''
        Return dict output for testing purposes
        :param kwargs:
        '''

        return {
            "client": self.get_name(),
            "content": kwargs['text'],
            "media": kwargs['media_path'] if kwargs['media_path'] else None
        }

    def post(self, entry):
        '''
        Post entry to Twitter.
        :param entry:
        '''

        def download_media(the_url):
            '''
            Download the media file referenced by the_url
            Returns the path to the downloaded file
            :param the_url:
            '''

            request = requests.get(the_url, allow_redirects=True)
            filename = get_filename_from_cd(
                request.headers.get('Content-Disposition'))

            if not filename:
                filename = 'random.jpg'
            media_dir = os.getenv('MEDIA_DIR', '/tmp')
            full_path = media_dir + '/' + filename
            logging.info("Downloading %s as %s...", the_url, full_path)
            open(full_path, 'wb').write(request.content)

            return full_path

        def get_filename_from_cd(content_disp):
            '''
            Get filename from Content-Disposition
            :param content_disp:
            '''

            to_return = None

            if content_disp:
                fname = re.findall('filename=(.+)', content_disp)

                if fname:
                    to_return = fname[0]

            return to_return

        def strip_html(before_strip):
            '''
            Strip HTML from the content
            :param before_strip:
            '''

            to_return = None
            if before_strip:
                # Getting the stripped HTML might take multiple attempts
                done = False
                while not done:
                    to_return = lxml.html.fromstring(
                        before_strip).text_content().strip()
                    done = to_return == before_strip
                    if not done:
                        before_strip = to_return
                # Remove all tags from end of content!
                to_return = self.remove_ending_tags(to_return)

            return to_return

        putative_urls = re.findall(r'[a-zA-Z0-9]+\.[a-zA-Z]{2,3}', entry.title)
        # Infer the 'inner links' Twitter may charge length for
        adjust_with_inner_links = self._link_cost + \
            sum([self._link_cost - len(u) for u in putative_urls])
        maxlen = self._max_len - adjust_with_inner_links - 1  # for last ' '

        # Let's build our tweet!
        text = ""

        # Apply optional prefix
        if self._post_prefix:
            text = self._post_prefix + " "

        # Process contents
        raw_contents = entry.title

        stripped_html = strip_html(entry.content)
        if self._include_content and stripped_html:
            raw_contents += ": " + stripped_html
        text += self._mkrichtext(raw_contents, self.filter_tags(entry),
                                 maxlen=maxlen)

        # Apply optional suffix
        if self._post_suffix:
            text += " " + self._post_suffix
        # Shorten the link URL if configured/possible
        text += " " + self.shorten_url(entry.link)

        # Finally ready to post.  Let's find out how (media/text)
        media_path = None

        if self._include_media and entry.media_url:
            # Need to download image from that URL in order to post it!
            media_path = download_media(entry.media_url)

        to_return = False

        if self.is_testing():
            self.accumulate_testing_output(
                self.get_dict_output(text=text, media_path=media_path))
        elif media_path:
            to_return = self._api.update_with_media(media_path, text)
        else:
            to_return = self._api.update_status(text)

        return to_return
