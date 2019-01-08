from mastodon import Mastodon

'''
Copied from the Mastodon.py docs at 
https://mastodonpy.readthedocs.io/en/latest/
(includes minor FeedSpora-specific edits)

Edit the below to reflect your app name and the URL of your Mastodon instance,
then run it once ("python 1_register_app.py")
The produced file (feedspora_clientcred.secret) will contain two lines of
output:
  * your client_id on the first line and
  * your client_secret on the second line
'''

Mastodon.create_app(
     'FeedSpora',
     api_base_url = 'https://mastodon.social',
     to_file = 'feedspora_clientcred.secret'
)
