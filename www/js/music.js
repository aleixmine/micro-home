const nowEl = document.getElementById('now');
const listEl = document.getElementById('file-list');
const msgEl = document.getElementById('msg');
let current = null;

function setPlaying(file) {
    current = file;
    nowEl.textContent = file || 'Nothing playing';
    document.querySelectorAll('.file-item').forEach(i => {
        const name = i.querySelector('.file-name').textContent;
        i.classList.toggle('playing', name === file);
    });
    document.querySelector("#btn-stop").classList.toggle("is-invisible", file === null)
}

async function loadStatus() {
    try {
        const res = await fetch('/api/music/status', { cache: 'no-store' });
        const data = await res.json();
        setPlaying(data.playing ? data.file : null);
    } catch { }
}

async function loadFiles() {
    try {
        const res = await fetch('/api/music/files', { cache: 'no-store' });
        const data = await res.json();
        const files = data.files || [];
        listEl.innerHTML = '';
        if (!files.length) {
            listEl.innerHTML = '<div class="box container is-flex is-justify-content-space-between"><span>No WAV files found on SD card.</span></div>';
            return;
        }
        files.forEach(f => {
            const item = document.createElement('div');
            item.className = 'file-item box container is-flex is-justify-content-space-between';
            item.innerHTML = `<span class="file-name">${f}</span><span class="has-text-info is-size-4">&#9654;</span>`;
            item.onclick = () => play(f, item);
            listEl.appendChild(item);
        });
        // restore state after list is built
        await loadStatus();
    } catch { listEl.innerHTML = '<div class="box container is-flex is-justify-content-space-between"><span>Could not load file list.</span></div>'; }
}

async function play(file, el) {
    try {
        const res = await fetch('/api/music/play', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file })
        });
        if (!res.ok) throw new Error();
        setPlaying(file);
        msgEl.textContent = '';
    } catch { msgEl.textContent = 'Error starting playback.'; }
}

document.getElementById('btn-stop').onclick = async () => {
    await fetch('/api/music/stop');
    setPlaying(null);
};

loadFiles();