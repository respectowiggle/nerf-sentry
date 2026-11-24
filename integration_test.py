import RPi.GPIO as GPIO
import time

# ─────────────────────────────────────────
#  PIN CONFIGURATION  (adjust to your wiring)
# ─────────────────────────────────────────

# L298N – Motor (Output 1 / IN1 & IN2 + ENA)
MOTOR_IN1 = 17
MOTOR_IN2 = 27
MOTOR_ENA = 22   # PWM pin for speed control

# L298N – Actuator (Output 2 / IN3 & IN4 + ENB)
ACT_IN3   = 23
ACT_IN4   = 24
ACT_ENB   = 25   # PWM pin for speed control

PWM_FREQ  = 1000  # Hz

# ─────────────────────────────────────────
#  GPIO SETUP
# ─────────────────────────────────────────

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

for pin in [MOTOR_IN1, MOTOR_IN2, MOTOR_ENA,
            ACT_IN3,   ACT_IN4,   ACT_ENB]:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

motor_pwm = GPIO.PWM(MOTOR_ENA, PWM_FREQ)
act_pwm   = GPIO.PWM(ACT_ENB,   PWM_FREQ)
motor_pwm.start(0)
act_pwm.start(0)

# ─────────────────────────────────────────
#  LOW-LEVEL HELPERS
# ─────────────────────────────────────────

def motor_set(direction: str, speed: int):
    """
    direction : 'forward' | 'backward' | 'stop'
    speed     : 0-100 (PWM duty cycle %)
    """
    speed = max(0, min(100, speed))
    if direction == 'forward':
        GPIO.output(MOTOR_IN1, GPIO.HIGH)
        GPIO.output(MOTOR_IN2, GPIO.LOW)
        motor_pwm.ChangeDutyCycle(speed)
    elif direction == 'backward':
        GPIO.output(MOTOR_IN1, GPIO.LOW)
        GPIO.output(MOTOR_IN2, GPIO.HIGH)
        motor_pwm.ChangeDutyCycle(speed)
    else:  # stop
        GPIO.output(MOTOR_IN1, GPIO.LOW)
        GPIO.output(MOTOR_IN2, GPIO.LOW)
        motor_pwm.ChangeDutyCycle(0)

def actuator_set(direction: str, speed: int):
    """
    direction : 'extend' | 'retract' | 'stop'
    speed     : 0-100 (PWM duty cycle %)
    """
    speed = max(0, min(100, speed))
    if direction == 'extend':
        GPIO.output(ACT_IN3, GPIO.HIGH)
        GPIO.output(ACT_IN4, GPIO.LOW)
        act_pwm.ChangeDutyCycle(speed)
    elif direction == 'retract':
        GPIO.output(ACT_IN3, GPIO.LOW)
        GPIO.output(ACT_IN4, GPIO.HIGH)
        act_pwm.ChangeDutyCycle(speed)
    else:  # stop
        GPIO.output(ACT_IN3, GPIO.LOW)
        GPIO.output(ACT_IN4, GPIO.LOW)
        act_pwm.ChangeDutyCycle(0)

# ─────────────────────────────────────────
#  NON-BLOCKING TIMED-ACTION ENGINE
# ─────────────────────────────────────────

class TimedAction:
    """
    Runs a sequence of (action_fn, duration_s) steps
    without blocking – call .update() every loop tick.
    """
    def __init__(self, name: str):
        self.name      = name
        self.sequence  = []   # list of (callable, duration)
        self.index     = 0
        self.start_ts  = None
        self.running   = False

    def run(self, sequence: list):
        """
        sequence: [(action_callable, duration_seconds), ...]
        Each action_callable is called once when the step starts.
        """
        self.sequence = sequence
        self.index    = 0
        self.running  = True
        self.start_ts = time.time()
        # Fire the first action immediately
        if self.sequence:
            fn, _ = self.sequence[0]
            fn()
            print(f"[{self.name}] step 0 started")

    def update(self):
        """Call this every main-loop iteration."""
        if not self.running or not self.sequence:
            return

        _, duration = self.sequence[self.index]
        if time.time() - self.start_ts >= duration:
            self.index += 1
            if self.index >= len(self.sequence):
                self.running  = False
                self.sequence = []
                print(f"[{self.name}] sequence complete")
            else:
                self.start_ts = time.time()
                fn, _ = self.sequence[self.index]
                fn()
                print(f"[{self.name}] step {self.index} started")

    def stop(self):
        self.running  = False
        self.sequence = []

# ─────────────────────────────────────────
#  INSTANTIATE CONTROLLERS
# ─────────────────────────────────────────

motor_ctrl   = TimedAction("Motor")
actuator_ctrl = TimedAction("Actuator")

# ─────────────────────────────────────────
#  EXAMPLE SEQUENCES  (edit freely)
# ─────────────────────────────────────────

# Motor: forward 2 s → backward 2 s → stop
motor_sequence = [
    (lambda: motor_set('forward',  75),  2.0),
    (lambda: motor_set('backward', 75),  2.0),
    (lambda: motor_set('stop',      0),  0.1),
]

# Actuator: extend 3 s → retract 3 s → stop
#   (starts 1 s after the motor, just to show independence)
actuator_sequence = [
    (lambda: actuator_set('extend',  60),  3.0),
    (lambda: actuator_set('retract', 60),  3.0),
    (lambda: actuator_set('stop',     0),  0.1),
]

# ─────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────

try:
    print("Starting sequences …")
    motor_ctrl.run(motor_sequence)

    act_start_ts = time.time()
    act_started  = False

    while True:
        # Kick off the actuator 1 s after the motor (non-blocking delay demo)
        if not act_started and time.time() - act_start_ts >= 1.0:
            actuator_ctrl.run(actuator_sequence)
            act_started = True

        # Tick both controllers every loop — fully independent
        motor_ctrl.update()
        actuator_ctrl.update()

        # Exit when both are done
        if not motor_ctrl.running and not actuator_ctrl.running and act_started:
            print("All done.")
            break

        time.sleep(0.01)   # 10 ms tick — only sleep for CPU relief, NOT for timing

except KeyboardInterrupt:
    print("\nInterrupted by user.")

finally:
    motor_set('stop', 0)
    actuator_set('stop', 0)
    motor_pwm.stop()
    act_pwm.stop()
    GPIO.cleanup()
    print("GPIO cleaned up.")
