# ============================================================
#  Waveshare N20 DC Gear Motor + Magnetic Hall Encoder
#  MicroPython — ESP32 / Raspberry Pi Pico Starter Code
# ============================================================

from machine import Pin, PWM
import time

# --- Pin Definitions ---
MOTOR_IN1_PIN = 16   # PWM forward
MOTOR_IN2_PIN = 17   # PWM reverse
ENC_A_PIN     = 18   # Encoder Channel A
ENC_B_PIN     = 19   # Encoder Channel B

# --- Motor & Encoder Specs (adjust to YOUR variant) ---
PPR        = 11                    # Pulses Per Revolution (motor shaft)
GEAR_RATIO = 50                    # Your gearbox ratio
CPR        = PPR * GEAR_RATIO * 4  # Counts Per output shaft Revolution

PWM_FREQ   = 1000                  # Hz
PWM_MAX    = 65535                 # MicroPython PWM range (16-bit)


# ============================================================
#  ENCODER CLASS
# ============================================================
class Encoder:
    def __init__(self, pin_a, pin_b):
        self._count  = 0
        self._pin_a  = Pin(pin_a, Pin.IN, Pin.PULL_UP)
        self._pin_b  = Pin(pin_b, Pin.IN, Pin.PULL_UP)

        # Attach IRQ on BOTH edges of BOTH channels
        self._pin_a.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING,
                        handler=self._isr_a)
        self._pin_b.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING,
                        handler=self._isr_b)

    def _isr_a(self, pin):
        a = self._pin_a.value()
        b = self._pin_b.value()
        if a == 1:
            self._count += 1 if b == 0 else -1
        else:
            self._count += 1 if b == 1 else -1

    def _isr_b(self, pin):
        a = self._pin_a.value()
        b = self._pin_b.value()
        if b == 1:
            self._count += 1 if a == 1 else -1
        else:
            self._count += 1 if a == 0 else -1

    @property
    def count(self):
        return self._count

    def reset(self):
        self._count = 0

    def to_degrees(self):
        return (self._count / CPR) * 360.0

    def to_revolutions(self):
        return self._count / CPR


# ============================================================
#  MOTOR CLASS
# ============================================================
class Motor:
    def __init__(self, pin_in1, pin_in2, freq=PWM_FREQ):
        self._in1 = PWM(Pin(pin_in1), freq=freq, duty_u16=0)
        self._in2 = PWM(Pin(pin_in2), freq=freq, duty_u16=0)

    def _duty(self, speed_pct):
        """Convert 0–100% → 0–65535"""
        return int(max(0.0, min(100.0, speed_pct)) / 100.0 * PWM_MAX)

    def forward(self, speed_pct=50):
        self._in1.duty_u16(self._duty(speed_pct))
        self._in2.duty_u16(0)

    def backward(self, speed_pct=50):
        self._in1.duty_u16(0)
        self._in2.duty_u16(self._duty(speed_pct))

    def brake(self):
        self._in1.duty_u16(PWM_MAX)
        self._in2.duty_u16(PWM_MAX)

    def coast(self):
        self._in1.duty_u16(0)
        self._in2.duty_u16(0)


# ============================================================
#  RPM HELPER
# ============================================================
def measure_rpm(encoder, sample_ms=200):
    """Measure RPM over a short sample window."""
    encoder.reset()
    time.sleep_ms(sample_ms)
    counts = encoder.count
    revs_per_sec = counts / CPR / (sample_ms / 1000.0)
    return revs_per_sec * 60.0


# ============================================================
#  MAIN — Demo
# ============================================================
def main():
    motor   = Motor(MOTOR_IN1_PIN, MOTOR_IN2_PIN)
    encoder = Encoder(ENC_A_PIN, ENC_B_PIN)

    print(f"CPR (counts/output rev): {CPR}")

    # --- Demo 1: Forward for 2 seconds ---
    print("\n>> Forward at 50% speed")
    encoder.reset()
    motor.forward(50)
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < 2000:
        print(f"  Counts: {encoder.count:6d} | "
              f"Degrees: {encoder.to_degrees():7.1f} | "
              f"Revs: {encoder.to_revolutions():.3f}")
        time.sleep_ms(100)

    motor.brake()
    time.sleep_ms(500)

    # --- Demo 2: Backward for 2 seconds ---
    print("\n>> Backward at 50% speed")
    encoder.reset()
    motor.backward(50)
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < 2000:
        print(f"  Counts: {encoder.count:6d} | "
              f"Degrees: {encoder.to_degrees():7.1f}")
        time.sleep_ms(100)

    motor.coast()

    # --- Demo 3: RPM measurement ---
    print("\n>> RPM Measurement at 75% speed")
    motor.forward(75)
    time.sleep_ms(500)   # Let motor spin up
    rpm = measure_rpm(encoder, sample_ms=500)
    print(f"  Measured RPM: {rpm:.1f}")
    motor.coast()
    print("\nDone!")


main()
