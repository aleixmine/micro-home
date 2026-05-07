(() => {
  const $ = e => document.querySelector(e);
  const $s = (e, c) => {
    $(e).textContent = c
  };
  async function load() {
    try {
      const res = await fetch('/api/about', { cache: 'no-store' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      const d = data;
      const cpu = d.cpu || {};
      const ram = d.ram || {};
      const flash = d.flash_internal || {};
      const sd = d.sd_card || {};
      const net = d.network || {};
      const temp = d.temperature || {};
      const up = d.uptime || {};
      const sys = d.system || {};
      const sta = net.sta || {};
      const ap = net.ap || {};

      $s(".system .platform", sys.platform);
      $s(".system .micropython", sys.version);
      $s(".system .cpu", cpu.freq_mhz !== undefined ? cpu.freq_mhz + ' MHz' : '—');
      $s(".system .uptime", up.formatted);
      $s(".system .lastreset", d.reset_cause);

      $s(".temp .cel", temp.celsius);
      $s(".temp .fah", temp.fahrenheit);

      $s(".ram .used", ram.used_kb);
      $s(".ram .free", ram.free_kb);
      $s(".ram .total", ram.total_kb);

      if (flash.mounted) {
        $s(".flash .used", flash.used_mb);
        $s(".flash .total", flash.total_mb);
      }

      if (sd.mounted) {
        $s(".sd .used", sd.used_mb);
        $s(".sd .total", sd.total_mb);
      }
      $s(".sta .status", "Disconnected");
      if (sta.connected) {
        $s(".sta .status", "Connected");
        $s(".sta .ip", sta.ip);
        $s(".sta .netmask", sta.netmask);
        $s(".sta .gateway", sta.gateway);
        $s(".sta .dns", sta.dns);
      }

      $s(".ap .status", "Disconnected");
      if (ap.active) {
        $s(".ap .status", "Connected");
        $s(".ap .ip", ap.ip);
      }
      
    } catch (e) {
    }
  }

  load();


})()