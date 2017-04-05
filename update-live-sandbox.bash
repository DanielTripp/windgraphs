#!/usr/bin/env bash

set -eu -o pipefail

cd "$(dirname "$0")"

if [ "$(whoami)" == 'root' ] ; then 
	echo 'Failed.  You must not be root.'
	exit 1
fi

if [ "$(pwd)" != '/var/www-danieltripp.ca/windgraphs' ] ; then 
	echo 'Failed.  You are not in the live directory.'
	exit 1
fi

hg pull
hg up -C

