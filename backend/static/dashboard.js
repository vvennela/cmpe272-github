(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const state = { hubs: [], routes: [], shuttles: [], selected: new URLSearchParams(location.search).get('hub'), loaded: false, loading: false, nearestBusy: false, nearestVersion: 0, nearestController: null };
  const theme = getComputedStyle(document.documentElement);
  const color = (name) => theme.getPropertyValue(`--${name}`).trim();
  const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
  let map, layers, userLayer, tileErrors = 0;
  const text = (tag, value, className) => {
    const element = document.createElement(tag);
    element.textContent = value;
    if (className) element.className = className;
    return element;
  };
  const latLng = (position) => [position.lat, position.lng];
  const time = (value) => {
    const [hours, minutes] = value.split(':');
    const hour = Number(hours);
    return `${hour % 12 || 12}:${minutes} ${hour >= 12 ? 'PM' : 'AM'}`;
  };
  function setStatus(message, error = false) {
    $('network-status').textContent = message;
    $('network-status').classList.toggle('error', error);
  }
  async function request(path, options = {}) {
    const timeout = new AbortController();
    const timer = setTimeout(() => timeout.abort(), 12000);
    const signal = options.signal ? AbortSignal.any([options.signal, timeout.signal]) : timeout.signal;
    try {
      const response = await fetch(path, { ...options, signal, cache: 'no-store' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'The request failed. Try again.');
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('The request took too long. Try again.');
      if (error instanceof TypeError) throw new Error('Cannot connect. Check your connection and try again.');
      throw error;
    } finally { clearTimeout(timer); }
  }
  function initMap() {
    if (!window.L) {
      $('map-status').textContent = 'The map could not load. Hub details and schedules are available below.';
      $('fit-map').disabled = true;
      return;
    }
    map = L.map('map', { scrollWheelZoom: false }).setView([37.37, -121.95], 11);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).on('tileerror', () => {
      tileErrors += 1;
      if (tileErrors >= 3) $('map-status').textContent = 'Map background unavailable. Network markers and schedules are still available.';
    }).on('tileload', () => {
      tileErrors = 0;
      $('map-status').textContent = '';
    }).addTo(map);
    layers = L.layerGroup().addTo(map);
    userLayer = L.layerGroup().addTo(map);
  }
  function fitMap() {
    if (!map) return;
    const points = [...state.hubs, ...state.shuttles, ...state.routes.flatMap((route) => route.stops)].map((item) => latLng(item.position));
    if (points.length) map.fitBounds(points, { padding: [45, 45], maxZoom: 13, animate: false });
  }
  function renderMap(fit = false) {
    if (!map) return;
    layers.clearLayers();
    const chosenRoutes = state.routes.filter((route) => route.hubId === state.selected);
    chosenRoutes.forEach((route) => {
      const hub = state.hubs.find((item) => item.id === route.hubId);
      if (!hub) return;
      const points = [latLng(hub.position), ...route.stops.map((stop) => latLng(stop.position))];
      L.polyline(points, { color: color('brand'), weight: 3, dashArray: '7 7', opacity: 0.7 }).addTo(layers);
      route.stops.forEach((stop) => L.circleMarker(latLng(stop.position), { radius: 6, color: color('brand'), weight: 2, fillColor: color('surface'), fillOpacity: 1 }).bindTooltip(text('span', stop.name)).addTo(layers));
    });
    state.hubs.forEach((hub) => {
      const icon = L.divIcon({ className: '', html: `<span class="hub-marker${hub.id === state.selected ? ' selected' : ''}">H</span>`, iconSize: [30, 30], iconAnchor: [15, 15] });
      L.marker(latLng(hub.position), { icon, title: `Select ${hub.name}`, alt: hub.name, keyboard: true }).bindTooltip(text('span', hub.name)).on('click', () => selectHub(hub.id)).addTo(layers);
    });
    state.shuttles.forEach((shuttle) => {
      const icon = L.divIcon({ className: '', html: '<span class="shuttle-marker">↗</span>', iconSize: [30, 30], iconAnchor: [15, 15] });
      L.marker(latLng(shuttle.position), { icon, title: `Shuttle ${shuttle.id} · Last reported position`, keyboard: true }).bindPopup(text('span', `Shuttle ${shuttle.id} · Last reported position. Position time unavailable.`)).addTo(layers);
    });
    if (fit) fitMap();
  }
  function renderHubs() {
    $('hub-count').textContent = state.hubs.length;
    const list = $('hub-list');
    list.replaceChildren();
    if (!state.hubs.length) {
      list.append(text('p', 'No pickup hubs are configured yet. Refresh after a network is added.', 'empty'));
      return;
    }
    for (const hub of state.hubs) {
      const routes = state.routes.filter((route) => route.hubId === hub.id);
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'hub-card';
      button.setAttribute('aria-pressed', String(hub.id === state.selected));
      const top = text('span', '', 'hub-card-top');
      top.append(text('span', { BART: 'BART station', BUS_STOP: 'Bus stop', COMPANY: 'Company' }[hub.type] || 'Pickup hub', 'tag'));
      const check = text('span', hub.id === state.selected ? '✓' : '↗', 'hub-check');
      check.setAttribute('aria-hidden', 'true');
      top.append(check);
      button.append(top, text('strong', hub.name), text('span', hub.address, 'address'), text('span', routes.length ? `${routes.length} shuttle ${routes.length === 1 ? 'route' : 'routes'}` : 'No shuttle routes scheduled', 'route-count'));
      button.addEventListener('click', () => selectHub(hub.id));
      list.append(button);
    }
  }
  function renderSchedule() {
    const panel = $('schedule');
    panel.replaceChildren();
    const hub = state.hubs.find((item) => item.id === state.selected);
    if (!hub) {
      panel.append(text('p', 'Select a pickup hub to see its shuttle schedule.', 'empty'));
      return;
    }
    panel.append(text('p', hub.name, 'selected-hub'));
    const routes = state.routes.filter((route) => route.hubId === hub.id);
    if (!routes.length) {
      const empty = text('div', '', 'empty');
      empty.append(text('strong', 'No shuttles scheduled'), text('p', 'This hub is on the network, but has no assigned shuttle routes. Choose another pickup hub.'));
      panel.append(empty);
    }
    for (const route of routes) {
      const card = text('article', '', 'route-card');
      const top = text('div', '', 'route-top');
      const available = Math.max(0, route.capacity - route.riders);
      top.append(text('h3', `Shuttle ${route.shuttleId} · Route ${route.id}`, 'route-title'), text('span', available ? `${available} seats available` : 'Shuttle full', 'seats'));
      const times = text('div', '', 'times');
      const departure = text('div', time(route.departure), 'time');
      departure.append(text('span', 'Departure', 'time-label'));
      const arrival = text('div', time(route.arrival), 'time');
      arrival.append(text('span', 'Arrival', 'time-label'));
      const line = text('div', '', 'journey-line');
      const minutes = (value) => { const [h, m] = value.split(':').map(Number); return h * 60 + m; };
      const duration = (minutes(route.arrival) - minutes(route.departure) + 1440) % 1440;
      line.append(text('span', `${duration} min`));
      times.append(departure, line, arrival);
      const stops = text('ol', '', 'stops');
      stops.setAttribute('aria-label', 'Scheduled stop order');
      [hub, ...route.stops].forEach((stop) => stops.append(text('li', stop.name)));
      const notes = text('div', '', 'route-notes');
      notes.append(text('p', `${route.riders} assigned riders / ${route.capacity} seats`));
      const stored = state.shuttles.find((shuttle) => shuttle.id === route.shuttleId);
      notes.append(text('p', stored ? `Last reported: ${stored.position.lat.toFixed(4)}, ${stored.position.lng.toFixed(4)}. Position time unavailable.` : 'Shuttle position unavailable.'));
      card.append(top, times, stops, notes);
      panel.append(card);
    }
    if (hub.parking || hub.bikeParking) {
      const access = text('div', '', 'route-notes');
      if (hub.parking) access.append(text('p', `Parking: ${hub.parking}`));
      if (hub.bikeParking) access.append(text('p', `Bike parking: ${hub.bikeParking}`));
      panel.append(access);
    }
  }
  function selectHub(id, announce = true) {
    state.selected = id;
    const url = new URL(location.href);
    if (id) url.searchParams.set('hub', id); else url.searchParams.delete('hub');
    history.replaceState(null, '', url);
    // Keep keyboard focus on the equivalent hub button when rendering selection.
    const focusedHub = document.activeElement.closest?.('.hub-card');
    const index = focusedHub ? [...$('hub-list').children].indexOf(focusedHub) : -1;
    renderHubs(); renderSchedule(); renderMap();
    updateDirectionsHub(state.hubs.find((hub) => hub.id === id));
    if (index >= 0) $('hub-list').children[index]?.focus({ preventScroll: true });
    if (announce) {
      const hub = state.hubs.find((item) => item.id === id);
      if (hub) setStatus(`Showing schedules for ${hub.name}.`);
    }
  }
  async function loadNetwork() {
    if (state.loading) return;
    state.loading = true;
    $('refresh').disabled = true;
    $('workspace').setAttribute('aria-busy', 'true');
    setStatus(state.loaded ? 'Refreshing network… Existing data stays visible.' : 'Loading shuttle network…');
    try {
      const [networkResult, shuttleResult] = await Promise.allSettled([request('/api/map/network'), request('/api/map/shuttles')]);
      if (networkResult.status === 'rejected') throw networkResult.reason;
      const network = networkResult.value;
      state.hubs = network.hubs;
      state.routes = network.routes;
      state.shuttles = shuttleResult.status === 'fulfilled' ? shuttleResult.value.shuttles : [];
      if (!state.hubs.some((hub) => hub.id === state.selected)) state.selected = state.hubs[0]?.id || null;
      state.loaded = true;
      selectHub(state.selected, false);
      fitMap();
      $('updated').textContent = `Loaded ${new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit', timeZone: 'America/Los_Angeles', timeZoneName: 'short' }).format(new Date())}`;
      setStatus(shuttleResult.status === 'rejected' ? 'Schedules loaded. Shuttle positions are unavailable; refresh to try again.' : `${state.hubs.length} pickup hubs · ${state.routes.length} shuttle ${state.routes.length === 1 ? 'route' : 'routes'} · ${state.shuttles.length} stored shuttle ${state.shuttles.length === 1 ? 'position' : 'positions'}`);
    } catch (error) {
      setStatus(`${error.message} ${state.loaded ? 'Showing the previously loaded network.' : 'Use Refresh network to retry.'}`, true);
      if (!state.loaded) {
        $('hub-list').replaceChildren(text('p', 'Pickup hubs could not load. Use Refresh network to try again.', 'empty'));
        $('schedule').replaceChildren(text('p', 'Schedules will appear when the network is available.', 'empty'));
      }
    } finally {
      state.loading = false;
      $('refresh').disabled = false;
      $('workspace').setAttribute('aria-busy', 'false');
    }
  }
  function nearestBusy(busy) {
    state.nearestBusy = busy;
    $('locate').disabled = busy;
    $('find-coordinates').disabled = busy;
    $('coordinates').setAttribute('aria-busy', String(busy));
  }
  async function findNearest(position, version) {
    state.nearestController?.abort();
    state.nearestController = new AbortController();
    try {
      const result = await request('/api/map/hubs/nearest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(position), signal: state.nearestController.signal });
      if (version !== state.nearestVersion) return;
      if (!state.loaded) await loadNetwork();
      if (!state.hubs.some((hub) => hub.id === result.hub.id)) throw new Error('The network has changed. Refresh the network and try again.');
      selectHub(result.hub.id);
      $('location-status').textContent = `${result.hub.name} is ${number.format(result.distanceKm)} km away in a straight line.`;
      if (map) {
        userLayer.clearLayers();
        L.circleMarker(latLng(position), { radius: 7, color: color('ink'), fillColor: color('surface'), fillOpacity: 1 }).bindTooltip(text('span', 'Your selected location')).addTo(userLayer);
        map.fitBounds([latLng(position), latLng(result.hub.position)], { padding: [55, 55], maxZoom: 14, animate: false });
      }
    } catch (error) {
      if (version === state.nearestVersion) $('location-status').textContent = error.message;
    } finally {
      if (version === state.nearestVersion) nearestBusy(false);
    }
  }
  $('refresh').addEventListener('click', loadNetwork);
  $('fit-map').addEventListener('click', fitMap);
  $('locate').addEventListener('click', () => {
    if (state.nearestBusy) return;
    if (!navigator.geolocation) {
      $('location-status').textContent = 'Location is unavailable in this browser. Use coordinates instead.';
      return;
    }
    const version = ++state.nearestVersion;
    nearestBusy(true);
    $('location-status').textContent = 'Waiting for your location…';
    navigator.geolocation.getCurrentPosition((result) => {
      if (version !== state.nearestVersion) return;
      $('location-status').textContent = 'Finding your nearest hub…';
      findNearest({ lat: result.coords.latitude, lng: result.coords.longitude }, version);
    }, (error) => {
      if (version !== state.nearestVersion) return;
      nearestBusy(false);
      $('location-status').textContent = error.code === 1 ? 'Location access was denied. Use coordinates instead, or allow location in your browser.' : 'Could not get your location. Try again or use coordinates instead.';
    }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 });
  });
  $('coordinates').addEventListener('submit', (event) => {
    event.preventDefault();
    if (state.nearestBusy) return;
    const fields = [['latitude', 'Latitude', 90], ['longitude', 'Longitude', 180]];
    let invalid;
    const values = fields.map(([id, name, limit]) => {
      const field = $(id);
      const value = field.value.trim();
      const valid = value !== '' && /^[-+]?(?:\d+\.?\d*|\.\d+)$/.test(value) && Number.isFinite(Number(value)) && Math.abs(Number(value)) <= limit;
      field.setAttribute('aria-invalid', String(!valid));
      if (!valid && !invalid) invalid = { field, message: `${name} must be a number from ${-limit} to ${limit}.` };
      return Number(value);
    });
    $('coordinate-error').textContent = invalid?.message || '';
    if (invalid) { invalid.field.focus(); return; }
    nearestBusy(true);
    $('location-status').textContent = 'Finding your nearest hub…';
    findNearest({ lat: values[0], lng: values[1] }, ++state.nearestVersion);
  });
  // Directions belong to the selected hub and input values, never to a stale response.
  const directions = { hub: null, signature: '', version: 0, controller: null, pending: false, map: null, line: null, mapsPromise: null };
  function directionsMessage(message, error = false) {
    $('directions-status').textContent = message;
    $('directions-status').classList.toggle('error', error);
  }
  function clearDirections(message) {
    directions.version += 1;
    directions.controller?.abort();
    directions.pending = false;
    $('directions-form').setAttribute('aria-busy', 'false');
    $('get-directions').disabled = !directions.hub;
    directions.line?.setMap(null);
    directions.line = null;
    $('directions-map').hidden = true;
    $('directions-map-status').textContent = '';
    $('directions-results').replaceChildren(text('p', 'Enter a starting address to see travel time, distance, and directions to the selected hub.', 'empty'));
    directionsMessage(message);
  }
  function updateDirectionsHub(hub) {
    const signature = hub ? JSON.stringify([hub.id, hub.name, hub.position]) : '';
    directions.hub = hub || null;
    $('directions-destination').textContent = hub ? `To: ${hub.name}` : 'Choose a pickup hub above.';
    if (signature !== directions.signature) {
      directions.signature = signature;
      clearDirections(hub ? 'Ready for your starting address.' : 'Select a hub to get started.');
    }
    $('get-directions').disabled = !hub || directions.pending;
  }
  function loadGoogleMap() {
    if (window.google?.maps?.Map) return Promise.resolve(window.google.maps);
    if (directions.mapsPromise) return directions.mapsPromise;
    const key = document.querySelector('.directions-panel').dataset.browserKey;
    if (!key) return Promise.reject(new Error('Route map unavailable here. Use the Google Maps link to view your trip.'));
    directions.mapsPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      const timer = setTimeout(() => fail(), 12000);
      function fail() {
        clearTimeout(timer);
        script.remove();
        directions.mapsPromise = null;
        reject(new Error('The route map could not load. Use the Google Maps link or get directions again to retry.'));
      }
      window.shuttleScopeGoogleReady = () => {
        clearTimeout(timer);
        resolve(window.google.maps);
      };
      window.gm_authFailure = () => {
        fail();
        $('directions-map').hidden = true;
        $('directions-map-status').textContent = 'The route map is unavailable. Use the Google Maps link to view your trip.';
      };
      script.async = true;
      script.onerror = fail;
      const params = new URLSearchParams({ key, loading: 'async', callback: 'shuttleScopeGoogleReady', libraries: 'geometry', v: 'quarterly', language: 'en', region: 'US' });
      script.src = `https://maps.googleapis.com/maps/api/js?${params}`;
      document.head.append(script);
    });
    return directions.mapsPromise;
  }
  async function drawDirections(route, version) {
    const encoded = route.polyline?.encodedPolyline;
    if (!encoded) {
      $('directions-map-status').textContent = 'No map path was returned. Travel details are available above.';
      return;
    }
    $('directions-map-status').textContent = 'Loading route map…';
    try {
      const maps = await loadGoogleMap();
      if (version !== directions.version) return;
      const path = maps.geometry.encoding.decodePath(encoded);
      if (path.length < 2) throw new Error('The route map path is unavailable. Use the Google Maps link to view your trip.');
      $('directions-map').hidden = false;
      if (!directions.map) directions.map = new maps.Map($('directions-map'), { center: directions.hub.position, zoom: 12, mapTypeControl: false, streetViewControl: false, gestureHandling: 'cooperative' });
      directions.line?.setMap(null);
      directions.line = new maps.Polyline({ map: directions.map, path, strokeColor: color('brand'), strokeWeight: 5, strokeOpacity: 0.9 });
      const bounds = new maps.LatLngBounds();
      path.forEach((point) => bounds.extend(point));
      directions.map.fitBounds(bounds, 35);
      $('directions-map-status').textContent = '';
    } catch (error) {
      if (version === directions.version) {
        $('directions-map').hidden = true;
        $('directions-map-status').textContent = error.message;
      }
    }
  }
  function renderDirections(route, hub, origin, mode) {
    const results = $('directions-results');
    results.replaceChildren();
    const heading = text('h3', `Your route to ${hub.name}`);
    const duration = /^([0-9]+(?:\.[0-9]+)?)s$/.exec(route.duration || '');
    const durationLabel = duration ? `${Math.max(1, Math.ceil(Number(duration[1]) / 60))} min` : 'Travel time unavailable';
    const distanceLabel = typeof route.distanceMeters === 'number' ? `${number.format(route.distanceMeters / 1000)} km` : 'Distance unavailable';
    results.append(heading, text('p', `${durationLabel} · ${distanceLabel} · ${{ WALK: 'Walking', BICYCLE: 'Cycling', TRANSIT: 'Transit', DRIVE: 'Driving' }[mode]}`, 'directions-summary'));
    const attribution = text('p', 'Google Maps', 'google-attribution');
    attribution.setAttribute('translate', 'no');
    results.append(attribution);
    const link = text('a', 'Open trip in Google Maps', 'directions-link');
    const params = new URLSearchParams({ api: '1', origin, destination: `${hub.position.lat},${hub.position.lng}`, travelmode: { WALK: 'walking', BICYCLE: 'bicycling', TRANSIT: 'transit', DRIVE: 'driving' }[mode] });
    link.href = `https://www.google.com/maps/dir/?${params}`;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    results.append(link);
    for (const warning of route.warnings || []) results.append(text('p', warning, 'directions-warning'));
    const steps = (route.legs || []).flatMap((leg) => leg.steps || []);
    const list = text('ol', '', 'directions-steps');
    list.setAttribute('aria-label', 'Travel instructions');
    for (const step of steps) {
      const transit = step.transitDetails;
      let instruction = step.navigationInstruction?.instructions;
      if (transit) {
        const line = transit.transitLine?.nameShort || transit.transitLine?.name || 'transit';
        const from = transit.stopDetails?.departureStop?.name;
        const to = transit.stopDetails?.arrivalStop?.name;
        instruction = `Take ${line}${transit.headsign ? ` toward ${transit.headsign}` : ''}${from ? ` from ${from}` : ''}${to ? ` to ${to}` : ''}.`;
      }
      if (instruction) list.append(text('li', instruction));
    }
    if (list.children.length) results.append(list);
    else results.append(text('p', 'Detailed instructions were not returned. Use the Google Maps link for navigation.', 'directions-help'));
    results.append(text('p', 'Travel time is an estimate to the pickup hub, not a guarantee of catching your shuttle.', 'directions-help'));
  }
  $('directions-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    if (event.isComposing || directions.pending) return;
    const field = $('directions-origin');
    const origin = field.value.trim();
    const invalid = !origin || origin.length > 500;
    field.setAttribute('aria-invalid', String(invalid));
    $('directions-error').textContent = invalid ? 'Enter a starting address of 500 characters or fewer.' : '';
    if (invalid) { field.focus(); return; }
    if (!directions.hub) { directionsMessage('Select a pickup hub above first.', true); return; }
    clearDirections('Finding directions…');
    const version = directions.version;
    const hub = directions.hub;
    const mode = document.querySelector('input[name="travelMode"]:checked').value;
    directions.controller = new AbortController();
    directions.pending = true;
    $('get-directions').disabled = true;
    $('directions-form').setAttribute('aria-busy', 'true');
    $('directions-results').replaceChildren(text('p', 'Finding your route…', 'empty'));
    try {
      const data = await request(`/api/map/hubs/${encodeURIComponent(hub.id)}/directions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ origin, travelMode: mode }), signal: directions.controller.signal });
      if (version !== directions.version) return;
      if (!Array.isArray(data.routes)) throw new Error('Directions could not be read. Try again.');
      if (!data.routes.length) {
        $('directions-results').replaceChildren(text('p', 'No route found for this trip. Try a different starting address or travel mode.', 'empty'));
        directionsMessage('No route found. Change your address or travel mode and try again.');
        return;
      }
      renderDirections(data.routes[0], hub, origin, mode);
      directionsMessage(`Directions ready for ${hub.name}.`);
      // Map loading has its own timeout and does not block readable directions.
      void drawDirections(data.routes[0], version);
    } catch (error) {
      if (version !== directions.version) return;
      const message = error.message === 'Google Maps is not configured.' ? 'Directions are not configured yet. The project owner needs to enable Google Routes for this feature.' : error.message;
      $('directions-results').replaceChildren(text('p', 'Your route could not load. Keep your address and try Get directions again.', 'empty'));
      directionsMessage(message, true);
    } finally {
      if (version === directions.version) {
        directions.pending = false;
        $('get-directions').disabled = !directions.hub;
        $('directions-form').setAttribute('aria-busy', 'false');
      }
    }
  });
  $('directions-origin').addEventListener('input', () => {
    $('directions-origin').setAttribute('aria-invalid', 'false');
    $('directions-error').textContent = '';
    clearDirections('Starting address changed. Get directions to update your trip.');
  });
  document.querySelectorAll('input[name="travelMode"]').forEach((input) => input.addEventListener('change', () => clearDirections('Travel mode changed. Get directions to update your trip.')));

  window.addEventListener('offline', () => setStatus('You are offline. Showing any previously loaded network. Reconnect and refresh to update.', true));
  $('refresh').disabled = false;
  $('locate').disabled = false;
  $('fit-map').disabled = false;
  initMap();
  loadNetwork();
})();
