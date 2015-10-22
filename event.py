import time
import math
import random
import types
import colorsys
import wub
from kinet import *

class Wrapper(object):
    def __init__(self, instance, fget):
        self.instance = instance
        self.fget = fget

    def __call__(self):
        return self.fget(self.instance)

class Output(object):
    def __init__(self, fget=None):
        self.fget = fget

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if self.fget is None:
            raise AttributeError("unreadable attribute")
        return Wrapper(obj, self.fget)

    def getter(self, fget):
        return type(self)(fget)

class Proxy(object):
    def __init__(self, prop, default=None):
        self.prop = prop
        self.default = default

    def __get__(self, obj, objtype=None):
        prop = obj.inputs.get(self.prop, None)
        if prop == None:
            return obj.__dict__.get(self.prop, self.default)
        return prop()

class MetaNode(type):
    def __new__(cls, name, parents, dct):
        inputs = dct.get("Inputs", {})
        for (prop, default) in inputs.items():
            dct[prop] = Proxy(prop, default)
        return super(MetaNode, cls).__new__(cls, name, parents, dct)

class Node(object):
    __metaclass__ = MetaNode
    Inputs = {}

    def __init__(self, **kw):
        self.inputs = {}

        for (key, value) in kw.items():
            if type(value) == Wrapper:
                self.inputs[key] = value
            else:
                self.__dict__[key] = value

class Sin(Node):
    Inputs = {
        "amplitude": 0.5,
        "angle": 0,
        "period": 2 * math.pi,
        "center": 0.5,
    }

    @Output
    def output(self):
        step = (2 * math.pi) / self.period
        return math.sin(self.angle * step) * self.amplitude + self.center

class Scale(Node):
    Inputs = {
        "input_min": 0,
        "input_max": 1,
        "output_min": 0,
        "output_max": 1,
        "value": 0,
    }

    @Output
    def output(self):
        input_range = self.input_max - self.input_min
        output_range = self.output_max - self.output_min
        ratio = float(output_range) / input_range
        return self.value * ratio + self.output_min

class HSV_RGB(Node):
    Inputs = {
        "hue": 0,
        "saturation": 0.5,
        "value": 1,
        "scale": 0xff,
    }

    @Output
    def rgb(self):
        rgb = colorsys.hsv_to_rgb(self.hue, self.saturation, self.value)
        rgb = [int(round(self.scale * val)) for val in rgb]
        return rgb

class Modulo(Node):
    Inputs = {
        "mod": 1.0,
        "value": 0,
    }

    @Output
    def output(self):
        return self.value % self.mod

class Timer(Node):
    @Output
    def time(self):
        return time.time()

class Decay(Node):
    Inputs = {
        "decay_time": 0.1,
        "min_value": 0.1,
        "max_value": 1.0,
    }

    def __init__(self, *args, **kw):
        super(Decay, self).__init__(*args, **kw)
        self.trigger()

    def trigger(self):
        self.trigger_ts = time.time()

    @Output
    def output(self):
        elapsed = time.time() - self.trigger_ts
        ratio = elapsed / float(self.decay_time)
        _range = self.max_value - self.min_value
        value = min(self.max_value, max(self.min_value, self.max_value - ratio * _range))
        return value

class Clamp(Node):
    Inputs = {
        "min_value": 0.0,
        "max_value": 1.0,
        "value": 0.0,
    }

    @Output
    def output(self):
        return min(self.max_value, max(self.min_value, self.value))

class Threshold(Node):
    Inputs = {
        "threshold": 0.5,
        "min_value": 0.0,
        "max_value": 1.0,
        "value": 0,
    }

    @Output
    def output(self):
        return self.min_value if self.value < self.threshold else self.max_value

class MyTempo(wub.SafeTempo):
    def __init__(self, trigger, *args):
        wub.SafeTempo.__init__(self, *args)
        self.trigger = trigger

    def tempo(self, bpm, conf):
        if conf > 0.1:
            self.trigger.trigger()

class TempoMonitor(object):
    def __init__(self, trigger):
        card = "plughw:1,0"
        bufsize = 128
        channels = 1
        sample_rate = 44100
        self.tempo = MyTempo(trigger, bufsize * 2, bufsize, sample_rate, "specdiff");
        self.tempo.open()
        self.source = wub.ALSAAudioSource(sample_rate, card, channels, bufsize)
        self.source.open()
        wub.start(self.source, self.tempo)

"""
t = Timer()
h = Sin(period=10, angle=t.time)
s = Sin(period=20, angle=t.time, amplitude=0.25, center=0.25)
v = Sin(period=1, angle=t.time)
q = Modulo(value=t.time)
brightness = Threshold(threshold=v.output, value=q.output)
"""

decay = Decay(min_value=0.0, decay=0.1)
tempo = TempoMonitor(decay)

t = Timer()
h = Sin(period=10, angle=t.time)
h = Clamp(value=h.output)
#s = Sin(period=20, angle=t.time, amplitude=0.25, center=0.25)
#v = Sin(period=1, angle=t.time)
#q = Modulo(value=t.time)
#brightness = Threshold(threshold=v.output, value=q.output)

c = HSV_RGB(hue=h.output, value=decay.output)
pds = PowerSupply("192.168.1.121")
fix1 = FixtureRGB(15)
pds.append(fix1)

while 1:
    fix1.rgb = c.rgb()
    pds.go()
    #time.sleep(.0001)
