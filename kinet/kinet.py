import socket
import colorsys
import time
import struct
import random

class Header(object):
    Order = ["magic", "version", "type", "sequence", "port", "padding", "flags", "timer", "uni"]
    Struct = ">IHHIBBHIB"
    Defaults = [0x0401dc4a, 0x0100, 0x0101, 0x00000000, 0x00, 0x00, 0x0000, 0xffffffff, 0x00]

    def __init__(self, **kw):
        defaults = dict(zip(self.Order, self.Defaults))
        defaults.update(kw)
        self.__dict__.update(defaults)
        self.__update()

    def __str__(self):
        return self.__cache

    def __update(self):
        data = [getattr(self, name) for name in self.Order]
        self.__cache = struct.pack(self.Struct, *data)

    def __setattr__(self, name, value):
        super(Header, self).__setattr__(name, value)
        if name in self.Order:
            self.__update()

class PowerSupply(list):
    def __init__(self, host, header=None, port=6038, sock=None):
        super(PowerSupply, self).__init__()
        self.host = host
        self.port = port
        if not sock:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            addr = (self.host, self.port)
            self.socket.connect(addr)
        else:
            self.socket = sock
        if header == None:
            self.header = Header()
        else:
            self.header = header

    def copy(self):
        newdim = self.__class__(self.host, self.header, self.port, self.socket)
        for fixture in self:
            newdim.append(fixture.copy())
        return newdim

    def clear(self, go=True):
        for fixture in self:
            fixture.clear()
        if go:
            self.go()

    def __str__(self):
        out = ''
        patch = [str(fixture) for fixture in self]
        return str.join(' ', patch)

    def go(self):
        buf = ''
        data = [0] * 512
        for fixture in self:
            addr = fixture.address
            for idx, val in enumerate(fixture):
                data[addr + idx] = val
        data = str(self.header) + struct.pack('512B', *data)
        self.socket.send(data)
    
class Fixture(object):
    def __init__(self, address):
        self.address = address

class FixtureRGB(Fixture):
    _RED = (0, 0xff)
    _GRN = (0, 0xff)
    _BLU = (0, 0xff)

    def __init__(self, address, red=0, green=0, blue=0):
        super(FixtureRGB, self).__init__(address)
        self.red = red
        self.green = green
        self.blue = blue

    def copy(self):
        return self.__class__(self.address, self.red, self.green, self.blue)

    def __cmp__(self, other):
        return compare(self.address, other.address)

    def __getitem__(self, color):
        if color == 0: return self.red
        if color == 1: return self.green
        if color == 2: return self.blue
        raise ValueError, color

    def __setitem__(self, color, value):
        if color == 0: self.red = value
        elif color == 1: self.green = value
        elif color == 2: self.blue = value
        else: raise ValueError, color

    def ascii(self):
        chars = [chr(ord('0') + x) for x in range(10)]
        val = self.red + self.green + self.blue
        if val == 0:
            return '-'
        return chars[val % len(chars)]

    def go(self):
        return str.join('', [chr(x) for x in self])

    def __iter__(self):
        return iter([self.red, self.green, self.blue])

    def __repr__(self):
        return "<Pixel %d,%d,%d>" % (self.red, self.green, self.blue)

    def __str__(self):
        return '[%03d %03d %03d]' % tuple(self)

    def get_red(self): 
        return self._red
    def set_red(self, val):
        self._red = max(self._RED[0], min(self._RED[1], int(val)))
    red = property(get_red, set_red)

    def get_green(self): 
        return self._green
    def set_green(self, val):
        self._green = max(self._GRN[0], min(self._GRN[1], int(val)))
    green = property(get_green, set_green)
    grn = property(get_green, set_green)

    def get_blue(self): 
        return self._blue
    def set_blue(self, val):
        self._blue = max(self._BLU[0], min(self._BLU[1], int(val)))
    blue = property(get_blue, set_blue)
    blu = property(get_blue, set_blue)

    def get_rgb(self):
        return (self.red, self.green, self.blue)
    def set_rgb(self, rgb):
        self.red = rgb[0]
        self.green = rgb[1]
        self.blue = rgb[2]
    rgb = property(get_rgb, set_rgb)

    def get_hsv(self):
        red = self.red / float(self._RED[1]) 
        green = self.green / float(self._GRN[1]) 
        blue = self.blue / float(self._BLU[1]) 
        rgb = (red, green, blue)
        hsv = colorsys.rgb_to_hsv(*rgb)
        return hsv

    def set_hsv(self, hsv):
        rgb = colorsys.hsv_to_rgb(*hsv)
        self.red = (self._RED[1] * rgb[0])
        self.green = (self._GRN[1] * rgb[1])
        self.blue = (self._BLU[1] * rgb[2])
    hsv = property(get_hsv, set_hsv)

    def clear(self):
        self.rgb = (self._RED[0], self._GRN[0], self._BLU[0])

class FadeIter(object):
    def __init__(self, old_patch, new_patch, ttl):
        self.old_patch = old_patch
        self.new_patch = new_patch
        self.slopes = []
        self.ttl = ttl
        self.setup_increments()

    def setup_increments(self):
        for fidx, fixture in enumerate(self.old_patch):
            slopes = []
            for channel, level in enumerate(fixture):
                distance = self.new_patch[fidx][channel] - self.old_patch[fidx][channel]
                slopes.append(distance / float(self.ttl))
            self.slopes.append(slopes)

    def __iter__(self):
        return self.FadeIterCore(self.old_patch, self.slopes, self.ttl)

    def go(self):
        for nothing in self:
            pass

    class FadeIterCore(object):
        def __init__(self, old_patch, slopes, ttl):
            self.old_patch = old_patch
            self.cur_patch = old_patch.copy()
            self.cur_patch.clear(False)
            self.slopes = slopes
            self.ttl = ttl
            self.ts = time.time()

        def next(self):
            now = time.time()
            delta = now - self.ts
            if delta > self.ttl:
                delta = self.ttl
            for led in range(len(self.cur_patch)):
                for clr in range(3):
                    self.cur_patch[led][clr] = self.slopes[led][clr] * delta + \
                        self.old_patch[led][clr]
            self.cur_patch.go()
            if delta >= self.ttl:
                raise StopIteration
