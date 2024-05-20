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

# Send GPS data to BLE device
def send_gps_data(data):
    try:
        uart_ble.write(data)
    except Exception as e:
        print("Error sending GPS data:", str(e))
        led_error.on()

# Define an async function to read and forward GPS data
async def forward_gps_data():
    gps_buffer = b''  # Initialize an empty buffer to accumulate GPS data
    while True:
        try:
            gps_data = uart_gps.read(256)
            if gps_data:
                gps_buffer += gps_data
                while b'\r\n' in gps_buffer:
                    sentence, gps_buffer = gps_buffer.split(b'\r\n', 1)
                    if sentence.startswith(b'$'):
                        print(sentence.decode('utf-8'))
                        led_data.on()
                        send_gps_data(sentence + b'\r\n')  # Send complete NMEA sentence
                        led_data.off()

            await asyncio.sleep(0.1)  # Send data once per 0.1 second

        except OSError as e:
            print("UART read error:", str(e))
            led_error.on()
            await asyncio.sleep(1)
            reset()
        except Exception as e:
            print("Exception occurred:", str(e))
            led_error.on()
            await asyncio.sleep(1)
            reset()

# Create an event loop and run the GPS data forwarding task
loop = asyncio.get_event_loop()
loop.create_task(forward_gps_data())
loop.run_forever()

