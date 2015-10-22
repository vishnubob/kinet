from kinet import *

discover = Discover()
discover.discover()
pds = PowerSupply(host="192.168.1.122")
pds.discover()
pds = PowerSupply(host="192.168.1.121")
pds.discover()

