from kinet import *

def rainbow_cycle(pds, pause=.1, steps=1000):
    div = steps / len(pds)
    for step in range(steps):
        ratio = 0
        for idx, fixture in enumerate(pds):
            ratio += (step + idx * div) % steps / float(steps)
            fixture.hsv = (ratio, 1.0, 1.0)
        print pds
        pds.go()
        time.sleep(pause)
        
# example of how to use the FadeIter
def fader(pds1, cnt):
    pds2 = pds1.copy()
    while cnt:
        pds1[random.randint(0, 2)][random.randint(0, 2)] = random.randint(0, 255)
        pds2[random.randint(0, 2)][random.randint(0, 2)] = random.randint(0, 255)
        print "%s => %s" % (pds1, pds2)
        fi1 = FadeIter(pds1, pds2, .5)
        fi2 = FadeIter(pds2, pds1, .5)
        fi1.go()
        fi2.go()
        pds1.clear()
        pds2.clear()
        cnt -= 1

if __name__ == '__main__':
    # Our ethernet attached power supply.
    pds = PowerSupply("192.168.1.121")

    # Our light fixtures
    fix1 = FixtureRGB(0)
    fix2 = FixtureRGB(3)
    fix3 = FixtureRGB(6)

    # Attach our fixtures to the power supply
    pds.append(fix1)
    pds.append(fix2)
    pds.append(fix3)

    while 1:
        fader(pds, 10)
        rainbow_cycle(pds)
