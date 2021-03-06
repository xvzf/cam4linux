#!/usr/bin/env python3
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
from _thread import start_new_thread # For now let's keep it - @TODO Replace the threading library

class Grid(object):

    # IDs based on reverse engineering the "protocol"
    ID_GET_RPM          = 138
    ID_SET_VOLTAGE      = 68
    ID_GET_VOLTAGE      = 132
    ID_GET_CURRENT      = 133

    # Maximum voltage, NZXT uses 12.4 in their software, however if I send 12.4v to the fan controller,
    # it does response with an OK, but it doesn't change the voltage. This problem appears on windows
    # side too, if I set the fan speed to 100% in the CAM Software, there is no change in fan speed.
    max_voltage         = 12.0
    min_voltage         = 5.0   # Should be OK for most fans. Maybe raise to 7 if needed. An option will
                                # be added in the config file
    max_response_wait   = 6     # Used in _transmit

    everythingok        = False

    # Buffer Array for the update thread
    _rpms               = [0, 0, 0, 0, 0, 0]
    _powers             = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    # Buffer for speeds to set
    _set_rpms           = [-1, -1, -1, -1, -1, -1]


    def __init__(self, port):
        super(Grid, self).__init__()
        self.port = port
        self.connection = serial.Serial(port,baudrate=4800) # Maybe they think that no error correction 
                                                            # is needed when they use low baud rates
        
        # Lets start an update routine so we don't have to deal with the slow response times!
        self.everythingok = self.connection.isOpen()
        start_new_thread(Grid._updatethread, (self,))


    # This functions updates all values at a given update intervall
    def _update(self):
        # The device supports 6 fans attached 
        for i in range(0,6):
            # Set the ports according to the defined values
            self._set_percentage(i, self._set_rpms[i])

            # Update values
            self._rpms[i] = self._get_rpm(i)                                    # Update_rpm
            self._powers[i] = self._get_voltage(i) * self._get_current(i)       # Update power usage


    # Should be self explaining
    # I don't know what I wanted to do with the update interval?! Just let it run and then some time to 
    # settle
    def _updatethread(self):
        while self.everythingok:
            self._update() # Measured at max 3 seconds
            time.sleep(1)  # Data shouldn't be older than 4 seconds, 


    def _transmit(self, buffer, bytes_to_read):
        self.connection.write(buffer)

        # Do not wait longer than 0.5 seconds for a response
        totalwait = 0
        while self.connection.inWaiting() != bytes_to_read and totalwait < self.max_response_wait:
            time.sleep(0.1)
            totalwait = totalwait + 1

        # If there are more bytes in the fifo than expected, there might be an error in the transmission
        # Drop everything so the next transmission works again.
        if self.connection.inWaiting() > bytes_to_read:
            self.connection.read(self.connection.inWaiting())
            return []

        tmp = self.connection.read(self.connection.inWaiting())

        # Converting the character array to an int array makes it easier to implement further operations
        # without converting the array in each individually
        returnbuffer = []
        for i in tmp:
            returnbuffer.append(i)

        return returnbuffer


    def _checkresponse(self, response):
        if len(response) != 1:
            return -1

        if response[0] == 1:
            return 0
        else:
            return -1


    # The rpm is _transmitted in two bytes, which are combined in either uint16_t or int16_t (doesnt matter)
    def _get_rpm(self, index):

        # Indexes starting at 1
        index = index + 1

        if index not in range(1,7):
            return -1

        sendbuffer = [self.ID_GET_RPM, index]
        response = self._transmit(sendbuffer, 5)
        
        # Check if error occured
        if len(response) != 5:
            return -1

        # Sometimes, RPM measurement goes way above 10k RPM, that's an issue inside the Grid controller.
        return (int(response[3]) << 8) + int(response[4])


    # The voltage is _transmitted in a 2 byte block. first byte covers the decimal value and the 2nd byte 
    # responses to the 1st and 2nd digit.
    # @TODO Maybe send 2 times in a row - sometime it doesn't pick changes. For now that's handled by the
    # update thread
    def _set_voltage(self, index , voltage):

        # Indexes starting at 1
        index = index + 1

        # I don't think the fan controller can handle precision up to 0.01v, so I dropped the support
        vsteps = int(voltage*10) # Preparations for linux kernel module integration
                                 # no floating point in kernelspace so we use 0.1v steps!
        
        sendbuffer = [self.ID_SET_VOLTAGE, index ,192, 0, 0, int(vsteps/10), int((vsteps % 10) << 4)]
        
        response = self._transmit(sendbuffer, 1)

        return self._checkresponse(response)


    # The requested answer is provided in the same format as the voltage is set. I don't think the internal
    # measurement is precise - I measured 12.13v on one fan out put using my multimeter (not calibrated!) -
    # get_voltage() returns 11.4, which a 0.7v difference.
    def _get_voltage(self, index):

        # Indexes starting at 1
        index = index + 1

        sendbuffer = [self.ID_GET_VOLTAGE, index]

        response = self._transmit(sendbuffer, 5)

        if len(response) != 5:
            return -1.0

        # Again, preparations for kernel integration. We drop the 2nd digit.
        tmp_voltage = int(response[3]) * 10 + (int(response[4] >> 4))

        return float(tmp_voltage)/10.0


    # Get the current so we can calculate the power afterwards. Usefull to check if a fan is connected
    # Not precise at all!
    def _get_current(self, index):
        
        # Indexes starting at 1
        index = index + 1

        sendbuffer = [self.ID_GET_CURRENT, index]

        response = self._transmit(sendbuffer, 5)

        if len(response)  != 5:
            return -1.0

        # This time, we keep the 2nd digit. I don't think the current will go over 1A so it is required for a 
        # "precise" measurement -> Again preparations for linux kernel.
        tmp_current = int(response[3]) * 1000 + (int(response[4]) >> 4) * 100 +\
                      ((int(response[4]) << 4 ) >> 4) * 10


        return float(tmp_current)/1000.0


    # Should be self explaining as well
    def _set_percentage(self, index, p):
        
        if p > 100:
            return -1
       
        # Now we use a minimum voltage!
        return self._set_voltage(index, (self.min_voltage + float(p)/100.0) * (self.max_voltage - self.min_voltage))


    # Now updated in the _update() function.
    def set_percentage(self, index, p):
        # Just check index to prevent a crash. Percentage is set by the _set_percentage() function
        if index in range(0,6):
            self._set_rpms[index] = p


    # Get RPM
    def get_rpm(self,index):
        if index in range(0,6):
            return self._rpms[index]
        else:
            return -1


    # Get Power
    def get_power(self,index):
        if index in range(0,6):
            return self._powers[index]
        else:
            return -1.0


    # Makes integration in camservice easier
    def get_json(self):
        return {
           "rpm": {
                0: self.get_rpm(0),
                1: self.get_rpm(1),
                2: self.get_rpm(2),
                3: self.get_rpm(3),
                4: self.get_rpm(4),
                5: self.get_rpm(5)
            },
            "power": {
                0: self.get_power(0),
                1: self.get_power(1),
                2: self.get_power(2),
                3: self.get_power(3),
                4: self.get_power(4),
                5: self.get_power(5)
            },
            "type": "grid"
        }


    # Same as get_json
    def set_json(self, toset):
        inputok = True

        for i in toset.keys():
        
            if int(i) not in range(6):
                inputok = False

            if toset[i] not in range(101):
                inputok = False

            if inputok:
                self.set_percentage(int(i), int(toset[i]))

        if inputok:
            return "OK"
        else:
            return "ERROR"