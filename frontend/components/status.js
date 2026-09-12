export function initStatus() {
  function updateTime() {
    const now = new Date();

    const time = now.toLocaleTimeString();
    const date = now.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
    const day = now.toLocaleDateString(undefined, {
      weekday: 'long'
    });

    document.getElementById('local-time').textContent = time;
    document.getElementById('date').textContent = date.toUpperCase();
    document.getElementById('day').textContent = day.toUpperCase();
  }

  updateTime();
  setInterval(updateTime, 1000);
}