#!/usr/bin/env python3
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
import sys

# Allow comments starting with '#' in the config file. JSON does not support comments natively
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

        The following functions are quite abstract and not easy to understand. Also, I still
        have to comment the functions. Do not change it unless you know what you are doing.

        Integration of new devices:
            A device (python class) with:
                json_get()  outputs a dictionary with all values which are currently measured

                json_set()  some sort of function, that takes a dictionary as input and sets
                            the devices values according to the json file. Output OK if 
                            everything worked. If not, Output ERROR. Both as a string.
    """

    devices = []
    
    def __init__(self, configfile):
        super(Camservice, self).__init__()
        self.configfile = configfile
        self.readconfig()
        print(self.devices)

    def readconfig(self):
        try:
            with open(self.configfile, "r") as file:
                parsed_json = json.loads(cleanupconfig(file.read()))
                self.parseconfig(parsed_json)

        except IOError:
            print("[-] Could not open configuration file, exiting", file=sys.stderr)
        
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
            return self.devices[index]["node"].get_json()

    def setdevice(self, index, values):
        return self.devices[index]["node"].set_json(values)

    def setdevices(self, setlist):
        retbuf = {}
        # Go through all registered devices
        for i in range(len(self.devices)):
            # Check if the device should be set to a new value
            if self.devices[i]["name"] in setlist.keys():
                retbuf[self.devices[i]["name"]] = self.setdevice(i, setlist[self.devices[i]["name"]])

        return json.dumps(retbuf)

    def query(self, query):
        try:
            if json.loads(query)["type"] == "all":
                return self.getall()

            if json.loads(query)["type"] == "set":
                tmp = json.loads(query)
                del tmp["type"]
                return self.setdevices(tmp)

        except Exception as e:
            print(e, file=sys.stderr)
            return '{}'
