import tinyweb
import os
import time
import _thread
import esp32
import uasyncio as asyncio
from machine import Pin, I2S
from dht import DHT22
import stats
import config

class ClimateResource:
    """Returns the latest DHT22 reading as JSON."""

    def __init__(self, sensor_data, data_lock):
        self._data = sensor_data
        self._lock = data_lock

    def get(self, data):
        with self._lock:
            return dict(self._data)


class MusicPlayResource:
    """POST { "file": "song.wav" } – starts I2S playback."""

    def __init__(self, music_player):
        self._player = music_player

    def post(self, data):
        filename = data.get('file', '')
        if not filename:
            return {'error': 'missing file'}, 400
        self._player.play('/sd/' + filename)
        return {'status': 'playing', 'file': filename}, 200


class MusicStopResource:
    """GET /api/stop – stops I2S playback."""

    def __init__(self, music_player):
        self._player = music_player

    def get(self, data):
        self._player.stop()
        return {'status': 'stopped'}


class MusicFilesResource:
    """GET /api/files - returns list of WAV files on the SD card."""

    def get(self, data):
        try:
            files = [f for f in os.listdir('/sd') if f.lower().endswith('.wav')]
        except Exception:
            files = []
        return {'files': files}


class MusicStatusResource:
    """GET /api/status - returns current playback state."""

    def __init__(self, music_player):
        self._player = music_player

    def get(self, data):
        current = self._player.current_file
        if current:
            name = current[4:] if current.startswith('/sd/') else current
            return {'playing': True, 'file': name}
        return {'playing': False, 'file': None}

class AboutResource:
    """GET /api/stop – stops I2S playback."""

    def __init__(self, ifconfig):
        self._ifconfig = ifconfig

    def get(self, data):
        return stats.SystemStats(sd_mount='/sd').to_json()

# ---------------------------------------------------------------------------
# I2S Music Player
# ---------------------------------------------------------------------------

class MusicPlayer:
    """
    Non-blocking WAV player using I2S interrupt callbacks.
    Only supports 16-bit mono PCM WAV files at 22 050 Hz.
    """

    BUF_SIZE = 2048
    WAV_HEADER = 44  # bytes to skip

    def __init__(self, sck_pin=14, ws_pin=12, sd_pin=13):
        self._i2s = I2S(
            0,
            sck=Pin(sck_pin),
            ws=Pin(ws_pin),
            sd=Pin(sd_pin),
            mode=I2S.TX,
            bits=16,
            format=I2S.MONO,
            rate=22050,
            ibuf=20000,
        )
        self._buf  = bytearray(self.BUF_SIZE)
        self._file = None
        self.current_file = None  # public: path being played or None
        self._i2s.irq(self._callback)

    # ---- public API --------------------------------------------------------

    def play(self, path):
        """Start playing a WAV file. Stops any current playback first."""
        self.stop()
        try:
            f = open(path, 'rb')
            f.read(self.WAV_HEADER)  # skip WAV header
            self._file = f
            self.current_file = path
            self._feed()             # prime the I2S buffer
        except OSError as e:
            print('[MusicPlayer] Cannot open file:', path, e)

    def stop(self):
        """Stop playback and close the file."""
        if self._file:
            self._file.close()
            self._file = None
        self.current_file = None

    # ---- internal ----------------------------------------------------------

    def _feed(self):
        if self._file is None:
            return
        n = self._file.readinto(self._buf)
        if n == 0:
            self.stop()  # also clears current_file
            print('[MusicPlayer] Playback finished.')
        else:
            self._i2s.write(self._buf[:n])

    def _callback(self, arg):
        """I2S IRQ – called when the hardware buffer needs more data."""
        self._feed()


# ---------------------------------------------------------------------------
# Main HomeManager
# ---------------------------------------------------------------------------

class MicroHome:
    """Orchestrates the web server, climate sensor, and music player."""

    def __init__(self, ifconfig: tuple):
        self._web    = tinyweb.webserver()
        self._player = None
        self._ifconfig = ifconfig

    # ---- climate -----------------------------------------------------------

    def _setup_climate(self):
        sensor      = DHT22(Pin(2))
        sensor_data = {'temperature': 0.0, 'humidity': 0.0}
        lock        = _thread.allocate_lock()

        def _sensor_loop():
            while True:
                try:
                    sensor.measure()
                    with lock:
                        sensor_data['temperature'] = sensor.temperature()
                        sensor_data['humidity']    = sensor.humidity()
                except Exception as e:
                    print('[DHT22] Read error:', e)
                time.sleep(2)

        _thread.start_new_thread(_sensor_loop, ())

        @self._web.route('/climate')
        async def climate_page(request, response):
            await response.start_html()
            with open("/climate.html","r") as f:
                while True:
                  data = f.read(1024)
                  if not data:
                      break
                  await response.send(data)

        self._web.add_resource(
            ClimateResource(sensor_data, lock),
            '/api/climate'
        )
        print('[HomeManager] Climate module ready.')

    # ---- music -------------------------------------------------------------

    def _setup_music(self):
        self._player = MusicPlayer(sck_pin=14, ws_pin=12, sd_pin=13)

        @self._web.route('/music')
        async def music_page(request, response):
            await response.start_html()
            with open("/music.html","r") as f:
                while True:
                  data = f.read(1024)
                  if not data:
                      break
                  await response.send(data)

        self._web.add_resource(MusicPlayResource(self._player),  '/api/music/play')
        self._web.add_resource(MusicStopResource(self._player),  '/api/music/stop')
        self._web.add_resource(MusicFilesResource(),              '/api/music/files')
        self._web.add_resource(MusicStatusResource(self._player), '/api/music/status')
        print('[HomeManager] Music module ready.')
    
    # ---- about -------------------------------------------------------------

    def _setup_about(self):
        @self._web.route('/about')
        async def about_page(request, response):
            await response.start_html()
            with open("/about.html","r") as f:
                while True:
                  data = f.read(1024)
                  if not data:
                      break
                  await response.send(data)
        self._web.add_resource(AboutResource(self._ifconfig), '/api/about')
        
        print('[HomeManager] About module ready.')

    # ---- entry points ------------------------------------------------------

    def _setup_routes(self):
        @self._web.route('/')
        async def index(request, response):
            await response.redirect('/climate')
        self._setup_climate()
        self._setup_music()
        self._setup_about()

    def run(self):
        """Blocking – use directly if you don't need the REPL."""
        self._setup_routes()
        print('[HomeManager] Starting web server on port 80…')
        self._web.run(host='0.0.0.0', port=80)

    async def run_async(self):
        """
        Non-blocking server: registers tinyweb's handler directly into the
        running uasyncio event loop without calling loop.run_forever(),
        so the REPL stays free on the same loop.
        """
        self._setup_routes()
        print('[HomeManager] Starting web server on port 80...')
        self._server = await asyncio.start_server(
            self._web._handler,
            '0.0.0.0',
            config.WEB_PORT,
            backlog=5
        )
        print('[HomeManager] HTTP server listening on port 80.')

