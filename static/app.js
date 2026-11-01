'use strict';
let state = null;
let active = ['trip', 'packing', 'admin'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'trip';
let saving = 0;
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const shortDate = date => new Date(date.slice(0,10) + 'T12:00:00').toLocaleDateString('en-GB', {day:'numeric',month:'short'});

function status(text, warning = false) { $('#sync').textContent = text; $('#sync').classList.toggle('warning', warning); }
function error(text = '') { $('#error').textContent = text; $('#error').hidden = !text; }
let toastTimer;
function toast(text) { $('#toast').textContent = text; $('#toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#toast').hidden = true, 2600); }

function accept(next) {
  if (state && next.revision < state.revision) return;
  const tripChanged = !state || JSON.stringify(next.trip) !== JSON.stringify(state.trip);
  state = next;
  if (tripChanged) renderTrip();
  renderStats();
  renderLists();
}

async function refresh() {
  if (saving) return;
  try {
    const response = await fetch('api/state', {cache:'no-store'});
    if (!response.ok) throw new Error('Unable to load the trip');
    const next = await response.json();
    if (saving) return;
    if (!state || next.revision !== state.revision) accept(next);
    status('Shared · up to date');
    error();
  } catch {
    status('Not connected', true);
    error('Cannot reach the travel app. Check your connection to the demo server; changes need a connection to save.');
  }
}

async function mutate(body) {
  saving++;
  status('Saving…');
  error();
  try {
    const response = await fetch('api/items', {method:'POST', headers:{'Content-Type':'application/json','X-Travel-App':'1'}, body:JSON.stringify(body)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not save');
    accept(result);
    status('Shared · saved');
    return true;
  } catch (e) {
    error(e.message === 'Failed to fetch' ? 'Change not saved. Reconnect to the demo server and try again.' : e.message);
    status('Not saved', true);
    renderLists();
    return false;
  } finally { saving--; }
}

function renderStats() {
  for (const [section, prefix] of [['packing','pack'], ['admin','admin']]) {
    const list = state.items.filter(item => item.section === section);
    const count = list.filter(item => item.done).length;
    $(`#${prefix}-count`).textContent = `${count} / ${list.length} ready`;
    $(`#${prefix}-progress`).max = list.length || 1;
    $(`#${prefix}-progress`).value = count;
  }
  $('#arrival-state').textContent = state.items.find(i => i.id === 'visitor-cards').done ? 'Marked complete ✓' : 'For all five Simpsons →';
}

function renderTrip() {
  const passes = state.trip.boardingPasses;
  $('#boarding-pass-section').hidden = !passes?.flights?.length;
  if (passes?.flights?.length) {
    $('#boarding-pass-bundle').href = 'boarding-passes/' + encodeURIComponent(passes.bundle);
    $('#boarding-passes').innerHTML = passes.flights.map(flight => `<article class="booking">
      <h3>${esc(flight.title)}</h3><p class="small muted">${esc(flight.note)}</p>
      <div class="pdf-links">${flight.passes.map(pass => `<a href="boarding-passes/${encodeURIComponent(pass.file)}" download>${esc(pass.person)} · ${esc(pass.seat)} · PDF ↓</a>`).join('')}</div>
    </article>`).join('');
  }
  $('#bookings').innerHTML = state.trip.bookings.map((booking,index) => `<article class="booking">
    <h3>${esc(booking.title)}</h3><div class="small muted">${esc(booking.subtitle)}</div>
    <div class="reference"><div><small>Booking reference</small><code>${esc(booking.reference)}</code></div><button class="copy-button" data-copy="${index}" aria-label="Copy ${esc(booking.airline)} booking reference">Copy</button></div>
    <div class="pdf-links">${booking.tickets.map(ticket => `<a href="tickets/${encodeURIComponent(ticket.file)}" download>${esc(ticket.person)} · PDF ↓</a>`).join('')}</div>
    </article>`).join('');
  $('#flights').innerHTML = state.trip.flights.map((flight,index) => `<article class="flight"><div class="flight-main">
    <div class="flight-head"><strong>${esc(flight.number)}</strong><span>${esc(flight.carrier)}</span></div>
    <div class="flight-route"><div class="endpoint"><span class="airport">${esc(flight.from)}</span><span class="city">${esc(flight.fromCity)}</span><span class="time">${esc(flight.depart.slice(11))}</span><span class="date">${esc(shortDate(flight.depart))} ${esc(flight.depart.slice(0,4))}</span><span class="terminal">${esc(flight.fromTerminal)}</span></div>
    <span class="flight-arrow" aria-hidden="true">→</span><div class="endpoint"><span class="airport">${esc(flight.to)}</span><span class="city">${esc(flight.toCity)}</span><span class="time">${esc(flight.arrive.slice(11))}</span><span class="date">${esc(shortDate(flight.arrive))} ${esc(flight.arrive.slice(0,4))}</span><span class="terminal">${esc(flight.toTerminal)}</span></div></div>
    <p class="flight-note">${esc(flight.note)}</p></div>${flight.after ? `<div class="flight-after">${esc(flight.after)}</div>` : '<div class="flight-after">Home · Springfield</div>'}</article>`).join('');
}

function renderLists() {
  if (!state || active === 'trip') return;
  const query = $('#search').value.trim().toLowerCase();
  const remaining = $('#remaining').checked;
  const all = state.items.filter(item => item.section === active);
  const shown = all.filter(item => (!remaining || !item.done) && `${item.text} ${item.note || ''} ${item.group}`.toLowerCase().includes(query));
  const groups = [...new Set(shown.map(item => item.group))];
  $('#checklists').innerHTML = groups.length ? groups.map(group => {
    const total = all.filter(i => i.group === group);
    return `<section class="check-group"><div class="group-header"><h3>${esc(group)}</h3><span>${total.filter(i=>i.done).length} / ${total.length}</span></div>
      ${shown.filter(i=>i.group===group).map(item => `<div class="item ${item.done ? 'done' : ''}" data-item="${esc(item.id)}">
      <label><input type="checkbox" data-check="${esc(item.id)}" ${item.done ? 'checked' : ''} aria-label="${esc(item.text)}"><span class="item-body"><span class="item-text">
      ${item.due ? `<span class="due">DO ON ${esc(shortDate(item.due).toUpperCase())}</span>` : ''}<span class="item-title">${esc(item.text)}</span>${item.source === 'suggested' ? '<span class="badge">Added</span>' : ''}
      </span>${item.note ? `<span class="item-note">${esc(item.note)}</span>` : ''}${item.link ? `<a class="item-link" href="${esc(item.link)}" target="_blank" rel="noopener noreferrer">${esc(item.linkLabel || 'More information')} ↗</a>` : ''}</span></label>
      ${item.custom ? `<button class="remove" data-remove="${esc(item.id)}" aria-label="Remove ${esc(item.text)}">×</button>` : ''}</div>`).join('')}</section>`;
  }).join('') : '<p class="empty">No items in this view. Try another search or show completed items.</p>';
}

function navigate(tab, scroll = false) {
  active = tab;
  history.replaceState(null, '', '#' + tab);
  document.querySelectorAll('[data-tab]').forEach(button => {
    button.classList.toggle('active', button.dataset.tab === tab);
    if (button.dataset.tab === tab) button.setAttribute('aria-current','page'); else button.removeAttribute('aria-current');
  });
  $('#trip-panel').hidden = tab !== 'trip';
  $('#list-panel').hidden = tab === 'trip';
  $('#list-title').textContent = tab === 'packing' ? 'Packing checklist' : 'Travel admin';
  $('#list-eyebrow').textContent = tab === 'packing' ? 'GETTING READY' : 'BEFORE YOU GO';
  $('#list-intro').textContent = tab === 'packing' ? 'One shared checklist for Homer, Marge, Bart, Lisa and Maggie. Tick each kit when everything in it is ready. These fictional examples can be replaced with your own packing items.' : 'Keep track of fictional documents, Maggie’s travel arrangements and the Cypress Creek stay. Check items off once you have completed them; checking a box does not submit any form.';
  $('#search').value = '';
  $('#remaining').checked = false;
  renderLists();
  if (scroll) $('.tabs').scrollIntoView({behavior:'smooth',block:'start'});
}

document.addEventListener('click', async event => {
  const nav = event.target.closest('[data-tab],[data-open]');
  if (nav) return navigate(nav.dataset.tab || nav.dataset.open, Boolean(nav.dataset.open));
  if (event.target.closest('.item-link')) event.stopPropagation();
  const copy = event.target.closest('[data-copy]');
  if (copy && state) {
    const value = state.trip.bookings[Number(copy.dataset.copy)].reference;
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(value);
      else {
        const input = document.createElement('textarea'); input.value = value; input.setAttribute('readonly',''); document.body.append(input); input.select(); input.setSelectionRange(0,value.length);
        const ok = document.execCommand('copy'); input.remove(); if (!ok) throw new Error();
      }
      toast('Booking reference copied');
    } catch { toast('Press and hold the booking reference to copy it.'); }
  }
  const remove = event.target.closest('[data-remove]');
  if (remove) { remove.disabled = true; await mutate({action:'remove',id:remove.dataset.remove}); }
});
document.addEventListener('change', async event => {
  if (event.target.matches('[data-check]')) {
    const input = event.target;
    input.disabled = true;
    await mutate({action:'toggle',id:input.dataset.check,done:input.checked});
  }
});
$('#search').addEventListener('input', renderLists);
$('#remaining').addEventListener('change', renderLists);
$('#add-form').addEventListener('submit', async event => {
  event.preventDefault();
  const input = $('#new-item');
  const text = input.value.trim();
  if (!text) return;
  const button = $('#add-form button'); button.disabled = true;
  if (await mutate({action:'add',text,section:active})) { input.value = ''; toast('Added to your shared list'); }
  button.disabled = false;
});
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
window.addEventListener('online', refresh);
navigate(active);
refresh();
setInterval(() => { if (!document.hidden) refresh(); }, 5000);
