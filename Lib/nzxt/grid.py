#!/bin/python2
"""
CAM4LINUX - a control suite for nzxt devices
Copyright (C) 2016 Matthias Riegler <matthias@xvzf.tech>

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
"""

import serial
import time

class Grid(object):

    # IDs based on reverse engineering the "protocol"
    ID_GET_RPM      = 138
    ID_SET_VOLTAGE  = 68
    ID_GET_VOLTAGE  = 132

    # Maximum voltage, NZXT uses 12.4 in their software, however if I send 12.4v to the fan controller,
    # it does response with an OK, but it doesn't change the voltage. This problem appears on windows
    # side too, if I set the fan speed to 100% in the CAM Software, there is no change in fan speed.
    max_voltage     = 12.0

    def __init__(self, port):
        super(Grid, self).__init__()
        self.port = port
        self.connection = serial.Serial(port,baudrate=4800)


    def transmit(self, buffer, bytes_to_read):
        # TODO ERROR HANDLING
        self.connection.write(buffer)
        time.sleep(0.25)
        tmp = self.connection.read(self.connection.inWaiting())
        returnbuffer = []
        for i in tmp:
            returnbuffer.append(ord(i))
        return returnbuffer


    def checkresponse(self, response):
        if len(response) != 1:
            return -1

        if response[0] == 1:
            return 0
        else:
            return -1


    def get_rpm(self, index):
        if index not in range(1,7):
            return -1

        sendbuffer = [self.ID_GET_RPM, index]
        response = self.transmit(sendbuffer, 5)
        
        # Check if error occured
        if len(response) != 5:
            return -1

        return (int(response[3]) << 8) + int(response[4])


    def set_voltage(self, index , voltage):
        # I don't think the fan controller can handle precision up to 0.01v, so I dropped the support
        vsteps = int(voltage*10) # Preparations for linux kernel module integration
                                 # no floating point in kernelspace so we use 0.1v steps!
        
        sendbuffer = [self.ID_SET_VOLTAGE, index ,192, 0, 0, (vsteps/10), ((vsteps % 10) << 4)]
        
        response = self.transmit(sendbuffer, 1)

        return self.checkresponse(response)


    def set_percentage(self, index, p):
        
        if p > 100:
            return -1
       
        return self.set_voltage(index, (p/100.0) * max_voltage)


    def get_voltage(self, index):

        sendbuffer = [self.ID_GET_VOLTAGE, index]

        response = self.transmit(sendbuffer, 5)

        if len(response) != 5:
            return -1.0

        # Again, preparations for kernel integration. We drop the 2nd digit.
        tmp_voltage = int(response[3]) * 10 + (int(response[4] >> 4))

        return float(tmp_voltage)/10.0


    def get_current(self, index):
        #TODO
        pass