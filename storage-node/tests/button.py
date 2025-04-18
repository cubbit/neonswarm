from gpiozero import Button
from signal import pause
from RPLCD.i2c import CharLCD
from time import sleep

# Set up the I2C LCD (adjust address if needed)
lcd = CharLCD('PCF8574', 0x27, cols=16, rows=2)

# Set up the button with internal pull-up and debounce
button = Button(17, pull_up=True, bounce_time=0.05)


def on_press():
    lcd.clear()
    sleep(0.05)  # short delay for stability
    lcd.write_string('Switch is ON')


def on_release():
    lcd.clear()
    sleep(0.05)  # short delay for stability
    lcd.write_string('Switch is OFF')


# Initialize LCD with default message
lcd.clear()
lcd.write_string('The Switch is OFF')

# Bind button events
button.when_pressed = on_press
button.when_released = on_release

# Wait for events
pause()
