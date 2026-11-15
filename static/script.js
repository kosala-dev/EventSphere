const authStatus = document.getElementById('authStatus');
const eventList = document.getElementById('eventList');
const searchInput = document.getElementById('searchInput');
const bookingsPanel = document.getElementById('bookingsPanel');
const dashboardPanel = document.getElementById('dashboardPanel');
const hireRequestsPanel = document.getElementById('hireRequestsPanel');
const authFeedback = document.getElementById('authFeedback');
const API_BASE = '';

let token = localStorage.getItem('eventsphere_token') || '';
let currentUser = null;
let venues = [];
let searchTimer;
let pendingBooking = null;
let scannerStream = null;
let scannerFrame = null;
let barcodeDetector = null;
let scannerCanvas = null;
let scannerContext = null;
let lastQrScanAt = 0;
let bookingsLoadPending = false;
let lastBookingsSignature = null;
const ticketQrCache = new Map();

function escapeHTML(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[character]);
}

function setToken(newToken) {
  token = newToken;
  if (token) localStorage.setItem('eventsphere_token', token);
  else localStorage.removeItem('eventsphere_token');
}

async function apiFetch(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !(options.body instanceof URLSearchParams) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  if (token && !headers.Authorization) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!response.ok) {
    const detail = data?.detail;
    const message = typeof detail === 'string' ? detail : detail?.message || data?.message || 'Request failed';
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return data;
}

function formatDateTime(value) {
  if (!value) return 'Date to be announced';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
}

function setFeedback(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle('error', isError);
}

function updateNavigation() {
  const signedIn = Boolean(currentUser);
  document.getElementById('loginLink').hidden = signedIn;
  document.getElementById('registerLink').hidden = signedIn;
  document.getElementById('logoutButton').hidden = !signedIn;
  document.getElementById('workspaceNav').hidden = !signedIn || currentUser.role !== 'attendee';
  document.getElementById('adminNav').hidden = !signedIn || currentUser.role !== 'admin';
  document.getElementById('staffNav').hidden = !signedIn || currentUser.role !== 'staff';
  authStatus.textContent = signedIn
    ? `${currentUser.username} · ${currentUser.role === 'admin' ? 'Organiser' : currentUser.role === 'staff' ? 'Gate staff' : 'Attendee'}`
    : 'Guest';

  document.getElementById('attendeeWorkspace').hidden = !signedIn || currentUser.role !== 'attendee';
  document.getElementById('staffWorkspace').hidden = !signedIn || currentUser.role !== 'staff';
  document.getElementById('adminWorkspace').hidden = !signedIn || currentUser.role !== 'admin';
  document.getElementById('workspaceTitle').textContent = currentUser?.role === 'admin'
    ? 'Organiser console'
    : currentUser?.role === 'staff'
      ? 'Gate check-in'
      : 'Your workspace';
}

function routeToHash() {
  const route = window.location.hash || '#browse';
  const isLogin = route === '#login';
  const isRegister = route === '#register';
  const isAuth = isLogin || isRegister;
  document.getElementById('authView').hidden = !isAuth;
  document.getElementById('publicView').hidden = isAuth;
  document.getElementById('workspace').hidden = isAuth || route !== '#workspace' || !currentUser;
  document.getElementById('loginPage').hidden = !isLogin;
  document.getElementById('registerPage').hidden = !isRegister;
  if (isAuth) setFeedback(authFeedback, '');
  if (route !== '#workspace' && scannerStream) stopQrScanner();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function renderEvents(events) {
  if (!events?.length) {
    eventList.innerHTML = '<div class="empty-state">No events found. Try another search or check back soon.</div>';
    return;
  }

  eventList.innerHTML = events.map((event, index) => {
    const categories = event.ticket_categories || [];
    const initialCategory = categories.find((category) => category.tickets_left > 0);
    const options = categories.map((category) => {
      const label = `${escapeHTML(category.name)} · ${Number(category.price || 0).toFixed(2)}${category.tickets_left <= 0 ? ' · Sold out' : ''}`;
      return `<option value="${category.id}" ${category.tickets_left <= 0 ? 'disabled' : ''} ${category.id === initialCategory?.id ? 'selected' : ''}>${label}</option>`;
    }).join('');
    const action = currentUser?.role === 'attendee'
      ? initialCategory
        ? `<div class="event-footer"><select aria-label="Ticket category for ${escapeHTML(event.title)}" data-category-for="${event.id}">${options}</select><button class="button button-primary" type="button" data-book-event="${event.id}">Book</button></div>`
        : categories.length
          ? '<div class="event-footer"><span class="event-price">No tickets remaining</span><button class="button button-quiet" type="button" disabled>Sold out</button></div>'
          : '<div class="event-footer"><span class="event-price">Ticket categories unavailable</span></div>'
      : `<div class="event-footer"><span class="event-price">${currentUser ? 'Attendee account required' : 'Join us at this event'}</span><a class="button button-primary" href="#${currentUser ? 'workspace' : 'login'}">${currentUser ? 'My workspace' : 'Log in to book'}</a></div>`;

    return `
      <article class="event-card">
        <div class="event-art art-${index % 6}"><span>${escapeHTML((event.category || 'Live').slice(0, 2).toUpperCase())}</span></div>
        <div class="event-content">
          <div class="event-meta"><span class="event-category">${escapeHTML(event.category || 'Event')}</span><span class="event-price">${initialCategory ? `From ${Number(initialCategory.price || 0).toFixed(2)}` : 'Explore event'}</span></div>
          <h3>${escapeHTML(event.title)}</h3>
          <p class="event-description">${escapeHTML(event.description || 'A great event is waiting to be discovered.')}</p>
          <p class="event-date">${escapeHTML(formatDateTime(event.start_time))} · ${escapeHTML(event.venue_name || `Venue #${event.venue_id}`)}</p>
          ${action}
        </div>
      </article>`;
  }).join('');

  eventList.querySelectorAll('[data-book-event]').forEach((button) => {
    button.addEventListener('click', () => {
      const eventId = Number(button.dataset.bookEvent);
      const categoryId = Number(eventList.querySelector(`[data-category-for="${eventId}"]`)?.value);
      const event = events.find((item) => item.id === eventId);
      const category = event?.ticket_categories?.find((item) => item.id === categoryId);
      if (!event || !category || category.tickets_left <= 0) {
        loadEvents(searchInput.value.trim());
        return;
      }

      pendingBooking = {
        eventId,
        eventTitle: event.title,
        categoryId,
        categoryName: category.name,
        price: Number(category.price || 0),
      };
      document.getElementById('bookingSummary').textContent =
        `Book 1 ${category.name} ticket for ${event.title} at ${pendingBooking.price.toFixed(2)}?`;
      setFeedback(document.getElementById('bookingDialogFeedback'), '');
      document.getElementById('bookingConfirmDialog').showModal();
    });
  });
}

document.getElementById('cancelBookingConfirm').addEventListener('click', () => {
  pendingBooking = null;
  document.getElementById('bookingConfirmDialog').close();
});

document.getElementById('bookingConfirmDialog').addEventListener('cancel', () => {
  pendingBooking = null;
});

document.getElementById('confirmBookingBtn').addEventListener('click', async (event) => {
  if (!pendingBooking) return;
  const confirmButton = event.currentTarget;
  const cancelButton = document.getElementById('cancelBookingConfirm');
  confirmButton.disabled = true;
  cancelButton.disabled = true;
  setFeedback(document.getElementById('bookingDialogFeedback'), 'Confirming your ticket…');

  let booking;
  try {
    booking = await apiFetch('/bookings/', {
      method: 'POST',
      body: JSON.stringify({
        event_id: pendingBooking.eventId,
        ticket_category_id: pendingBooking.categoryId,
        quantity: 1,
      }),
    });
  } catch (error) {
    setFeedback(document.getElementById('bookingDialogFeedback'), error.message, true);
    await loadEvents(searchInput.value.trim());
    confirmButton.disabled = false;
    cancelButton.disabled = false;
    return;
  }

  pendingBooking = null;
  document.getElementById('bookingConfirmDialog').close();
  const bookingSuccess = document.getElementById('bookingSuccess');
  setFeedback(bookingSuccess, `Booking #${booking.id} confirmed. Your ticket QR code is in My bookings.`);
  bookingSuccess.hidden = false;
  window.location.hash = '#workspace';
  await Promise.all([
    loadBookings(),
    loadEvents(searchInput.value.trim()),
  ]);
  confirmButton.disabled = false;
  cancelButton.disabled = false;
});

async function loadEvents(keyword = '') {
  try {
    const query = keyword ? `?keyword=${encodeURIComponent(keyword)}` : '';
    renderEvents(await apiFetch(`/events/search${query}`));
  } catch (error) {
    eventList.innerHTML = `<div class="empty-state">${escapeHTML(error.message)}</div>`;
  }
}

function updateVenueSelects() {
  const options = venues.map((venue) => `<option value="${venue.id}">${escapeHTML(venue.name)} · ${escapeHTML(venue.location)}</option>`).join('');
  ['hireVenueSelect', 'eventVenueSelect'].forEach((id) => {
    const select = document.getElementById(id);
    const selected = select.value;
    select.innerHTML = `<option value="">Choose a venue</option>${options}`;
    if (selected) select.value = selected;
  });
}

async function loadVenues() {
  try {
    venues = await apiFetch('/venues/');
    updateVenueSelects();
  } catch (error) {
    if (currentUser?.role === 'admin') window.alert(`Could not load venues: ${error.message}`);
  }
}

async function renderBookings(bookings) {
  if (!bookings?.length) {
    bookingsPanel.innerHTML = '<div class="empty-state">Your bookings will show up here.</div>';
    return true;
  }
  bookingsPanel.innerHTML = bookings.map((booking) => {
    const tickets = booking.status === 'active' ? booking.tickets || [] : [];
    const scannedCount = tickets.filter((ticket) => ticket.is_checked_in).length;
    const scanStatus = scannedCount === 1 ? 'Ticket scanned' : `${scannedCount} tickets scanned`;
    const bookingStatus = scannedCount ? scanStatus : booking.status;
    const bookingAction = booking.status !== 'active'
      ? ''
      : scannedCount
        ? `<span class="status-pill">${escapeHTML(scanStatus)}</span>`
        : `<button class="button button-danger" type="button" data-cancel-booking="${booking.id}">Cancel</button>`;
    return `
      <div class="booking-group">
        <div class="list-row">
          <div><strong>${escapeHTML(booking.event_title || `Event #${booking.event_id}`)} · Booking #${escapeHTML(booking.id)}</strong>
            <small>${escapeHTML(formatDateTime(booking.booked_at))} · ${escapeHTML(booking.quantity)} ticket(s) · ${escapeHTML(booking.ticket_category_name || 'Ticket')} · Total ${escapeHTML(Number(booking.total_price || 0).toFixed(2))} · ${escapeHTML(bookingStatus)}</small></div>
          ${bookingAction}
        </div>
        ${tickets.length ? `<div class="ticket-grid">${tickets.map((ticket) => `
          <article class="ticket-card" data-ticket-id="${escapeHTML(ticket.id)}">
            <div class="ticket-qr">
              <span data-ticket-qr-placeholder>Creating ticket QR…</span>
              <img data-ticket-qr alt="QR code for ticket ${escapeHTML(ticket.id)}" hidden />
            </div>
            <div class="ticket-details">
              <strong>Ticket #${escapeHTML(ticket.id)}${ticket.is_checked_in ? ' · Scanned' : ''}</strong>
              <code data-ticket-code>Loading ticket code…</code>
              <div class="ticket-actions">
                <a class="button button-quiet" data-download-ticket-qr hidden download="eventsphere-ticket-${escapeHTML(ticket.id)}.png">Download QR</a>
                <button class="button button-quiet" type="button" data-copy-ticket-qr disabled>Copy QR code</button>
                <button class="button button-quiet" type="button" data-copy-ticket-code disabled>Copy code</button>
              </div>
              <p class="ticket-feedback" data-ticket-feedback aria-live="polite"></p>
            </div>
          </article>`).join('')}</div>` : ''}
      </div>`;
  }).join('');

  let ticketQrLoadFailed = false;
  const ticketCards = [...bookingsPanel.querySelectorAll('.ticket-card')];
  await Promise.all(ticketCards.map(async (card) => {
    try {
      const ticketId = card.dataset.ticketId;
      let ticket = ticketQrCache.get(ticketId);
      if (!ticket) {
        ticket = await apiFetch(`/tickets/${ticketId}/qr`);
        ticketQrCache.set(ticketId, ticket);
      }
      const image = card.querySelector('[data-ticket-qr]');
      image.src = ticket.qr_code_base64;
      image.hidden = false;
      card.querySelector('[data-ticket-qr-placeholder]').hidden = true;
      card.querySelector('[data-ticket-code]').textContent = ticket.ticket_code;
      card.dataset.ticketCode = ticket.ticket_code;
      const downloadLink = card.querySelector('[data-download-ticket-qr]');
      downloadLink.href = ticket.qr_code_base64;
      downloadLink.hidden = false;
      card.querySelectorAll('[data-copy-ticket-qr], [data-copy-ticket-code]').forEach((button) => {
        button.disabled = false;
      });
    } catch (error) {
      ticketQrLoadFailed = true;
      card.querySelector('[data-ticket-qr-placeholder]').textContent = 'Ticket QR unavailable';
      setFeedback(card.querySelector('[data-ticket-feedback]'), error.message, true);
    }
  }));

  bookingsPanel.querySelectorAll('[data-cancel-booking]').forEach((button) => {
    button.addEventListener('click', async () => {
      if (!window.confirm('Cancel this booking?')) return;
      button.disabled = true;
      try {
        const result = await apiFetch(`/bookings/${button.dataset.cancelBooking}`, { method: 'DELETE' });
        window.alert(`${result.message} ${result.policy_applied}`);
        await loadBookings();
        await loadEvents(searchInput.value.trim());
      } catch (error) {
        window.alert(error.message);
        button.disabled = false;
      }
    });
  });

  bookingsPanel.querySelectorAll('[data-copy-ticket-qr]').forEach((button) => {
    button.addEventListener('click', async () => {
      const card = button.closest('.ticket-card');
      try {
        if (!navigator.clipboard?.write || typeof ClipboardItem === 'undefined') {
          throw new Error('This browser cannot copy QR images. Use Copy code instead.');
        }
        const image = card.querySelector('[data-ticket-qr]');
        const response = await fetch(image.src);
        if (!response.ok) throw new Error('Could not read the ticket QR image.');
        const imageBlob = await response.blob();
        await navigator.clipboard.write([new ClipboardItem({ [imageBlob.type]: imageBlob })]);
        setFeedback(card.querySelector('[data-ticket-feedback]'), 'QR code copied.');
      } catch (error) {
        setFeedback(card.querySelector('[data-ticket-feedback]'), error.message, true);
      }
    });
  });

  bookingsPanel.querySelectorAll('[data-copy-ticket-code]').forEach((button) => {
    button.addEventListener('click', async () => {
      const card = button.closest('.ticket-card');
      try {
        await navigator.clipboard.writeText(card.dataset.ticketCode);
        setFeedback(card.querySelector('[data-ticket-feedback]'), 'Ticket code copied.');
      } catch (error) {
        setFeedback(card.querySelector('[data-ticket-feedback]'), `Could not copy ticket code: ${error.message}`, true);
      }
    });
  });

  return !ticketQrLoadFailed;
}

async function loadBookings() {
  if (currentUser?.role !== 'attendee' || bookingsLoadPending) return;
  bookingsLoadPending = true;
  try {
    const bookings = await apiFetch('/bookings/history');
    const signature = JSON.stringify({ username: currentUser.username, bookings });
    if (signature !== lastBookingsSignature && await renderBookings(bookings)) {
      lastBookingsSignature = signature;
    }
  } catch (error) {
    bookingsPanel.innerHTML = `<div class="empty-state">${escapeHTML(error.message)}</div>`;
  } finally {
    bookingsLoadPending = false;
  }
}

function renderDashboard(data) {
  const events = data?.events_breakdown || [];
  const totalSold = events.reduce((sum, event) => sum + Number(event.tickets_sold || 0), 0);
  const totalRevenue = events.reduce((sum, event) => sum + Number(event.simulated_revenue || 0), 0);
  const totalCheckIns = events.reduce((sum, event) => sum + Number(event.check_ins || 0), 0);
  const salesEvents = [...events].sort((a, b) => Number(b.simulated_revenue || 0) - Number(a.simulated_revenue || 0));
  const maxRevenue = Math.max(0, ...salesEvents.map((event) => Number(event.simulated_revenue) || 0));
  const salesChart = salesEvents.length
    ? `<div class="sales-chart-list">${salesEvents.map((event) => {
      const revenue = Math.max(0, Number(event.simulated_revenue) || 0);
      const barWidth = maxRevenue > 0 ? Math.min(100, (revenue / maxRevenue) * 100) : 0;
      return `<div class="sales-chart-row"><div class="sales-chart-label"><span>${escapeHTML(event.title)}</span><strong>${revenue.toFixed(2)}</strong></div><div class="sales-chart-track" aria-hidden="true"><span style="width:${barWidth}%"></span></div></div>`;
    }).join('')}</div>`
    : '<div class="empty-state">No event sales to chart yet.</div>';
  const checkIns = data?.check_ins_over_time || [];
  const maxCheckIns = Math.max(1, ...checkIns.map((entry) => Number(entry.check_ins) || 0));
  const chartBars = checkIns.map((entry, index) => {
    const count = Math.max(0, Number(entry.check_ins) || 0);
    const x = 26 + index * 96;
    const height = count > 0 ? (count / maxCheckIns) * 132 : 0;
    const y = 178 - height;
    const dateLabel = String(entry.date || '').slice(5).replace('-', '/');
    return `<g><title>${escapeHTML(entry.date)}: ${count} check-ins</title><rect class="checkin-chart-bar" x="${x}" y="${y}" width="46" height="${height}" rx="5"></rect><text class="checkin-chart-value" x="${x + 23}" y="${Math.max(28, y - 8)}" text-anchor="middle">${count}</text><text class="checkin-chart-date" x="${x + 23}" y="202" text-anchor="middle">${escapeHTML(dateLabel)}</text></g>`;
  }).join('');
  const metrics = [
    ['Events', data?.total_events || 0],
    ['Tickets sold', totalSold],
    ['Simulated revenue', totalRevenue.toFixed(2)],
    ['Check-ins', totalCheckIns],
  ];
  dashboardPanel.innerHTML = metrics.map(([label, value]) => `<div class="metric-card"><span>${label}</span><strong>${escapeHTML(value)}</strong></div>`).join('') +
    `<div class="dashboard-charts full-field">
      <article class="surface-card chart-card">
        <div class="card-heading"><div><p class="eyebrow">Sales</p><h3>Revenue by event</h3></div></div>
        ${salesChart}
      </article>
      <article class="surface-card chart-card">
        <div class="card-heading"><div><p class="eyebrow">Attendance</p><h3>Check-ins over time</h3></div></div>
        ${checkIns.length
          ? `<svg class="checkin-chart-svg" viewBox="0 0 650 220" role="img" aria-label="Ticket check-ins per day for the last seven days"><line class="checkin-chart-axis" x1="10" y1="178" x2="640" y2="178"></line>${chartBars}</svg><p class="chart-caption">Daily check-ins · last 7 days</p>`
          : '<div class="empty-state">No check-ins recorded yet.</div>'}
      </article>
    </div>` +
    `<div class="surface-card full-field"><div class="card-heading"><div><p class="eyebrow">Live overview</p><h3>Event performance</h3></div></div><div class="stack-list">${
      events.length ? events.map((event) => `<div class="list-row"><div><strong>${escapeHTML(event.title)}</strong><small>${escapeHTML(event.status)} · ${escapeHTML(event.tickets_sold)} sold · ${escapeHTML(event.check_ins)} checked in</small></div><strong>${escapeHTML(Number(event.simulated_revenue || 0).toFixed(2))}</strong></div>`).join('') : '<div class="empty-state">No events to report yet.</div>'
    }</div></div>`;
}

async function loadDashboard() {
  if (currentUser?.role !== 'admin') return;
  try {
    renderDashboard(await apiFetch('/dashboard/metrics'));
  } catch (error) {
    dashboardPanel.innerHTML = `<div class="empty-state">${escapeHTML(error.message)}</div>`;
  }
}

async function loadHireRequests() {
  if (currentUser?.role !== 'admin') return;
  try {
    const requests = await apiFetch('/private-hire/');
    if (!requests.length) {
      hireRequestsPanel.innerHTML = '<div class="empty-state">No private hire requests need review.</div>';
      return;
    }
    hireRequestsPanel.innerHTML = requests.map((request) => `
      <div class="list-row">
        <div><strong>${escapeHTML(request.venue_name)} · Request #${escapeHTML(request.id)}</strong>
          <small>${escapeHTML(request.username)} · ${escapeHTML(formatDateTime(request.start_time))} · ${escapeHTML(request.guest_count)} guests · ${escapeHTML(request.status)}</small>
          <small>${escapeHTML(request.purpose || 'No purpose provided')}</small></div>
        ${request.status === 'pending_admin_approval' || request.status === 'pending' ? `<span class="approval-actions"><button class="button button-primary" type="button" data-hire-decision="${request.id}" data-approve="true">Approve</button><button class="button button-danger" type="button" data-hire-decision="${request.id}" data-approve="false">Decline</button></span>` : ''}
      </div>`).join('');
    hireRequestsPanel.querySelectorAll('[data-hire-decision]').forEach((button) => {
      button.addEventListener('click', async () => {
        button.disabled = true;
        const requestId = button.dataset.hireDecision;
        const approve = button.dataset.approve;
        try {
          await apiFetch(`/private-hire/${requestId}/admin-decision?approve=${approve}`, { method: 'PATCH' });
          await loadHireRequests();
        } catch (error) {
          window.alert(error.message);
          button.disabled = false;
        }
      });
    });
  } catch (error) {
    hireRequestsPanel.innerHTML = `<div class="empty-state">${escapeHTML(error.message)}</div>`;
  }
}

async function loadAllData() {
  await Promise.all([loadEvents(searchInput.value.trim()), loadVenues(), loadBookings(), loadDashboard(), loadHireRequests()]);
}

async function loadCurrentUser() {
  if (!token) {
    currentUser = null;
    updateNavigation();
    return;
  }
  try {
    currentUser = await apiFetch('/users/me');
  } catch (error) {
    if (error.status !== 401) throw error;
    setToken('');
    currentUser = null;
  }
  updateNavigation();
}

document.getElementById('registerForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = {
    username: form.elements.username.value.trim(),
    email: form.elements.email.value.trim(),
    password: form.elements.password.value,
  };
  try {
    await apiFetch('/register', { method: 'POST', body: JSON.stringify(payload) });
    form.reset();
    setFeedback(authFeedback, 'Account created. Log in to explore your workspace.');
    window.setTimeout(() => { window.location.hash = '#login'; }, 800);
  } catch (error) {
    setFeedback(authFeedback, error.message, true);
  }
});

document.getElementById('loginForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const formData = new URLSearchParams({
    username: form.elements.username.value.trim(),
    password: form.elements.password.value,
  });
  try {
    const result = await apiFetch('/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData,
    });
    setToken(result.access_token);
    await loadCurrentUser();
    form.reset();
    updateNavigation();
    window.location.hash = '#workspace';
    await loadAllData();
  } catch (error) {
    setFeedback(authFeedback, error.message, true);
  }
});

document.getElementById('logoutButton').addEventListener('click', () => {
  setToken('');
  currentUser = null;
  updateNavigation();
  window.location.hash = '#browse';
});

document.getElementById('reloadEventsBtn').addEventListener('click', () => loadEvents(searchInput.value.trim()));
document.getElementById('refreshAllBtn').addEventListener('click', loadAllData);
searchInput.addEventListener('input', () => {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => loadEvents(searchInput.value.trim()), 250);
});
window.addEventListener('hashchange', routeToHash);

document.getElementById('venueForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = {
    name: form.elements.name.value.trim(),
    location: form.elements.location.value.trim(),
    capacity: Number(form.elements.capacity.value),
    description: form.elements.description.value,
    image_url: form.elements.image_url.value,
    hourly_rate: Number(form.elements.hourly_rate.value),
    is_open_for_hire: form.elements.is_open_for_hire.checked,
  };
  try {
    await apiFetch('/venues/', { method: 'POST', body: JSON.stringify(payload) });
    form.reset();
    form.elements.is_open_for_hire.checked = true;
    await loadVenues();
    window.alert('Venue added.');
  } catch (error) {
    window.alert(error.message);
  }
});

document.getElementById('managedAccountForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = {
    username: form.elements.username.value.trim(),
    email: form.elements.email.value.trim(),
    password: form.elements.password.value,
    role: form.elements.role.value,
  };
  const feedback = document.getElementById('managedAccountFeedback');
  try {
    const result = await apiFetch('/admin/users', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    form.reset();
    setFeedback(feedback, `${result.message} The user can now log in.`);
  } catch (error) {
    setFeedback(feedback, error.message, true);
  }
});

document.getElementById('addTicketTier').addEventListener('click', () => {
  const tier = document.createElement('div');
  tier.className = 'ticket-tier';
  tier.innerHTML = '<input name="tier_name" aria-label="Ticket category name" required placeholder="Category e.g. General" /><input name="tier_price" aria-label="Ticket price" type="number" min="0" step="0.01" required placeholder="Price" /><input name="tier_quantity" aria-label="Ticket quantity" type="number" min="1" required placeholder="Quantity" /><button class="remove-tier" type="button" aria-label="Remove ticket category">×</button>';
  tier.querySelector('.remove-tier').addEventListener('click', () => tier.remove());
  document.getElementById('ticketTiers').appendChild(tier);
});

document.getElementById('eventForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const ticketCategories = [...form.querySelectorAll('.ticket-tier')].map((tier) => ({
    name: tier.querySelector('[name="tier_name"]').value.trim(),
    price: Number(tier.querySelector('[name="tier_price"]').value),
    quantity: Number(tier.querySelector('[name="tier_quantity"]').value),
  }));
  const payload = {
    title: form.elements.title.value.trim(),
    category: form.elements.category.value.trim(),
    venue_id: Number(form.elements.venue_id.value),
    start_time: form.elements.start_time.value,
    end_time: form.elements.end_time.value,
    description: form.elements.description.value,
    status: form.elements.status.value,
    ticket_categories: ticketCategories,
  };
  try {
    await apiFetch('/events/', { method: 'POST', body: JSON.stringify(payload) });
    form.reset();
    document.getElementById('ticketTiers').innerHTML = '<div class="ticket-tier"><input name="tier_name" aria-label="Ticket category name" required placeholder="Category e.g. General" /><input name="tier_price" aria-label="Ticket price" type="number" min="0" step="0.01" required placeholder="Price" /><input name="tier_quantity" aria-label="Ticket quantity" type="number" min="1" required placeholder="Quantity" /></div>';
    await Promise.all([loadEvents(), loadDashboard()]);
    window.alert('Event created.');
  } catch (error) {
    window.alert(error.message);
  }
});

document.getElementById('privateHireForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = {
    venue_id: Number(form.elements.venue_id.value),
    start_time: form.elements.start_time.value,
    end_time: form.elements.end_time.value,
    purpose: form.elements.purpose.value.trim(),
    guest_count: Number(form.elements.guest_count.value),
  };
  const feedback = document.getElementById('hireFeedback');
  try {
    const result = await apiFetch('/private-hire/', { method: 'POST', body: JSON.stringify(payload) });
    form.reset();
    setFeedback(feedback, result.message || `Request submitted: ${result.decision}.`);
  } catch (error) {
    setFeedback(feedback, error.message, true);
  }
});

async function verifyTicketFromForm(form) {
  if (!form.elements.expected_event_id.value) {
    setFeedback(document.getElementById('scannerFeedback'), 'Enter the event ID before scanning a ticket.', true);
    return;
  }
  const query = new URLSearchParams({
    ticket_code: form.elements.ticket_code.value.trim(),
    expected_event_id: form.elements.expected_event_id.value,
  });
  const feedback = document.getElementById('scannerFeedback');
  try {
    const result = await apiFetch(`/tickets/scanner/verify?${query}`, { method: 'POST' });
    feedback.textContent = result.message;
    feedback.classList.remove('error');
    form.elements.ticket_code.value = '';
  } catch (error) {
    setFeedback(feedback, error.message, true);
  }
}

document.getElementById('scannerForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  await verifyTicketFromForm(event.currentTarget);
});

async function scanQrFrame() {
  if (!scannerStream) return;
  try {
    const video = document.getElementById('scannerVideo');
    if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
      let code;
      if (barcodeDetector) {
        const detections = await barcodeDetector.detect(video);
        code = detections.find((detection) => detection.rawValue)?.rawValue;
      } else if (video.videoWidth > 0) {
        const now = performance.now();
        if (now - lastQrScanAt >= 150) {
          lastQrScanAt = now;
          const scale = Math.min(1, 640 / Math.max(video.videoWidth, video.videoHeight));
          const width = Math.max(1, Math.round(video.videoWidth * scale));
          const height = Math.max(1, Math.round(video.videoHeight * scale));
          if (!scannerCanvas) {
            scannerCanvas = document.createElement('canvas');
            scannerContext = scannerCanvas.getContext('2d', { willReadFrequently: true });
          }
          scannerCanvas.width = width;
          scannerCanvas.height = height;
          scannerContext.drawImage(video, 0, 0, width, height);
          const imageData = scannerContext.getImageData(0, 0, width, height);
          code = window.jsQR(imageData.data, width, height, { inversionAttempts: 'dontInvert' })?.data;
        }
      }
      if (code) {
        stopQrScanner();
        const form = document.getElementById('scannerForm');
        form.elements.ticket_code.value = code;
        await verifyTicketFromForm(form);
        return;
      }
    }
    scannerFrame = window.requestAnimationFrame(scanQrFrame);
  } catch (error) {
    stopQrScanner();
    setFeedback(document.getElementById('cameraFeedback'), `QR scan failed: ${error.message}`, true);
  }
}

function stopQrScanner() {
  if (scannerFrame !== null) window.cancelAnimationFrame(scannerFrame);
  scannerFrame = null;
  if (scannerStream) scannerStream.getTracks().forEach((track) => track.stop());
  scannerStream = null;
  const video = document.getElementById('scannerVideo');
  video.pause();
  video.srcObject = null;
  video.hidden = true;
  document.getElementById('startQrScanner').hidden = false;
  document.getElementById('stopQrScanner').hidden = true;
}

document.getElementById('startQrScanner').addEventListener('click', async () => {
  const feedback = document.getElementById('cameraFeedback');
  const supportsBarcodeDetector = typeof window.BarcodeDetector === 'function';
  if (!supportsBarcodeDetector && typeof window.jsQR !== 'function') {
    setFeedback(feedback, 'Camera QR scanning is not supported in this browser. Enter the ticket code manually.', true);
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    setFeedback(feedback, 'Camera access is unavailable. Use a secure connection or enter the ticket code manually.', true);
    return;
  }

  try {
    barcodeDetector = supportsBarcodeDetector
      ? new window.BarcodeDetector({ formats: ['qr_code'] })
      : null;
    lastQrScanAt = 0;
    scannerStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' } },
      audio: false,
    });
    const video = document.getElementById('scannerVideo');
    video.srcObject = scannerStream;
    await video.play();
    video.hidden = false;
    document.getElementById('startQrScanner').hidden = true;
    document.getElementById('stopQrScanner').hidden = false;
    setFeedback(feedback, 'Point the camera at the ticket QR code.');
    scannerFrame = window.requestAnimationFrame(scanQrFrame);
  } catch (error) {
    stopQrScanner();
    setFeedback(feedback, `Could not start the camera: ${error.message}`, true);
  }
});

document.getElementById('stopQrScanner').addEventListener('click', stopQrScanner);

document.getElementById('year').textContent = new Date().getFullYear();

window.setInterval(() => {
  if (
    document.visibilityState === 'visible'
    && window.location.hash === '#workspace'
    && currentUser?.role === 'attendee'
  ) {
    loadBookings();
  }
}, 5000);

(async function initialize() {
  try {
    await loadCurrentUser();
  } catch (error) {
    window.alert(`Unable to verify your saved sign-in: ${error.message}`);
    currentUser = null;
  }
  updateNavigation();
  routeToHash();
  await loadAllData();
})();
