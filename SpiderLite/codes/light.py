import smbus
import time

bus = smbus.SMBus(1)
ADDR = 0x48

def read_channel(ch):
    if ch < 0 or ch > 7:
        return 0
    

    cmd = 0x84 | (ch << 4)
    
    return bus.read_byte_data(ADDR, cmd)

while True:
    val = read_channel(0)
    voltage = val * 3.3 / 255
    
    print(f"CH0 = {val}  |  {voltage:.2f} V")
    time.sleep(0.5)
