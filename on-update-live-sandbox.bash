#!/usr/bin/env bash

cd "$(dirname "$0")"

if "$(whoami)" != 'root' ; then 
	echo 'Failed.'
	exit 1
fi

/etc/init.d/windgraphs stop
rm static_graph_info/*
/etc/init.d/windgraphs start
sleep 10
/etc/init.d/windgraphs status

