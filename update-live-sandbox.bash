#!/usr/bin/env bash

set -eu -o pipefail

cd "$(dirname "$0")"

if [ "$(whoami)" == 'root' ] ; then 
	echo 'Failed.'
	exit 1
fi

hg pull
hg up -C

