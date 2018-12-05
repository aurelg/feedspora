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

import logging
import os
import re
import sqlite3
import time
import urllib
from urllib.error import HTTPError
from urllib.parse import urlparse

import diaspy.connection
import diaspy.models
import diaspy.streams
import facebook
import lxml.html
import pyshorteners
import requests
import tweepy
from bs4 import BeautifulSoup
from linkedin import linkedin
from mastodon import Mastodon
from readability.readability import Document, Unparseable
from shaarpy.shaarpy import Shaarpy
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost


def trim_string(text, maxlen, etc='...', etc_if_shorter_than=None):
    if len(text) < maxlen:
        to_return = text
    else:
        tmpmaxlen = maxlen - len(etc)
        space_pos = [
            x for x in range(0, len(text)) if text[x] == ' ' and x < tmpmaxlen
        ]
        cut_at = space_pos[-1] if space_pos else tmpmaxlen
        to_return = text[:cut_at]

        if etc_if_shorter_than and cut_at < etc_if_shorter_than:
            to_return += etc

    return to_return


def mkrichtext(text, keywords, maxlen=None, etc='...', separator=' |'):
    '''
    Process the text to include hashtagged keywords and adhere to the specified
    maximum length.
    '''
    def repl(m):
        return '%s#%s%s' % (m.group(1), m.group(2), m.group(3))

    # Constants used in regex pattern generation
    # pylint: disable=anomalous-backslash-in-string
    before_tag = '(\A|[\'"/([{\s])'
    after_tag = '(\Z|[\'"/\s)\]},.!?:])'
    # pylint: enable=anomalous-backslash-in-string

    to_return = text

    # Tag/keyword order needs to be observed
    # Set manipulations ignore that, so use lists instead!

    # Find inline and extra keywords
    inline_kw = []
    extra_kw = []
    for word in keywords:
        # remove any illegal characters
        word = re.sub(r'[\-\.]', '', word)
        if re.search(r'%s#?(%s)%s' %
                     (before_tag, re.escape('%s' % word), after_tag),
                     to_return, re.IGNORECASE):
            inline_kw.append(word)
        else:
            extra_kw.append(word)

    # Process inline keywords
    for word in inline_kw:
        pattern = (r'%s(%s)%s' %
                   (before_tag, re.escape('%s' % word), after_tag))
        if re.search(pattern, to_return, re.IGNORECASE):
            to_return = re.sub(pattern, repl, to_return, flags=re.IGNORECASE)

    # Add separator and keywords, if needed
    minlen_wo_xtra_kw = len(to_return)

    if extra_kw:
        fake_separator = separator.replace(' ', '_')
        to_return += fake_separator
        minlen_wo_xtra_kw = len(to_return)

        # Add extra (ordered) keywords
        for word in extra_kw:
            # prevent duplication
            pattern = (r'%s#(%s)%s' % \
                       (before_tag, re.escape('%s' % word), after_tag))
            if re.search(pattern, to_return, re.IGNORECASE) is None:
                to_return += " #" + word

    # If the text is too long, cut it and, if needed, add suffix
    if maxlen is not None:
        to_return = trim_string(
            to_return, maxlen, etc=etc, etc_if_shorter_than=minlen_wo_xtra_kw)

    # Restore separator
    if extra_kw:
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

    to_return = None

    if cd:
        fname = re.findall('filename=(.+)', cd)

        if fname:
            to_return = fname[0]

    return to_return


def download_media(the_url):
    """
    Download the media file referenced by the_url
    Returns the path to the downloaded file
    """

    r = requests.get(the_url, allow_redirects=True)
    filename = get_filename_from_cd(r.headers.get('Content-Disposition'))

    if not filename:
        filename = 'random.jpg'
    media_dir = os.getenv('MEDIA_DIR', '/tmp')
    full_path = media_dir + '/' + filename
    logging.info("Downloading %s as %s...", the_url, full_path)
    open(full_path, 'wb').write(r.content)

    return full_path


class GenericClient:
    '''
    Implements the case functionalities expected from clients
    '''

    _name = None
    # Special handling of default (0) value that allows unlimited postings
    _max_posts = 0
    _posts_done = 0
    _keywords = []
    _url_shortener = None
    _url_shortener_opts = {}
    _max_tags = 100
    _post_prefix = None
    _include_content = False
    _include_media = False
    _post_suffix = None
    _testing_root = None

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

        return self._max_posts != 0

    def post_within_limits(self, entry_to_post):
        '''
        Client post entry, as long as within specified limits
        :param entry_to_post:
        '''
        to_return = False

        if not self.is_post_limited(
        ) or self._posts_done < self.get_max_posts():
            to_return = self.post(entry_to_post)

            if to_return:
                self._posts_done += 1

        return to_return

    def post(self, entry):
        """ Placeholder for post, override it in subclasses """
        raise NotImplementedError("Please implement!")

    def seeding_published_db(self, item_num):
        '''
        Override to post not being published, but marking it as published
        in the DB anyway ("seeding" the published DB)
        :param item_num:
        '''

        return self._max_posts < 0 and item_num + self._max_posts <= 0

    def set_testing_root(self, testing_root):
        '''
        Client testing_root setter
        :param testing_root:
        '''
        self._testing_root = testing_root

    def get_testing_root(self):
        '''
        Client testing_root getter
        '''

        return self._testing_root

    def is_testing(self):
        '''
        Are we testing this client?
        '''

        return self._testing_root is not None

    def output_test(self, text):
        '''
        Print output for testing purposes
        :param: text
        '''
        print(text)

        return True

    def test_output(self, text):
        '''
        Define output for testing purposes (potentially overridden on
        per-client basis - this is the default), then output that definition
        :param: text
        '''
        output = '>>> '+self.get_name()+' posting:\n'+ \
                 'Content: '+text

        return self.output_test(output)

    def shorten_url(self, the_url):
        '''
        Apply configured URL shortener (if present) to the provided link and
        return the result.  If anything goes awry, return the unmodified link.
        '''
        to_return = the_url
        # Default
        short_options = {'timeout': 3}
        short_options.update(self._url_shortener_opts)
        if the_url and self._url_shortener and self._url_shortener != 'none':
            try:
                shortener = pyshorteners.Shortener(**short_options)
                # Verify a legal choice
                assert self._url_shortener in shortener.available_shorteners
                to_return = getattr(shortener, self._url_shortener).short(the_url)
                # Sanity check!
                if len(to_return) > len(the_url):
                    # Not shorter?  You're fired!
                    raise RuntimeError('Shortener %s produced a longer URL ' +
                                       'than the original!',
                                       self._url_shortener)
            # pylint: disable=broad-except
            except Exception as exception:
                # Shortening attempt failed somehow (we don't care how, except
                # for messaging purposes) - revert to non-shortened link
                if isinstance(exception, AssertionError):
                    all_shorteners = ' '.join(shortener.available_shorteners)
                    logging.error('URL shortener %s is unimplemented!',
                                  self._url_shortener)
                    logging.info('Available URL shorteners: %s',
                                 all_shorteners)
                else:
                    logging.error('Cannot shorten URL %s with %s: %s',
                                  the_url, self._url_shortener, str(exception))
                to_return = the_url
            # pylint: enable=broad-except

        return to_return

    def set_common_opts(self, account):
        '''
        Set options common to all clients
        '''

        # Keywords
        if 'keywords' in account:
            self._keywords = [
                word.strip() for word in account['keywords'].split(',')
            ]

        # Post/run limit. Negative value implies a seed-only operation.
        if 'max_posts' in account:
            self.set_max_posts(account['max_posts'])

        if 'max_tags' in account:
            self._max_tags = account['max_tags']

        # Include content?
        if 'post_include_content' in account:
            self._include_content = account['post_include_content']

        # Include media?
        if 'post_include_media' in account:
            self._include_media = account['post_include_media']

        # Post prefix
        if 'post_prefix' in account:
            self._post_prefix = account['post_prefix']

        # Post suffix
        if 'post_suffix' in account:
            self._post_suffix = account['post_suffix']

        if 'url_shortener' in account:
            self._url_shortener = account['url_shortener'].lower()

        if 'url_shortener_opts' in account:
            self._url_shortener_opts = account['url_shortener_opts']


class FacebookClient(GenericClient):
    """ The FacebookClient handles the connection to Facebook. """
    # See https://stackoverflow.com/questions/11510850/
    #     python-facebook-api-need-a-working-example
    # https://github.com/pythonforfacebook/facebook-sdk
    # https://facebook-sdk.readthedocs.org/en/latest/install.html
    _graph = None
    _post_as = None

    def __init__(self, account, testing):
        profile = None

        if not testing:
            self._graph = facebook.GraphAPI(account['token'])
            profile = self._graph.get_object('me')
        self._post_as = 'TESTER'

        if 'post_as' in account:
            self._post_as = account['post_as']
        elif not testing:
            self._post_as = profile['id']

    def test_output(self, text, attachment, post_as):
        '''
        Print output for testing purposes
        :param: text
        :param: attachment
        :param: post_as
        '''
        output = '>>> '+self.get_name()+' posting as '+post_as+':\n'+ \
                 'Name: '+attachment['name']+':\n'+ \
                 'Link: '+attachment['link']+':\n'+ \
                 'Content: '+text

        return self.output_test(output)

    def post(self, entry):
        '''
        Post entry to Facebook.
        :param entry:
        '''
        text = entry.title + ''.join(
            [' #{}'.format(k) for k in entry.keywords])
        attachment = {'name': entry.title, 'link': entry.link}

        to_return = False

        if self.is_testing():
            to_return = self.test_output(text, attachment, self._post_as)
        else:
            to_return = self._graph.put_wall_post(text, attachment,
                                                  self._post_as)

        return to_return


class TweepyClient(GenericClient):
    """ The TweepyClient handles the connection to Twitter. """
    _api = None

    def __init__(self, account, testing):
        """ Should be self-explaining. """
        # handle auth
        # See https://tweepy.readthedocs.org/en/v3.2.0/auth_tutorial.html
        # #auth-tutorial
        auth = None

        if not testing:
            auth = tweepy.OAuthHandler(account['consumer_token'],
                                       account['consumer_secret'])
            auth.set_access_token(account['access_token'],
                                  account['access_token_secret'])
        self._link_cost = 22
        self._max_len = 280
        self._api = tweepy.API(auth)

        self.set_common_opts(account)

    def test_output(self, text, media_path):
        '''
        Print output for testing purposes
        :param: text
        :param: media_path
        '''
        output = '>>> '+self.get_name()+' posting:\n'+ \
                 'Content: '+text

        if media_path:
            output += '\nMedia: ' + media_path
        else:
            output += '\nMedia: None'

        return self.output_test(output)

    def post(self, entry):
        """ Post entry to Twitter. """

        # Shorten the link URL if configured/possible
        post_url = self.shorten_url(entry.link)

        # TODO: These should all be shortened too, right?
        putative_urls = re.findall(r'[a-zA-Z0-9]+\.[a-zA-Z]{2,3}', entry.title)
        # Infer the 'inner links' Twitter may charge length for
        adjust_with_inner_links = self._link_cost + \
            sum([self._link_cost - len(u) for u in putative_urls])
        maxlen = self._max_len - len(
            post_url) - adjust_with_inner_links - 1  # for last ' '

        stripped_html = None

        if entry.content:
            # The content with all HTML stripped will be used later,
            # but get it now
            stripped_html = lxml.html.fromstring(
                entry.content).text_content().strip()

        # Apply any tag limits specified
        # TODO: This should move into mkrichtext
        used_keywords = entry.keywords
        if self._max_tags < len(used_keywords):
            used_keywords = used_keywords[:self._max_tags]

        # Let's build our tweet!
        text = ""

        # Apply optional prefix
        if self._post_prefix:
            text = self._post_prefix + " "

        # Process contents
        raw_contents = entry.title
        if self._include_content and stripped_html:
            raw_contents += ": " + stripped_html
        text += mkrichtext(raw_contents, used_keywords, maxlen=maxlen)

        # Apply optional suffix
        if self._post_suffix:
            text += " " + self._post_suffix
        text += " " + post_url

        # Finally ready to post.  Let's find out how (media/text)
        media_path = None
        if self._include_media and entry.media_url:
            # Need to download image from that URL in order to post it!
            media_path = download_media(entry.media_url)

        to_return = False
        if self.is_testing():
            to_return = self.test_output(text, media_path)
        elif media_path:
            to_return = self._api.update_with_media(media_path, text)
        else:
            to_return = self._api.update_status(text)

        return to_return


class DiaspyClient(GenericClient):
    """ The DiaspyClient handles the connection to Diaspora. """
    stream = None

    def __init__(self, account, testing):
        """ Should be self-explaining. """
        connection = None

        if not testing:
            self.connection = diaspy.connection.Connection(
                pod=account['pod'],
                username=account['username'],
                password=account['password'])
            self.connection.login()
            try:
                self.stream = diaspy.streams.Stream(self.connection,
                                                    'stream.json')
            except diaspy.errors.PostError as e:
                logging.error("Cannot get diaspy stream: %s", str(e))
                self.stream = None
        self.keywords = []
        try:
            self.keywords = [
                word.strip() for word in account['keywords'].split(',')
            ]
        except KeyError:
            pass

    def post(self, entry):
        """ Post entry to Diaspora. """

        text = '['+entry.title+']('+entry.link+')' \
            + ' | ' + ''.join([" #{}".format(k) for k in self.keywords]) \
            + ' ' + ''.join([" #{}".format(k) for k in entry.keywords])
        to_return = True

        if self.stream:
            to_return = self.stream.post(
                text, aspect_ids='public', provider_display_name='FeedSpora')
        elif self.is_testing():
            to_return = self.test_output(text)
        else:
            logging.info("Diaspy stream is None, not posting anything")

        return to_return


class WPClient(GenericClient):
    """ The WPClient handles the connection to Wordpress. """
    client = None

    def __init__(self, account, testing):
        """ Should be self-explaining. """

        if not testing:
            self.client = Client(account['wpurl'], account['username'],
                                 account['password'])
        self.keywords = []
        try:
            self.keywords = [
                word.strip() for word in account['keywords'].split(',')
            ]
        except KeyError:
            pass

    def get_content(self, url):
        """ Retrieve URL content and parse it w/ readability if it's HTML """
        r = requests.get(url)
        content = ''

        if r.status_code == requests.codes.ok and \
           r.headers['Content-Type'].find('html') != -1:
            try:
                content = Document(r.text).summary()
            except Unparseable:
                pass

        return content

    def test_output(self, entry):
        '''
        Print output for testing purposes
        :param: text
        '''
        output = '>>> '+self.get_name()+' posting:\n'+ \
                 'Title: '+entry.title+'\n'+ \
                 'post_tag: '+', '.join(entry.keywords)+'\n'+ \
                 'category: AutomatedPost\n'+ \
                 'status: publish\n'+ \
                 'Content: <as captured from '+entry.link+'>'

        return self.output_test(output)

    def post(self, entry):
        """ Post entry to Wordpress. """

        post_content = r"Source: <a href='{}'>{}</a><hr\>{}".format(
            entry.link,
            urlparse(entry.link).netloc, self.get_content(entry.link))
        to_return = False

        if self.is_testing():
            to_return = self.test_output(entry)
        else:
            # get text with readability
            post = WordPressPost()
            post.title = entry.title
            post.content = post_content
            post.terms_names = {
                'post_tag': entry.keywords,
                'category': ["AutomatedPost"]
            }
            post.post_status = 'publish'
            post_id = self.client.call(NewPost(post))
            to_return = post_id != 0

        return to_return


class MastodonClient(GenericClient):
    """ The MastodonClient handles the connection to Mastodon. """
    _mastodon = None

    def __init__(self, account, testing):
        """ Should be self-explaining. """
        client_id = account['client_id']
        client_secret = account['client_secret']
        access_token = account['access_token']
        api_base_url = account['url']

        if not testing:
            self._mastodon = Mastodon(
                client_id=client_id,
                client_secret=client_secret,
                access_token=access_token,
                api_base_url=api_base_url)
        self._delay = 0 if 'delay' not in account else account['delay']
        self._visibility = 'unlisted' if 'visibility' not in account or \
            account['visibility'] not in ['public', 'unlisted', 'private'] \
            else account['visibility']

    def test_output(self, text, delay, visibility):
        '''
        Print output for testing purposes
        :param: delay
        :param: visibility
        :param: text
        '''
        output = '>>> '+self.get_name()+' posting:\n'+ \
                 'Delay: '+str(delay)+'\n'+ \
                 'Visibility: '+visibility+'\n'+ \
                 'Content: '+text

        return self.output_test(output)

    def post(self, entry):
        maxlen = 500 - len(entry.link) - 1
        text = mkrichtext(entry.title, entry.keywords, maxlen=maxlen)
        text += ' ' + entry.link

        to_return = False

        if self.is_testing():
            to_return = self.test_output(text, self._delay, self._visibility)
        else:
            if self._delay > 0:
                time.sleep(self._delay)

            to_return = self._mastodon.status_post(
                text, visibility=self._visibility)

        return to_return


class ShaarpyClient(GenericClient):
    """ The ShaarpyClient handles the connection to Shaarli. """
    _shaarpy = None

    def __init__(self, account, testing):
        """ Should be self-explaining. """

        if not testing:
            self._shaarpy = Shaarpy()
            self._shaarpy.login(account['username'], account['password'],
                                account['url'])

    def test_output(self, link, keywords, title, text):
        '''
        Print output for testing purposes
        :param: text
        '''
        output = '>>> '+self.get_name()+' posting:\n'+ \
                 'Title: '+title+'\n'+ \
                 'Link: '+link+'\n'+ \
                 'Keywords: '+', '.join(keywords)+'\n'+ \
                 'Content: '+text

        return self.output_test(output)

    def post(self, entry):
        content = entry.content
        try:
            soup = BeautifulSoup(entry.content, 'html.parser')
            content = soup.text
        except Exception:
            pass

        to_return = False

        if self.is_testing():
            to_return = self.test_output(entry.link, entry.keywords,
                                         entry.title, content)
        else:
            to_return = self._shaarpy.post_link(
                entry.link,
                entry.keywords,
                title=entry.title,
                desc=content)

        return to_return


class LinkedInClient(GenericClient):
    """ The LinkedInClient handles the connection to LinkedIn. """
    _linkedin = None
    _visibility = None

    def __init__(self, account, testing):
        """ Should be self-explaining. """

        if not testing:
            self._linkedin = linkedin.LinkedInApplication(
                token=account['authentication_token'])
        self._visibility = account['visibility']

    def test_output(self, entry, visibility):
        '''
        Print output for testing purposes
        :param: entry
        :param: visibility
        '''
        output = '>>> '+self.get_name()+' posting:\n'+ \
                 'Title: '+trim_string(entry.title, 200)+'\n'+ \
                 'Link: '+entry.link+'\n'+ \
                 'Visibility: '+visibility+'\n'+ \
                 'Description: '+trim_string(entry.title, 256)+'\n'+ \
                 'Comment: '+mkrichtext(entry.title, entry.keywords, maxlen=700)

        return self.output_test(output)

    def post(self, entry):
        to_return = False

        if self.is_testing():
            to_return = self.test_output(entry, self._visibility)
        else:
            to_return = self._linkedin.submit_share(
                comment=mkrichtext(entry.title, entry.keywords, maxlen=700),
                title=trim_string(entry.title, 200),
                description=trim_string(entry.title, 256),
                submitted_url=entry.link,
                visibility_code=self._visibility)

        return to_return


class FeedSporaEntry:
    """ A FeedSpora entry.
    This class is generated from each entry/item in an Atom/RSS feed,
    then posted to your client accounts """
    title = ''
    link = ''
    published_date = None
    content = ''
    keywords = None
    media_url = None


class FeedSpora:
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
            logging.info("Creating new database file %s", self._db_file)
            sql = "CREATE table posts (id INTEGER PRIMARY KEY, " \
                  "feedspora_id, client_id TEXT)"
            self._cur.execute(sql)
        else:
            logging.info("Found database file %s", self._db_file)

    def entry_identifier(self, entry):
        """ Defines the identifier associated with the specified entry """
        # Unique item formed of link data, perhaps with published date
        to_return = entry.link

        if entry.published_date:
            to_return += ' ' + entry.published_date

        return to_return

    def is_already_published(self, entry, client):
        """ Checks if a FeedSporaEntry has already been published.
        It checks if it's already in the database of published items.
        """
        pub_item = self.entry_identifier(entry)
        sql = "SELECT id from posts WHERE feedspora_id=:feedspora_id AND "\
              "client_id=:client_id"
        self._cur.execute(sql, {
            "feedspora_id": pub_item,
            "client_id": client.get_name()
        })
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
        logging.info('Storing in database of published items: ' + pub_item)
        self._cur.execute(
            "INSERT INTO posts (feedspora_id, client_id) "
            "values (?,?)", (pub_item, client.get_name()))
        self._conn.commit()

    def _publish_entry(self, item_num, entry):
        """ Publish a FeedSporaEntry to your all your registered account. """

        if self._client is None:
            logging.error("No client found, aborting publication")

            return
        logging.info('Publishing: %s', entry.title)

        for client in self._client:
            if not self.is_already_published(entry, client):
                try:
                    posted_to_client = client.post_within_limits(entry)
                except Exception as error:
                    logging.error(
                        "Error while publishing '%s' to client"
                        " '%s' : %s", entry.title, client.__class__.__name__,
                        format(error))

                    continue

                if posted_to_client or client.seeding_published_db(item_num):
                    try:
                        self.add_to_published_entries(entry, client)
                    except Exception as error:
                        logging.error(
                            "Error while storing '%s' to client"
                            "'%s' : %s", entry.title,
                            client.__class__.__name__, format(error))

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
            req = urllib.request.Request(
                url=feed_url,
                data=b'None',
                method='GET',
                headers={'User-Agent': self._ua})
            feed_content = urllib.request.urlopen(req).read()
        logging.info("Feed read.")

        return BeautifulSoup(feed_content, 'html.parser')

    def get_keyword_list(self, title, content):
        """
        Determine the list of keywords, in priority order from title and
        content (content may be modified by this operation)
        """
        keywords = []
        # Add keywords from title
        for word in title.split():
            if word.startswith('#') and word[1:].lower() not in keywords:
                keywords.append(word[1:].lower())
        # Add keywords from end of content (removing from content in the
        # process of gathering keywords)
        if content:
            content_keyword_start = len(keywords)
            tag_pattern = r'\s+#([\w]+)$'
            match_result = re.search(tag_pattern, content)
            while match_result:
                tag = match_result.group(1).lower()
                if tag not in keywords:
                    keywords.insert(content_keyword_start, tag)
                content = re.sub(tag_pattern, '', content)
                match_result = re.search(tag_pattern, content)
            if re.match(r'^#[\w]+$', content):
                # Left with a single tag!
                if content[1:].lower() not in keywords:
                    keywords.insert(content_keyword_start, content[1:].lower())
                    content = ''

        return content, keywords

    # Define generator for Atom
    def parse_atom(self, soup):
        """ Generate FeedSpora entries out of an Atom feed. """

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
                fse.content = entry.find('content').text
            # If no content, attempt to use summary
            if not fse.content and entry.find('summary'):
                fse.content = entry.find('summary').text
            if fse.content is None:
                fse.content = ''

            # Keywords from title and content, potentially modifying content
            fse.content, fse.keywords = self.get_keyword_list(fse.title,
                                                              fse.content)
            # Add keywords from category
            for keyword in entry.find_all('category'):
                new_keyword = keyword['term'].replace(' ', '_').strip().lower()
                if new_keyword not in fse.keywords:
                    fse.keywords.append(new_keyword)

            # Published_date implementation for Atom
            if entry.find('updated'):
                fse.published_date = entry.find('updated').text
            elif entry.find('published'):
                fse.published_date = entry.find('published').text
            yield fse

    def find_rss_image_url(self, entry, link):
        '''
        Extract specified image URL, if it exists in the item (entry)
        :param: entry
        :param: link
        '''
        def content_img_src(entity):
            result = None
            for content in entity.contents:
                img_tag = re.search(r'<img [^>]*src=["\']([^"\']+)["\']',
                                    content)
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
                        to_return = url_root+to_return
                    else:
                        to_return = url_root+"/"+to_return
        return to_return

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
            if entry.find('content'):
                fse.content = entry.find('content')[0].text
            else:
                fse.content = entry.find('description').text

            # PubDate
            fse.published_date = entry.find('pubdate').text

            # Keywords from title and content, potentially modifying content
            fse.content, fse.keywords = self.get_keyword_list(fse.title,
                                                              fse.content)
            # Add keywords from category
            for keyword in entry.find_all('category'):
                new_keyword = keyword.text.replace(' ', '_').strip()
                if new_keyword not in fse.keywords:
                    fse.keywords.append(new_keyword)

            # And for our final act, media
            fse.media_url = self.find_rss_image_url(entry, fse.link)
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
            logging.error("Error while reading feed at " + feed_url + ": " +
                          format(error))

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

        if not self._client:
            logging.error("No client found, aborting publication")

            return
        self._init_db()

        for feed_url in self._feed_urls:
            self._process_feed(feed_url)
