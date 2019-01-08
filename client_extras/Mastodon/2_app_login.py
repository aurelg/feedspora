from mastodon import Mastodon

'''
Copied from the Mastodon.py docs at 
https://mastodonpy.readthedocs.io/en/latest/
(includes minor FeedSpora-specific edits)

Edit the below to reflect your app name, the URL of your Mastodon instance,
and your login email/password,
then run it once ("python 2_app_login.py")
The produced file (feedspora_usercred.secret) will contain your access_token
'''

mastodon = Mastodon(
    client_id = 'feedspora_clientcred.secret',
    api_base_url = 'https://mastodon.social'
)
mastodon.log_in(
    'my_login_email@example.com',
    'incrediblygoodpassword',
    to_file = 'feedspora_usercred.secret'
)
