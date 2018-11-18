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
from pyshorteners import Shortener
import lxml.html


# TODO: Still additional shorteners to implement...
# (see https://pypi.org/project/pyshorteners/)
# (see also https://github.com/ellisonleao/pyshorteners/)
# Note that none of the current shorteners below require any keys/tokens...
def shorten_url(the_url,url_shortener):
    to_return = the_url
    _no_params_shorteners = ['Chilpit',
                             'Clkru',
                             'Dagd',
                             'Isgd',
                             'Osdb',
                             'Qpsru',
                             'Readability',
                             'Sentala',
                             'Soogd',
                             'Tinyurl',
                            ]
    if ((the_url is not None) and
        (url_shortener is not None) and
        (url_shortener is not "None")):
        try:
            if (url_shortener in _no_params_shorteners):
                shortener = Shortener(url_shortener,timeout=3)
                to_return = shortener.short(the_url)
        #except NotImplementedError as e:
        # Parameter advertised as existing, but RTEs say otherwise
        # Undoubtedly a pyshorteners version issue
        #    logging.error("URL shortening error: {}".format(str(e)))
        #    logging.info("Available URL shorteners: "+
        #                 ' '.join(Shortener().available_shorteners))
        except Exception as e:
            # Shortening attempt failed - revert to non-shortened link
            logging.error("Cannot shorten URL {} with {}: {}".format(the_url,url_shortener,str(e)))
            to_return = the_url
            pass
    return to_return

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

    to_return = text

    # Find inline and extra keywords
    inline_kw = {k for k in keywords
                 if re.search(r'(\A|\W)(%s)(\W|\Z)' % re.escape('%s' % k),
                              to_return, re.IGNORECASE)}
    # Tag/keyword order needs to be observed
    # Set manipulations ignore that, so don't use them!
    extra_kw = []
    for kw in keywords:
        if kw not in inline_kw:
            extra_kw.append(kw)

    # Process inline keywords
    for kw in inline_kw:
        pattern = r'(\A|\W)[^#](%s)(\W|\Z)' % re.escape('%s' % kw)
        if re.search(pattern, to_return, re.IGNORECASE):
            to_return = re.sub(pattern, repl, to_return, flags=re.IGNORECASE)

    # Add separator and keywords, if needed
    minlen_wo_xtra_kw = len(to_return)
    if len(extra_kw) > 0:
        fake_separator = separator.replace(' ', '_')
        to_return += fake_separator
        minlen_wo_xtra_kw = len(to_return)

        # Add extra (ordered) keywords
        for kw in extra_kw:
            # remove any illegal characters
            kw = re.sub('[\-\.]','',kw)
            # prevent duplication
            pattern = r'(\A|\W)#(%s)(\W|\Z)' % re.escape('%s' % kw)
            if re.search(pattern, to_return, re.IGNORECASE) == None:
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

def get_filename_from_cd(cd):
    """
    Get filename from Content-Disposition
    """
    if not cd:
        return None
    fname = re.findall('filename=(.+)', cd)
    if len(fname) == 0:
        return None
    return fname[0]

def download_media(the_url):
    """
    Download the media file referenced by the_url
    Returns the path to the downloaded file
    """

    r = requests.get(the_url, allow_redirects=True)
    filename = get_filename_from_cd(r.headers.get('Content-Disposition'))
    if (filename is None):
      filename = 'random.jpg'
    media_dir = os.getenv('MEDIA_DIR','/tmp');
    full_path = media_dir+'/'+filename
    logging.info("Downloading "+the_url+" as "+full_path+"...")
    open(full_path, 'wb').write(r.content)
    return full_path

class GenericClient(object):
    '''
    Implements the case functionalities expected from clients
    '''

    _name = None
    # Special handling of default (0) value that allows unlimited postings
    _max_posts = 0
    _posts_done = 0

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

    def set_max_posts(self, max_posts):
        '''
        Client max posts setter
        :param max_posts:
        '''
        self._max_posts = max_posts

    def get_max_posts(self):
        '''
        Client max posts getter
        '''
        return self._max_posts

    def is_post_limited(self):
        '''
        Client has a post limit set
        '''
        return (self._max_posts != 0)

    def post_within_limits(self, entry_to_post):
        '''
        Client post entry, as long as within specified limits
        :param entry_to_post:
        '''
        if (self.is_post_limited() and 
            (self._posts_done >= self.get_max_posts())):
            return False
        else:
            to_return = self.post(entry_to_post)
            if to_return:
                self._posts_done += 1
            return to_return

    def seeding_published_db(self, item_num): 
        '''
        Override to post not being published, but marking it as published
        in the DB anyway ("seeding" the published DB)
        :param item_num:
        '''
        return ((self._max_posts < 0) and ((item_num + self._max_posts) <= 0))


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
        # Post/run limit. Negative value implies a seed-only operation.
        if ('max_posts' in account):
            self.set_max_posts(account['max_posts'])
        # Tags/post limit
        # Default.  Essentially "no limit"...
        self._max_tags = 100 
        if ('max_tags' in account):
            self._max_tags = account['max_tags']
        # Shorten URLs?
        self._url_shortener = None
        if ('url_shortener' in account):
            self._url_shortener = account['url_shortener'].capitalize()
        # Post prefix
        self._post_prefix = None
        if ('post_prefix' in account):
            self._post_prefix = account['post_prefix']
        # Post suffix
        self._post_suffix = None
        if ('post_suffix' in account):
            self._post_suffix = account['post_suffix']
        # Include media?
        self._include_media = False
        if ('post_include_media' in account):
            self._include_media = account['post_include_media']
        # Include content?
        self._include_content = False
        if ('post_include_content' in account):
            self._include_content = account['post_include_content']

    def post(self, entry):
        """ Post entry to Twitter. """

        # Shorten the link URL if configured/possible
        post_url = shorten_url(entry.link, self._url_shortener) 

        # TODO: These should all be shortened too, right?
        putative_urls = re.findall('[a-zA-Z0-9]+\.[a-zA-Z]{2,3}',
                                   entry.title)
        # Infer the 'inner links' Twitter may charge length for
        adjust_with_inner_links = self._link_cost + \
            sum([self._link_cost - len(u) for u in putative_urls])
        maxlen = self._max_len - len(post_url) - adjust_with_inner_links - 1  # for last ' '

        # The content with all HTML stripped will be used later, but get it now
        stripped_html = lxml.html.fromstring(entry.content).text_content().strip()
        # Derive additional keywords (tags) from the end of content
        all_keywords = []
        tag_pattern = r'\s+#([\w]+)$'
        m = re.search(tag_pattern, stripped_html)
        while (m):
            tag = m.group(1)
            if (tag not in all_keywords):
                all_keywords.insert(0, tag)
            stripped_html = re.sub(tag_pattern, '', stripped_html)
            m = re.search(tag_pattern, stripped_html)
        if (re.match(r'^#[\w]+$', stripped_html)):
            # Left with a single tag!
            if (stripped_html not in all_keywords):
                all_keywords.insert(0, stripped_html[1:])
                stripped_html = None
        # Now add the original keywords on to the end of the existing array
        for word in entry.keywords:
            if (word not in all_keywords):
                all_keywords.append(word)
	# Apply any tag limits specified
        if (self._max_tags < len(all_keywords)):
            all_keywords = all_keywords[:self._max_tags]

        # Let's build our tweet!
        text = ''
        # Apply optional prefix
        if (self._post_prefix is not None):
            text = self._post_prefix+' '
        raw_contents = entry.title
        if (self._include_content and (stripped_html is not None)):
            raw_contents += ': '+stripped_html
        text += mkrichtext(raw_contents, all_keywords, maxlen=maxlen)
        # Apply optional suffix
        if (self._post_suffix is not None):
            text += ' '+self._post_suffix
        text += ' '+post_url
        if (self._include_media and (entry.media_url is not None)):
            # Need to download image from that URL in order to post it!
            media_path = download_media(entry.media_url)
            if (media_path is not None):
                return self._api.update_with_media(media_path, text)
            else:
                # Punt; post text only
                return self._api.update_status(text)
        else:
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
    _visibility = None

    def __init__(self, account):
        """ Should be self-explaining. """
        self._linkedin = linkedin.LinkedInApplication(
            token=account['authentication_token'])
        self._visibility = account['visibility']

    def post(self, entry):
        return self._linkedin.submit_share(
            comment=mkrichtext(entry.title, entry.keywords, maxlen=700),
            title=trim_string(entry.title, 200),
            description=trim_string(entry.title, 256),
            submitted_url=entry.link, visibility_code=self._visibility)


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

    def entry_identifier(self, entry):
        """Defines the identifier associated with the specified entry"""
        # Unique item formed of link data, perhaps with published date
        to_return = entry.link
        # Try before you buy...
        try: entry.published_date
        except NameError: entry.published_date = None
        if (entry.published_date is not None):
            to_return += ' '+entry.published_date
        return to_return

    def is_already_published(self, entry, client):
        """ Checks if a FeedSporaEntry has already been published.
        It checks if it's already in the database of published items.
        """
        pub_item = self.entry_identifier(entry)
        sql = "SELECT id from posts WHERE feedspora_id=:feedspora_id AND "\
              "client_id=:client_id"
        self._cur.execute(sql, {"feedspora_id": pub_item,
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
        pub_item = self.entry_identifier(entry)
        logging.info('Storing in database of published items: '+pub_item)
        self._cur.execute("INSERT INTO posts (feedspora_id, client_id) "
                          "values (?,?)", (pub_item, client.get_name()))
        self._conn.commit()

    def _publish_entry(self, item_num, entry):
        """ Publish a FeedSporaEntry to your all your registered account. """
        if self._client is None:
            logging.error("No client found, aborting publication")
            return
        logging.info('Publishing: '+entry.title)
        for client in self._client:
            if not self.is_already_published(entry, client):
                try:
                    posted_to_client = client.post_within_limits(entry)
                except Exception as error:
                    logging.error("Error while publishing '" + entry.title +
                                  "' to client '" + client.__class__.__name__ +
                                  "': " + format(error))
                    continue
                if (posted_to_client or client.seeding_published_db(item_num)):
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
                                         data=b'None', method='GET',
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
            if fse.keywords is None:
                fse.keywords = []
            kw = kw.union({word[1:]
                          for word in fse.title.split()
                          if word.startswith('#')
                          and word not in fse.keywords})
            fse.keywords = kw
            yield fse

    # Define generator for RSS
    def parse_rss(self, soup):
        """ Generate FeedSpora entries out of a RSS feed. """
        for entry in soup.find_all('item')[::-1]:
            fse = FeedSporaEntry()
            # Title
            fse.title = entry.find('title').text
            # Link
            fse.link = entry.find('link').text
            # Content takes priority over Description
            if (entry.find('content') is not None):
                fse.content = entry.find('content')[0].text
            else:
                fse.content = entry.find('description').text
            # PubDate
            fse.published_date = entry.find('pubdate').text
            # Keywords (from category)
            kw = set()
            kw = kw.union({keyword.text.replace(' ', '_').strip()
                           for keyword in entry.find_all('category')})
            kw = kw.union({word[1:]
                           for word in fse.title.split()
                           if word.startswith('#')})
            fse.keywords = kw
            # And for our final act, media
            fse.media_url = None
            if ((entry.find('media:content') is not None) and
                (entry.find('media:content')['medium'] == 'image')):
                fse.media_url = entry.find('media:content')['url']
            elif (entry.find('img') is not None):
                # TODO: handle possibility of an incomplete URL (prepend link
                #       site root)
                fse.media_url = entry.find('img')['src']
            # TODO: additional measures to retrieve "buried" image 
            #       specifications, such as within CDATA constructs of
            #       content or description tags
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
            return
        entry_count = 0
        for entry in entry_generator:
            entry_count += 1
            self._publish_entry(entry_count, entry)

    def run(self):
        """ Run FeedSpora: initialize the database and process the list of
            feed URLs. """
        if self._client is None or len(self._client) == 0:
            logging.error("No client found, aborting publication")
            return
        self._init_db()
        for feed_url in self._feed_urls:
            self._process_feed(feed_url)
