#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import os
import sys
import ruamel.yaml as yaml
import spotipy
import spotipy.util as util

def myArgparse():
    """
    Overwrite argparse's default behavior when required input is missing, to display usage information.

    :return:
    """
    class MyParser(argparse.ArgumentParser):
        def error(self, message):
            sys.stderr.write('error: {0}\n'.format(message))
            self.print_help()
            sys.exit(2)

    # parse user input
    parser = MyParser()
    parser.add_argument('-c', '--config', action='store', metavar='/path/to/configfile', required=False, help='Path to '
                        'a configfile to use. If this is skipped, it is searched for at the predefined locations. If '
                        'none is found, internal defaults are used.')
    return parser.parse_args()

def find_configfile(configfile_locations=None):
    """
    Search for a config at the places defined in the provided iterable 'configfile_locations'.
    If none is found there, use a build in default.

    :param configfile_locations: iterable or string with possible config file locations
    :return:
    """

    # Always search '/config' subdirectory of script path as last resort location
    defaults_file = '%s/%s' % (os.path.dirname(sys.argv[0]), 'conf/pySongSync_defaults.yml')

    # If no configfile location was provided, set it to the last resort location 'defaults_file'
    if configfile_locations is None:
        configfile_locations = defaults_file
    # make configfile_locations of type list()
    if not isinstance(configfile_locations, list):
        configfile_locations = list(configfile_locations)
    # make sure the last resort location 'defaults_file' is in list 'configfile_locations'
    if defaults_file not in configfile_locations:
        configfile_locations.append(defaults_file)

    # Return the first existing file
    for file in list(configfile_locations):
        realfile = os.path.abspath(file)
        if os.path.isfile(realfile):
            return realfile
    # Should never be the case
    raise RuntimeError('No configfile found. Please create one first.')

def load_config(configfile=None):
    """
    Load YAML configfile
    :param configfile: Path to a YAML file
    :return:
    """
    if configfile is None:
        raise RuntimeError('No configfile given.')
    with open(configfile) as ymlfile:
        return yaml.load(ymlfile)

def main():
    # Get arguments
    args = myArgparse()

    # try to load config file
    # define list of default locations
    config_locations = ['~/.pySongSync.conf', os.path.dirname(sys.argv[0]) + '/pySongSync.conf', '/etc/pySongSync.conf']
    # if a config was defined with args, insert it into the first position
    if args.config:
        config_locations.insert(0, args.config)
    try:
        config = load_config(find_configfile(config_locations))
        sp_conf = config['spotify']
    except RuntimeError as err:
        print('Error: Unable to load config from any of the following locations:')
        for location in config_locations:
            print('  - %s' % location)
        print('Error was: %s' % str(err))
        sys.exit(1)

    # create a pointer for spotipy.Spotify()
    # http://spotipy.readthedocs.io/en/latest/#client-credentials-flow
    #spotify = spotipy.Spotify(client_credentials_manager=SCC(client_id=sp_conf['client_id'], client_secret=sp_conf['client_secret']))
    # http://spotipy.readthedocs.io/en/latest/#authorization-code-flow
    #token = util.prompt_for_user_token(sp_conf['user'], scope='', client_id=sp_conf['client_id'], client_secret=sp_conf['client_secret'], redirect_uri=sp_conf['redirect_URI'])
    scope=''
    token = util.prompt_for_user_token(sp_conf['user'], scope, client_id=sp_conf['client_id'], client_secret=sp_conf['client_secret'],
                                       redirect_uri=sp_conf['redirect_URI'])
    spotify = spotipy.Spotify(auth=token)

    spotify.trace = False
    results = spotify.current_user_playlists(limit=5)
    for i, item in enumerate(results['items']):
        print("%d %s" % (i, item['name']))


if __name__ == "__main__":
    main()
