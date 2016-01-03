#!/usr/bin/env python3
# encoding: utf-8
'''
FeedSpora is a bot that posts automatically RSS/Atom feeds to your social network account.
It currently supports Facebook, Twitter and Diaspora.

@author:     Aurelien Grosdidier

@copyright:  2015 Latitude77

@license:    GPL

@contact:    aurelien.grosdidier@gmail.com
'''


import sqlite3
import os
import logging
import urllib
from urllib.error import HTTPError

from bs4 import BeautifulSoup
import diaspy.models
import diaspy.streams
import diaspy.connection
import tweepy
import facebook

class GenericClient(object):
    '''
    Implements the case functionalities expected from clients
    '''

    _name = None

    def set_name(self, name):
        '''
        Client name setter
        :param name:
        '''
        self._name = name

    def get_name(self):
        '''
        Client name getter
        '''
        return self._name

class FacebookClient(GenericClient):
    """ The FacebookClient handles the connection to Facebook. """
    # See https://stackoverflow.com/questions/11510850/python-facebook-api-need-a-working-example
    # https://github.com/pythonforfacebook/facebook-sdk
    # https://facebook-sdk.readthedocs.org/en/latest/install.html
    _graph = None
    _post_as = None

    def __init__(self, account):
        self._graph = facebook.GraphAPI(account['token'])
        profile = self._graph.get_object('me')
        self._post_as = account['post_as'] if 'post_as' in account else profile['id']

    def post(self, entry):
        '''
        Post entry to Facebook.
        :param entry:
        '''
        text = entry.title + ' '.join(['#'+keyword for keyword in entry.keywords])
        attachment = {'name': entry.title, 'link': entry.link}
        self._graph.put_wall_post(text, attachment, self._post_as)

class TweepyClient(GenericClient):
    """ The TweepyClient handles the connection to Twitter. """

    _api = None

    def __init__(self, account):
        """ Should be self-explaining. """
        # handle auth
        # See https://tweepy.readthedocs.org/en/v3.2.0/auth_tutorial.html#auth-tutorial
        auth = tweepy.OAuthHandler(account['consumer_token'], account['consumer_secret'])
        auth.set_access_token(account['access_token'], account['access_token_secret'])
        self._api = tweepy.API(auth)

    def post(self, entry):
        """ Post entry to Twitter. """
        if len(entry.title) < 110:
            text = entry.title
        else:
            text = ''
            for word in [' '+word for word in entry.title.split(' ')]:
                if len(text) + len(word) < 100:
                    text += word
                else:
                    text += "..."
                    break
        if len(entry.keywords) > 0:
            for keyword in [' #'+keyword for keyword in entry.keywords]:
                if len(text) + len(keyword) < 111:
                    text += keyword
                else:
                    break
        text += ' '+entry.link
        self._api.update_status(text.encode('utf-8'))

class DiaspyClient(GenericClient):
    """ The DiaspyClient handles the connection to Diaspora. """

    def __init__(self, account):
        """ Should be self-explaining. """
        self.connection = diaspy.connection.Connection( \
            pod=account['pod'],
            username=account['username'],
            password=account['password'])
        self.connection.login()
        self.stream = diaspy.streams.Stream(self.connection, 'stream.json')
        self.keywords = []
        try:
            self.keywords = [kw.strip() for kw in account['keywords'].split(',')]
        except KeyError:
            pass

    def post(self, entry):
        """ Post entry to Diaspora. """
        text = '['+entry.title+']('+entry.link+')'
        if len(self.keywords) > 0:
            text += ' #' + ' #'.join(self.keywords)
        if len(entry.keywords) > 0:
            text += ' #' + ' #'.join(entry.keywords)
        return self.stream.post(text, aspect_ids='public', provider_display_name='FeedSpora')

class FeedSporaEntry(object):
    """ A FeedSpora entry.
    This class is generated from each entry/item in an Atom/RSS feed,
    then posted to your client accounts """
    title = ''
    link = ''
    content = ''
    keywords = None

class FeedSpora(object):
    """ FeedSpora itself. """

    _client = None
    _feed_urls = None
    _db_file = "feedspora.db"
    _conn = None
    _cur = None
    #_ua = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:12.0) Gecko/20100101 Firefox/12.0'
    _ua = 'Mozilla/5.0 (X11; Linux x86_64; rv:42.0) Gecko/20100101 Firefox/42.0'

    def __init__(self):
        logging.basicConfig(level=logging.INFO)

    def set_feed_urls(self, feed_urls):
        """ Set feeds URL """
        self._feed_urls = feed_urls

    def set_db_file(self, db_file):
        """ Set database file to track entries that have been already published """
        self._db_file = db_file

    def connect(self, client):
        """ Connects to your account. """
        if self._client is None:
            self._client = []
        self._client.append(client)

    def _init_db(self):
        """ Initialize the connection to the database.
        It also creates the table if the file does not exist yet."""
        should_init = not os.path.exists(self._db_file)
        self._conn = sqlite3.connect(self._db_file)
        self._cur = self._conn.cursor()
        if should_init:
            logging.info('Creating new database file '+self._db_file)
            sql = "CREATE table posts (id INTEGER PRIMARY KEY, feedspora_id, client_id TEXT)"
            self._cur.execute(sql)
        else:
            logging.info('Found database file '+self._db_file)

    def is_already_published(self, entry, client):
        """ Checks if a FeedSporaEntry has already been published.
        It checks if it's already in the database of published items.
        """
        sql = "SELECT id from posts WHERE feedspora_id=:feedspora_id AND client_id=:client_id"
        self._cur.execute(sql, {"feedspora_id": entry.link, "client_id": client.get_name()})
        already_published = self._cur.fetchone() is not None
        if already_published:
            logging.info('Skipping already published entry in '+client.get_name()+
                         ': '+entry.title)
        else:
            logging.info('Found entry to publish in '+client.get_name()+': '+entry.title)
        return already_published

    def add_to_published_entries(self, entry, client):
        """ Add a FeedSporaEntries to the database of published items. """
        logging.info('Storing in database of published items: '+entry.title)
        self._cur.execute("INSERT INTO posts (feedspora_id, client_id) values (?,?)",
                          (entry.link, client.get_name()))
        self._conn.commit()

    def _publish_entry(self, entry):
        """ Publish a FeedSporaEntry to your all your registered account. """
        if self._client is None:
            logging.error("No client found, aborting publication")
            return
        logging.info('Publishing: '+entry.title)
        for client in self._client:
            if not self.is_already_published(entry, client):
                try:
                    client.post(entry)
                    self.add_to_published_entries(entry, client)
                except Exception as error:
                    logging.error("Error while publishing '" + entry.title +
                                  "' to client '" + client.__class__.__name__ +
                                  "': "+ format(error))

    def _retrieve_feed_soup(self, feed_url):
        """ Retrieve and parse the specified feed.
        :param feed_url: can either be a URL or a path to a local file
        """
        feed_content = None
        try:
            logging.info("Trying to read %s as a file.", feed_url)
            with open(feed_url, encoding='utf-8') as feed_file:
                feed_content = ''.join(feed_file.readlines())
        except FileNotFoundError:
            logging.info("File not found.")
            logging.info("Trying to read %s as a URL.", feed_url)
            req = urllib.request.Request(url=feed_url,
                                         data=b'None',
                                         headers={'User-Agent': self._ua})
            feed_content = urllib.request.urlopen(req).read()
        logging.info("Feed read.")
        return BeautifulSoup(feed_content, 'html.parser')

    def _process_feed(self, feed_url):
        """ Handle RSS/Atom feed
        It retrieves the feed content and publish entries that haven't been published yet. """
        # get feed content
        try:
            soup = self._retrieve_feed_soup(feed_url)
        except (HTTPError, ValueError, OSError, urllib.error.URLError) as error:
            logging.error("Error while reading feed at " + feed_url + ": " + format(error))
            return
        # Define generator for Atom
        def parse_atom(soup):
            """ Generate FeedSpora entries out of an Atom feed. """
            for entry in soup.find_all('entry')[::-1]:
                fse = FeedSporaEntry()
                try:
                    fse.title = BeautifulSoup(entry.find('title').text,
                                              'html.parser').find('a').text
                except AttributeError:
                    fse.title = entry.find('title').text
                fse.link = entry.find('link')['href']
                fse.content = entry.find('content').text
                fse.keywords = [keyword['term'].replace(' ', '_').lower().strip()
                                for keyword in entry.find_all('category')]
                fse.keywords += [word[1:]
                                 for word in fse.title.split()
                                 if word.startswith('#') and not word in fse.keywords]
                yield fse
        # Define generator for RSS
        def parse_rss(soup):
            """ Generate FeedSpora entries out of a RSS feed. """
            for entry in soup.find_all('item')[::-1]:
                fse = FeedSporaEntry()
                fse.title = entry.find('title').text
                fse.link = entry.find('link').text
                fse.content = entry.find('description').text
                fse.keywords = [keyword.text.replace(' ', '_').lower().strip()
                                for keyword in entry.find_all('category')]
                fse.keywords += [word[1:]
                                 for word in fse.title.split()
                                 if word.startswith('#') and not word in fse.keywords]
                yield fse
        # Choose which generator to use, or abort.
        if soup.find('entry'):
            entry_generator = parse_atom(soup)
        elif soup.find('item'):
            entry_generator = parse_rss(soup)
        else:
            raise Exception("Unknown format")
        for entry in entry_generator:
            self._publish_entry(entry)

    def run(self):
        """ Run FeedSpora: initialize the database and process the list of feed URLs."""
        self._init_db()
        for feed_url in self._feed_urls:
            self._process_feed(feed_url)
