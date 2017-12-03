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
from linkedin import linkedin


def trim_string(text, maxlen, etc='...', etc_if_shorter_than=None):
    if len(text) < maxlen:
        to_return = text
    else:
        tmpmaxlen = maxlen - len(etc)
        space_pos = [x for x in range(0, len(text))
                     if text[x] == ' ' and x < tmpmaxlen]
        cut_at = space_pos[-1] if len(space_pos) > 0 else tmpmaxlen
        to_return = text[:cut_at]
        if etc_if_shorter_than is not None and cut_at < etc_if_shorter_than:
            to_return += etc
    return to_return


def mkrichtext(text, keywords, maxlen=None, etc='...', separator=' |'):

    def repl(m):
        return '%s#%s%s' % (m.group(1), m.group(2), m.group(3))

    keywords = set(keywords)

    # Find inline and extra keywords
    to_return = text.rstrip('.')
    inline_kw = {k for k in keywords
                 if re.search(r'(\A|\W)(%s)(\W|\Z)' % re.escape('%s' % k),
                              to_return, re.IGNORECASE)}
    extra_kw = keywords - inline_kw

    # Add inline keywords
    for kw in inline_kw:
        pattern = r'(\A|\W)(%s)(\W|\Z)' % re.escape('%s' % kw)
        if re.search(pattern, to_return, re.IGNORECASE):
            to_return = re.sub(pattern, repl, to_return, flags=re.IGNORECASE)

    # Add separator and keywords, if needed
    minlen_wo_xtra_kw = len(to_return)
    if len(extra_kw) > 0:
        fake_separator = separator.replace(' ', '_')
        to_return += fake_separator
        minlen_wo_xtra_kw = len(to_return)

        # Add extra keywords
        for kw in extra_kw:
            to_return += " #" + kw

    # If the text is too long, cut it and, if needed, add suffix
    if maxlen is not None:
        to_return = trim_string(to_return, maxlen, etc=etc,
                                etc_if_shorter_than=minlen_wo_xtra_kw)

    # Restore separator
    if len(extra_kw) > 0:
        to_return = to_return.replace(fake_separator, separator)

        # Remove separator if nothing comes after it
        stripped_separator = separator.rstrip()
        if to_return.endswith(stripped_separator):
            to_return = to_return[:-len(stripped_separator)]

    if maxlen is not None:
        assert not len(to_return) > maxlen, \
            "{}:{} : {} > {}".format(text, to_return, len(to_return), maxlen)
    return to_return


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
    # See https://stackoverflow.com/questions/11510850/
    #     python-facebook-api-need-a-working-example
    # https://github.com/pythonforfacebook/facebook-sdk
    # https://facebook-sdk.readthedocs.org/en/latest/install.html
    _graph = None
    _post_as = None

    def __init__(self, account):
        self._graph = facebook.GraphAPI(account['token'])
        profile = self._graph.get_object('me')
        self._post_as = account['post_as'] if 'post_as' in account \
            else profile['id']

    def post(self, entry):
        '''
        Post entry to Facebook.
        :param entry:
        '''
        text = entry.title + ''.join([' #{}'.format(k)
                                      for k in entry.keywords])
        attachment = {'name': entry.title, 'link': entry.link}
        return self._graph.put_wall_post(text, attachment, self._post_as)


class TweepyClient(GenericClient):
    """ The TweepyClient handles the connection to Twitter. """

    _api = None

    def __init__(self, account):
        """ Should be self-explaining. """
        # handle auth
        # See https://tweepy.readthedocs.org/en/v3.2.0/auth_tutorial.html
        # #auth-tutorial
        auth = tweepy.OAuthHandler(account['consumer_token'],
                                   account['consumer_secret'])
        auth.set_access_token(account['access_token'],
                              account['access_token_secret'])
        self._link_cost = 22
        self._max_len = 280
        self._api = tweepy.API(auth)

    def post(self, entry):
        """ Post entry to Twitter. """
        putative_urls = re.findall('[a-zA-Z0-9]+\.[a-zA-Z]{2,3}',
                                   entry.title)
        # Infer the 'inner links' Twitter may charge length for
        adjust_with_inner_links = self._link_cost + \
            sum([self._link_cost - len(u) for u in putative_urls])
        maxlen = self._max_len - adjust_with_inner_links - 1  # for last ' '
        text = mkrichtext(entry.title, entry.keywords, maxlen=maxlen)
        text += ' '+entry.link
        return self._api.update_status(text)


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
            self.keywords = [kw.strip()
                             for kw in account['keywords'].split(',')]
        except KeyError:
            pass

    def post(self, entry):
        if self.stream is None:
            logging.info("Diaspy stream is None, not posting anything")
            return True
        """ Post entry to Diaspora. """
        text = '['+entry.title+']('+entry.link+')' \
            + ' | ' + ''.join([" #{}".format(k) for k in self.keywords]) \
            + ' ' + ''.join([" #{}".format(k) for k in entry.keywords])
        return self.stream.post(text, aspect_ids='public',
                                provider_display_name='FeedSpora')


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
        client_id = account['client_id']
        client_secret = account['client_secret']
        access_token = account['access_token']
        api_base_url = account['url']
        self._mastodon = Mastodon(client_id=client_id,
                                  client_secret=client_secret,
                                  access_token=access_token,
                                  api_base_url=api_base_url)
        self._delay = 0 if 'delay' not in account else account['delay']
        self._visibility = 'unlisted' if 'visibility' not in account or \
            account['visibility'] not in ['public', 'unlisted', 'private'] \
            else account['visibility']

    def post(self, entry):
        maxlen = 500 - len(entry.link) - 1
        text = mkrichtext(entry.title, entry.keywords, maxlen=maxlen)
        text += ' '+entry.link
        if self._delay > 0:
            time.sleep(self._delay)
        return self._mastodon.status_post(text, visibility=self._visibility)


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
        return self._shaarpy.post_link(entry.link,
                                       list(entry.keywords),
                                       title=entry.title,
                                       desc=content)


class LinkedInClient(GenericClient):
    """ The LinkedInClient handles the connection to LinkedIn. """
    _linkedin = None

    def __init__(self, account):
        """ Should be self-explaining. """
        self._linkedin = linkedin.LinkedInApplication(
            token=account['authentication_token'])

    def post(self, entry):
        return self._linkedin.submit_share(
            comment=mkrichtext(entry.title, entry.keywords, maxlen=700),
            title=trim_string(entry.title, 200),
            description=trim_string(entry.title, 256),
            submitted_url=entry.link)


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
    _ua = "Mozilla/5.0 (X11; Linux x86_64; rv:42.0) Gecko/20100101 " \
          "Firefox/42.0"

    def __init__(self):
        logging.basicConfig(level=logging.INFO)

    def set_feed_urls(self, feed_urls):
        """ Set feeds URL """
        self._feed_urls = feed_urls

    def set_db_file(self, db_file):
        """ Set database file to track entries that have been already
            published """
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
            sql = "CREATE table posts (id INTEGER PRIMARY KEY, " \
                  "feedspora_id, client_id TEXT)"
            self._cur.execute(sql)
        else:
            logging.info('Found database file '+self._db_file)

    def is_already_published(self, entry, client):
        """ Checks if a FeedSporaEntry has already been published.
        It checks if it's already in the database of published items.
        """
        sql = "SELECT id from posts WHERE feedspora_id=:feedspora_id AND "\
              "client_id=:client_id"
        self._cur.execute(sql, {"feedspora_id": entry.link,
                                "client_id": client.get_name()})
        already_published = self._cur.fetchone() is not None
        if already_published:
            logging.info('Skipping already published entry in ' +
                         client.get_name() + ': ' + entry.title)
        else:
            logging.info('Found entry to publish in ' + client.get_name() +
                         ': ' + entry.title)
        return already_published

    def add_to_published_entries(self, entry, client):
        """ Add a FeedSporaEntries to the database of published items. """
        logging.info('Storing in database of published items: '+entry.title)
        self._cur.execute("INSERT INTO posts (feedspora_id, client_id) "
                          "values (?,?)", (entry.link, client.get_name()))
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
                    continue
                try:
                    self.add_to_published_entries(entry, client)
                except Exception as error:
                    logging.error("Error while storing '" + entry.title +
                                  "' to client '" + client.__class__.__name__ +
                                  "': " + format(error))

    def retrieve_feed_soup(self, feed_url):
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

    # Define generator for Atom
    def parse_atom(self, soup):
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
            kw = set()
            kw = kw.union({keyword['term'].replace(' ', '_').strip()
                           for keyword in entry.find_all('category')})
            kw = kw.union({word[1:]
                          for word in fse.title.split()
                          if word.startswith('#')
                          and word not in fse.keywords})
            with open('/tmp/totocat', 'w') as f:
                f.write(str(kw))
            fse.keywords = kw
            yield fse

    # Define generator for RSS
    def parse_rss(self, soup):
        """ Generate FeedSpora entries out of a RSS feed. """
        for entry in soup.find_all('item')[::-1]:
            fse = FeedSporaEntry()
            fse.title = entry.find('title').text
            fse.link = entry.find('link').text
            fse.content = entry.find('description').text
            kw = set()
            kw = kw.union({keyword.text.replace(' ', '_').strip()
                           for keyword in entry.find_all('category')})
            kw = kw.union({word[1:]
                           for word in fse.title.split()
                           if word.startswith('#')})
            fse.keywords = kw
            yield fse

    def _process_feed(self, feed_url):
        """ Handle RSS/Atom feed
        It retrieves the feed content and publish entries that haven't been
        published yet. """
        # get feed content
        try:
            soup = self.retrieve_feed_soup(feed_url)
        except (HTTPError, ValueError, OSError,
                urllib.error.URLError) as error:
            logging.error("Error while reading feed at " + feed_url + ": "
                          + format(error))
            return

        # Choose which generator to use, or abort.
        if soup.find('entry'):
            entry_generator = self.parse_atom(soup)
        elif soup.find('item'):
            entry_generator = self.parse_rss(soup)
        else:
            print("No entry/item found in %s" % feed_url)
            os.sys.exit(1)
        for entry in entry_generator:
            self._publish_entry(entry)

    def run(self):
        """ Run FeedSpora: initialize the database and process the list of
            feed URLs. """
        if self._client is None or len(self._client) == 0:
            logging.error("No client found, aborting publication")
            return
        self._init_db()
        for feed_url in self._feed_urls:
            self._process_feed(feed_url)
