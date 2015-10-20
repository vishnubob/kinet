import socket
import colorsys
import time
import struct
import random
import errno

class MetaStruct(type):
    def __new__(cls, name, parents, dct):
        struct = dct.get("Struct", tuple())
        keys = [st[0] for st in struct]
        dct["Keys"] = set(keys)
        return super(MetaStruct, cls).__new__(cls, name, parents, dct)

class KinetHeader(object):
    Struct = ()
    Flags = ">"

    __metaclass__ = MetaStruct

    def __init__(self, packed_data=None, **kw):
        self._struct = struct.Struct(self.struct_format)
        self._packed_data = None
        self._build_index()
        self._unpacked_data = []
        if packed_data == None:
            packed_data = ('\0' * self._struct.size)
            self.unpack(packed_data)
            self.update(self.defaults)
        else:
            self.unpack(packed_data)
        self.update(kw)

    def _build_index(self):
        self._index = {}
        offset = 0
        for (key, fmt, default) in self.Struct:
            (count, _type) = (fmt[:-1], fmt[-1])
            count = 1 if not count or _type == 's' else int(count)
            self._index[key] = slice(offset, offset + count)
            offset += count

    @property
    def struct_format(self):
        return self.Flags + str.join('', [st[1] for st in self.Struct])

    @property
    def size(self):
        return self._struct.size

    @property
    def defaults(self):
        return {st[0]: st[2] for st in self.Struct if st[2] != None}

    def __getattr__(self, key):
        if key not in self.Keys:
            return super(KinetHeader, self).__getattribute__(key)
        return self[key]

    def __setattr__(self, key, val):
        if key not in self.Keys:
            super(KinetHeader, self).__setattr__(key, val)
            return
        self[key] = val

    def __setitem__(self, key, val):
        if type(key) != int:
            key = self._index[key]
        if type(val) not in (list, tuple):
            val = [val]
        self._unpacked_data[key] = val
        self._packed_data = None

    def __getitem__(self, key):
        if type(key) != int:
            key = self._index[key]
        val = self._unpacked_data[key]
        if type(val) in (list, tuple) and len(val) == 1:
            return val[0]
        return val

    def update(self, _dict):
        for (key, val) in _dict.items():
            self[key] = val
        self._packed_data = None


    def __str__(self):
        return self.pack()

    def __repr__(self):
        vals = {key: self[key] for key in self._index}
        kw = str.join(', ', ['%s=%r' % kv for kv in dict(vals).items()])
        return "%s(%s)" % (self.__class__.__name__, kw)

    def pack(self):
        if self._packed_data == None:
            self._packed_data = self._struct.pack(*self._unpacked_data)
        return self._packed_data

    def unpack(self, packed_data):
        self._unpacked_data = list(self._struct.unpack(packed_data))

class DiscoverSupplies(KinetHeader):
    Struct = (
        ("magic", "I", 0x0401dc4a),
        ("version", "H", 0x0100),
        ("type", "H", 0x0100),
        ("sequence", "I", 0x00000000),
        ("command", "I", 0xc0a80189),
    )

class DiscoverFixturesSerialRequest(KinetHeader):
    Struct = (
        ("magic", "I", 0x0401dc4a),
        ("version", "H", 0x0100),
        ("type", "H", 0x0102),
        ("ip_address", "4B", None),
    )

class DiscoverFixturesSerialReply(KinetHeader):
    Struct = (
        ("magic", "I", None),
        ("version", "H", None),
        ("type", "H", None),
        ("ip_address", "4B", None),
        ("serial", "I", None),
    )

class DiscoverFixturesChannelRequest(KinetHeader):
    Struct = (
        ("magic", "I", 0x0401dc4a),
        ("version", "H", 0x0100),
        ("type", "H", 0x0302),
        ("ip_address", "4B", None),
        ("serial", "I", None),
        ("something", "H", 0x4100),
    )

class DiscoverFixturesChannelReply(KinetHeader):
    Struct = (
        ("magic", "I", None),
        ("version", "H", None),
        ("type", "H", None),
        ("ip_address", "4B", None),
        ("serial", "I", None),
        ("something", "H", None),
        ("channel", "B", None),
        ("ok", "B", None),
    )


class DiscoverySuppliesReply(KinetHeader):
    Struct = (
        ("magic", "I", None),
        ("version", "H", None),
        ("type", "H", None),
        ("sequence", "I", None),
        ("source_ip", "4B", None),
        ("mac_address", "6B", None),
        ("data", "2s", None),
        ("serial", "I", None),
        ("zero_1", "I", None),
        ("node_name", "60s", None),
        ("node_label", "31s", None),
        ("zero_2", "H", None),
    )

class Header(KinetHeader):
    Struct = (
        ("magic", "I", 0x0401dc4a),
        ("version", "H", 0x0100),
        ("type", "H", 0x0101),
        ("sequence", "I", 0x00000000),
        ("port", "B", 0x00),
        ("padding", "B", 0x00),
        ("flags", "H", 0x0000),
        ("timer", "I", 0xffffffff),
        ("universe", "B", 0x00),
    )

class Discover(object):
    BroadcastAddress = "255.255.255.255"

    def __init__(self, host=None, port=6038, header=None, sock=None, timeout=1):
        self.host = host if host != None else self.BroadcastAddress
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket.settimeout(timeout)
        if header == None:
            header = DiscoverSupplies()
        self.header = header

    def discover(self):
        self.socket.sendto(str(self.header), (self.host, self.port))
        for reply in self.gather():
            print repr(reply)

    def gather(self):
        replies = []
        while True:
            reply = DiscoverySuppliesReply()
            try:
                resp = self.socket.recvfrom(reply.size)
            except socket.timeout:
                break
            (data, addr) = resp
            reply.unpack(data)
            yield reply

class PowerSupply(list):
    def __init__(self, host, header=None, port=6038, sock=None, timeout=1):
        super(PowerSupply, self).__init__()
        self.host = host
        self.port = port
        self.timeout = timeout
        if not sock:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.settimeout(self.timeout)
            addr = (self.host, self.port)
            self.socket.connect(addr)
        else:
            self.socket = sock
        if header == None:
            self.header = Header()
        else:
            self.header = header

    def discover(self):
        for serial in self.discover_fixtures_serial():
            channel = self.discover_fixtures_channel(serial)
            print serial, channel


    def discover_fixtures_serial(self):
        ip_addr = map(int, self.host.split('.'))
        packet = DiscoverFixturesSerialRequest(ip_address=ip_addr)
        self.socket.send(str(packet))
        serials = []
        while 1:
            reply = DiscoverFixturesSerialReply()
            try:
                data = self.socket.recv(reply.size)
            except socket.timeout:
                break
            reply.unpack(data)
            serials.append(reply.serial)
        return serials

    def discover_fixtures_channel(self, serial):
        ip_addr = map(int, self.host.split('.'))
        packet = DiscoverFixturesChannelRequest(serial=serial)
        self.socket.send(str(packet))
        reply = DiscoverFixturesChannelReply()
        try:
            data = self.socket.recv(reply.size)
        except socket.timeout:
            pass
        reply.unpack(data)
        return reply.channel

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
