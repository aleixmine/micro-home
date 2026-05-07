(async () => {
    const MAX = 30;
    const labels = Array(MAX).fill('');
    const tempHistory = Array(MAX).fill(null);
    const humHistory = Array(MAX).fill(null);
    const doc = getComputedStyle(document.documentElement);
    const fontName = doc.getPropertyValue('--bulma-body-family');
    const tempColor = getComputedStyle(document.querySelector("#temp")).color;
    const humColor = getComputedStyle(document.querySelector("#hum")).color;
    const chart = new Chart(document.getElementById('chart'), {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Temperature (°C)',
                    data: tempHistory,
                    borderColor: tempColor,
                    backgroundColor: 'rgba(248,81,73,0.08)',
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.4,
                    fill: true,
                    yAxisID: 'yTemp'
                },
                {
                    label: 'Humidity (%)',
                    data: humHistory,
                    borderColor: humColor,
                    backgroundColor: 'rgba(88,166,255,0.08)',
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.4,
                    fill: true,
                    yAxisID: 'yHum'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 300 },
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    labels: {
                        color: '#8b949e', font: { family: fontName, size: 11 },
                        boxWidth: 12, padding: 12
                    }
                },
                tooltip: {
                    backgroundColor: '#161b22',
                    borderColor: '#30363d',
                    borderWidth: 1,
                    titleColor: '#8b949e',
                    bodyColor: '#e6edf3',
                    bodyFont: { family: fontName }
                }
            },
            scales: {
                x: { display: false },
                yTemp: {
                    position: 'left',
                    ticks: { color: tempColor, font: { family: fontName, size: 10 }, maxTicksLimit: 4 },
                    grid: { color: 'rgba(48,54,61,0.6)' }
                },
                yHum: {
                    position: 'right',
                    ticks: { color: humColor, font: { family: fontName, size: 10 }, maxTicksLimit: 4 },
                    grid: { drawOnChartArea: false }
                }
            }
        }
    });

    const tempEl = document.getElementById('temp');
    const humEl = document.getElementById('hum');
    const dot = document.getElementById('dot');
    const statusEl = document.getElementById('status-text');

    async function update() {
        try {
            const res = await fetch('/api/climate', { cache: 'no-store' });
            if (!res.ok) throw new Error('HTTP ' + res.status);
            const data = await res.json();

            tempEl.innerHTML = data.temperature.toFixed(1) + '<span class="unit"> &deg;C</span>';
            humEl.innerHTML = data.humidity.toFixed(1) + '<span class="unit"> %</span>';
            dot.className = 'dot';
            statusEl.textContent = 'Live · ' + new Date().toLocaleTimeString();

            tempHistory.push(data.temperature);
            humHistory.push(data.humidity);
            labels.push('');
            if (tempHistory.length > MAX) { tempHistory.shift(); humHistory.shift(); labels.shift(); }

            chart.update('none');
        } catch (err) {
            dot.className = 'dot error';
            statusEl.textContent = 'Sensor error - retrying...';
        }
    }
    update();
    setInterval(update, 2000);
    
})()