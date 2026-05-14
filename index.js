let selectedSlot = null;

function makeSlot(s) {
  const cls = s.is_occupied ? 'occupied' : 'free';
  const status = s.is_occupied ? 'Occ' : 'Free';
  const selected = selectedSlot === s.slot_number ? 'selected' : '';
  const onclick = s.is_occupied ? '' : `onclick="selectSlot('${s.slot_number}')"`;
  return `<div class="slot ${cls} ${selected}" ${onclick}>${s.slot_number}<span class="slot-status">${status}</span></div>`;
}

function makeAisle() {
  return `<div class="slot-aisle"></div>`;
}

function selectSlot(slotNumber) {
  selectedSlot = selectedSlot === slotNumber ? null : slotNumber;
  document.getElementById('selected-slot-label').textContent = selectedSlot
    ? `Selected: ${selectedSlot}`
    : 'No slot selected';
  document.getElementById('assign-btn').disabled = !selectedSlot;
  renderSlots(window._lastSlots);
}

function renderSlots(slots) {
  window._lastSlots = slots;
  const grid = document.getElementById('slots-grid');

  const rows = {};
  slots.forEach(s => {
    const row = s.slot_number[0];
    if (!rows[row]) rows[row] = [];
    rows[row].push(s);
  });

  let html = '';
  Object.keys(rows).sort().forEach(row => {
    const r = rows[row].sort((a, b) =>
      parseInt(a.slot_number.slice(1)) - parseInt(b.slot_number.slice(1))
    );

    if ('EFG'.includes(row)) {
      html += `<div class="slot-row"><div class="slot-section">${r.map(makeSlot).join('')}</div></div>`;
    } else {
      const left   = r.filter(s => parseInt(s.slot_number.slice(1)) <= 4);
      const middle = r.filter(s => parseInt(s.slot_number.slice(1)) >= 5 && parseInt(s.slot_number.slice(1)) <= 12);
      const right  = r.filter(s => parseInt(s.slot_number.slice(1)) >= 13);
      html += `<div class="slot-row">
        <div class="slot-section">${left.map(makeSlot).join('')}</div>
        ${makeAisle()}
        <div class="slot-section">${middle.map(makeSlot).join('')}</div>
        ${makeAisle()}
        <div class="slot-section">${right.map(makeSlot).join('')}</div>
      </div>`;
    }
  });

  grid.innerHTML = html;
}

async function loadSlots() {
  const res = await fetch('/slots');
  const slots = await res.json();
  if (!slots.length) {
    document.getElementById('slots-grid').innerHTML = '<div class="empty">No slots found.</div>';
    return;
  }
  renderSlots(slots);
}

async function loadRecords() {
  const res = await fetch('/records');
  const records = await res.json();
  const container = document.getElementById('records-container');
  if (!records.length) { container.innerHTML = '<div class="empty">No records yet.</div>'; return; }
  container.innerHTML = `
    <table>
      <thead>
        <tr><th>ID</th><th>Vehicle</th><th>Slot</th><th>Entry</th><th>Exit</th></tr>
      </thead>
      <tbody>
        ${records.map(r => `
          <tr>
            <td>${r.id}</td>
            <td>${r.vehicle_number}</td>
            <td>${r.slot_number}</td>
            <td>${r.entry_time}</td>
            <td class="${r.exit_time === 'Still parked' ? 'still' : 'exited'}">${r.exit_time}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

async function assignSlot() {
  const vehicle = document.getElementById('assign-vehicle').value.trim();
  const msg = document.getElementById('assign-msg');
  if (!vehicle) { msg.textContent = 'Enter vehicle number.'; msg.className = 'msg err'; return; }
  if (!selectedSlot) { msg.textContent = 'Select a slot first.'; msg.className = 'msg err'; return; }

  const res = await fetch('/assign', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ vehicle_number: vehicle, slot_number: selectedSlot })
  });
  const data = await res.json();
  msg.textContent = data.message || data.error;
  msg.className = res.ok ? 'msg' : 'msg err';
  if (res.ok) {
    document.getElementById('assign-vehicle').value = '';
    selectedSlot = null;
    document.getElementById('selected-slot-label').textContent = 'No slot selected';
    document.getElementById('assign-btn').disabled = true;
    loadSlots();
    loadRecords();
  }
}

async function releaseSlot() {
  const vehicle = document.getElementById('release-vehicle').value.trim();
  const msg = document.getElementById('release-msg');
  if (!vehicle) { msg.textContent = 'Enter vehicle number.'; msg.className = 'msg err'; return; }
  const res = await fetch('/release', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ vehicle_number: vehicle })
  });
  const data = await res.json();
  msg.textContent = data.message || data.error;
  msg.className = res.ok ? 'msg' : 'msg err';
  if (res.ok) { document.getElementById('release-vehicle').value = ''; loadSlots(); loadRecords(); }
}

loadSlots();
loadRecords();