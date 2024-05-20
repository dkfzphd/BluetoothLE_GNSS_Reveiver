import uasyncio as asyncio
from machine import UART, reset, Pin
import bluetooth
from ble_uart import BLEUART

# Initialize BLE
ble = bluetooth.BLE()
uart_ble = BLEUART(ble, name="GNSS-Receiver")

# Initialize GPS UART
uart_gps = UART(1, baudrate=115200, tx=0, rx=1, timeout=10)  # Modify these settings based on your hardware 

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

# Define an async function to read and forward GPS data
async def forward_gps_data():
    gps_buffer = bytearray()  # Initialize an empty buffer to accumulate GPS data
    MAX_BUFFER_SIZE = 1024  # Adjust this value based on your memory constraints

    while True:
        try:
            gps_data = uart_gps.read(256)  # Adjust read size if needed
            if gps_data:
                gps_buffer.extend(gps_data)

                # Ensure buffer doesn't grow indefinitely
                if len(gps_buffer) > MAX_BUFFER_SIZE:
                    log_error("GPS buffer overflow, trimming buffer")
                    gps_buffer = gps_buffer[-MAX_BUFFER_SIZE:]

                while b'\r\n' in gps_buffer:
                    sentence, gps_buffer = gps_buffer.split(b'\r\n', 1)
                    if sentence.startswith(b'$'):
                        # Check if the sentence is complete
                        if sentence.endswith(b'*'):
                            continue  # Ignore incomplete sentences
                        print(sentence.decode('utf-8'))
                        led_data.on()
                        send_gps_data(sentence + b'\r\n')  # Send complete NMEA sentence
                        led_data.off()

            await asyncio.sleep(0.1)  # Send data once per 0.1 second

        except OSError as e:
            log_error("UART read error: " + str(e))
            await asyncio.sleep(1)
            try:
                # Try to reinitialize UART instead of resetting
                uart_gps.init(baudrate=115200, tx=0, rx=1, timeout=10)
            except Exception as e:
                log_error("UART reinitialization failed: " + str(e))
        except Exception as e:
            log_error("Exception occurred: " + str(e))
            await asyncio.sleep(1)

# Create an event loop and run the GPS data forwarding task
loop = asyncio.get_event_loop()
loop.create_task(forward_gps_data())
loop.run_forever()

