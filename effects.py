import time
import math
import random
import types
import colorsys
import wub
import threading
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

class Neuron(Node):
    Inputs = {
        "decay_time": 0.1,
        "min_value": 0.1,
        "max_value": 1.0,
        "step_value": 0.1,
        "offset": 0.0,
    }

    def __init__(self, *args, **kw):
        super(Neuron, self).__init__(*args, **kw)
        self.trigger()

    def trigger(self):
        self.trigger_ts = time.time()
        self.value += self.step_value

    @Output
    def output(self):
        elapsed = time.time() - self.trigger_ts
        ratio = elapsed / float(self.decay_time)
        _range = self.value - self.min_value
        self.value = min(self.max_value, max(self.min_value, self.value - ratio * _range))
        return self.value


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

class Tempo(wub.Tempo):
    def __init__(self, source, silence=None, method="default"):
        self.source = source
        bufsize = self.source.get_buffer_size()
        srate = self.source.get_sample_rate()
        super(Tempo, self).__init__(bufsize * 4, bufsize, srate, method)
        if silence != None:
            self.set_silence(silence)
        self.bind(self.source)
        self.hooks = []

    def add_hook(self, hook):
        self.hooks.append(hook)

    def tempo_callback(self, bpm=0.0, confidence=0.0):
        self.bpm = bpm
        self.confidence = confidence
        for hook in self.hooks:
            hook(self)

class Pitch(wub.Pitch):
    def __init__(self, source, silence=None, unit="midi", method="default"):
        self.source = source
        bufsize = self.source.get_buffer_size()
        srate = self.source.get_sample_rate()
        super(Pitch, self).__init__(bufsize * 4, bufsize, srate, method)
        if unit != None:
            self.set_unit(unit)
        if silence != None:
            self.set_silence(silence)
        self.bind(self.source)
        self.hooks = []

    def add_hook(self, hook):
        self.hooks.append(hook)

    def pitch_callback(self, pitch=0.0, confidence=0.0):
        self.pitch = pitch
        self.confidence = confidence
        for hook in self.hooks:
            hook(self)

class Onset(wub.Onset):
    def __init__(self, source, silence=None, method="default"):
        self.source = source
        bufsize = self.source.get_buffer_size()
        srate = self.source.get_sample_rate()
        super(Onset, self).__init__(bufsize * 4, bufsize, srate, method)
        if silence != None:
            self.set_silence(silence)
        self.bind(self.source)
        self.hooks = []

    def add_hook(self, hook):
        self.hooks.append(hook)

    def onset_callback(self, *args):
        for hook in self.hooks:
            hook(self)

def build_source():
    card = "plughw:1,0"
    bufsize = 128
    channels = 2
    sample_rate = 44100
    source = wub.ALSAAudioSource(card, sample_rate, channels, bufsize)
    return source

"""
t = Timer()
h = Sin(period=10, angle=t.time)
s = Sin(period=20, angle=t.time, amplitude=0.25, center=0.25)
v = Sin(period=1, angle=t.time)
q = Modulo(value=t.time)
brightness = Threshold(threshold=v.output, value=q.output)
"""

source = build_source()
tempo = Tempo(source)
onset = Onset(source, silence=-47)
pitch = Pitch(source, silence=-47)
decay = Decay(min_value=0.6, max_value=1.0,  decay=1.5)
#decay = Neuron(min_value=0.1, decay=5)
midi_scale = Scale(input_min=0, input_max=127, output_min=0, output_max=1)

def tempo_decay_hook(_tempo):
    if _tempo.confidence < 0.01:
        return
    decay.decay = (_tempo.bpm / 60.0) * 0.9
    decay.trigger()

def onset_decay_hook(_onset):
    #decay.decay = (_tempo.bpm / 60.0) * 0.9
    decay.trigger()

def pitch_scale_hook(_pitch):
    midi_scale.value = _pitch.pitch

tempo.add_hook(tempo_decay_hook)
onset.add_hook(onset_decay_hook)
pitch.add_hook(pitch_scale_hook)
source.start()

t = Timer()
sinwave = Sin(period=10, angle=t.time)

"""
def sin_hook(_tempo):
    if _tempo.confidence < 0.01:
        return
    sinwave.period = (_tempo.bpm / 60.0) * 4
tempo.add_hook(sin_hook)
"""

#h = Clamp(value=h.output)
#s = Sin(period=20, angle=t.time, amplitude=0.25, center=0.25)
#v = Sin(period=1, angle=t.time)
#q = Modulo(value=t.time)
#brightness = Threshold(threshold=v.output, value=q.output)

#c = HSV_RGB(hue=sinwave.output, value=decay.output)
#c = HSV_RGB(hue=midi_scale.output, value=decay.output)
c = HSV_RGB(hue=midi_scale.output, saturation=0.9, value=0.5)
pds = PowerSupply("192.168.1.121")
fix1 = FixtureRGB(15)
pds.append(fix1)

while 1:
    fix1.rgb = c.rgb()
    #print fix1.rgb
    pds.go()
    #time.sleep(.0001)
