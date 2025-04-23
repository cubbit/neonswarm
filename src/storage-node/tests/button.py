from gpiozero import Button
from signal import pause

# Set up the button with internal pull-up and debounce
button = Button(17, pull_up=True, bounce_time=0.05)


def on_press():
    print("Switch is ON")


def on_release():
    print("Switch is OFF")


# Bind button events
button.when_pressed = on_press
button.when_released = on_release

# Wait for events
pause()
