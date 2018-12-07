"""
GenericClient: baseclass providing features to specific clients.
"""

import logging
import re

import pyshorteners


class GenericClient:
    ''' Implements the case functionalities expected from clients '''

    # pylint: disable=too-many-instance-attributes
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

    # pylint: enable=too-many-instance-attributes

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

        if not self.is_post_limited() or \
           self._posts_done < self.get_max_posts():
            to_return = self.post(entry_to_post)

            if to_return:
                self._posts_done += 1

        return to_return

    def post(self, entry):
        '''
        Placeholder for post, override it in subclasses
        :param entry:
        '''
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

    # pylint: disable=no-self-use
    def output_test(self, text):
        '''
        Print output for testing purposes
        :param text:
        '''
        print(text)

        return True

    # pylint: enable=no-self-use

    def test_output(self, **kwargs):
        '''
        Define output for testing purposes (potentially overridden on
        per-client basis - this is the default), then output that definition
        :param kwargs:
        '''
        output = '>>> ' + self.get_name() + ' posting:\nContent: ' \
            + kwargs['text']

        return self.output_test(output)

    def shorten_url(self, the_url):
        '''
        Apply configured URL shortener (if present) to the provided link and
        return the result.  If anything goes awry, return the unmodified link.
        :param the_url:
        '''
        to_return = the_url
        # Default
        short_options = {'timeout': 3}
        short_options.update(self._url_shortener_opts)

        if the_url and self._url_shortener and self._url_shortener != 'none':
            try:
                shortener = pyshorteners.Shortener(**short_options)
                # Verify a legal choice
                # pylint: disable=no-member
                assert self._url_shortener in shortener.available_shorteners
                # pylint: enable=no-member
                to_return = getattr(shortener,
                                    self._url_shortener).short(the_url)
                # Sanity check!

                if len(to_return) > len(the_url):
                    # Not shorter?  You're fired!
                    raise RuntimeError(
                        'Shortener %s produced a longer URL ' +
                        'than the original!', self._url_shortener)
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
                    logging.error('Cannot shorten URL %s with %s: %s', the_url,
                                  self._url_shortener, str(exception))
                to_return = the_url
            # pylint: enable=broad-except

        return to_return

    def set_common_opts(self, account):
        '''
        Set options common to all clients
        :param account:
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

    # pylint: disable=no-self-use
    def _trim_string(self, text, maxlen, etc='...', etc_if_shorter_than=None):
        '''
        Trim the string to the specified length, using the etc notation to show
        this has been done
        :param text:
        :param maxlen:
        :param etc:
        :param etc_if_shorter_than:
        '''

        if len(text) < maxlen:
            to_return = text
        else:
            tmpmaxlen = maxlen - len(etc)
            space_pos = [
                x for x in range(0, len(text))

                if text[x] == ' ' and x < tmpmaxlen
            ]
            cut_at = space_pos[-1] if space_pos else tmpmaxlen
            to_return = text[:cut_at]

            if etc_if_shorter_than and cut_at < etc_if_shorter_than:
                to_return += etc

        return to_return

    # pylint: enable=no-self-use

    # pylint: disable=too-many-locals
    # pylint: disable=too-many-arguments
    # pylint: disable=no-self-use
    def _mkrichtext(self,
                    text,
                    keywords,
                    maxlen=None,
                    etc='...',
                    separator=' |'):
        '''
        Process the text to include hashtagged keywords and adhere to the
        specified maximum length.
        :param text:
        :param keywords:
        :param maxlen:
        :param etc:
        :param separator:
        '''

        def repl(match):
            return '%s#%s%s' % (match.group(1), match.group(2), match.group(3))

        # Constants used in regex pattern generation
        # pylint: disable=anomalous-backslash-in-string
        before_tag = r'(\A|[\'"/([{\s])'
        after_tag = r'(\Z|[\'"/\s)\]},.!?:])'
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

            if re.search(
                    r'%s#?(%s)%s' % (before_tag, re.escape('%s' % word),
                                     after_tag), to_return, re.IGNORECASE):
                inline_kw.append(word)
            else:
                extra_kw.append(word)

        # Process inline keywords

        for word in inline_kw:
            pattern = (
                r'%s(%s)%s' % (before_tag, re.escape('%s' % word), after_tag))

            if re.search(pattern, to_return, re.IGNORECASE):
                to_return = re.sub(
                    pattern, repl, to_return, flags=re.IGNORECASE)

        # Add separator and keywords, if needed
        minlen_wo_xtra_kw = len(to_return)

        if extra_kw:
            fake_separator = separator.replace(' ', '_')
            to_return += fake_separator
            minlen_wo_xtra_kw = len(to_return)

            # Add extra (ordered) keywords

            for word in extra_kw:
                # prevent duplication
                pattern = (r'%s#(%s)%s' % (before_tag, re.escape('%s' % word),
                                           after_tag))

                if re.search(pattern, to_return, re.IGNORECASE) is None:
                    to_return += " #" + word

        # If the text is too long, cut it and, if needed, add suffix

        if maxlen is not None:
            to_return = self._trim_string(
                to_return,
                maxlen,
                etc=etc,
                etc_if_shorter_than=minlen_wo_xtra_kw)

        # Restore separator

        if extra_kw:
            to_return = to_return.replace(fake_separator, separator)

            # Remove separator if nothing comes after it
            stripped_separator = separator.rstrip()

            if to_return.endswith(stripped_separator):
                to_return = to_return[:-len(stripped_separator)]

        if maxlen is not None:
            assert not len(to_return) > maxlen, \
                "{}:{} : {} > {}".format(text, to_return, len(to_return),
                                         maxlen)

        return to_return

    # pylint: enable=no-self-use
    # pylint: enable=too-many-locals
    # pylint: enable=too-many-arguments