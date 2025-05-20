import board
import digitalio
import time
import busio
import displayio
import terminalio
from adafruit_display_text import label
import adafruit_displayio_ssd1306
from adafruit_bitmap_font import bitmap_font
import analogio

# Load custom fonts
small_font = bitmap_font.load_font("/lib/adafruit_gfx/fonts/NokiaCellphoneFC-Small-8.bdf")
large_font = bitmap_font.load_font("/lib/adafruit_gfx/fonts/GallaeciaForte-16.bdf")

# Define all buttons as general inputs
button_pins = {
    "B1": board.D5,
    "B2": board.D6,
    "B3": board.D9,
    "B4": board.D10,
    "B5": board.D11,
    "B6": board.D12,
    "B7": board.D13,
    "page": board.D4
}

buttons = {}
button_states = {}
last_press_times = {}

for name, pin in button_pins.items():
    buttons[name] = digitalio.DigitalInOut(pin)
    buttons[name].direction = digitalio.Direction.INPUT
    buttons[name].pull = digitalio.Pull.UP
    button_states[name] = True  # Default to released
    last_press_times[name] = 0

# Display setup
displayio.release_displays()
i2c = busio.I2C(board.SCL, board.SDA)
display_bus = displayio.I2CDisplay(i2c, device_address=0x3C)
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)

# Counters
joules_counter = 0
cmd1_counter, cmd2_counter, cmd3_counter = 0, 0, 0
infect_counter = 1
speed_counter = 1

# Page tracking
pages = ["Joules Counter", "CMD Counters", "Infect Counter", "Speed Tracker", "Battery Voltage"]
current_page_index = 0
selected_page = None
display_dirty = True

# Battery voltage input
vbat_voltage = analogio.AnalogIn(board.A3)

def get_voltage(pin):
    return pin.value / 65535 * 3.3 * 2

def format_counter(counter):
    return "{:02d}".format(counter)

def centered_label(font, text, y, scale=1):
    temp = label.Label(font, text=text, color=0xFFFFFF, scale=scale)
    width = temp.bounding_box[2] * scale
    temp.x = (display.width - width) // 2
    temp.y = y
    return temp

# Flashing low battery icon state
flash_state = False
last_flash_time = time.monotonic()

def update_display():
    global display_dirty, flash_state, last_flash_time
    global joules_counter, cmd1_counter, cmd2_counter, cmd3_counter, infect_counter, speed_counter

    if not display_dirty:
        return

    display_group = displayio.Group()

    if selected_page is None:
        font = small_font
        for i in range(len(pages)):
            index = (current_page_index + i) % len(pages)
            page_name = pages[index]
            text_label = centered_label(font, page_name, 10 + (i * 15))
            display_group.append(text_label)
    else:
        font = large_font
        if selected_page == "Joules Counter":
            display_group.append(centered_label(font, "Joules", 5))
            display_group.append(centered_label(font, format_counter(joules_counter), 30, scale=2))

        elif selected_page == "CMD Counters":
            col_width = display.width // 3
            column_centers = [(i * col_width) + col_width // 2 for i in range(3)]
            for i, text in enumerate(["1", "2", "3"]):
                heading = label.Label(font, text=text, color=0xFFFFFF)
                heading_width = heading.bounding_box[2]
                heading.x = column_centers[i] - heading_width // 2
                heading.y = 5
                display_group.append(heading)

            counters = [cmd1_counter, cmd2_counter, cmd3_counter]
            for i, value in enumerate(counters):
                counter_text = format_counter(value)
                counter = label.Label(font, text=counter_text, color=0xFFFFFF)
                counter_width = counter.bounding_box[2]
                counter.x = column_centers[i] - counter_width // 2
                counter.y = 40
                display_group.append(counter)

        elif selected_page == "Infect Counter":
            if infect_counter <= 9:
                display_group.append(centered_label(font, "TOXIC", 5))
                counter_text = centered_label(font, str(infect_counter), 25, scale=2)
                display_group.append(counter_text)
            elif infect_counter == 10:
                display_group.append(centered_label(font, "TOXIC", 5))
                counter_text = centered_label(font, str(infect_counter), 25, scale=1)
                display_group.append(counter_text)
                display_group.append(centered_label(font, "COMPLEATED", 50))
                counter_text.x = 55

        elif selected_page == "Speed Tracker":
            if speed_counter <= 3:
                display_group.append(centered_label(font, "Speed", 5))
                display_group.append(centered_label(font, str(speed_counter), 30, scale=2))
            elif speed_counter == 4:
                display_group.append(centered_label(font, "MAX SPEED", 5))
                display_group.append(centered_label(font, str(speed_counter), 30, scale=2))

        elif selected_page == "Battery Voltage":
            battery_voltage = get_voltage(vbat_voltage)
            display_group.append(centered_label(font, "Battery", 5))
            display_group.append(centered_label(font, f"{battery_voltage:.2f}V", 30, scale=2))

    # Flashing battery icon
    battery_voltage = get_voltage(vbat_voltage)
    now = time.monotonic()
    if battery_voltage < 3.3 and now - last_flash_time >= 0.5:
        flash_state = not flash_state
        last_flash_time = now

    if battery_voltage < 3.3 and flash_state:
        icon_bitmap = displayio.Bitmap(10, 10, 2)
        icon_palette = displayio.Palette(2)
        icon_palette[0] = 0x000000
        icon_palette[1] = 0xFFFFFF
        for x in range(2, 9):
            icon_bitmap[x, 1] = 1
            icon_bitmap[x, 8] = 1
        for y in range(2, 8):
            icon_bitmap[2, y] = 1
            icon_bitmap[8, y] = 1
        for i in range(10):
            if 0 <= i < 10:
                icon_bitmap[i, i] = 1
        icon_tile = displayio.TileGrid(icon_bitmap, pixel_shader=icon_palette, x=display.width - 12, y=2)
        display_group.append(icon_tile)

    display.root_group = display_group
    display_dirty = False

def mark_display_dirty():
    global display_dirty
    display_dirty = True

def check_button_presses():
    now = time.monotonic()
    for name, button in buttons.items():
        current_state = button.value
        if not current_state and button_states[name] and (now - last_press_times[name] > 0.2):
            last_press_times[name] = now
            handle_button_press(name)
        button_states[name] = current_state

def handle_button_press(name):
    global current_page_index, selected_page
    global joules_counter, cmd1_counter, cmd2_counter, cmd3_counter, infect_counter, speed_counter

    if selected_page is None:
        if name == "B3":
            current_page_index = (current_page_index - 1) % len(pages)
        elif name == "B4":
            current_page_index = (current_page_index + 1) % len(pages)
        elif name == "page":
            selected_page = pages[current_page_index]
        mark_display_dirty()
        return

    if name == "B7":
        selected_page = None
        mark_display_dirty()
        return

    if selected_page == "Joules Counter":
        if name == "B1":
            joules_counter += 1
        elif name == "B2":
            joules_counter -= 1
        elif name == "B3":
            joules_counter += 2
        elif name == "B4":
            joules_counter -= 2
        elif name == "B5":
            joules_counter += 3
        elif name == "B6":
            joules_counter = 0

    elif selected_page == "CMD Counters":
        if name == "B1":
            cmd1_counter += 1
        elif name == "B2":
            cmd1_counter -= 1
        elif name == "B3":
            cmd2_counter += 1
        elif name == "B4":
            cmd2_counter -= 1
        elif name == "B5":
            cmd3_counter += 1
        elif name == "B6":
            cmd3_counter -= 1
        elif name == "B7":
            cmd1_counter = cmd2_counter = cmd3_counter = 0

    elif selected_page == "Infect Counter":
        if name == "B1":
            infect_counter = min(infect_counter + 1, 10)
        elif name == "B2":
            infect_counter = max(infect_counter - 1, 0)
        elif name == "B6":
            infect_counter = 0

    elif selected_page == "Speed Tracker":
        if name == "B1":
            speed_counter = min(speed_counter + 1, 4)
        elif name == "B2":
            speed_counter = max(speed_counter - 1, 1)
        elif name == "B7":
            speed_counter = 0

    mark_display_dirty()

update_display()

while True:
    check_button_presses()
    update_display()
    time.sleep(0.01)
