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
hg purge
hg up -C

cp .htaccess-live .htaccess
/etc/init.d/windgraphs stop
if [ -d generated_data_files ] ; then
	touch -t 198001010000 generated_data_files/*
fi
/etc/init.d/windgraphs start
sleep 5
/etc/init.d/windgraphs status


