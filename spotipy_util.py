#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This was copied from spotipy.util and slightly altered to (better) support the spawning of
inkognito / private browsers to lower the risk to login to the wrong Spotify account.
Also, the help output was clarified some.
"""

import os
from spotipy import oauth2
import spotipy
import webbrowser

class MozillaInkognito(webbrowser.Mozilla):
    remote_action = "-private-window"

class ChromeInkognito(webbrowser.Chrome):
    remote_action = "--incognito"

class OperaInkognito(webbrowser.Opera):
    remote_action = ",new-private-tab"

def _inkognito_wrap_browsers(webbrowser_object):
    # Opera, quite popular
    for browser in ("opera",):
        if browser in webbrowser_object._browsers:
            webbrowser_object.register(browser, None, OperaInkognito(browser), update_tryorder=-1)
            break

    # The Mozilla browsers
    for browser in ("firefox", "iceweasel", "iceape", "seamonkey"):
        if browser in webbrowser_object._browsers:
            webbrowser_object.register(browser, None, MozillaInkognito(browser), update_tryorder=-1)
            break

    # Google Chrome/Chromium browsers
    for browser in ("google-chrome", "chrome", "chromium", "chromium-browser"):
        if browser in webbrowser_object._browsers:
            webbrowser_object.register(browser, None, ChromeInkognito(browser), update_tryorder=-1)
            break

    # Cleanup duplicates from webbrowser_object._tryorder
    uniq_elements = []
    for elem in webbrowser_object._tryorder:
        if elem not in uniq_elements:
            uniq_elements.append(elem)
    webbrowser_object._tryorder = uniq_elements


def prompt_for_user_token(username, scope=None, client_id=None, client_secret=None,
                          redirect_uri=None, cache_path=None, direction='source'):
    """ prompts the user to login if necessary and returns
        the user token suitable for use with the spotipy.Spotify 
        constructor

        Parameters:

         - username - the Spotify username
         - scope - the desired scope of the request
         - client_id - the client id of your app
         - client_secret - the client secret of your app
         - redirect_uri - the redirect URI of your app
         - cache_path - path to location to save tokens
    """

    if not client_id:
        client_id = os.getenv('SPOTIPY_CLIENT_ID')

    if not client_secret:
        client_secret = os.getenv('SPOTIPY_CLIENT_SECRET')

    if not redirect_uri:
        redirect_uri = os.getenv('SPOTIPY_REDIRECT_URI')

    if not client_id:
        print('''
            You need to set your Spotify API credentials. You can do this by
            setting environment variables like so:

            export SPOTIPY_CLIENT_ID='your-spotify-client-id'
            export SPOTIPY_CLIENT_SECRET='your-spotify-client-secret'
            export SPOTIPY_REDIRECT_URI='your-app-redirect-url'

            Get your credentials at     
                https://developer.spotify.com/my-applications
        ''')
        raise spotipy.SpotifyException(550, -1, 'no credentials set')

    cache_path = cache_path or ".cache-" + username
    sp_oauth = oauth2.SpotifyOAuth(client_id, client_secret, redirect_uri, 
        scope=scope, cache_path=cache_path)

    # try to get a valid token for this user, from the cache,
    # if not in the cache, the create a new (this will send
    # the user to a web page where they can authorize this app)

    token_info = sp_oauth.get_cached_token()

    if not token_info:
        print(f'''
            #####################################################
            
            Need to authenticate the Spotify user:
                {username}
            for login type: {direction.upper()}
            
            Login type SOURCE means, that we need to
            authenticate for an account which will be used to
            read collections and items from (READ only).
            
            Login type DESTINATION means, that we need to
            authenticate for an account which will be used to
            copy collections and items from the SOURCE
            accounts TO (READ/WRITE).
            
            We will accuire the following permissions:
            ''')

        for s in scope.split():
            print(f'               {s}')

        print(f'''
            Please login to Spotify as this user in the web
            browser which just should have been opened.

            Once you enter your credentials and give
            authorization, you will be redirected to a url.
            
            IMPORTANT:
            Even if the page is not displayed or indicates an
            error (like "Could not be found" or similar), copy
            the url you were directed to from your browser's
            address bar and paste it to this shell to 
            complete the authorization.
            
            !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            Please make sure to close the browser window after
            you have copied the URL (and before pasting it to
            this window) to make sure the next instances are
            launched in a new private session.
            !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

        ''')
        auth_url = sp_oauth.get_authorize_url()
        try:
            _inkognito_wrap_browsers(webbrowser)
            webbrowser.open(auth_url)
            print("Opened %s in your browser" % auth_url)
        except webbrowser.Error:
            print("Please navigate here: %s" % auth_url)

        print()
        print()
        response = input("Enter the URL you were redirected to: ")
        print()
        print() 

        code = sp_oauth.parse_response_code(response)
        token_info = sp_oauth.get_access_token(code)

    # Auth'ed API request
    if token_info:
        return token_info['access_token']
    else:
        return None

_inkognito_wrap_browsers(webbrowser)
