#!/usr/bin/env python3
#
# Copyright 2015 Sean Dague <sean@dague.net>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Fly-hack is a helper program for running flake8 in flymake mode.

This provides a wrapper around running a flake8 either from a
discovered working tox environment, or building a flake8 tox on the
fly.

The flymake-mode is slightly limited, in that all stdout must be
structured correctly for flymake, if it is not, it disables the
mode. So if you need to debug this executable configure logging to log
to a file.

"""

import argparse
import configparser
import logging
import os
import re
import subprocess
import sys

# We manipulate the environment for our test runner, so better to just
# accumulate this as a global.
ENV = {}

FORMAT = '%(asctime)-15s - %(message)s'

logging.basicConfig(format=FORMAT)
LOG_FILENAME = '/home/sdague/flyhack.log'
logging.basicConfig(format=FORMAT, filename=LOG_FILENAME, level=logging.DEBUG)
LOG = logging.getLogger('fly-hack')
# Left for debugging purposes, the flyhack log will end up in the same
# directory as the files you are editing as emacs sets working
# directory based on buffer.
#
#
# fh = logging.FileHandler('/home/sdague/flyhack.log')
# fh.setLevel(logging.DEBUG)
# LOG.addHandler(fh)


def find_realpath_to_file(fname):
    """Find the real file path.

    In order for this to be tramp-mode safe we are copying all files
    to local tempdir before we run flake8 on them. In the local file
    case we want to unwind the filename so that we can go look for a
    working tox environment.
    """
    # TODO: this is my defined temp directory, would be nice to be
    # configurable.
    match = re.search('.emacs.d/tmp(.*)', fname)
    if match:
        return match.group(1)
    else:
        return os.path.abspath(fname)


def ignores(path):
    """Pull the flake8 ignores out of the tox file"""
    toxini = path + "/tox.ini"
    LOG.debug("Tox %s\n" % toxini)
    config = configparser.ConfigParser()
    config.read(toxini)
    options = {}
    for option in ('ignore', 'import-order-style', 'application-import-names', 'max-line-length'):
        if config.has_option('flake8', option):
            options[option] = config.get('flake8', option)
    return options


def _find_possible_tox(path, toxenv):
    """Given a path and a tox target, see if flake8 is already installed."""

    runner = None
    # First try to discover existing flake8
    while(path and path != '/'):
        path = os.path.dirname(path)
        # the locations of possible flake8
        venv = path + "/.tox/%s" % toxenv
        flake8 = venv + "/bin/flake8"
        if os.path.isdir(venv) and os.path.exists(flake8):
            # we found a flake8 in a venv so set that as the running venv
            ENV["VIRTUAL_ENV"] = venv
            # parse the ignores to pass them on the command line
            ENV["CONFIG"] = ignores(path)
            ENV["IGNORES"] = ENV["CONFIG"].get("ignore", "")
            # set the working directory so that 'hacking' can pick up
            # it's config
            ENV['PWD'] = path
            LOG.debug("Found flake8 %s, ENV=%s" % (flake8, ENV))
            return flake8


def find_flake8(fname):
    """Given an absolute file, find a relevant flake8 venv.

    Starting with a file and work your way all the way back up the
    directory structure to the root to discover whether or not there
    is an existing tox environment that supports flake8.

    If so, we'll use that with, with the project specific ignores and
    customizations. If not we'll fall back to a flake8 .venv we built
    ourselves.
    """
    path = fname
    runner = None

    for toxenv in ("flake8", "pep8", "lint"):
        runner = _find_possible_tox(path, toxenv)
        if runner is not None:
            break

    # or we might be a sad panda, and have no flake8, in which case,
    # lets make one.
    if runner is None:
        ourdir = os.path.dirname(os.path.realpath(__file__))
        venv = ourdir + "/.venv"
        if not os.path.isdir(venv):
            subprocess.call(["virtualenv", venv])
            pip = venv + "/bin/pip"
            subprocess.call([pip, 'install', '-U', 'flake8'])
        ENV['VIRTUAL_ENV'] = venv
        # default ignores is all of hacking, and all the indenting
        # rules. emacs python mode indents everything correctly in the
        # first place (except for silly overreach rules) so assume the
        # editor is not too drunk to remember to hit the tab key when
        # appropriate.
        ENV['IGNORES'] = 'H,E12'
        runner = venv + "/bin/flake8"

    LOG.debug("Runner is %s" % runner)
    return runner


def run(cmd, fname, *args):
    LOG.info("attempting to run %s %s\n" % (cmd, fname))
    fullcmd = [cmd]
    if "IGNORES" in ENV:
        fullcmd.append("--ignore=%s" % ENV["IGNORES"])
        del ENV["IGNORES"]
    # flake8-import-order work arounds, people should not use this module.
    for workaround in ('import-order-style', 'application-import-names', 'max-line-length'):
        if "CONFIG" in ENV:
            value = ENV["CONFIG"].get(workaround, "")
            if value:
                fullcmd.append("--%s=%s" % (workaround, value))
    fullcmd.append(fname)
    fullcmd.extend(args)
    LOG.info("Running: %s" % " ".join(fullcmd))
    # if we have a PWD chdir there before we run it to pick up hacking
    # config in tox.ini (it doesn't know how to parse anything except
    # a relative path tox.ini)
    if 'PWD' in ENV:
        os.chdir(ENV['PWD'])
    if 'VIRTUAL_ENV' in ENV:
        del ENV['VIRTUAL_ENV']
    proc = subprocess.Popen(fullcmd, stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    for line in proc.stdout:
        LOG.debug("Flake8: %s " % line.decode("utf-8"))
        print(line.decode("utf-8"))

    sys.exit(proc.returncode)


def main():
    fname = get_args().file[0]
    absfile = find_realpath_to_file(fname)
    testrunner = find_flake8(absfile)
    # this final abspath lets us safely do the chdir for hacking. It
    # also makes it simpler to run from the command line.
    run(testrunner, os.path.abspath(fname))


def get_args():
    parser = argparse.ArgumentParser(
        description='Flymake helper for hacking.')
    parser.add_argument('file', nargs=1,
                        help='file to be scanned')
    return parser.parse_args()


if __name__ == '__main__':
    main()
