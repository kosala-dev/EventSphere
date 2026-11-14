const authStatus = document.getElementById('authStatus');
const eventList = document.getElementById('eventList');
const searchInput = document.getElementById('searchInput');
const venuesPanel = document.getElementById('venuesPanel');
const bookingsPanel = document.getElementById('bookingsPanel');
const dashboardPanel = document.getElementById('dashboardPanel');

const API_BASE = '';
let token = localStorage.getItem('eventsphere_token') || '';

function setToken(newToken) {
  token = newToken;
  localStorage.setItem('eventsphere_token', newToken || '');
  authStatus.textContent = token ? 'Signed in' : 'Not signed in';
}

async function apiFetch(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  };

  if (token && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  const text = await response.text();
  let data = null;

  try {
    data = text ? JSON.parse(text) : null;
  } catch (error) {
    data = text;
  }

  if (!response.ok) {
    const message = data?.detail || data?.message || 'Request failed';
    throw new Error(message);
  }

  return data;
}

function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function renderEvents(events) {
  if (!events || !events.length) {
    eventList.innerHTML = '<div class="empty-state">No events found.</div>';
    return;
  }

  eventList.innerHTML = events
    .map((event) => {
      const categories = (event.ticket_categories || [])
        .map((cat) => `${cat.name} · ${cat.price || 0}`)
        .join('<br>');

      return `
        <article class="event-item">
          <div class="event-thumb">🎟️</div>
          <div class="event-body">
            <div class="event-meta">
              <span class="event-status">${event.status || 'published'}</span>
              <span class="event-price">${event.ticket_categories?.[0]?.price || '—'}</span>
            </div>
            <h4>${event.title}</h4>
            <p>${formatDateTime(event.start_time)} → ${formatDateTime(event.end_time)}</p>
            <p>${event.category || 'General'} · ${event.venue_id || 'Venue'}</p>
            <div class="ticket-summary">${categories || 'No categories'}</div>
            <button class="book-button" data-member="book-${event.id}" data-event-id="${event.id}">Book now</button>
          </div>
        </article>
      `;
    })
    .join('');

  eventList.querySelectorAll('[data-member^="book-"]').forEach((button) => {
    button.addEventListener('click', () => {
      const eventId = button.getAttribute('data-event-id');
      const bookingField = document.querySelector('#bookingForm input[name="event_id"]');
      if (bookingField) bookingField.value = eventId;
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  });
}

function renderVenueList(items) {
  if (!items || !items.length) {
    venuesPanel.innerHTML = '<div class="empty-state">No venues found.</div>';
    return;
  }

  venuesPanel.innerHTML = items
    .map(
      (venue) => `
        <div class="mini-card">
          <strong>${venue.name}</strong>
          <span>${venue.location}</span>
          <span>Capacity: ${venue.capacity}</span>
          <span>Rate: ${venue.hourly_rate}</span>
        </div>
      `
    )
    .join('');
}

function renderBookings(items) {
  if (!items || !items.length) {
    bookingsPanel.innerHTML = '<div class="empty-state">No bookings yet.</div>';
    return;
  }

  bookingsPanel.innerHTML = items
    .map(
      (item) => `
        <div class="mini-card">
          <strong>Booking #${item.id}</strong>
          <span>Event: ${item.event_id}</span>
          <span>Qty: ${item.quantity}</span>
          <span>Status: ${item.status}</span>
          <span>Total: ${item.total_price || 0}</span>
        </div>
      `
    )
    .join('');
}

function renderDashboard(data) {
  if (!data || !data.events_breakdown) {
    dashboardPanel.innerHTML = '<div class="empty-state">No dashboard data.</div>';
    return;
  }

  const parts = data.events_breakdown
    .map(
      (event) => `
        <div class="mini-card">
          <strong>${event.title}</strong>
          <span>Sold: ${event.tickets_sold}</span>
          <span>Revenue: ${event.simulated_revenue}</span>
          <span>Check-ins: ${event.check_ins}</span>
        </div>
      `
    )
    .join('');

  dashboardPanel.innerHTML = `<div><strong>Total events: ${data.total_events}</strong></div>${parts}`;
}

async function loadVenues() {
  try {
    const data = await apiFetch('/venues/');
    renderVenueList(data);
  } catch (error) {
    venuesPanel.innerHTML = `<div class="empty-state">${error.message}</div>`;
  }
}

async function loadEvents(keyword = '') {
  try {
    const query = keyword ? `?keyword=${encodeURIComponent(keyword)}` : '';
    const data = await apiFetch(`/events/search${query}`);
    renderEvents(data);
  } catch (error) {
    eventList.innerHTML = `<div class="empty-state">${error.message}</div>`;
  }
}

async function loadBookings() {
  try {
    const data = await apiFetch('/bookings/history');
    renderBookings(data);
  } catch (error) {
    bookingsPanel.innerHTML = `<div class="empty-state">${error.message}</div>`;
  }
}

async function loadDashboard() {
  try {
    const data = await apiFetch('/dashboard/metrics');
    renderDashboard(data);
  } catch (error) {
    dashboardPanel.innerHTML = `<div class="empty-state">${error.message}</div>`;
  }
}

async function loadAllData() {
  await Promise.allSettled([loadVenues(), loadEvents(), loadBookings(), loadDashboard()]);
}

function showResponse(message) {
  window.alert(message);
}

document.getElementById('registerForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.target;
  const payload = {
    username: form.username.value,
    email: form.email.value,
    password: form.password.value,
  };

  try {
    const result = await apiFetch('/register', {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' },
    });
    showResponse(result.message || 'Registered successfully');
    form.reset();
  } catch (error) {
    showResponse(error.message);
  }
});

document.getElementById('loginForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.target;
  const formData = new URLSearchParams({
    username: form.username.value,
    password: form.password.value,
  });

  try {
    const result = await fetch(`${API_BASE}/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData,
    });

    const data = await result.json();
    if (!result.ok) throw new Error(data.detail || 'Login failed');

    setToken(data.access_token);
    showResponse('Login successful');
    form.reset();
    loadAllData();
  } catch (error) {
    showResponse(error.message);
  }
});

document.getElementById('logoutButton').addEventListener('click', () => {
  setToken('');
  showResponse('Logged out');
});

document.getElementById('reloadEventsBtn').addEventListener('click', () => loadEvents(searchInput.value.trim()));
document.getElementById('refreshAllBtn').addEventListener('click', loadAllData);

searchInput.addEventListener('input', (event) => {
  loadEvents(event.target.value.trim());
});

document.getElementById('venueForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.target;
  const payload = {
    name: form.name.value,
    location: form.location.value,
    capacity: Number(form.capacity.value),
    description: form.description.value,
    image_url: form.image_url.value,
    hourly_rate: Number(form.hourly_rate.value),
    is_open_for_hire: form.is_open_for_hire.checked,
  };

  try {
    const result = await apiFetch('/venues/', {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' },
    });
    showResponse(`Venue created: ${result.name}`);
    form.reset();
    loadVenues();
  } catch (error) {
    showResponse(error.message);
  }
});

document.getElementById('eventForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.target;
  const categories = form.ticket_categories.value ? JSON.parse(form.ticket_categories.value) : [];

  const payload = {
    title: form.title.value,
    category: form.category.value,
    venue_id: Number(form.venue_id.value),
    start_time: form.start_time.value,
    end_time: form.end_time.value,
    description: form.description.value,
    status: form.status.value,
    ticket_categories: categories,
  };

  try {
    const result = await apiFetch('/events/', {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' },
    });
    showResponse(`Event created: ${result.title}`);
    form.reset();
    loadEvents();
  } catch (error) {
    showResponse(error.message);
  }
});

document.getElementById('bookingForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.target;
  const payload = {
    event_id: Number(form.event_id.value),
    ticket_category_id: Number(form.ticket_category_id.value),
    quantity: Number(form.quantity.value),
  };

  try {
    const result = await apiFetch('/bookings/', {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' },
    });
    showResponse(`Booking created: ${result.id}`);
    form.reset();
    loadBookings();
  } catch (error) {
    showResponse(error.message);
  }
});

document.getElementById('privateHireForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.target;
  const payload = {
    venue_id: Number(form.venue_id.value),
    start_time: form.start_time.value,
    end_time: form.end_time.value,
    purpose: form.purpose.value,
    guest_count: Number(form.guest_count.value),
  };

  try {
    const result = await apiFetch('/private-hire/', {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' },
    });
    showResponse(`Private hire request: ${result.decision}`);
    form.reset();
  } catch (error) {
    showResponse(error.message);
  }
});

setToken(token);
loadAllData();
