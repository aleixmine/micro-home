import os, machine, network, time, neopixel, config
state_led = neopixel.NeoPixel(machine.Pin(48), 1)

def state(*rgb):
    state_led[0] = rgb
    state_led.write()

class WiFiManager:
    def __init__(self):
        self.sta = network.WLAN(network.STA_IF)
        self.ap = network.WLAN(network.AP_IF)

    def connect_sta(self, ssid, password, timeout=10): # STATION
        self.sta.active(True)
        if self.sta.isconnected():
            return self.sta.ifconfig()

        self.sta.connect(ssid, password)
        start = time.time()

        while not self.sta.isconnected():
            if time.time() - start > timeout:
                return None
            time.sleep(0.5)

        return self.sta.ifconfig()

    def start_ap(self, ssid="ESP32_AP", password="12345678"): # ACCESS POINT
        self.ap.active(True)
        self.ap.config(essid=ssid, password=password)
        return self.ap.ifconfig()
    
    def start_ap_sta(self, ssid, password, ap_ssid="ESP32_AP", ap_pass="12345678", timeout =10): # ACCESS POINT - STATION
        self.start_ap(ap_ssid, ap_pass)
        return self.connect_sta(ssid, password, timeout)
    
    def stop(self):
        self.sta.active(False)
        self.ap.active(False)


def wifi_setup():
    if config.START_MODE is None:
        return

    wifi = WiFiManager()

    if config.START_MODE == "STA":
        ifconfig = wifi.connect_sta(
            config.WIFI_SSID,
            config.WIFI_PASSWORD,
            config.WIFI_TIMEOUT
        )
    if config.START_MODE == "AP":
        ifconfig = wifi.start_ap(
            config.AP_SSID,
            config.AP_PASSWORD,
        )
    if config.START_MODE == "AP_STA":
        ifconfig = wifi.start_ap_sta(
            config.WIFI_SSID,
            config.WIFI_PASSWORD,
            config.AP_SSID,
            config.AP_PASSWORD,
            config.WIFI_TIMEOUT
        )
    return ifconfig
        
def update_clock():
    import ntptime
    try:
        ntptime.settime()
        print("Hora sincronizada")
    except:
        print("No se pudo sincronizar la hora")
    print(time.localtime())

def mount_sd():
    path = "/sd"
    try:
        os.listdir(path)
        print("[home] SD already Mounted!")
        return True
    except OSError:
        pass
    try:
        sd = machine.SDCard(slot=1,width=1,sck=39,cmd=38,data=(40,),cd=None,wp=None)
        os.mount(sd, path)
        print("[home] SD Mounted!")
        return True
    except Exception as e:
        return False

state(0,0,255) # blue

# Mount automatically SDCard
mount_sd()

# Automatically loads wifi
ifconfig=wifi_setup()

# Setting up the clock
update_clock()

state(0,0,0) # disable

import webrepl
webrepl.start(password='root')

import microhome
manager = microhome.MicroHome(ifconfig)
manager.run()