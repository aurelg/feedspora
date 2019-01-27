"""
GenericFeed: base class providing features to specific feeds.
"""

import logging
import re
import requests
import lxml.html
from bs4 import BeautifulSoup

from feedspora.common_config import CommonConfig

# pylint: disable=too-few-public-methods
class FeedSporaEntry:
    '''
    A FeedSpora entry.
    This class is generated from each entry/item in an Atom/RSS feed,
    then posted to your client accounts
    '''
    title = ''
    link = ''
    published_date = None
    content = ''
    tags = None
    media_url = None
# pylint: enable=too-few-public-methods


class GenericFeed(CommonConfig):
    '''
    Implements the base functionalities expected from feeds.
    '''
    _path = None
    _ua = "Mozilla/5.0 (X11; Linux x86_64; rv:42.0) Gecko/20100101 " \
          "Firefox/42.0"

    def __init__(self, config):
        '''
        Initialize
        :param config:
        '''
        if isinstance(config, str):
            # "Old school" configuration (feeds as path strings)
            self._path = config
            # ...for setting defaults, etc. below
            config = dict()
        elif isinstance(config, dict):
            # New style configuration (feeds as dict structures)
            if 'path' in config:
                self._path = config['path']
        self._config = config
        # Feed options are an override to client options
        self.set_common_opts(config, is_override=True)

    def get_path(self):
        '''
        Get the defined path (URL)
        '''
        return self._path

    def max_posts_done(self):
        '''
        Return whether or not the specified number of posts (if existing)
        have been done
        '''
        return self._config['max_posts'] > 0 and \
               self._posts_done >= self._config['max_posts']

    def retrieve_feed_soup(self, feed_url):
        '''
        Retrieve and parse the specified feed.
        :param feed_url: can either be a URL or a path to a local file
        '''
        feed_content = None
        try:
            logging.info("Trying to read %s as a file.", feed_url)
            with open(feed_url, encoding='utf-8') as feed_file:
                feed_content = ''.join(feed_file.readlines())
        except FileNotFoundError:
            logging.info("File not found.")
            logging.info("Trying to read %s as a URL.", feed_url)
            response = requests.get(feed_url, headers={'User-Agent': self._ua})

            if not response.ok:
                raise Exception(feed_content)
            feed_content = response.text
        logging.info("Feed read.")

        return BeautifulSoup(feed_content, 'html.parser')

    # pylint: disable=no-self-use
    def get_tag_lists(self, title, content):
        '''
        Determine the list of tags, both from title and content
        :param title:
        :param content:
        '''
        title_tags = []
        # Add tags from title
        for word in title.split():
            if word.startswith('#') and word[1:] not in title_tags:
                title_tags.append(word[1:])

        # Add tags from end of content (removing from content in the
        # process of gathering tags)
        content_tags = []
        if content:
            # Remove tags to improve processing
            content = lxml.html.fromstring(content).text_content().strip()
            tag_pattern = r'\s+#([\w]+)$'
            match_result = re.search(tag_pattern, content)

            while match_result:
                tag = match_result.group(1)

                if tag not in content_tags:
                    content_tags.insert(0, tag)
                content = re.sub(tag_pattern, '', content)
                match_result = re.search(tag_pattern, content)

            tag_pattern = r'^\s*#([\w]+)$'
            match_result = re.search(tag_pattern, content)
            if match_result:
                # Left with a single tag!
                tag = match_result.group(1)
                if tag not in content_tags:
                    content_tags.insert(0, tag)
                content = ''

        return title_tags, content_tags
    # pylint: enable=no-self-use

    # Define generator for Atom
    def parse_atom(self, soup):
        '''
        Generate FeedSpora entries out of an Atom feed.
        :param soup:
        '''

        for entry in soup.find_all('entry')[::-1]:
            fse = FeedSporaEntry()

            # Title
            try:
                fse.title = BeautifulSoup(
                    entry.find('title').text, 'html.parser').find('a').text
            except AttributeError:
                fse.title = entry.find('title').text

            # Link
            fse.link = entry.find('link')['href']

            # Content
            if entry.find('content'):
                fse.content = entry.find('content').text.strip()
            # If no content, attempt to use summary

            if not fse.content and entry.find('summary'):
                fse.content = entry.find('summary').text.strip()

            if fse.content is None:
                fse.content = ''

            # Tags
            fse.tags = dict()
            # Tags from title and content, each in their own list
            fse.tags['title'], fse.tags['content'] = self.get_tag_lists(
                fse.title, fse.content)

            # Add tags from category
            fse.tags['category'] = []
            for tag in entry.find_all('category'):
                new_tag = tag['term'].replace(' ', '_').strip()
                if new_tag not in fse.tags['category']:
                    fse.tags['category'].append(new_tag)

            # Published_date implementation for Atom
            if entry.find('updated'):
                fse.published_date = entry.find('updated').text
            elif entry.find('published'):
                fse.published_date = entry.find('published').text
            yield fse

    # pylint: disable=no-self-use
    def find_rss_image_url(self, entry, link):
        '''
        Extract specified image URL, if it exists in the item (entry)
        :param entry:
        :param link:
        '''

        def content_img_src(entity):
            result = None

            compiled_pattern = re.compile(r'<img [^>]*src=["\']([^"\']+)["\']')

            for content in entity.contents:
                img_tag = compiled_pattern.search(content)

                if img_tag:
                    result = img_tag.group(1)

                    break

            return result

        to_return = None

        if entry.find('media:content') and \
           entry.find('media:content')['medium'] == 'image':
            to_return = entry.find('media:content')['url']
        elif entry.find('content'):
            to_return = content_img_src(entry.find('content'))
        elif entry.find('description'):
            to_return = content_img_src(entry.find('description'))

        if to_return and link:
            tag_pattern = r'^(https?://[^/]+)/'
            match_result = re.search(tag_pattern, to_return)

            if not match_result:
                # Not a full URL, need to adjust using link
                match_result = re.search(tag_pattern, link)

                if match_result:
                    url_root = match_result.group(1)

                    if to_return.startswith("/"):
                        to_return = url_root + to_return
                    else:
                        to_return = url_root + "/" + to_return

        return to_return
    # pylint: enable=no-self-use

    # Define generator for RSS
    def parse_rss(self, soup):
        '''
        Generate FeedSpora entries out of an RSS feed.
        :param soup:
        '''

        for entry in soup.find_all('item')[::-1]:
            fse = FeedSporaEntry()

            # Title
            fse.title = entry.find('title').text

            # Link
            fse.link = entry.find('link').text

            # Content takes priority over Description

            if entry.find('content'):
                fse.content = entry.find('content')[0].text.strip()
            else:
                fse.content = entry.find('description').text.strip()

            # PubDate
            fse.published_date = entry.find('pubdate').text

            fse.tags = dict()
            # Tags from title and content, each in their own list
            fse.tags['title'], fse.tags['content'] = self.get_tag_lists(
                fse.title, fse.content)

            # Add tags from category
            fse.tags['category'] = []
            for tag in entry.find_all('category'):
                new_tag = tag.text.replace(' ', '_').strip()

                if new_tag not in fse.tags['category']:
                    fse.tags['category'].append(new_tag)

            # And for our final act, media
            fse.media_url = self.find_rss_image_url(entry, fse.link)
            yield fse

    def feed_generator(self):
        '''
        Handle RSS/Atom feed
        Sets up a generator for the feed content
        :param feed:
        '''
        to_return = None
        # get feed content
        feed_url = self.get_path()
        try:
            soup = self.retrieve_feed_soup(feed_url)
        except (requests.exceptions.ConnectionError, ValueError,
                OSError) as error:
            logging.error(
                "Error while reading feed at %s: %s",
                feed_url,
                format(error),
                exc_info=True)
            return to_return

        # Choose which generator to use, or abort.
        if soup.find('entry'):
            to_return = self.parse_atom(soup)
        elif soup.find('item'):
            to_return = self.parse_rss(soup)
        else:
            print("No entry/item found in %s" % feed_url)
        return to_return
