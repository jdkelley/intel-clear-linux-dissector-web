#!/usr/bin/env python3

# Standalone script which rebuilds the history of all the upgrades.
#
# To detect package versions of the recipes the script uses the name of the recipe.
#
# Copyright (C) 2015, 2018 Intel Corporation
# Authors: Anibal Limon <anibal.limon@linux.intel.com>
#          Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

from datetime import datetime, timedelta

import sys
import os.path
import optparse
import logging

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__))))
from common import common_setup, get_logger

common_setup()
from layerindex import utils

utils.setup_django()
import settings

logger = get_logger("HistoryUpgrade", settings)
fetchdir = settings.LAYER_FETCH_DIR
bitbakepath = os.path.join(fetchdir, 'bitbake')
if not fetchdir:
    logger.error("Please set LAYER_FETCH_DIR in settings.py")
    sys.exit(1)


def run_internal(maintplanlayerbranch, commit, commitdate, options, logger, bitbake_map, initial=False):
    from layerindex.models import PythonEnvironment
    from rrs.models import Release
    if commitdate < maintplanlayerbranch.python3_switch_date:
        # Python 2
        if maintplanlayerbranch.python2_environment:
            cmdprefix = maintplanlayerbranch.python2_environment.get_command()
        else:
            cmdprefix = 'python'
        # Ensure we're using a bitbake version that is python 2 compatible
        if commitdate > datetime(2016, 5, 10):
            commitdate = datetime(2016, 5, 10)
    else:
        # Python 3
        if maintplanlayerbranch.python3_environment:
            cmdprefix = maintplanlayerbranch.python3_environment.get_command()
        else:
            cmdprefix = 'python3'

    bitbake_rev = utils.runcmd('git rev-list -1 --before="%s" origin/master' % str(commitdate),
                    bitbakepath, logger=logger)
    check_rev = bitbake_map.get(bitbake_rev, None)
    if check_rev:
        logger.debug('Preferring bitbake revision %s over %s' % (check_rev, bitbake_rev))
        bitbake_rev = check_rev

    cmd = '%s upgrade_history_internal.py %s %s' % (cmdprefix, maintplanlayerbranch.layerbranch.id, commit)
    if initial:
        release = Release.get_by_date(maintplanlayerbranch.plan, commitdate)
        if release:
            comment = 'Initial import at %s release start.' % release.name
        else:
            comment = 'Initial import at %s' % commit
        cmd += ' --initial="%s"' % comment
    if bitbake_rev:
        cmd += ' --bitbake-rev %s' % bitbake_rev
    if options.dry_run:
        cmd += ' --dry-run'
    if options.loglevel == logging.DEBUG:
        cmd += ' --debug'
    logger.debug('Running %s' % cmd)
    ret, output = utils.run_command_interruptible(cmd)
    if ret == 254:
        # Interrupted by user, break out of loop
        logger.info('Update interrupted, exiting')
        sys.exit(254)

"""
    Upgrade history handler.
"""
def upgrade_history(options, logger):
    from rrs.models import MaintenancePlan

    # start date
    now = datetime.today()
    today = now.strftime("%Y-%m-%d")
    if options.initial:
        # starting date of the yocto project 1.6 release
        since = "2013-11-11"
        #RecipeUpgrade.objects.all().delete()
    else:
        # FIXME this is awful - we should be storing the last commit somewhere
        since = (now - timedelta(days=8)).strftime("%Y-%m-%d")

    maintplans = MaintenancePlan.objects.filter(updates_enabled=True)
    if not maintplans.exists():
        logger.error('No enabled maintenance plans found')
        sys.exit(1)
    for maintplan in maintplans:
        for maintplanbranch in maintplan.maintenanceplanlayerbranch_set.all():
            layerbranch = maintplanbranch.layerbranch
            layer = layerbranch.layer
            urldir = layer.get_fetch_dir()
            repodir = os.path.join(fetchdir, urldir)
            layerdir = os.path.join(repodir, layerbranch.vcs_subdir)

            commits = utils.runcmd("git log --since='" + since +
                                    "' --format='%H %ct' --reverse origin/master", repodir,
                                    logger=logger)
            commit_list = commits.split('\n')

            bitbake_map = {}
            # Filter out some bad commits
            bitbake_commits = utils.runcmd("git rev-list fef18b445c0cb6b266cd939b9c78d7cbce38663f^..39780b1ccbd76579db0fc6fb9369c848a3bafa9d^",
                                bitbakepath,
                                logger=logger)
            bitbake_commit_list = bitbake_commits.splitlines()
            for commit in bitbake_commit_list:
                bitbake_map[commit] = '39780b1ccbd76579db0fc6fb9369c848a3bafa9d'

            if options.initial:
                logger.debug("Adding initial upgrade history ....")

                ct, ctepoch = commit_list.pop(0).split()
                ctdate = datetime.fromtimestamp(int(ctepoch))
                run_internal(maintplanbranch, ct, ctdate, options, logger, bitbake_map, initial=True)

            logger.debug("Adding upgrade history from %s to %s ..." % (since, today))
            for item in commit_list:
                if item:
                    ct, ctepoch = item.split()
                    ctdate = datetime.fromtimestamp(int(ctepoch))
                    logger.debug("Analysing commit %s ..." % ct)
                    run_internal(maintplanbranch, ct, ctdate, options, logger, bitbake_map)

            if commit_list:
                utils.runcmd("git clean -dfx", repodir, logger=logger)

if __name__=="__main__":
    parser = optparse.OptionParser(usage = """%prog [options]""")
    
    parser.add_option("-i", "--initial",
            help = "Do initial population of upgrade histories",
            action="store_true", dest="initial", default=False)

    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel", default=logging.INFO)

    parser.add_option("--dry-run",
            help = "Do not write any data back to the database",
            action="store_true", dest="dry_run", default=False)

    options, args = parser.parse_args(sys.argv)
    logger.setLevel(options.loglevel)

    upgrade_history(options, logger)
