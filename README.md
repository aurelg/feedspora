# What is FeedSpora?

FeedSpora posts RSS/Atom feeds to your social network accounts. It currently supports Facebook, Twitter, Diaspora, Wordpress, Mastodon and Shaarli. It's a bot written in Python3, inspired from [Fefebot](https://github.com/svbergerem/fefebot).

# Installation

Install dependencies: `pip install -r requirements.txt`

Then extract FeedSpora and install it with the usual:

    python setup.py install

# Configuration

- Create a config file out of the provided template `feedspora.yml.template`. The `enabled` directive is optional and allow you to selectively enable/disable accounts by setting it to `True` or `False`. By default, the account is enabled.

# Usage

- Publish all RSS/Atom entries to your account with:

		python -m feedspora

## Twitter

... how to get customer/app token/secrets...

## Facebook

See [here](https://developers.facebook.com/docs/facebook-login/access-tokens) for more information about tokens.
- Get your User Access Token ([how](https://developers.facebook.com/docs/facebook-login/access-tokens#usertokens))
- Get your Page Access Token if you need it ([how](https://developers.facebook.com/docs/facebook-login/access-tokens#pagetokens))
- Extend its lifefime (if needed) ([how](https://developers.facebook.com/docs/facebook-login/access-tokens#extending)) on the graph debug stuff, 0-live token :-/
- With the [Graph API Explorer](https://developers.facebook.com/tools/explorer/), generate a new token with ad hoc extended permissions (publish_actions, and if you want to publish on Pages, publish_pages and manage_pages)
- You can manage/extend/debug your tokens [here](https://developers.facebook.com/tools/accesstoken/)

-
- Make sure to grant the token the right to push posts to your timeline

Problem: the token has a very short lifetime and need to be extended.

- check with facebook-sdk ?
