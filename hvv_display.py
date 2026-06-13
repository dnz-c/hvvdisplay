import time
import sys
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image, ImageDraw, ImageFont
from geofox import *

# CONFIG
STATION_NAME = "Jungfernstieg"
API_UPDATE_INTERVAL = 30.0
SCROLL_SPEED = 0.5
PAUSE_DURATION = 3.0

def get_line_color(line_name):
    colors = {
        "S1": (0, 150, 44),
        "S2": (180, 20, 57),
        "S3": (84, 33, 110),
        "S5": (0, 138, 189),
        "S7": (214, 158, 0),
        "U1": (0, 96, 173),
        "U2": (227, 33, 25),
        "U3": (253, 212, 0),
        "U4": (0, 142, 152),
    }
    return colors.get(line_name, (200, 200, 200))

# CLASSES
class ScrollingText:
    def __init__(self, font, pause_duration=PAUSE_DURATION, scroll_speed=SCROLL_SPEED):
        self.font = font
        self.pause_duration = pause_duration
        self.scroll_speed = scroll_speed
        
        self.text = ""
        self.offset = 0.0
        self.state = "PAUSE"
        self.timer = time.time()
        self.gap = "   *** "

    def update_text(self, new_text):
        if self.text != new_text:
            self.text = new_text
            self.offset = 0.0
            self.state = "PAUSE"
            self.timer = time.time()

    def draw(self, target_image, x, y, max_width, color):
        if not self.text:
            return

        temp_img = Image.new("RGB", (int(max_width), 14))
        temp_draw = ImageDraw.Draw(temp_img)
        
        text_width = temp_draw.textlength(self.text, font=self.font)

        if text_width <= max_width:
            temp_draw.text((0, 0), self.text, fill=color, font=self.font)
        else:
            gap_width = temp_draw.textlength(self.gap, font=self.font)
            cycle_width = text_width + gap_width
            current_time = time.time()

            if self.state == "PAUSE":
                if current_time - self.timer > self.pause_duration:
                    self.state = "SCROLL"
            elif self.state == "SCROLL":
                self.offset -= self.scroll_speed
                
                if self.offset <= -cycle_width:
                    self.offset = 0.0
                    self.state = "PAUSE"
                    self.timer = current_time

            temp_draw.text((int(self.offset), 0), self.text, fill=color, font=self.font)
            temp_draw.text((int(self.offset + text_width), 0), self.gap, fill=(100, 100, 100), font=self.font)
            temp_draw.text((int(self.offset + cycle_width), 0), self.text, fill=color, font=self.font)

        target_image.paste(temp_img, (x, y))


class TrainBoard:
    def __init__(self):
        options = RGBMatrixOptions()
        options.rows = 64
        options.cols = 64
        options.hardware_mapping = 'adafruit-hat'
        self.matrix = RGBMatrix(options=options)
        
        try:
            self.font = ImageFont.truetype("DejaVuSans-Bold.ttf", 10)
        except OSError:
            self.font = ImageFont.truetype("DejaVuSans.ttf", 10)
            
        self.header_scroller = ScrollingText(self.font)
        self.header_scroller.update_text(STATION_NAME)
        
        self.dest_scrollers = [ScrollingText(self.font) for _ in range(4)]
        self.y_positions = [12, 25, 38, 51]
        
        self.departures = []
        self.last_api_update = 0

    def fetch_api_data(self):
        try:
            raw_deps = get_station_departures(STATION_NAME)
            raw_deps.sort(key=lambda x: x[3])
            self.departures = []
            
            for dep in raw_deps[:4]:
                line_name, direction, platform, time_display, delay_minutes = dep
                time_str = "Now" if time_display <= 0 else f"{time_display}m"
                
                self.departures.append({
                    "line": line_name,
                    "dest": direction,
                    "time": time_str,
                    "is_delayed": delay_minutes > 0
                })
        except Exception as e:
            print(f"API Fehler: {e}")

    def run(self):
        while True:
            current_time = time.time()
            
            if current_time - self.last_api_update > API_UPDATE_INTERVAL:
                self.fetch_api_data()
                self.last_api_update = current_time

            image = Image.new("RGB", (self.matrix.width, self.matrix.height))
            draw = ImageDraw.Draw(image)
            
            # HEADER
            self.header_scroller.draw(image, x=2, y=-1, max_width=62, color=(255, 255, 255))
            draw.line((0, 10, 64, 10), fill=(50, 50, 50))

            # ABFAHRTEN
            for i, dep in enumerate(self.departures):
                if i >= len(self.y_positions):
                    break
                    
                y = self.y_positions[i]
                
                line_col = get_line_color(dep["line"])
                time_col = (255, 0, 0) if dep["is_delayed"] else (255, 255, 255)
                
                draw.text((1, y), dep["line"], fill=line_col, font=self.font)
                
                time_width = draw.textlength(dep["time"], font=self.font)
                time_x = self.matrix.width - time_width - 1
                draw.rectangle((time_x - 2, y, self.matrix.width, y + 12), fill=(0, 0, 0))
                draw.text((time_x, y), dep["time"], fill=time_col, font=self.font)
                
                dest_start_x = 16
                dest_visible_width = (time_x - 3) - dest_start_x
                
                self.dest_scrollers[i].update_text(dep["dest"])
                self.dest_scrollers[i].draw(image, x=dest_start_x, y=y, 
                                            max_width=dest_visible_width, color=(255, 255, 255))

            self.matrix.SetImage(image, 0, 0)
            time.sleep(0.02)

if __name__ == "__main__":
    load_geofox_creds()
    board = TrainBoard()
    board.run()