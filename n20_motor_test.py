# ============================================================
#  Waveshare N20 DC Gear Motor + Magnetic Hall Encoder
#  Raspberry Pi — Python Starter Code
#  Requires: pip install pigpio RPi.GPIO
#  Start pigpio daemon first: sudo pigpiod
# ============================================================

import pigpio
import time
import threading

# --- Pin Definitions (BCM numbering) ---
MOTOR_IN1 = 17   # PWM forward
MOTOR_IN2 = 27   # PWM reverse
ENC_A     = 23   # Encoder Channel A
ENC_B     = 24   # Encoder Channel B

# --- Motor & Encoder Specs (adjust to YOUR variant) ---
PPR        = 11          # Pulses Per Revolution (motor shaft)
GEAR_RATIO = 50          # Your gearbox ratio (e.g. 30, 50, 100, 150, 298)
CPR        = PPR * GEAR_RATIO * 4   # Counts Per output shaft Revolution
                                    # x4 = quadrature decoding

PWM_FREQ   = 1000        # Hz


# ============================================================
#  ENCODER CLASS
# ============================================================
class Encoder:
    def __init__(self, pi, pin_a, pin_b):
        self.pi       = pi
        self.pin_a    = pin_a
        self.pin_b    = pin_b
        self._count   = 0
        self._lock    = threading.Lock()
        self._last_a  = 0

        pi.set_mode(pin_a, pigpio.INPUT)
        pi.set_mode(pin_b, pigpio.INPUT)
        pi.set_pull_up_down(pin_a, pigpio.PUD_UP)
        pi.set_pull_up_down(pin_b, pigpio.PUD_UP)

        # Attach callbacks on BOTH edges of BOTH channels
        self._cb_a = pi.callback(pin_a, pigpio.EITHER_EDGE, self._isr)
        self._cb_b = pi.callback(pin_b, pigpio.EITHER_EDGE, self._isr)

    def _isr(self, gpio, level, tick):
        a = self.pi.read(self.pin_a)
        b = self.pi.read(self.pin_b)

        with self._lock:
            if gpio == self.pin_a:
                if level == 1:
                    self._count += 1 if b == 0 else -1
                else:
                    self._count += 1 if b == 1 else -1
            else:  # gpio == pin_b
                if level == 1:
                    self._count += 1 if a == 1 else -1
                else:
                    self._count += 1 if a == 0 else -1

    @property
    def count(self):
        with self._lock:
            return self._count

    def reset(self):
        with self._lock:
            self._count = 0

    def to_degrees(self):
        return (self.count / CPR) * 360.0

    def to_revolutions(self):
        return self.count / CPR

    def cancel(self):
        self._cb_a.cancel()
        self._cb_b.cancel()


# ============================================================
#  MOTOR CLASS
# ============================================================
class Motor:
    def __init__(self, pi, pin_in1, pin_in2, pwm_freq=PWM_FREQ):
        self.pi   = pi
        self.in1  = pin_in1
        self.in2  = pin_in2

        pi.set_mode(pin_in1, pigpio.OUTPUT)
        pi.set_mode(pin_in2, pigpio.OUTPUT)
        pi.set_PWM_frequency(pin_in1, pwm_freq)
        pi.set_PWM_frequency(pin_in2, pwm_freq)
        self.coast()

    def _duty(self, speed_pct):
        """Convert 0–100% → pigpio 0–255"""
        return int(max(0, min(100, speed_pct)) * 2.55)

    def forward(self, speed_pct=50):
        """Drive forward at speed 0–100%"""
        self.pi.set_PWM_dutycycle(self.in1, self._duty(speed_pct))
        self.pi.set_PWM_dutycycle(self.in2, 0)

    def backward(self, speed_pct=50):
        """Drive backward at speed 0–100%"""
        self.pi.set_PWM_dutycycle(self.in1, 0)
        self.pi.set_PWM_dutycycle(self.in2, self._duty(speed_pct))

    def brake(self):
        """Active stop"""
        self.pi.set_PWM_dutycycle(self.in1, 255)
        self.pi.set_PWM_dutycycle(self.in2, 255)

    def coast(self):
        """Passive stop (free spin)"""
        self.pi.set_PWM_dutycycle(self.in1, 0)
        self.pi.set_PWM_dutycycle(self.in2, 0)


# ============================================================
#  RPM HELPER
# ============================================================
def measure_rpm(encoder, sample_seconds=0.1):
    """Measure RPM over a short sample window."""
    encoder.reset()
    time.sleep(sample_seconds)
    counts = encoder.count
    revs_per_sec = counts / CPR / sample_seconds
    return revs_per_sec * 60.0


# ============================================================
#  MAIN — Demo
# ============================================================
def main():
    pi = pigpio.pi()
    if not pi.connected:
        raise RuntimeError("pigpio daemon not running! Run: sudo pigpiod")

    motor   = Motor(pi, MOTOR_IN1, MOTOR_IN2)
    encoder = Encoder(pi, ENC_A, ENC_B)

    print(f"CPR (counts/output rev): {CPR}")

    try:
        # --- Demo 1: Forward for 2 seconds ---
        print("\n>> Forward at 50% speed")
        encoder.reset()
        motor.forward(50)
        start = time.time()
        while time.time() - start < 2.0:
            print(f"  Counts: {encoder.count:6d} | "
                  f"Degrees: {encoder.to_degrees():7.1f}° | "
                  f"Revs: {encoder.to_revolutions():.3f}")
            time.sleep(0.1)

        motor.brake()
        time.sleep(0.5)

        # --- Demo 2: Backward for 2 seconds ---
        print("\n>> Backward at 50% speed")
        encoder.reset()
        motor.backward(50)
        start = time.time()
        while time.time() - start < 2.0:
            print(f"  Counts: {encoder.count:6d} | "
                  f"Degrees: {encoder.to_degrees():7.1f}°")
            time.sleep(0.1)

        motor.coast()

        # --- Demo 3: RPM measurement ---
        print("\n>> RPM Measurement at 75% speed")
        motor.forward(75)
        time.sleep(0.5)   # Let motor spin up
        rpm = measure_rpm(encoder, sample_seconds=0.5)
        print(f"  Measured RPM: {rpm:.1f}")
        motor.coast()

    except KeyboardInterrupt:
        print("\nStopped by user.")

    finally:
        motor.coast()
        encoder.cancel()
        pi.stop()
        print("Cleanup done.")


if __name__ == "__main__":
    main()