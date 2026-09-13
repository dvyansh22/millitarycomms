// Browser-only demonstration; never writes simulated readings to the backend.
const commands = [
  'enemy ahead need backup',
  'hold position',
  'move east 20m',
  'area clear moving ahead',
  'enemy spotted on the east ridge',
];
let lastStep = null;
let commandHistory = [];

export function createSimulationSnapshot(now = Date.now()) {
  const step = Math.floor(now / 3000);
  const timestamp = step * 3;
  const phase = step * 0.45;
  const nodes = ['S1', 'S2'].map((id, index) => ({
    id,
    lat: 12.9723 + index * 0.0008 + Math.sin(phase + index) * 0.00018,
    lon: 79.1685 + index * 0.0008 + Math.cos(phase + index) * 0.00018,
    hr: 75 + ((step * 7 + index * 11) % 35),
    cmd: commands[(step + index * 2) % commands.length],
    enemy_count: 1,
    timestamp,
  }));
  const threats = nodes.map((node, index) => ({
    enemy_id: index + 1,
    node_id: node.id,
    lat: 12.97265 + Math.sin(phase * 1.3 + index * 2) * 0.00035,
    lon: 79.1689 + Math.cos(phase * 1.1 + index * 2) * 0.00035,
    time: timestamp,
  }));
  if (step !== lastStep) {
    if (lastStep !== null && step < lastStep) commandHistory = [];
    commandHistory = [...commandHistory, ...nodes.map(node => ({
      id: node.id, cmd: node.cmd, time: timestamp,
    }))].slice(-20);
    lastStep = step;
  }
  return {
    nodes,
    vitals: nodes.map(({ cmd, ...vital }) => vital),
    threats,
    logs: commandHistory.map(log => ({ ...log })),
    summary: { node_count: nodes.length, enemy_count: threats.length, message_count: commandHistory.length, last_updated: timestamp },
  };
}
