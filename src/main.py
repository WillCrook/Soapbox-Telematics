import math
import random
import time
from typing import Tuple
import sys
import os

from dashboard import run_dashboard
from sensors import initialize_sensors, get_sensor_manager


class DemoSensors:
    """Lightweight sensor simulators to preview the UI on a laptop.

    - Speed: oscillates between 0 and ~42 km/h with noise
    - Altitude: slow drift around 120 m
    - Temperature: indoor-ish ~22-28 C
    - Accel: small random g noise
    """

    def __init__(self):
        self._t0 = time.time()

    def _t(self) -> float:
        return time.time() - self._t0

    def speed_kmh(self) -> float:
        t = self._t()
        base = (math.sin(t * 0.35) + 1) * 21.0  # 0..42 km/h
        noise = random.uniform(-1.2, 1.2)
        return max(0.0, base + noise)

    def altitude_m(self) -> float:
        t = self._t()
        return 120.0 + math.sin(t * 0.05) * 3.0 + random.uniform(-0.5, 0.5)

    def temperature_c(self) -> float:
        t = self._t()
        return 25.0 + math.sin(t * 0.1) * 2.0 + random.uniform(-0.3, 0.3)

    def accel_g(self) -> Tuple[float, float, float]:
        return (
            random.uniform(-0.05, 0.05),
            random.uniform(-0.05, 0.05),
            1.0 + random.uniform(-0.05, 0.05),
        )


def main(fullscreen: bool = False, use_real_sensors: bool = False):
    """Main function to run the dashboard"""
    
    if use_real_sensors:
        print("Initializing real sensors...")
        try:
            # Initialize sensors with your specific configuration
            hall_pin = 24  # GPIO pin for hall sensor
            wheel_circumference = 0.1397  # Wheel circumference in meters 
            
            sensor_manager = initialize_sensors(hall_pin, wheel_circumference)
            
            # Use real sensor data
            run_dashboard(
                sensor_manager.get_speed_kmh,
                sensor_manager.get_altitude_m,
                sensor_manager.get_temperature_c,
                sensor_manager.get_acceleration_g,
                sensor_manager.get_sensor_status,
                sensor_manager.get_data_source,
                sensor_manager.get_statistics,
                sensor_manager.reset_statistics,
                fullscreen=fullscreen,
            )
        except Exception as e:
            print(f"Failed to initialize real sensors: {e}")
            print("Falling back to demo mode...")
            use_real_sensors = False
    
    if not use_real_sensors:
        print("Using demo sensors...")
        sensors = DemoSensors()
        
        # Mock sensor status functions for demo mode
        def mock_sensor_status():
            return {
                'hall': {'healthy': True, 'error': False, 'time_since_last_read': 0.1},
                'barometer': {'healthy': True, 'error': False, 'time_since_last_read': 0.1},
                'thermometer': {'healthy': True, 'error': False, 'time_since_last_read': 0.1},
                'accelerometer': {'healthy': True, 'error': False, 'time_since_last_read': 0.1}
            }
        
        def mock_data_source():
            return "Demo Mode"
        
        def mock_statistics():
            return {
                'max_speed_kmh': 0.0,
                'total_distance_km': 0.0,
                'max_cornering_force_g': 0.0,
                'max_braking_force_g': 0.0,
                'session_duration_hours': 0.0
            }
        
        def mock_reset():
            pass  # No-op for demo mode
        
        run_dashboard(
            sensors.speed_kmh,
            sensors.altitude_m,
            sensors.temperature_c,
            sensors.accel_g,
            mock_sensor_status,
            mock_data_source,
            mock_statistics,
            mock_reset,
            fullscreen=fullscreen,
        )


if __name__ == "__main__":
    # Check command line arguments
    use_real = "--real-sensors" in sys.argv
    fullscreen = "--fullscreen" in sys.argv
    
    print("The Dark Ride - Bat-Dashboard")
    print("Usage:")
    print("  python main.py                    # Demo mode, windowed")
    print("  python main.py --fullscreen       # Demo mode, fullscreen")
    print("  python main.py --real-sensors     # Real sensors, windowed")
    print("  python main.py --real-sensors --fullscreen  # Real sensors, fullscreen")
    print()
    
    main(fullscreen=fullscreen, use_real_sensors=use_real)


