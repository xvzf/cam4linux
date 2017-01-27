#!/bin/python2
"""
CAM4LINUX - a control suite for nzxt devices
Copyright (C) 2017 Matthias Riegler <matthias@xvzf.tech>

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
"""


import socket
import sys
import nzxt

# Now reserved for cam4linux. Deal with it.
SERVERPORT = 3567

def main():
    # Create camservice instance, only one at a time can run! 
    c = nzxt.Camservice("/etc/cam4linux/config.json")

    # Create socket for server
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Bind to the given port on localhost.
        s.bind(('localhost',SERVERPORT))
        s.listen(1)

        while True:
            # Wait for client to connect
            conn, addr = s.accept()
            try:
                data = conn.recv(65535)
                # Query from camservice
                if data:
                    retbuf = c.query(data)
                    if retbuf:
                        conn.sendall(retbuf)
            except Exception as e:
                raise
            finally:
                conn.close()

    except socket.error as e:
        print >>sys.stderr, e
    except KeyboardInterrupt as e:
        s.close()
        
    except Exception as e:
        print >>sys.stderr, e
    finally:
        s.close()




if __name__ == '__main__':
    main()