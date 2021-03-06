import time
from datetime import datetime
import math
import csv
import os
from gps3.agps3threaded import AGPS3mechanism
import smbus2 as smbus
import Adafruit_DHT as dht
import .camera

# log config variables
LOG_FREQUENCY = 1  # how often to log in seconds

# compass config vars
compass_reg_a = 0  # compass config register addresses
compass_reg_b = 0x01
compass_reg_mode = 0x02
compass_xaxis = 0x03  # axis msb registers
compass_yaxis = 0x05
compass_zaxis = 0x07
compass_deviceAddress = 0x1e  # sensor address
declination = math.radians(-10.27)

pressure_deviceAddress = 0x5d

dht_pin = 18
dht_sensor = dht.DHT11

bus = smbus.SMBus(1)

bus.write_byte_data(compass_deviceAddress, compass_reg_a, 0x70)
bus.write_byte_data(compass_deviceAddress, compass_reg_b, 0xa0)
bus.write_byte_data(compass_deviceAddress, compass_reg_mode, 0)

bus.write_byte_data(pressure_deviceAddress, 0x21, 0b100)  # reset pressure sensor
bus.write_byte_data(pressure_deviceAddress, 0x20, 0b11000000)  # turn on and run at 25hz


def jpg():
    time = datetime.now().strftime("%y-%m-%d %H:%M:%S")
    cmd = os.system("libcamera-jpeg -o \"/data/" + time + ".jpg\"")
    if os.path.exists("/data/" + time + ".jpg") and cmd == 0:
        return "/data/" + time + ".jpg"
    else:
        return None


def compass_raw(addr):
    high = bus.read_byte_data(compass_deviceAddress, addr)
    low = bus.read_byte_data(compass_deviceAddress, addr+1)
    value = ((high << 8) | low)
    if(value > 32768):
        value = value - 65536
    return value


def pressure():
    # read 24bit 2 compliment from 0x29-0x2a
    raw = bus.read_byte_data(pressure_deviceAddress, 0x2a)*256**2
    raw += bus.read_byte_data(pressure_deviceAddress, 0x29)*256
    raw += bus.read_byte_data(pressure_deviceAddress, 0x28)
    # convert 2s compliment
    if raw & (1 << 23) != 0:
        raw = raw - (1 << 24)
    # pressure in hPa
    return raw / 4096.0


def get_heading():
    x = compass_raw(compass_xaxis)
    y = compass_raw(compass_yaxis)
    z = compass_raw(compass_zaxis)

    heading = math.atan2(y, x) + declination

    if heading > 2*math.pi:
        heading = heading - 2*math.pi
    if heading < 0:
        heading = heading + 2*math.pi
    return int(heading * 180/math.pi)


print("logging to sensorLog.csv")
print("press ctrl+c to stop execution")

agps_thread = AGPS3mechanism()
agps_thread.stream_data()
agps_thread.run_thread()

while True:
    log = open("sensorLog.csv", 'a', newline='')
    writer = csv.writer(log)
    humidity, temp = dht.read_retry(dht_sensor, dht_pin)
    data = [
        str(datetime.now()),
        agps_thread.data_stream.lat,
        agps_thread.data_stream.lon,
        get_heading(),
        pressure(),
        humidity,
        temp
        ]
    writer.writerow(data)
    log.close()
    if datetime.now().second % 10 == 0:
        camera.jpg()
    time.sleep(LOG_FREQUENCY)
