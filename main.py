import uasyncio as asyncio
from machine import UART, Pin
import bluetooth
from ble_uart import BLEUART
import gc

# Constants
UART_GPS_ID = 1
UART_BAUDRATE = 115200
UART_READ_SIZE = 256
MAX_BUFFER_SIZE = 1024
BLE_DEVICE_NAME = "GNSS-Receiver"

# Initialize BLE
ble = bluetooth.BLE()
uart_ble = BLEUART(ble, name=BLE_DEVICE_NAME)

# Initialize GPS UART
uart_gps = UART(UART_GPS_ID, baudrate=UART_BAUDRATE, tx=0, rx=1, timeout=10)

# Initialize LEDs
led_data = Pin(13, Pin.OUT)
led_error = Pin(12, Pin.OUT)

# Log error messages
def log_error(message):
    # You can modify this function to log messages to a file or external storage
    print("ERROR:", message)
    led_error.on()

# Send GPS data to BLE device
def send_gps_data(data):
    try:
        uart_ble.write(data)
    except Exception as e:
        log_error("Error sending GPS data: " + str(e))

# Forward GPS data asynchronously
async def forward_gps_data():
    gps_buffer = bytearray()

    while True:
        try:
            gps_data = uart_gps.read(UART_READ_SIZE)
            if gps_data:
                gps_buffer.extend(gps_data)

                if len(gps_buffer) > MAX_BUFFER_SIZE:
                    log_error("GPS buffer overflow, trimming buffer")
                    gps_buffer = gps_buffer[-MAX_BUFFER_SIZE:]

                while b'\r\n' in gps_buffer:
                    sentence, gps_buffer = gps_buffer.split(b'\r\n', 1)
                    if sentence.startswith(b'$') and not sentence.endswith(b'*'):
                        print(sentence.decode('utf-8'))
                        led_data.on()
                        send_gps_data(sentence + b'\r\n')
                        led_data.off()

            await asyncio.sleep(0.1)

        except OSError as e:
            log_error("UART read error: " + str(e))
            await asyncio.sleep(1)
            try:
                uart_gps.init(baudrate=UART_BAUDRATE, tx=0, rx=1, timeout=10)
            except Exception as e:
                log_error("UART reinitialization failed: " + str(e))
        except Exception as e:
            log_error("Exception occurred: " + str(e))
            await asyncio.sleep(1)

# Main function
def main():
    loop = asyncio.get_event_loop()
    loop.create_task(forward_gps_data())
    loop.run_forever()

# Run main function with garbage collection
try:
    main()
except Exception as e:
    log_error("Exception occurred in main: " + str(e))
finally:
    gc.collect()

