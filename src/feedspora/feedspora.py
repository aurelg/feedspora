#!/usr/bin/env python3
# encoding: utf-8
'''
FeedSpora is a bot that post automatically RSS/Atom feeds to your Diaspora account.
This file defines a DiaspyClient, a FeedSpora Entry, and FeedSpora itself.

@author:     Aurelien Grosdidier

@copyright:  2015 Latitude77

@license:    GPL

@contact:    aurelien.grosdidier@gmail.com
'''


import sqlite3
import os
import logging
import urllib
from bs4 import BeautifulSoup
import diaspy.models
import diaspy.streams
import diaspy.connection
from urllib.error import HTTPError

class DiaspyClient:
    """ The DiaspyClient handles the connection to Diaspora """

    def __init__(self, pod, username, password):
        """ Should be self-explaining. """
        self.connection = diaspy.connection.Connection(pod=pod,
                                                       username=username,
                                                       password=password)
        self.connection.login()
        self.stream = diaspy.streams.Stream(self.connection, 'stream.json')

    def post(self, text):
        """ Post content to your public timeline. """
        return self.stream.post(text, aspect_ids='public', provider_display_name='FeedSpora')

class FeedSporaEntry(object):
    """ A FeedSpora entry.
    This class is generated from each entry/item in an Atom/RSS feed,
    then posted to your Diaspora account """
    title = ''
    link = ''
    content = ''
    keywords = None

class FeedSpora(object):
    """ FeedSpora itself. """

    _diaspy_client = None
    _feed_urls = None
    _db_file = "feedspora.db"
    _conn = None
    _cur = None

    def __init__(self):
        logging.basicConfig(level=logging.INFO)

    def set_feed_urls(self, feed_urls):
        """ Set feeds URL """
        self._feed_urls = feed_urls

    def set_db_file(self, db_file):
        """ Set database file to track entries that have been already published """
        self._db_file = db_file

    def connect(self, pod, username, password):
        """ Connects to your Diaspora pod. """
        self._diaspy_client = DiaspyClient(pod, username, password)

    def _init_db(self):
        """ Initialize the connection to the database.
        It also creates the table if the file does not exist yet."""
        should_init = not os.path.exists(self._db_file)
        self._conn = sqlite3.connect(self._db_file)
        self._cur = self._conn.cursor()
        if should_init:
            logging.info('Creating new database file '+self._db_file)
            self._cur.execute("CREATE table posts (id INTEGER PRIMARY KEY, feedspora_id TEXT)")
        else:
            logging.info('Found database file '+self._db_file)

    def _parse_atom(self, soup):
        """ Generate FeedSpora entries out of an Atom feed. """
        for entry in soup.find_all('entry')[::-1]:
            fse = FeedSporaEntry()
            fse.title = entry.find('title').text
            fse.link = entry.find('link')['href']
            fse.content = fse.title
            fse.keywords = [keyword['term'].replace(' ', '_').strip()
                            for keyword in entry.find_all('category')]
            yield fse

    def _parse_rss(self, soup):
        """ Generate FeedSpora entries out of a RSS feed. """
        for entry in soup.find_all('item')[::-1]:
            fse = FeedSporaEntry()
            fse.title = entry.find('title').text
            fse.link = entry.find('link').text
            fse.content = fse.title
            fse.keywords = [keyword.text.replace(' ', '_').strip()
                            for keyword in entry.find_all('category')]
            yield fse

    def is_already_published(self, entry):
        """ Checks if a FeedSporaEntry has already been published.
        It checks if it's already in the database of published items.
        """
        self._cur.execute("SELECT id from posts WHERE feedspora_id=:feedspora_id",
                          {"feedspora_id": entry.link})
        already_published = self._cur.fetchone() is not None
        if already_published:
            logging.info('Skipping already published entry: '+entry.title)
        else:
            logging.info('Found entry to publish: '+entry.title)
        return already_published

    def add_to_published_entries(self, entry):
        """ Add a FeedSporaEntries to the database of published items. """
        logging.info('Storing in database of published items: '+entry.title)
        self._cur.execute("INSERT INTO posts (feedspora_id) values (?)",
                          (entry.link,))
        self._conn.commit()

    def _publish_entry(self, entry):
        """ Publish a FeedSporaEntry to your Diaspora account. """
        logging.info('Publishing: '+entry.title)
        post_text = '['+entry.title+']('+entry.link+')'
        if len(entry.keywords) > 0:
            post_text += ' #' + ' #'.join(entry.keywords)
        self._diaspy_client.post(post_text)
        self.add_to_published_entries(entry)

    def _process_feed(self, feed_url):
        """ Handle RSS/Atom feed
        It retrieves the feed content and publish entries that haven't been published yet. """
        # get feed content
        try:
            feed_content = urllib.request.urlopen(feed_url).read()
        except HTTPError as error:
            logging.error("Error while reading feed at " + feed_url + ": " + format(error))
            return
        soup = BeautifulSoup(feed_content, 'html.parser')
        if soup.find('entry'):
            entry_generator = self._parse_atom(soup)
        elif soup.find('item'):
            entry_generator = self._parse_rss(soup)
        else:
            raise Exception("Unknown format")
        [self._publish_entry(entry)
         for entry in entry_generator
         if not self.is_already_published(entry)]

    def run(self):
        """ Run FeedSpora: initialize the database and process the list of feed URLs."""
        self._init_db()
        [self._process_feed(feed_url) for feed_url in self._feed_urls]
