function createStat(label, value) {
    const stat = document.createElement('div');
    stat.className = 'vital-stat';

    const statLabel = document.createElement('div');
    statLabel.className = 'vital-label';
    statLabel.textContent = label;

    const statValue = document.createElement('div');
    statValue.className = 'vital-value';
    statValue.textContent = value;

    stat.appendChild(statLabel);
    stat.appendChild(statValue);
    return stat;
}

function getECGPath(bpm) {
    if (!bpm || bpm === 0) {
        return `<path d="M0,30 L300,30" class="flatline"/>`;
    }

    return `
        <path d="M0,30 
                 L20,30 
                 L30,10 
                 L40,50 
                 L50,30 
                 L70,30 
                 L80,25 
                 L90,35 
                 L100,30 
                 L130,30 
                 L140,5 
                 L150,55 
                 L160,30 
                 L200,30 
                 L300,30" />
    `;
}

export function loadVitals(vitals = []) {
    const container = document.getElementById('vitals');
    container.innerHTML = '';

    if (!vitals.length) {
        container.innerHTML = '<div class="placeholder">Waiting for heart-rate packets from ESP...</div>';
        return;
    }

    vitals.forEach((vital) => {
        const card = document.createElement('div');
        card.className = 'vital-card';

        const title = document.createElement('div');
        title.className = 'vital-name';
        title.textContent = vital.id;

        const bpm = vital.hr ?? 0;

        const bpmDisplay = document.createElement('div');
        bpmDisplay.className = 'vital-bpm';
        bpmDisplay.textContent = bpm ? `${bpm} BPM` : 'NO READING';
        if (!bpm) bpmDisplay.classList.add('missing-reading');

        const ecg = document.createElement('div');
        ecg.className = 'ecg';
        ecg.innerHTML = `
            <svg viewBox="0 0 300 60" preserveAspectRatio="none">
                ${getECGPath(bpm)}
            </svg>
        `;

        const grid = document.createElement('div');
        grid.className = 'vital-grid';
        grid.appendChild(createStat('Enemy Count', `${vital.enemy_count ?? 0}`));

        card.appendChild(title);
        card.appendChild(bpmDisplay);
        card.appendChild(ecg);
        card.appendChild(grid);

        container.appendChild(card);
    });
}
