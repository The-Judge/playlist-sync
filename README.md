# Pre-requirements

This script works best on a Linux OS with one of the following browsers:
   - [Google Chrome / Chromium](https://www.google.de/chrome/)
   - [Firefox](https://www.mozilla.org/firefox/)
   - [Opera](https://www.opera.com/)

# Quick-Start

1. Clone this repo and cd into the resulting workdir.

1. Use [Pipenv](https://docs.pipenv.org/) to provide a proper Python environment and activate it:  
    ```bash
    your-fancy-prompt$ pipenv sync
    Creating a virtualenv for this project…
    ...
    Installing dependencies from Pipfile.lock (e82491)…
    🐍   ▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉ 10/10 — 00:00:05
    To activate this project's virtualenv, run the     following:
    $ pipenv shell
    All dependencies are now up-to-date!
    your-fancy-prompt$ pipenv shell
    Spawning environment shell (/bin/bash). Use 'exit' to leave.
    ...
    (playlist-sync-EogE3rS2) your-fancy-prompt$ 
    ```
 
1. Copy `conf/playlist_sync.defaults.yaml` to any of the pre-defined locations or to wherever you want (you will need to use `-c` pointing to that file in this case) and override the pre-defined parameters that way.  
The pre-defined locations are (in the order of preference):
    - `~/.playlist_sync.yaml`
    - `playlist_sync.yaml` in the script's directory
    - `/etc/playlist_sync.yaml`

1. Navigate to <https://developer.spotify.com/my-applications> and register a new application. As `Redirect URIs` you just add `http://localhost/`; the rest can be set by your personal preference.

1. Copy the `Client ID` and `Client Secret` resulting from that registration and enter it as `client_id` and `client_secret` to the config file you created in step 2.

1. Define a desired filesystem location where the script may store it's working files in.  
**Attention:** Tokens which will allow access to your Spotify accounts will be stored here! Make sure to carefully set appropriate permissions on this location.  
If you just want to stick to the defaults (`~/.playlist_sync`), just comment this setting out or remove it.

1. Un-comment the `sources` and `destinations` section in your config file.  
You can define a name for each account as shown in the template with `src` and `dst`. This is completely free to choose - it reflects to be any identifyer you can identify your accounts as. If you are not interested (which is perfectly OK), consider to just name these like "`src1`, `src2`, ...".  
In the next level of that yaml tree, you need to define `username`. This must be the username identifying the Spotify accounts. This is shown at the lower left of the [Web Player](https://open.spotify.com/browse/).  
If you want to add an account to be a source **and** a destination, just define it in both trees.

1. Execute the script `playlist_sync.py` as outlined in it's help text (`python playlist_sync.py --help`).
