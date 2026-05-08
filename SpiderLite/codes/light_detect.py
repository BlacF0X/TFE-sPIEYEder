import spidev
import math

class LightTracker3D:
    def __init__(self):
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = 1350000

        # directions des 8 LDR (coins d’un cube)
        self.directions = [
            (-1,  1,  1),
            ( 1,  1,  1),
            (-1, -1,  1),
            ( 1, -1,  1),
            (-1,  1, -1),
            ( 1,  1, -1),
            (-1, -1, -1),
            ( 1, -1, -1),
        ]

    def read_channel(self, ch):
        adc = self.spi.xfer2([1, (8 + ch) << 4, 0])
        return ((adc[1] & 3) << 8) | adc[2]

    def read_all(self):
        return [self.read_channel(i) for i in range(8)]

    def normalize(self, values):
        min_v = min(values)
        max_v = max(values)

        if max_v - min_v == 0:
            return [0]*len(values)

        return [(v - min_v) / (max_v - min_v) for v in values]

    def compute_vector(self, values):
        x = y = z = 0

        for i in range(8):
            x += values[i] * self.directions[i][0]
            y += values[i] * self.directions[i][1]
            z += values[i] * self.directions[i][2]

        norm = math.sqrt(x*x + y*y + z*z)
        if norm == 0:
            return (0, 0, 0)

        return (x/norm, y/norm, z/norm)

    def get_light_direction(self):
        raw = self.read_all()
        norm = self.normalize(raw)
        return self.compute_vector(norm)


def to_angles(x, y, z):
    azimut = math.atan2(y, x)
    elevation = math.atan2(z, math.sqrt(x*x + y*y))
    return azimut, elevation

tracker = LightTracker3D()


while True:
    d1,d2,d3= tracker.get_light_direction()
    az,el = to_angles(d1,d2,d3)
    print(tracker.read_channel(0))
