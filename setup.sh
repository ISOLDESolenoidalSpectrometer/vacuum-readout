#!/bin/bash
# Clone the mattermost python library and put it in the right folder
git clone https://github.com/ISOLDESolenoidalSpectrometer/mattermost-python

# This allows the rest of the scripts to find the package
ln -s mattermost-python/mattermostpython .