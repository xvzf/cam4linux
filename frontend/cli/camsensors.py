#!/bin/python2
"""
CAM4LINUX - a control suite for nzxt devices
Copyright (C) 2017 Matthias Riegler <matthias@xvzf.tech>

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
"""

import argparse
import socket
import json
import sys

prefix = "  "

def servercall(query, addr, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    jsonbuf = '{}'
    try:
        s.connect((addr,port))

        # Transmit query
        s.sendall(query)

        # Receive response
        jsonbuf = s.recv(65535)

    except Exception as e:
        raise
    finally:
        s.close()

    return json.loads(jsonbuf)

def printgrid(grid):

    print prefix + "RPM:"
    for i in range(6):
        print 2*prefix + str(i) + ":\t\t" + str(grid["rpm"][str(i)]) + " RPM"

    totalpower = 0.0
    for i in range(6):
        totalpower = totalpower + grid["power"][str(i)]

    print prefix + "Power:"
    print 2*prefix + "Total:\t" + str(totalpower) + " W"
    for i in range(6):
        print 2*prefix + str(i) + ":\t\t" + str(grid["power"][str(i)]) + " W"


def printout(device):
    if device["type"] == "grid":
            printgrid(device)

def setdevice(args):
    setquery = {}
    setquery["type"] = "set"
    if args.set:
        devset = {}
        if args.ports:
            for i in args.ports:
                if args.value:
                    devset[i] = int(args.value)
        setquery[args.set] = devset

    addr='127.0.0.1'
    port=3567

    if args.addr:
        print "[+] Using custom IP"
        addr = args.addr

    if args.port:
        print "[+] Using custom Port"
        port = int(args.port)

    retbuf = servercall(json.dumps(setquery), addr,port)

    try:
        if retbuf[args.set] == "OK":
            print "OK"
        else:
            print "ERROR"
    except Exception as e:
        print "ERROR"


def main():
    parser = argparse.ArgumentParser(description='CAM4LINUX CLI')
    parser.add_argument('--device', help='Select device', nargs='+')
    parser.add_argument('--addr', help='Custom IP')
    parser.add_argument('--port', help='Custom Port')
    parser.add_argument('--set', help='Set value for device')
    parser.add_argument('--value', help='Value to set')
    parser.add_argument('--ports', help='Select output ports', nargs='+')
    
    args = parser.parse_args()

    if args.set:
        setdevice(args)
        return

    addr='127.0.0.1'
    port=3567

    if args.addr:
        print "[+] Using custom IP"
        addr = args.addr

    if args.port:
        print "[+] Using custom Port"
        port = int(args.port)

    retbuf = servercall(json.dumps({"type":"all"}), addr,port)

    if args.device:
        for i in retbuf.keys():
            if i in args.device:
                print i + ":"
                printout(retbuf[i])
        
        return

    for i in retbuf.keys():
        print i + ":"
        printout(retbuf[i])


if __name__ == '__main__':
    main()