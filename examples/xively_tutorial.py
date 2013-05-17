#!/usr/bin/env python

import datetime
import os
import time
import xively

# extract feed_id and api_key from environment variables
FEED_ID = os.environ["FEED_ID"]
API_KEY = os.environ["API_KEY"]
DEBUG = os.environ["DEBUG"] or False

# initialize api client
api = xively.XivelyAPIClient(API_KEY)


# function to read 1 minute load average from system uptime command
def read_loadavg():
    if DEBUG:
        print "Reading load average"
    with open('/proc/loadavg') as loadavg:
        return loadavg.readline().split()[0]


# function to return a datastream object. This either creates a new datastream,
# or returns an existing one
def get_datastream(feed):
    try:
        datastream = feed.datastreams.get("load_avg")
        if DEBUG:
            print "Found existing datastream"
        return datastream
    except:
        if DEBUG:
            print "Creating new datastream"
        datastream = feed.datastreams.create("load_avg", tags="load_01")
    return datastream


# main program entry point - runs continuously updating our datastream with the
# current 1 minute load average
def run():
    print "Starting Xively tutorial script"

    feed = api.feeds.get(FEED_ID)

    datastream = get_datastream(feed)
    datastream.max_value = None
    datastream.min_value = None

    while True:
        load_avg = read_loadavg()

        if DEBUG:
            print "Updating Xively feed with value: %s" % load_avg

        datastream.current_value = load_avg
        datastream.at = datetime.datetime.utcnow()
        datastream.update()

        time.sleep(10)

if __name__ == '__main__':
    run()
