function formatTime(timestamp) {
    const date = new Date(Number(timestamp) * 1000);
    return Number.isNaN(date.getTime()) ? 'NO TIME' : date.toLocaleTimeString();
}

export function loadLogs(logs = []) {
    const container = document.getElementById("logs");
    container.innerHTML = '';

    if (!logs.length) {
        container.innerHTML = '<div class="placeholder">No incoming command text.</div>';
        return;
    }

    const ul = document.createElement("ul");
    ul.className = "log-list";

    [...logs].reverse().forEach(log => {
        const li = document.createElement("li");

        const time = document.createElement('span');
        time.className = 'log-time';
        time.textContent = `[${formatTime(log.time)}]`;
        const unit = document.createElement('span');
        unit.className = 'log-unit';
        unit.textContent = `${log.id}:`;
        const message = document.createElement('span');
        message.className = 'log-msg';
        message.textContent = log.cmd;
        li.append(time, unit, message);

        ul.appendChild(li);
    });

    container.appendChild(ul);
}
