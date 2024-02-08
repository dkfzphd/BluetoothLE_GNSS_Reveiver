import uasyncio as asyncio
from machine import UART,reset,Pin
import bluetooth
from ble_uart import BLEUART

# Initialize BLE
ble = bluetooth.BLE()
uart_ble = BLEUART(ble, name="GNSS-Receiver")

# Initialize GPS UART
uart_gps = UART(1, baudrate=115200, tx=0, rx=1, timeout=10)  # Modify these settings based on your hardware 

# Initialize LED
led13 = Pin(13, Pin.OUT)
led12 = Pin(12, Pin.OUT)
# Send GPS data to BLE device
def send_gps_data(data):
    try:
        uart_ble.write(data)
    except Exception as e:
        print("Error sending GPS data:", str(e))

# Define an async function to read and forward GPS data
async def forward_gps_data():
    gps_buffer = b''  # Initialize an empty buffer to accumulate GPS data
    while True:
        try:
            gps_data = uart_gps.read(256)
            led13.off()
            if gps_data:
                gps_buffer += gps_data
                decoded_data = gps_buffer.decode('utf-8')
                sentences = decoded_data.split('\r\n')
                for sentence in sentences[:-1]:
                    if sentence.startswith('$'):
                        print(sentence)
                        send_gps_data(sentence.encode('utf-8') + b'\r\n')  # Send complete NMEA sentence
                        led13.on()
                gps_buffer = sentences[-1].encode('utf-8')
                
            await asyncio.sleep(0.1)  # Send data once per second

        except Exception as e:
            print("Exception occurred:", str(e))
            reset()

# Create an event loop and run the GPS data forwarding task
loop = asyncio.get_event_loop()
loop.create_task(forward_gps_data())
loop.run_forever()


