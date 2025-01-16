import uasyncio as asyncio
from machine import UART, Pin
import bluetooth
from ble_uart import BLEUART
import gc
from micropython import const
import time

# Constants defined using micropython.const for memory optimization
UART_GPS_ID = const(1)
UART_BAUDRATE = const(115200)
UART_READ_SIZE = const(256)
MAX_BUFFER_SIZE = const(1024)
RETRY_DELAY_MS = const(1000)
GPS_SLEEP_MS = const(30)
LED_BLINK_MS = const(100)

class GPSReceiver:
    def __init__(self):
        # Device configuration
        self.ble = bluetooth.BLE()
        self.uart_ble = BLEUART(self.ble, name="GNSS-Receiver")
        self.uart_gps = UART(
            UART_GPS_ID,
            baudrate=UART_BAUDRATE,
            tx=0,
            rx=1,
            timeout=10,
            rxbuf=MAX_BUFFER_SIZE
        )
        
        # LED initialization with properties
        self._led_data = Pin(13, Pin.OUT)
        self._led_error = Pin(12, Pin.OUT)
        self._last_error_time = 0
        self._error_count = 0
        
        # Buffer initialization
        self._gps_buffer = bytearray()
        
    async def blink_led(self, led, duration_ms):
        led.on()
        await asyncio.sleep_ms(duration_ms)
        led.off()
    
    def log_error(self, message, critical=False):
        """Enhanced error logging with rate limiting and error counting"""
        current_time = time.time()
        self._error_count += 1
        
        # Only log errors once per second to prevent spam
        if current_time - self._last_error_time >= 1:
            print(f"ERROR ({self._error_count}): {message}")
            self._last_error_time = current_time
            self._error_count = 0
            
        if critical:
            asyncio.create_task(self.blink_led(self._led_error, LED_BLINK_MS))

    async def send_gps_data(self, data):
        """Asynchronous GPS data sending with retry mechanism"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                self.uart_ble.write(data)
                await self.blink_led(self._led_data, LED_BLINK_MS)
                return True
            except Exception as e:
                retry_count += 1
                self.log_error(f"BLE send error (attempt {retry_count}): {str(e)}")
                if retry_count < max_retries:
                    await asyncio.sleep_ms(RETRY_DELAY_MS)
        
        return False

    def process_gps_sentence(self, sentence):
        """Validate and process GPS sentence"""
        try:
            if not sentence.startswith(b'$'):
                return None
                
            # Basic NMEA checksum validation
            if b'*' in sentence:
                data, checksum = sentence.split(b'*')
                calculated_checksum = 0
                for byte in data[1:]:  # Skip the $
                    calculated_checksum ^= byte
                if format(calculated_checksum, '02X').encode() != checksum:
                    return None
            
            return sentence + b'\r\n'
            
        except Exception as e:
            self.log_error(f"GPS sentence processing error: {str(e)}")
            return None

    async def forward_gps_data(self):
        """Main GPS data forwarding loop with improved error handling"""
        while True:
            try:
                if self.uart_gps.any():
                    gps_data = self.uart_gps.read(UART_READ_SIZE)
                    if gps_data:
                        self._gps_buffer.extend(gps_data)
                        
                        # Buffer overflow protection
                        if len(self._gps_buffer) > MAX_BUFFER_SIZE:
                            self._gps_buffer = self._gps_buffer[-MAX_BUFFER_SIZE:]
                            self.log_error("Buffer overflow occurred")
                        
                        # Process complete sentences
                        while b'\r\n' in self._gps_buffer:
                            sentence, self._gps_buffer = self._gps_buffer.split(b'\r\n', 1)
                            processed_sentence = self.process_gps_sentence(sentence)
                            if processed_sentence:
                                await self.send_gps_data(processed_sentence)
                
                await asyncio.sleep_ms(GPS_SLEEP_MS)
                
            except OSError as e:
                self.log_error(f"UART read error: {str(e)}", critical=True)
                await self.reinitialize_uart()
            except Exception as e:
                self.log_error(f"Unexpected error: {str(e)}", critical=True)
                await asyncio.sleep_ms(RETRY_DELAY_MS)
    
    async def reinitialize_uart(self):
        """Handle UART reinitialization with retry mechanism"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                self.uart_gps.init(baudrate=UART_BAUDRATE, tx=0, rx=1, timeout=10)
                return True
            except Exception as e:
                retry_count += 1
                self.log_error(f"UART reinit failed (attempt {retry_count}): {str(e)}", critical=True)
                if retry_count < max_retries:
                    await asyncio.sleep_ms(RETRY_DELAY_MS)
        
        return False

async def main():
    gc.enable()
    receiver = GPSReceiver()
    await receiver.forward_gps_data()

def run():
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Fatal error: {str(e)}")
    finally:
        gc.collect()

if __name__ == "__main__":
    run()
