#!/usr/bin/env bash

set -eu -o pipefail

cd "$(dirname "$0")"

if [ "$(whoami)" != 'root' ] ; then 
	echo 'Failed.  You must be root.'
	exit 1
fi

/etc/init.d/windgraphs stop
touch -t 198001010000 generated_data_files/*
/etc/init.d/windgraphs start
sleep 5
/etc/init.d/windgraphs status

cp .htaccess-live .htaccess

