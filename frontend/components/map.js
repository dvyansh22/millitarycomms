function scaleCoordinate(value, min, max, fallback) {
    if (!Number.isFinite(value)) {
        return fallback;
    }

    if (min === max) {
        return 50;
    }

    const normalized = (value - min) / (max - min);
    return 12 + (normalized * 76);
}

function formatCoordinate(value) {
    return Number.isFinite(value) ? value.toFixed(5) : '--';
}

export function loadMap(nodes = [], threats = []) {
    const overlay = document.getElementById('node-overlay');
    overlay.innerHTML = '';

    const plottedNodes = nodes.filter((node) => (
        Number.isFinite(Number(node.lat)) && Number.isFinite(Number(node.lon))
    ));
    const plottedThreats = threats.filter((threat) => (
        Number.isFinite(Number(threat.lat)) && Number.isFinite(Number(threat.lon))
    ));

    if (!plottedNodes.length && !plottedThreats.length) {
        overlay.innerHTML = '<div class="placeholder map-placeholder">Waiting for ESP coordinates...</div>';
        return;
    }

    const latitudes = [
        ...plottedNodes.map((node) => Number(node.lat)),
        ...plottedThreats.map((threat) => Number(threat.lat)),
    ]
        .filter((value) => Number.isFinite(value));
    const longitudes = [
        ...plottedNodes.map((node) => Number(node.lon)),
        ...plottedThreats.map((threat) => Number(threat.lon)),
    ]
        .filter((value) => Number.isFinite(value));

    const minLat = latitudes.length ? Math.min(...latitudes) : 0;
    const maxLat = latitudes.length ? Math.max(...latitudes) : 0;
    const minLng = longitudes.length ? Math.min(...longitudes) : 0;
    const maxLng = longitudes.length ? Math.max(...longitudes) : 0;

    plottedNodes.forEach((node, index) => {
        const marker = document.createElement('div');
        const latitude = Number(node.lat);
        const longitude = Number(node.lon);
        const fallback = 20 + (index * 20);

        marker.className = 'node-marker';
        marker.style.left = `${scaleCoordinate(longitude, minLng, maxLng, fallback)}%`;
        marker.style.top = `${88 - scaleCoordinate(latitude, minLat, maxLat, fallback)}%`;

        const id = document.createElement('div');
        id.className = 'node-id';
        id.textContent = node.id;

        const details = document.createElement('div');
        details.className = 'node-status';
        details.textContent = node.hr == null ? 'HR -- BPM' : `HR ${node.hr} BPM`;

        const coords = document.createElement('div');
        coords.className = 'node-coords';
        coords.textContent = `${formatCoordinate(latitude)}, ${formatCoordinate(longitude)}`;

        marker.appendChild(id);
        marker.appendChild(details);
        marker.appendChild(coords);
        overlay.appendChild(marker);
    });

    plottedThreats.forEach((threat, index) => {
        const marker = document.createElement('div');
        const latitude = Number(threat.lat);
        const longitude = Number(threat.lon);
        const fallback = 15 + (index * 14);

        marker.className = 'enemy-marker';
        marker.style.left = `${scaleCoordinate(longitude, minLng, maxLng, fallback)}%`;
        marker.style.top = `${88 - scaleCoordinate(latitude, minLat, maxLat, fallback)}%`;
        marker.textContent = `E${threat.enemy_id}`;
        overlay.appendChild(marker);
    });
}
