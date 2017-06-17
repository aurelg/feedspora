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


import sqlite3
import os
import logging
import time
import re
import requests
import urllib
from urllib.error import HTTPError
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import diaspy.models
import diaspy.streams
import diaspy.connection
import tweepy
import facebook
from mastodon import Mastodon
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost
from shaarpy.shaarpy import Shaarpy
from readability.readability import Document, Unparseable


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
        def rl(text):
            return len(text.encode('utf-8'))
        if rl(entry.title) < 110:
            text = entry.title
        else:
            text = ''
            for word in [' '+word for word in entry.title.split(' ')]:
                if rl(text) + rl(word) < 100:
                    text += word
                else:
                    text += "..."
                    break
        if len(entry.keywords) > 0:
            for keyword in entry.keywords:
                # Check if it's already in the title (case insensitive)
                #
                newtext = text

                pattern = r'(\A|\W)(%s)(\W|\Z)' % re.escape('%s' % keyword)
                if re.search(pattern, text, re.IGNORECASE):
                    def repl(m):
                        return '%s#%s%s' % (m.group(1), m.group(2), m.group(3))
                    newtext = re.sub(pattern,
                                     repl,
                                     newtext,
                                     flags=re.IGNORECASE)
                else:
                    newtext = text + " #" + keyword
                if rl(newtext) < 111:
                    text = newtext
                else:
                    break
        text += ' '+entry.link
        self._api.update_status(text.encode('utf-8'))


class DiaspyClient(GenericClient):
    """ The DiaspyClient handles the connection to Diaspora. """

    def __init__(self, account):
        """ Should be self-explaining. """
        self.connection = diaspy.connection.Connection(
            pod=account['pod'],
            username=account['username'],
            password=account['password'])
        self.connection.login()
        try:
            self.stream = diaspy.streams.Stream(self.connection, 'stream.json')
        except diaspy.errors.PostError as e:
            logging.error("Cannot get diaspy stream: {}".format(str(e)))
            self.stream = None
            pass
        self.keywords = []
        try:
            self.keywords = [kw.strip() for kw in account['keywords'].split(',')]
        except KeyError:
            pass

    def post(self, entry):
        if self.stream is None:
            logging.info("Diaspy stream is None, not posting anything")
            return True
        """ Post entry to Diaspora. """
        text = '['+entry.title+']('+entry.link+')'
        if len(self.keywords) > 0:
            text += ' #' + ' #'.join(self.keywords)
        if len(entry.keywords) > 0:
            text += ' #' + ' #'.join(entry.keywords)
        return self.stream.post(text, aspect_ids='public', provider_display_name='FeedSpora')


class WPClient(GenericClient):
    """ The WPClient handles the connection to Wordpress. """

    def __init__(self, account):
        """ Should be self-explaining. """
        self.client = Client(account['wpurl'],
                             account['username'],
                             account['password'])
        self.keywords = []
        try:
            self.keywords = [kw.strip()
                             for kw in account['keywords'].split(',')]
        except KeyError:
            pass

    def get_content(self, url):
        """ Retrieve URL content and parse it w/ readability if it's HTML """
        r = requests.get(url)
        content = ''
        if r.status_code == requests.codes.ok and\
           r.headers['Content-Type'].find('html') != -1:
            try:
                content = Document(r.text).summary()
            except Unparseable:
                pass
        return content

    def post(self, entry):
        """ Post entry to Wordpress. """

        # get text with readability
        post = WordPressPost()
        post.title = entry.title
        post.content = "Source: <a href='{}'>{}</a><hr\>{}".format(
                entry.link,
                urlparse(entry.link).netloc,
                self.get_content(entry.link))
        post.terms_names = {'post_tag': entry.keywords,
                            'category': ["AutomatedPost"]}
        post.post_status = 'publish'
        self.client.call(NewPost(post))


class MastodonClient(GenericClient):
    """ The MastodonClient handles the connection to Mastodon. """
    _mastodon = None

    def __init__(self, account):
        """ Should be self-explaining. """
        client_id = '17a4d9914ec02ada3e9b61c2df1651cec091266877d1f92bcaa7964ba4045f99'
        client_secret = '4d027369768026475fea1992aaeda2cb6e3f76e539f1cad195ae38578639fc36'
        self._mastodon = Mastodon(client_id=client_id,
                                  client_secret=client_secret)
        self._mastodon.log_in(
            account['username'],
            account['password']
        )
        self._delay = 0 if 'delay' not in account else account['delay']
        self._visibility = 'unlisted' if 'visibility' not in account or \
            account['visibility'] not in ['public', 'unlisted', 'private'] \
            else account['visibility']

    def post(self, entry):
        def rl(text):
            return len(text.encode('utf-8'))
        if rl(entry.title) < 450:
            text = entry.title
        else:
            text = ''
            for word in [' '+word for word in entry.title.split(' ')]:
                if rl(text) + rl(word) < 450:
                    text += word
                else:
                    text += "..."
                    break
        if len(entry.keywords) > 0:
            for keyword in entry.keywords:
                # Check if it's already in the title (case insensitive)
                #
                newtext = text

                pattern = r'(\A|\W)(%s)(\W|\Z)' % re.escape('%s' % keyword)
                if re.search(pattern, text, re.IGNORECASE):
                    def repl(m):
                        return '%s#%s%s' % (m.group(1), m.group(2), m.group(3))
                    newtext = re.sub(pattern,
                                     repl,
                                     newtext,
                                     flags=re.IGNORECASE)
                else:
                    newtext = text + " #" + keyword
                if rl(newtext) < 450:
                    text = newtext
                else:
                    break
        text += ' '+entry.link
        self._mastodon.status_post(text, visibility=self._visibility)
        if self._delay > 0:
            time.sleep(self._delay)


class ShaarpyClient(GenericClient):
    """ The ShaarpyClient handles the connection to Shaarli. """
    _shaarpy = None

    def __init__(self, account):
        """ Should be self-explaining. """
        self._shaarpy = Shaarpy()
        self._shaarpy.login(account['username'],
                            account['password'],
                            account['url'])

    def post(self, entry):
        content = entry.content
        try:
            soup = BeautifulSoup(entry.content, 'html.parser')
            content = soup.text
        except Exception:
            pass
        self._shaarpy.post_link(entry.link,
                                entry.keywords,
                                title=entry.title,
                                desc=content)


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
                except Exception as error:
                    logging.error("Error while publishing '" + entry.title +
                                  "' to client '" + client.__class__.__name__ +
                                  "': " + format(error))
                try:
                    self.add_to_published_entries(entry, client)
                except Exception as error:
                    logging.error("Error while storing '" + entry.title +
                                  "' to client '" + client.__class__.__name__ +
                                  "': " + format(error))

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
                try:
                    fse.content = entry.find('content').text
                except AttributeError:
                    fse.content = ''
                fse.keywords = [keyword['term'].replace(' ', '_').strip()
                                for keyword in entry.find_all('category')]
                fse.keywords += [word[1:]
                                 for word in fse.title.split()
                                 if word.startswith('#') and word not in fse.keywords]
                yield fse

        # Define generator for RSS
        def parse_rss(soup):
            """ Generate FeedSpora entries out of a RSS feed. """
            for entry in soup.find_all('item')[::-1]:
                fse = FeedSporaEntry()
                fse.title = entry.find('title').text
                fse.link = entry.find('link').text
                fse.content = entry.find('description').text
                fse.keywords = [keyword.text.replace(' ', '_').strip()
                                for keyword in entry.find_all('category')]
                fse.keywords += [word[1:]
                                 for word in fse.title.split()
                                 if word.startswith('#') and word not in fse.keywords]
                yield fse
        # Choose which generator to use, or abort.
        if soup.find('entry'):
            entry_generator = parse_atom(soup)
        elif soup.find('item'):
            entry_generator = parse_rss(soup)
        else:
            print("No entry/item found in %s" % feed_url)
            os.sys.exit(1)
        for entry in entry_generator:
            self._publish_entry(entry)

    def run(self):
        """ Run FeedSpora: initialize the database and process the list of feed URLs."""
        self._init_db()
        for feed_url in self._feed_urls:
            self._process_feed(feed_url)
