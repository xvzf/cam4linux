#!/bin/python2
"""
CAM4LINUX - a control suite for nzxt devices
Copyright (C) 2017 Matthias Riegler <matthias@xvzf.tech>

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
"""

import nzxt
import json

def cleanupconfig(str):
    buffer = ""
    for i in str.splitlines():
        if '#' in i:
            buffer = buffer + i[0:i.find('#')]
        else:
            buffer = buffer + i

    return buffer


class Camservice(object):
    """
        I decided to use JSON as "transfer" protocol - easy to work with and compatible
        with the python dictionary type.

        First, a config file (JSON, but # indicates a comment and is filtered out) is read
        and the devices in the config file are discovered and evaluated. 
        After the initialization is finished, all components can be accessed and served via
        a server, integrated in a live website etc. This makes it possible to keep cam4linux
        versatile and compatible with any other programming language which supports a json
        api. 
    """

    devices = []
    
    def __init__(self, configfile):
        super(Camservice, self).__init__()
        self.configfile = configfile
        self.readconfig()
        print self.devices

    def readconfig(self):
        try:
            with open(self.configfile, "r") as file:
                parsed_json = json.loads(cleanupconfig(file.read()))
                self.parseconfig(parsed_json)

        except IOError:
            print "[-] Could not open configuration file, exiting"
        
    def add_device(self, name, device):
        if device["type"] == "grid":
            try:
                port = device["port"]
            except Exception as e:
                return
            finally:
                self.devices.append(
                    {
                        "type": "grid",
                        "name": name,
                        "node": nzxt.Grid(port)
                    }
                )

    
    def parseconfig(self, cfg):
        for i in cfg.keys():
            self.add_device(i, cfg[i])

    def getall(self):
        returndict = {}
        for i in range(len(self.devices)):
            returndict[self.devices[i]["name"]] = self.getdevice(i)

        return json.dumps(returndict)

    def getdevice(self, index):
        # JSON for Grid devices
        if self.devices[index]["type"] == "grid":
            return {
                "rpm": {
                    0: self.devices[index]["node"].get_rpm(0),
                    1: self.devices[index]["node"].get_rpm(1),
                    2: self.devices[index]["node"].get_rpm(2),
                    3: self.devices[index]["node"].get_rpm(3),
                    4: self.devices[index]["node"].get_rpm(4),
                    5: self.devices[index]["node"].get_rpm(5)
                },
                "current": {
                    0: self.devices[index]["node"].get_power(0),
                    1: self.devices[index]["node"].get_power(1),
                    2: self.devices[index]["node"].get_power(2),
                    3: self.devices[index]["node"].get_power(3),
                    4: self.devices[index]["node"].get_power(4),
                    5: self.devices[index]["node"].get_power(5)
                }
            }

    def query(self, query):
        try:
            if json.loads(query)["type"] == "all":
                return self.getall()

        except Exception as e:
            print e
            return '{}'
