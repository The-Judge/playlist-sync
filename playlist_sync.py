#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import os
import sys
from yamlreader import yaml_load
import spotipy
import spotipy_util as util
import copy
import pickle
from pathlib import Path
import tempfile

def myArgparse():
    """
    Get commandline parameters and return the Argument parser object.
    """

    class MyParser(argparse.ArgumentParser):
        """
        Overwrite argparse's default behavior when required input is missing, to display usage information.
        """
        def error(self, message):
            sys.stderr.write('error: {0}\n'.format(message))
            self.print_help()
            sys.exit(2)

    # parse user input
    parser = MyParser(description='This script will copy over user data from one or more Spotify accounts to one or '
                                  'more others.',
                      epilog='Upstream project: https://github.com/The-Judge/playlist-sync')
    parser.add_argument('-c', '--config', action='store', metavar='/path/to/configfile', required=False, help='Path to '
                        'a configfile to use. If this is skipped, it is searched for at the predefined locations. If '
                        'none is found, internal defaults are used.', default=None)
    read_write_group = parser.add_mutually_exclusive_group()
    read_write_group.add_argument('-r', '--read-only', action='store_true', required=False, help='If defined, only '
                                  'sources are read without writing to the destinations afterwards.', default=False)
    read_write_group.add_argument('-w', '--write-only', action='store_true', required=False, help='If defined, only '
                                  'destinations are written without reading the sources before.', default=False)
    return parser.parse_args()

def find_configfiles(configfile=None):
    """
    Search for a config at the pre-defined and provided locations and return a list containing pathlib.PosixPath objects
    for files found.

    :param configfile: string with config file location
    :return: list() containing strings of found config locations

    >>> assert isinstance(find_configfiles(None), list)
    >>> tmp_config = tempfile.NamedTemporaryFile()
    >>> assert Path(tmp_config.name).is_file()
    >>> assert isinstance(find_configfiles(tmp_config.name)[0], str)
    >>> assert tmp_config.name == find_configfiles(tmp_config.name)[0]
    >>> assert tmp_config.delete
    """
    # define list of possible locations
    config_locations = []
    config_locations_found = []

    # if a configfile was provided and it exists, add it to the list as first element
    if configfile is not None:
            config_locations.append(Path(configfile))

    # add a list of default locations to the list of possible locations
    for config in ['~/.playlist_sync.yaml', os.path.dirname(sys.argv[0]) + '/playlist_sync.yaml',
                   '/etc/playlist_sync.yaml']:
        config_locations.append(config)

    # Return the first existing file
    for file in config_locations:
        file_obj = Path(file)
        if file_obj.is_file():
            config_locations_found.append(str(file_obj.expanduser().absolute()))

    return config_locations_found


def load_config(configfile=None):
    """
    Load an default YAML configfile. After that, also load a user-config and have it's content overwrite defaults.
    :param configfile: Path to a YAML file
    :return: yaml object

    >>> defaults_file = Path(str(Path(__file__).parent) + '/conf/playlist_sync.defaults.yaml')
    >>> assert defaults_file.is_file()
    >>> yaml = yaml_load(str(defaults_file.absolute()))
    >>> assert isinstance(yaml, dict)
    >>> assert isinstance(load_config(None), dict)
    >>> yaml = load_config(None)
    >>> for x in ['client_id', 'client_secret', 'redirect_url', 'data_dir']: assert x in yaml
    """
    # Load all defaults from this location first. Will be overwritten if set in provided user config file.
    defaults_file = Path(str(Path(__file__).parent) + '/conf/playlist_sync.defaults.yaml')

    # Load defaults
    yaml = yaml_load(str(defaults_file.absolute()))

    # Load user config
    if configfile is not None:
        if isinstance(configfile, str):
            if not Path(configfile).is_file():
                print('WARNING: Config file {} was not found. Continue with default settings.'.format(configfile))
            else:
                yaml = yaml_load(configfile, yaml)
        else:
            raise ValueError('configfile needs to be of type str')
    return yaml


def authorize(yaml=None, path='~/.playlist_sync'):
    """
    Authorize all accounts defined in 'sources' and 'destinations' for the appropriate scopes, needed for the
    application to work. For each account authorization tokens will be saved in data_dir/username/.cached-username,
    along with refresh tokens, so this needs to be done only once per account.
    :param yaml: yaml object, containing 'sources' and 'destinations' trees (top level / complete yaml object)
    :param path: A string defining the parent path for the cached tokens to be saved in. Will be created if it doesn't
        exist.
    :return: dict() containing the authorized sessions.

    >>> yaml = load_config()
    >>> auths = authorize(yaml)
    >>> for x in ['sources', 'destinations']: assert x in auths
    >>> for x in ['sources', 'destinations']: assert isinstance(auths[x], dict)
    """
    # Authorization Code Flow
    # http://spotipy.readthedocs.io/en/latest/#authorization-code-flow

    # Create a dict to store a token for each account/username
    auths = {'sources': dict(), 'destinations': dict()}

    redirect_url = yaml['redirect_url']
    c_id         = yaml['client_id']
    c_secret     = yaml['client_secret']

    # https://developer.spotify.com/documentation/general/guides/scopes/
    read_scope  = 'playlist-read-private user-library-read user-follow-read'
    write_scope = 'playlist-modify-private playlist-modify-public user-library-modify user-follow-modify'
    write_scope = ' '.join([write_scope, read_scope])

    if 'sources' in yaml:
        for account in yaml['sources']:
            username        = yaml['sources'][account]['username']
            cache_path      = Path(path).expanduser().absolute().joinpath(username)
            cache_path.mkdir(parents=True, exist_ok=True)
            cache_path      = cache_path.joinpath('.cache-{}'.format(username))
            read_token      = util.prompt_for_user_token(username, read_scope, c_id, c_secret,
                                                         redirect_url, str(cache_path), 'source')
            auths['sources'][username] = spotipy.Spotify(auth=read_token)

    if 'destinations' in yaml:
        for account in yaml['destinations']:
            username        = yaml['destinations'][account]['username']
            cache_path      = Path(path).expanduser().absolute().joinpath(username)
            cache_path.mkdir(parents=True, exist_ok=True)
            cache_path      = cache_path.joinpath('.cache-{}'.format(username))
            write_token     = util.prompt_for_user_token(username, write_scope, c_id, c_secret,
                                                         redirect_url, str(cache_path), 'destination')
            auths['destinations'][username] = spotipy.Spotify(auth=write_token)

    return auths


def get_saved_tracks(auths=None, offset=0, limit=20):
    """
    This function takes a dictionary, which needs to be the 'sources' tree from the auths object authorize() creates.
    It then extracts all tracks wich are stored in those user account's libraries and returns a list() containing that
    tracks IDs.
    :param auths: 'sources'-tree dict() from authorize()
    :param offset: int() defining at which count of objects to start the query
    :param limit: int() defining the max count of objects to return per query
    :return: list() containing stored tracks IDs
    """
    tracks = list()

    for username in auths:
        new_tracks = {'next': 'foo'}
        while new_tracks['next'] is not None:
            new_tracks = auths[username].current_user_saved_tracks(limit=limit, offset=offset)
            for element in new_tracks['items']:
                tracks.append(element['track']['id'])
            offset += limit
    return tracks


def add_saved_tracks(auths=None, tracks=(None,)):
    """
    This function adds all track IDs from list tracks to all accounts listed in the provided auths dictionary (must be
    the 'destinations'-tree from authorize()).
    :param auths: 'destinations'-tree from authorize()
    :param tracks: list() containing track IDs
    :return: True
    """
    for username in auths:
        for track in tracks:
            if track is not None:
                auths[username].current_user_saved_tracks_add([track])
    return True

def get_saved_playlists(auths=None, offset=0, limit=20):
    """
    This function takes a dictionary, which needs to be the 'sources' tree from the auths object authorize() creates.
    It then extracts all playlists wich are stored in those user account's libraries and returns a list() containing
    the playlists objects spotipy.current_user_playlists() provides.
    :param auths: 'sources'-tree dict() from authorize()
    :param offset: int() defining at which count of objects to start the query
    :param limit: int() defining the max count of objects to return per query
    :return: list() containing playlists objects spotipy.current_user_playlists() provides
    """
    pl = list()

    for username in auths:
        new_pl = {'next': 'foo'}
        while new_pl['next'] is not None:
            new_pl = auths[username].current_user_playlists(limit=limit, offset=offset)
            for element in new_pl['items']:
                pl.append(copy.deepcopy(element))
            offset += limit
    return pl


def get_playlist_id(auth, username, playlist_name):
    """
    Extracts and returns an ID for the defined playlist name of the defined user.
    :param auth: dict() of an auth object's tree ('sources' or 'destinations') as returned from authorize(), which
        contains the defined username section.
    :param username: str() defining which user the searched playlist belongs to
    :param playlist_name: str() defining the name of the playlist
    :return: str() containing the ID if found. Otherwise 'None'
    """
    my_playlists = get_saved_playlists(auth)
    for my_pl in my_playlists:
        if my_pl['owner']['id'] == username:
            if my_pl['name'] == playlist_name:
                return my_pl['id']
    return None


def get_playlist_tracks(auth, username, playlist_id):
    """
    Extracts and returns a list containing the IDs for the tracks stored in the defined playlist ID of the defined user.
    :param auth: dict() of an auth object's tree ('sources' or 'destinations') as returned from authorize(), which
        contains the defined username section.
    :param username: str() defining which user the playlist belongs to
    :param playlist_id: str() defining the ID of the playlist
    :return: list() containing str() for all tracks added to the defined playlist
    """
    pl_tracks = list()
    for item in auth.user_playlist_tracks(username, playlist_id=playlist_id):
        pl_tracks.append(item['track']['id'])
    return pl_tracks


def add_saved_playlists(auths=None, playlists=None):
    """
    Adds/follows playlists. If a playlist from playlists is a foreign/public playlist, it is followed only.
    If that playlist belongs to any of the users listed in 'sources' it is copied over.
    :param auths: dict() being the complete auth object as returned from authorize() (Top Level / complete)
    :param playlists: list() containing all playlist objects to be transfered as returned from
        spotipy.current_user_playlists().
    :return: True
    """
    for username in auths['destinations']:
        for pl in playlists:
            # If this is a foreign PL
            if pl['owner']['id'] not in auths['sources']:
                auths['destinations'][username].user_playlist_follow_playlist(pl['owner']['id'], pl['id'])
            else:
                # Create own PLs and add tracks to them
                auths['destinations'][username].user_playlist_create(username, pl['name'], public=pl['public'])
                # Add tracks to it
                new_id      = get_playlist_id(auths['destinations'], username, pl['name'])
                track_list  = get_playlist_tracks(auths['sources'][username], username, pl['id'])
                auths['destinations'][username].user_playlist_add_tracks(username, new_id, track_list)
    return True


def get_saved_artists(auths=None, offset=0, limit=20):
    """
    Extracts and returns a list containing the IDs for all artists followed by any of the accounts defined in 'sources'.
    :param auths: dict() being the 'sources'-tree of the auth object as returned by authorize()
    :param offset: int() defining at which count of objects to start the query
    :param limit: int() defining the max count of objects to return per query
    :return: list() containing str() of the artists IDs
    """
    artists = list()

    for username in auths:
        new_artists = {'artists': {'next': 'foo'}}
        while new_artists['artists']['next'] is not None:
            new_artists = auths[username].current_user_followed_artists(limit=limit, after=offset)
            for element in new_artists['artists']['items']:
                artists.append(element['id'])
            offset += limit

    return artists


def add_saved_artists(auths, artists):
    """
    Adds/follows artists.
    :param auths: dict() being the 'destinations'-tree of the auth object as returned from authorize()
    :param artists: list() containing the artists IDs to add to the 'destinations' accounts
    :return: True
    """
    for username in auths:
        for artist in artists:
            if artist is not None:
                auths[username].user_follow_artists([artist])
    return True


def get_saved_albums(auths=None, offset=0, limit=20):
    """
    Extracts and returns a list containing the IDs for all albums followed by any of the accounts defined in 'sources'.
    :param auths: dict() being the 'sources'-tree of the auth object as returned by authorize()
    :param offset: int() defining at which count of objects to start the query
    :param limit: int() defining the max count of objects to return per query
    :return: list() containing str() of the albums IDs
    """
    albums = list()

    for username in auths:
        new_albums = {'next': 'foo'}
        while new_albums['next'] is not None:
            new_albums = auths[username].current_user_saved_albums(limit=limit, offset=offset)
            for element in new_albums['items']:
                albums.append(element['album']['id'])
            offset += limit

    return albums


def add_saved_albums(auths=None, albums=(None,)):
    """
    Adds/follows albums.
    :param auths: dict() being the 'destinations'-tree of the auth object as returned from authorize()
    :param albums: list() containing the albums IDs to add to the 'destinations' accounts
    :return: True
    """
    for username in auths:
        for album in albums:
            if album is not None:
                auths[username].current_user_saved_albums_add([album])
    return True

def store_to_pickle(obj, object_name, path='~/.playlist_sync'):
    """
    Saves the obj as file called object_name + '.p' at path.
    :param obj: Any pickleable object
    :param path: String or pathlib.PosixPath definind where to save the pickle files
    :param object_name: A string, describing the object. This is used as a filename for the pickle file.
    :return: True
    """
    # Create the data directory defined by path and store the location as a pathlib.PosixPath object
    f_path = create_dir(path)

    # Save the object
    with open('{}/{}.p'.format(str(f_path.expanduser().absolute()), str(object_name)), 'wb') as p_file:
        pickle.dump(obj, p_file)

    return True


def load_from_pickle(object_name, path='~/.playlist_sync'):
    """
    Loads the obj which is expected to be stored as file called object_name + '.p' in path.
    :param path: String or pathlib.PosixPath definind where to load the pickle files from
    :param object_name: A string, describing the object. This is used as a filename for the pickle file.
    :return: object restored from the pickle file if that file is found. Otherwise: None
    """
    # Create the data directory defined by path and store the location as a pathlib.PosixPath object
    f_path = make_pathlib(path)

    # Load the object
    try:
        with open('{}/{}.p'.format(str(f_path.expanduser().absolute()), str(object_name)), 'rb') as p_file:
            return pickle.load(p_file)
    except FileNotFoundError:
        return None


def make_pathlib(path):
    """
    Make an pathlib.PosixPath object from path argument
    :param path: str or pathlib.PosixPath object
    :return: pathlib.PosixPath object
    """
    if isinstance(path, Path):
        f_path = path
    else:
        if not isinstance(path, str):
            raise TypeError("'path' needs to be an pathlib.PosixPath or str object")
        else:
            f_path = Path(path)
    return f_path


def create_dir(path):
    """
    Create the defined path and it's parents if it is not existing and return it as a pathlib.PosixPath object.
    :param path: str or pathlib.PosixPath object
    :return: pathlib.PosixPath
    """
    f_path = make_pathlib(path)

    if not f_path.expanduser().absolute().is_dir():
        f_path.expanduser().absolute().mkdir(parents=True)

    return f_path


def main():
    # Get arguments
    args = myArgparse()

    # try to load config file
    config = load_config(find_configfiles(args.config)[0])
    # Cleanup yaml from trees not needed
    if args.write_only:
        del config['sources']
    if args.read_only:
        del config['destinations']

    # Define data_dir
    data_dir = config['data_dir']
    if os.environ.get('PS_DATA_DIR') is not None:
        data_dir = os.environ.get('PS_DATA_DIR')

    # Start authorization
    auth = authorize(yaml=config, path=data_dir)

    #store_to_pickle(obj=auth, object_name='auths',
    #                path=str(Path(data_dir).expanduser().absolute()))

    # Collect data from sources
    if not args.write_only:
        tracks    = get_saved_tracks(auth['sources'])
        artists   = get_saved_artists(auth['sources'])
        albums    = get_saved_albums(auth['sources'])
        playlists = get_saved_playlists(auth['sources'])

        # Save all 4 dictionaries into separate pickle files
        store_to_pickle(obj=tracks, object_name='tracks',
                        path=str(Path(data_dir).expanduser().absolute()))
        store_to_pickle(obj=artists, object_name='artists',
                        path=str(Path(data_dir).expanduser().absolute()))
        store_to_pickle(obj=albums, object_name='albums',
                        path=str(Path(data_dir).expanduser().absolute()))
        store_to_pickle(obj=playlists, object_name='playlists',
                        path=str(Path(data_dir).expanduser().absolute()))

    # Write data to destinations
    if not args.read_only:
        # Load all 4 dictionaries from its corresponding pickle file
        tracks    = load_from_pickle('tracks', path=str(Path(data_dir).expanduser().absolute()))
        artists   = load_from_pickle('artists', path=str(Path(data_dir).expanduser().absolute()))
        albums    = load_from_pickle('albums', path=str(Path(data_dir).expanduser().absolute()))
        playlists = load_from_pickle('playlists', path=str(Path(data_dir).expanduser().absolute()))

        add_saved_tracks(auth['destinations'], tracks)
        add_saved_artists(auth['destinations'], artists)
        add_saved_albums(auth['destinations'], albums)
        add_saved_playlists(auth, playlists)


if __name__ == "__main__":
    main()
