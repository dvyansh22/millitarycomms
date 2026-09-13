// Presentation state only: no source records, API responses or telemetry are changed.
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const validCoordinate = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
const hasPosition = item => validCoordinate(item.lat) && validCoordinate(item.lon)
  && Math.abs(Number(item.lat)) <= 90 && Math.abs(Number(item.lon)) <= 180;
const keyOf = item => JSON.stringify([item.node_id, item.enemy_id]);

export function createEnemyDisplay(random = Math.random, now = 0) {
  const between = (min, max) => min + random() * (max - min);
  const interval = index => random() < 0.35 ? between(20000, 60000)
    : index === 0 ? between(15000, 30000) : between(20000, 40000);
  const contacts = [0, 1].map(index => ({
    key: null, record: { enemy_id: index + 1, visualization: 'Simulated map contact' },
    label: `E${index + 1}`, x: 41 + index * 18, y: 50,
    anchorX: 41 + index * 18, anchorY: 50,
    hidden: index === 1, nextMove: now + interval(index),
  }));
  let projection = null;
  let nextGap = now + 18000;
  let missing = 1;
  let returnAt = now + 3000;

  function updateSources(threats) {
    const candidates = [];
    const seen = new Set();
    for (const threat of threats) {
      if (!hasPosition(threat) || seen.has(keyOf(threat))) continue;
      seen.add(keyOf(threat));
      candidates.push(threat);
    }
    if (!projection && candidates.length) {
      // Freeze the initial coordinate frame. Polling must not rescale the map.
      const selected = candidates.slice(0, 2);
      const lats = selected.map(t => Number(t.lat)), lons = selected.map(t => Number(t.lon));
      const minLat = Math.min(...lats), maxLat = Math.max(...lats);
      const minLon = Math.min(...lons), maxLon = Math.max(...lons);
      projection = {
        lat: (minLat + maxLat) / 2, lon: (minLon + maxLon) / 2,
        latSpan: Math.max(0.0015, (maxLat - minLat) * 1.8),
        lonSpan: Math.max(0.0015, (maxLon - minLon) * 1.8),
      };
    }
    for (const [index, contact] of contacts.entries()) {
      if (contact.key) continue; // Preserve each contact's original location and identity.
      const source = candidates.find(t => !contacts.some(c => c.key === keyOf(t)));
      if (!source) continue;
      contact.key = keyOf(source);
      contact.record = { ...source };
      contact.label = `E${index + 1} · ${source.node_id}`;
      // Keep source coordinates in the record; arrange the displayed pair side by side.
      contact.x = contact.anchorX = index === 0
        ? clamp(50 + (Number(source.lon) - projection.lon) / projection.lonSpan * 76, 15, 65)
        : contacts[0].anchorX + 18;
      contact.y = contact.anchorY = index === 0
        ? clamp(50 - (Number(source.lat) - projection.lat) / projection.latSpan * 76, 15, 85)
        : contacts[0].anchorY;
      if (index === 0 && !contacts[1].key) {
        contacts[1].x = contacts[1].anchorX = contact.anchorX + 18;
        contacts[1].y = contacts[1].anchorY = contact.anchorY;
      }
    }
  }

  function nudge(contact) {
    // Less than one percent of the map per move, never more than 3% from origin.
    contact.x = clamp(contact.x + between(-0.6, 0.6), contact.anchorX - 3, contact.anchorX + 3);
    contact.y = clamp(contact.y + between(-0.6, 0.6), contact.anchorY - 3, contact.anchorY + 3);
  }

  function tick(at) {
    if (missing !== null && at >= returnAt) {
      contacts[missing].hidden = false;
      contacts[missing].nextMove = at + interval(missing);
      missing = null;
      nextGap = at + 15000; // E2 remains visible for fifteen seconds after appearing.
    } else if (missing === null && at >= nextGap) {
      missing = 1; // Only E2 loses detection; E1 remains visible.
      contacts[missing].hidden = true;
      returnAt = at + 3000; // E2 stays hidden for three seconds.
    }
    contacts.forEach((contact, index) => {
      if (!contact.hidden && at >= contact.nextMove) {
        nudge(contact);
        contact.nextMove = at + 6000 + interval(index);
      }
    });
    return contacts;
  }
  return { updateSources, tick };
}

export function createEnemyMap(overlay, inspect) {
  const display = createEnemyDisplay(Math.random, performance.now());
  let markers = [];
  let timer;
  function paint() {
    const contacts = display.tick(performance.now());
    if (!markers.length) {
      overlay.replaceChildren();
      markers = contacts.map(contact => {
        const marker = document.createElement('button');
        marker.className = 'map-marker threat slow-contact';
        marker.append(document.createElement('span'));
        marker.addEventListener('click', () => inspect(contact.label, {
          ...contact.record, visualization: 'Slow/intermittent frontend contact; source coordinates retained',
        }));
        overlay.append(marker);
        return marker;
      });
    }
    contacts.forEach((contact, index) => {
      const marker = markers[index];
      marker.style.left = `${contact.x}%`;
      marker.style.top = `${contact.y}%`;
      marker.firstChild.textContent = contact.label;
      marker.setAttribute('aria-label', `Inspect ${contact.label}`);
      marker.title = hasPosition(contact.record)
        ? `${Number(contact.record.lat).toFixed(5)}, ${Number(contact.record.lon).toFixed(5)}`
        : 'Simulated map contact';
      marker.classList.toggle('detection-gap', contact.hidden);
      marker.inert = contact.hidden;
      marker.setAttribute('aria-hidden', String(contact.hidden));
    });
  }
  return {
    update(threats) {
      display.updateSources(threats);
      paint();
      if (!timer) timer = setInterval(() => { if (!document.hidden) paint(); }, 500);
    },
  };
}
