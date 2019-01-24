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
import sqlite3

class FeedSpora:
    ''' FeedSpora itself. '''

    _client = None
    _feed = None
    _db_file = "feedspora.db"
    _conn = None
    _cur = None

    def __init__(self):
        '''
        Initialize
        '''
        logging.basicConfig(level=logging.INFO)
        self._testing = False
        self._testing_accumulator = None

    def set_db_file(self, db_file):
        '''
        Set database file to track entries that have been already published
        :param db_file:
        '''
        self._db_file = db_file

    def connect_client(self, client):
        '''
        Connects to your client.
        :param client:
        '''

        if self._client is None:
            self._client = []
        self._client.append(client)

    def connect_feed(self, feed):
        '''
        Connects to your feed.
        :param feed:
        '''

        if self._feed is None:
            self._feed = []
        self._feed.append(feed)

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
            "client_id": client.get_config()['name']
        })
        already_published = self._cur.fetchone() is not None

        if already_published:
            logging.info('Skipping already published entry in %s: %s',
                         client.get_config()['name'], entry.title)
        else:
            logging.info('Found entry to publish in %s: %s',
                         client.get_config()['name'], entry.title)

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
            "values (?,?)", (pub_item, client.get_config()['name']))
        self._conn.commit()

    def _publish_entry(self, entry, entry_count, feed, feed_count):
        '''
        Publish a FeedSporaEntry to your all your registered account.
        :param entry:
        :param entry_count:
        :param feed:
        :param feed_count:
        '''

        if not self._client:
            logging.error(
                "No client found, aborting publication", exc_info=True)

            return
        logging.info('Publishing: %s', entry.title)

        entry_published = False
        for client in self._client:
            if not self.is_already_published(entry, client):
                # pylint: disable=broad-except
                try:
                    posted_to_client = client.post_within_limits(entry, feed)
                except Exception as error:
                    logging.error(
                        "Error while publishing '%s' to client"
                        " '%s' : %s",
                        entry.title,
                        client.__class__.__name__,
                        format(error),
                        exc_info=True)

                    continue

                if posted_to_client:
                    entry_published = True

                if posted_to_client or \
                   client.seeding_published_db(entry_count, feed, feed_count):
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

        if entry_published:
            feed.increment_posts_done()

    def _process_feed(self, entry_count, feed):
        '''
        Handle the feed content and publish entries that haven't been
        published yet.
        :param entry_count:
        :param feed:
        '''

        entry_generator = feed.feed_generator()
        if entry_generator:
            feed_count = 0
            for entry in entry_generator:
                entry_count += 1
                feed_count += 1
                self._publish_entry(entry, entry_count, feed, feed_count)
                if feed.max_posts_done():
                    # If feed limit reached, we're done here; break out
                    logging.info("Configured feed limit of %d reached.",
                                 feed.get_config()['max_posts'])
                    break

            if self._testing:
                output = {
                    client.get_config()['name']: client.pop_testing_output()

                    for client in self._client
                }
                self._testing_accumulator[feed.get_path()] = output
        return entry_count

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

        entry_count = 0
        for feed in self._feed:
            entry_count = self._process_feed(entry_count, feed)

        if self._testing:
            print(json.dumps(self._testing_accumulator, indent=4))
