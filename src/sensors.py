import time
import math
from typing import Tuple, Optional
import threading
from dataclasses import dataclass
import json
import os

# Try to import hardware libraries, fall back to mock if not available
try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False
    print("GPIO not available - using mock mode")

try:
    import board
    import busio
    import adafruit_bmp280  # BMP280 Barometer
    import adafruit_adxl34x  # ADXL343 Accelerometer
    HAS_I2C = True
except ImportError:
    HAS_I2C = False
    print("I2C sensors not available - using mock mode")


@dataclass
class SensorReading:
    """Container for sensor readings with timestamp"""
    value: float
    timestamp: float
    unit: str


class StatisticsTracker:
    """Tracks maximum values and total distance for the soapbox"""
    
    def __init__(self, data_file: str = "data/statistics.json"):
        self.data_file = data_file
        self.lock = threading.Lock()
        
        # Statistics data
        self.max_speed_kmh = 0.0
        self.total_distance_km = 0.0
        self.max_cornering_force_g = 0.0
        self.max_braking_force_g = 0.0
        self.session_start_time = time.time()
        self.last_position = None
        self.last_update_time = time.time()
        
        # Load existing data
        self._load_data()
    
    def _load_data(self):
        """Load statistics from file"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.max_speed_kmh = data.get('max_speed_kmh', 0.0)
                    self.total_distance_km = data.get('total_distance_km', 0.0)
                    self.max_cornering_force_g = data.get('max_cornering_force_g', 0.0)
                    self.max_braking_force_g = data.get('max_braking_force_g', 0.0)
        except Exception as e:
            print(f"Failed to load statistics: {e}")
    
    def _save_data(self):
        """Save statistics to file"""
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            data = {
                'max_speed_kmh': self.max_speed_kmh,
                'total_distance_km': self.total_distance_km,
                'max_cornering_force_g': self.max_cornering_force_g,
                'max_braking_force_g': self.max_braking_force_g,
                'last_updated': time.time()
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Failed to save statistics: {e}")
    
    def update_speed(self, speed_kmh: float):
        """Update speed statistics"""
        with self.lock:
            if speed_kmh > self.max_speed_kmh:
                self.max_speed_kmh = speed_kmh
                self._save_data()
    
    def update_distance(self, current_speed_kmh: float):
        """Update total distance based on current speed"""
        with self.lock:
            current_time = time.time()
            time_diff = current_time - self.last_update_time
            
            if time_diff > 0 and current_speed_kmh > 0:
                # Distance = speed * time
                distance_km = (current_speed_kmh * time_diff) / 3600.0  # Convert hours to seconds
                self.total_distance_km += distance_km
                self._save_data()
            
            self.last_update_time = current_time
    
    def update_acceleration(self, ax_g: float, ay_g: float, az_g: float):
        """Update acceleration statistics"""
        with self.lock:
            # Calculate lateral (cornering) force (magnitude of x and y components)
            lateral_force = math.sqrt(ax_g**2 + ay_g**2)
            if lateral_force > self.max_cornering_force_g:
                self.max_cornering_force_g = lateral_force
                self._save_data()
            
            # Calculate braking force (negative Z acceleration)
            braking_force = abs(min(0, az_g - 1.0))  # Subtract 1g for gravity
            if braking_force > self.max_braking_force_g:
                self.max_braking_force_g = braking_force
                self._save_data()
    
    def get_statistics(self) -> dict:
        """Get current statistics"""
        with self.lock:
            return {
                'max_speed_kmh': self.max_speed_kmh,
                'total_distance_km': self.total_distance_km,
                'max_cornering_force_g': self.max_cornering_force_g,
                'max_braking_force_g': self.max_braking_force_g,
                'session_duration_hours': (time.time() - self.session_start_time) / 3600.0
            }
    
    def reset_statistics(self):
        """Reset all statistics to zero"""
        with self.lock:
            self.max_speed_kmh = 0.0
            self.total_distance_km = 0.0
            self.max_cornering_force_g = 0.0
            self.max_braking_force_g = 0.0
            self.session_start_time = time.time()
            self.last_update_time = time.time()
            self._save_data()


class HallSensor:
    """Hall effect sensor for speed measurement via wheel rotation"""
    
    def __init__(self, gpio_pin: int = 18, wheel_circumference_m: float = 1.0):
        self.gpio_pin = gpio_pin
        self.wheel_circumference_m = wheel_circumference_m
        self.last_pulse_time = 0
        self.pulse_count = 0
        self.speed_kmh = 0.0
        self.lock = threading.Lock()
        
        if HAS_GPIO:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(self.gpio_pin, GPIO.RISING, callback=self._pulse_callback)
        else:
            # Mock mode - simulate pulses
            self._mock_thread = threading.Thread(target=self._mock_pulses, daemon=True)
            self._mock_thread.start()
    
    def _pulse_callback(self, channel):
        """Called when hall sensor detects magnet"""
        with self.lock:
            current_time = time.time()
            if self.last_pulse_time > 0:
                # Calculate speed from time between pulses
                time_diff = current_time - self.last_pulse_time
                if time_diff > 0:
                    # Speed = distance / time
                    speed_ms = self.wheel_circumference_m / time_diff
                    self.speed_kmh = speed_ms * 3.6  # Convert m/s to km/h
            
            self.last_pulse_time = current_time
            self.pulse_count += 1
    
    def _mock_pulses(self):
        """Simulate hall sensor pulses for testing"""
        while True:
            time.sleep(0.1)  # Simulate wheel rotation
            self._pulse_callback(None)
    
    def get_speed_kmh(self) -> float:
        """Get current speed in km/h"""
        with self.lock:
            return self.speed_kmh
    
    def get_pulse_count(self) -> int:
        """Get total pulse count"""
        with self.lock:
            return self.pulse_count


class Barometer:
    """BMP280 barometric pressure sensor for altitude"""
    
    def __init__(self, sea_level_pressure: float = 1013.25):
        self.sea_level_pressure = sea_level_pressure  # hPa
        self.sensor = None
        self.last_reading = SensorReading(0.0, 0.0, "m")
        
        if HAS_I2C:
            try:
                i2c = busio.I2C(board.SCL, board.SDA)
                self.sensor = adafruit_bmp280.Adafruit_BMP280_I2C(i2c)
                self.sensor.sea_level_pressure = self.sea_level_pressure
            except Exception as e:
                print(f"Failed to initialize BMP280: {e}")
                self.sensor = None
    
    def get_altitude_m(self) -> float:
        """Get altitude in meters"""
        if self.sensor:
            try:
                altitude = self.sensor.altitude
                self.last_reading = SensorReading(altitude, time.time(), "m")
                return altitude
            except Exception as e:
                print(f"BMP280 read error: {e}")
                return self.last_reading.value
        
        # Mock mode - simulate altitude changes
        base_altitude = 120.0
        variation = math.sin(time.time() * 0.1) * 5.0
        return base_altitude + variation


class Thermometer:
    """Temperature sensor (can use BMP280 or separate sensor)"""
    
    def __init__(self):
        self.sensor = None
        self.last_reading = SensorReading(25.0, 0.0, "°C")
        
        if HAS_I2C:
            try:
                i2c = busio.I2C(board.SCL, board.SDA)
                self.sensor = adafruit_bmp280.Adafruit_BMP280_I2C(i2c)
            except Exception as e:
                print(f"Failed to initialize temperature sensor: {e}")
                self.sensor = None
    
    def get_temperature_c(self) -> float:
        """Get temperature in Celsius"""
        if self.sensor:
            try:
                temp = self.sensor.temperature
                self.last_reading = SensorReading(temp, time.time(), "°C")
                return temp
            except Exception as e:
                print(f"Temperature read error: {e}")
                return self.last_reading.value
        
        # Mock mode - simulate temperature
        base_temp = 25.0
        variation = math.sin(time.time() * 0.05) * 2.0
        return base_temp + variation


class Accelerometer:
    """ADXL343 accelerometer"""
    
    def __init__(self):
        self.sensor = None
        self.last_reading = SensorReading(0.0, 0.0, "g")
        
        if HAS_I2C:
            try:
                i2c = busio.I2C(board.SCL, board.SDA)
                self.sensor = adafruit_adxl34x.ADXL343(i2c)
                # Set range to ±16g for soapbox racing
                self.sensor.range = adafruit_adxl34x.Range.RANGE_16_G
            except Exception as e:
                print(f"Failed to initialize ADXL343: {e}")
                self.sensor = None
    
    def get_acceleration_g(self) -> Tuple[float, float, float]:
        """Get acceleration in g (x, y, z)"""
        if self.sensor:
            try:
                accel = self.sensor.acceleration
                # ADXL343 returns values in m/s², convert to g
                x_g = accel[0] / 9.81
                y_g = accel[1] / 9.81
                z_g = accel[2] / 9.81
                return (x_g, y_g, z_g)
            except Exception as e:
                print(f"ADXL343 read error: {e}")
                return (0.0, 0.0, 1.0)  # Default to 1g downward
        
        # Mock mode - simulate small accelerations
        t = time.time()
        x = 0.1 * math.sin(t * 0.5)
        y = 0.05 * math.cos(t * 0.3)
        z = 1.0 + 0.02 * math.sin(t * 0.2)
        return (x, y, z)


class SensorManager:
    """Manages all sensors and provides unified interface"""
    
    def __init__(self, hall_pin: int = 18, wheel_circumference_m: float = 1.0):
        self.hall_sensor = HallSensor(hall_pin, wheel_circumference_m)
        self.barometer = Barometer()
        self.thermometer = Thermometer()
        self.accelerometer = Accelerometer()
        self.statistics = StatisticsTracker()
        
        # Calibration data
        self.speed_offset = 0.0
        self.altitude_offset = 0.0
        self.temp_offset = 0.0
        
        # Sensor health tracking
        self.sensor_errors = {
            'hall': False,
            'barometer': False,
            'thermometer': False,
            'accelerometer': False
        }
        self.last_successful_reads = {
            'hall': time.time(),
            'barometer': time.time(),
            'thermometer': time.time(),
            'accelerometer': time.time()
        }
        self.error_timeout = 5.0  # seconds before marking sensor as failed
    
    def get_speed_kmh(self) -> float:
        """Get speed in km/h"""
        try:
            speed = max(0.0, self.hall_sensor.get_speed_kmh() + self.speed_offset)
            self.last_successful_reads['hall'] = time.time()
            self.sensor_errors['hall'] = False
            
            # Update statistics
            self.statistics.update_speed(speed)
            self.statistics.update_distance(speed)
            
            return speed
        except Exception as e:
            print(f"Hall sensor error: {e}")
            self.sensor_errors['hall'] = True
            return 0.0
    
    def get_altitude_m(self) -> float:
        """Get altitude in meters"""
        try:
            altitude = self.barometer.get_altitude_m() + self.altitude_offset
            self.last_successful_reads['barometer'] = time.time()
            self.sensor_errors['barometer'] = False
            return altitude
        except Exception as e:
            print(f"Barometer error: {e}")
            self.sensor_errors['barometer'] = True
            return 0.0
    
    def get_temperature_c(self) -> float:
        """Get temperature in Celsius"""
        try:
            temp = self.thermometer.get_temperature_c() + self.temp_offset
            self.last_successful_reads['thermometer'] = time.time()
            self.sensor_errors['thermometer'] = False
            return temp
        except Exception as e:
            print(f"Thermometer error: {e}")
            self.sensor_errors['thermometer'] = True
            return 25.0
    
    def get_acceleration_g(self) -> Tuple[float, float, float]:
        """Get acceleration in g (x, y, z)"""
        try:
            accel = self.accelerometer.get_acceleration_g()
            self.last_successful_reads['accelerometer'] = time.time()
            self.sensor_errors['accelerometer'] = False
            
            # Update statistics
            self.statistics.update_acceleration(accel[0], accel[1], accel[2])
            
            return accel
        except Exception as e:
            print(f"Accelerometer error: {e}")
            self.sensor_errors['accelerometer'] = True
            return (0.0, 0.0, 1.0)
    
    def get_sensor_status(self) -> dict:
        """Get status of all sensors"""
        current_time = time.time()
        status = {}
        
        for sensor_name in self.sensor_errors:
            time_since_last = current_time - self.last_successful_reads[sensor_name]
            is_healthy = not self.sensor_errors[sensor_name] and time_since_last < self.error_timeout
            status[sensor_name] = {
                'healthy': is_healthy,
                'error': self.sensor_errors[sensor_name],
                'time_since_last_read': time_since_last
            }
        
        return status
    
    def get_data_source(self) -> str:
        """Return whether we're using real or mock data"""
        if HAS_GPIO and HAS_I2C:
            return "Real Sensors"
        else:
            return "Demo Mode"
    
    def get_statistics(self) -> dict:
        """Get current statistics"""
        return self.statistics.get_statistics()
    
    def reset_statistics(self):
        """Reset all statistics"""
        self.statistics.reset_statistics()
    
    def calibrate_speed(self, known_speed_kmh: float):
        """Calibrate speed sensor with known speed"""
        current_speed = self.hall_sensor.get_speed_kmh()
        self.speed_offset = known_speed_kmh - current_speed
    
    def calibrate_altitude(self, known_altitude_m: float):
        """Calibrate altitude sensor with known altitude"""
        current_altitude = self.barometer.get_altitude_m()
        self.altitude_offset = known_altitude_m - current_altitude
    
    def calibrate_temperature(self, known_temp_c: float):
        """Calibrate temperature sensor with known temperature"""
        current_temp = self.thermometer.get_temperature_c()
        self.temp_offset = known_temp_c - current_temp
    
    def cleanup(self):
        """Clean up GPIO resources"""
        if HAS_GPIO:
            GPIO.cleanup()


# Global sensor manager instance
sensor_manager: Optional[SensorManager] = None


def initialize_sensors(hall_pin: int = 18, wheel_circumference_m: float = 1.0) -> SensorManager:
    """Initialize and return sensor manager"""
    global sensor_manager
    sensor_manager = SensorManager(hall_pin, wheel_circumference_m)
    return sensor_manager


def get_sensor_manager() -> Optional[SensorManager]:
    """Get the global sensor manager instance"""
    return sensor_manager
