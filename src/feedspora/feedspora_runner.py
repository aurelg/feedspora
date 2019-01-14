#!/usr/bin/env python3
# encoding: utf-8
'''
FeedSpora is a bot that posts automatically RSS/Atom feeds to
your social network account.
It currently supports Facebook, Twitter, Diaspora, Wordpress and Mastodon.

@author:     Aurelien Grosdidier

@copyright:  2017 Latitude77

@license:    GPL

@contact:    aurelien.grosdidier@gmail.com
'''

import json
import logging
import os
import re
import sqlite3

import lxml.html
import requests
from bs4 import BeautifulSoup

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


class FeedSpora:
    ''' FeedSpora itself. '''

    _client = None
    _feed_urls = None
    _db_file = "feedspora.db"
    _conn = None
    _cur = None
    _ua = "Mozilla/5.0 (X11; Linux x86_64; rv:42.0) Gecko/20100101 " \
          "Firefox/42.0"

    def __init__(self):
        '''
        Initialize
        '''
        logging.basicConfig(level=logging.INFO)
        self._testing = False
        self._testing_accumulator = None

    def set_feed_urls(self, feed_urls):
        '''
        Set feeds URL
        :param feed_urls:
        '''
        self._feed_urls = feed_urls

    def set_db_file(self, db_file):
        '''
        Set database file to track entries that have been already published
        :param db_file:
        '''
        self._db_file = db_file

    def connect(self, client):
        '''
        Connects to your account.
        :param client:
        '''

        if self._client is None:
            self._client = []
        self._client.append(client)

    def _init_db(self):
        '''
        Initialize the connection to the database.
        It also creates the table if the file does not exist yet.
        '''
        should_init = not os.path.exists(self._db_file)
        self._conn = sqlite3.connect(self._db_file)
        self._cur = self._conn.cursor()

        if should_init:
            logging.info("Creating new database file %s", self._db_file)
            sql = "CREATE table posts (id INTEGER PRIMARY KEY, " \
                  "feedspora_id, client_id TEXT)"
            self._cur.execute(sql)
        else:
            logging.info("Found database file %s", self._db_file)

    def set_testing(self, testing):
        '''
        Are we testing feedspora?
        '''
        self._testing = testing

        if self._testing:
            self._testing_accumulator = dict()

    # pylint: disable=no-self-use
    def entry_identifier(self, entry):
        '''
        Defines the identifier associated with the specified entry
        :param entry:
        '''
        # Unique item formed of link data, perhaps with published date
        to_return = entry.link

        if entry.published_date:
            to_return += ' ' + entry.published_date

        return to_return

    # pylint: enable=no-self-use

    def is_already_published(self, entry, client):
        '''
        Checks if a FeedSporaEntry has already been published.
        It checks if it's already in the database of published items.
        :param entry:
        :param client:
        '''
        pub_item = self.entry_identifier(entry)
        sql = "SELECT id from posts WHERE feedspora_id=:feedspora_id AND "\
              "client_id=:client_id"
        self._cur.execute(sql, {
            "feedspora_id": pub_item,
            "client_id": client.get_account()['name']
        })
        already_published = self._cur.fetchone() is not None

        if already_published:
            logging.info('Skipping already published entry in %s: %s',
                         client.get_account()['name'], entry.title)
        else:
            logging.info('Found entry to publish in %s: %s',
                         client.get_account()['name'], entry.title)

        return already_published

    def add_to_published_entries(self, entry, client):
        '''
        Add a FeedSporaEntries to the database of published items.
        :param entry:
        :param client:
        '''
        pub_item = self.entry_identifier(entry)
        logging.info('Storing in database of published items: %s', pub_item)
        self._cur.execute(
            "INSERT INTO posts (feedspora_id, client_id) "
            "values (?,?)", (pub_item, client.get_account()['name']))
        self._conn.commit()

    def _publish_entry(self, item_num, entry):
        '''
        Publish a FeedSporaEntry to your all your registered account.
        :param item_num:
        :param entry:
        '''

        if not self._client:
            logging.error(
                "No client found, aborting publication", exc_info=True)

            return
        logging.info('Publishing: %s', entry.title)

        for client in self._client:

            if not self.is_already_published(entry, client):
                # pylint: disable=broad-except
                try:
                    posted_to_client = client.post_within_limits(entry)
                except Exception as error:
                    logging.error(
                        "Error while publishing '%s' to client"
                        " '%s' : %s",
                        entry.title,
                        client.__class__.__name__,
                        format(error),
                        exc_info=True)

                    continue

                if posted_to_client or client.seeding_published_db(item_num):
                    try:
                        self.add_to_published_entries(entry, client)
                    except Exception as error:
                        logging.error(
                            "Error while storing '%s' to client"
                            "'%s' : %s",
                            entry.title,
                            client.__class__.__name__,
                            format(error),
                            exc_info=True)
                # pylint: enable=broad-except

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

    def _process_feed(self, feed_url):
        '''
        Handle RSS/Atom feed
        It retrieves the feed content and publish entries that haven't been
        published yet.
        :param feed_url:
        '''
        # get feed content
        try:
            soup = self.retrieve_feed_soup(feed_url)
        except (requests.exceptions.ConnectionError, ValueError,
                OSError) as error:
            logging.error(
                "Error while reading feed at %s: %s",
                feed_url,
                format(error),
                exc_info=True)

            return

        # Choose which generator to use, or abort.

        if soup.find('entry'):
            entry_generator = self.parse_atom(soup)
        elif soup.find('item'):
            entry_generator = self.parse_rss(soup)
        else:
            print("No entry/item found in %s" % feed_url)

            return
        entry_count = 0

        for entry in entry_generator:
            entry_count += 1
            self._publish_entry(entry_count, entry)

        if self._testing:
            output = {
                client.get_account()['name']: client.pop_testing_output()

                for client in self._client
            }
            self._testing_accumulator[feed_url] = output

    def run(self):
        '''
        Run FeedSpora: initialize the database and process the list of
        feed URLs.
        '''

        if not self._client:
            logging.error(
                "No client found, aborting publication", exc_info=True)

            return

        self._init_db()

        for feed_url in self._feed_urls:
            self._process_feed(feed_url)

        if self._testing:
            print(json.dumps(self._testing_accumulator, indent=4))
