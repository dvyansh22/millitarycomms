function formatTime(timestamp) {
    const date = new Date(Number(timestamp) * 1000);
    return Number.isNaN(date.getTime()) ? 'NO TIME' : date.toLocaleTimeString();
}

function formatCoordinate(value) {
    return Number.isFinite(Number(value)) ? Number(value).toFixed(5) : '--';
}

export function loadThreats(threats = []) {
    const container = document.getElementById("threats");
    container.innerHTML = '';

    if (!threats.length) {
        container.innerHTML = '<div class="placeholder">No enemy coordinates in the latest packet.</div>';
        return;
    }

    [...threats].reverse().forEach(threat => {
        const card = document.createElement("div");
        card.className = "threat-card";

        const header = document.createElement('div');
        header.className = 'threat-header';
        const title = document.createElement('span');
        title.className = 'title';
        title.textContent = `Event E${threat.enemy_id}`;
        const time = document.createElement('span');
        time.className = 'time';
        time.textContent = formatTime(threat.time);
        header.append(title, time);
        const desc = document.createElement('div');
        desc.className = 'desc';
        desc.textContent = `Node ${threat.node_id} reported an event at (${formatCoordinate(threat.lat)}, ${formatCoordinate(threat.lon)})`;
        const tag = document.createElement('div');
        tag.className = 'tag';
        tag.textContent = `VERIFIED SOURCE: NODE ${threat.node_id}`;
        card.append(header, desc, tag);

        container.appendChild(card);
    });
}
