// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function () {
    if (typeof L === 'undefined') {
        console.error('Leaflet library not loaded');
        alert('Error: Leaflet mapping library not loaded. Please check your internet connection.');
        return;
    }

    const CITIES_URL = '/api/cities/';
    const weatherUrl = (cityId) => `/api/weather/${cityId}/`;
    const forecastUrl = (cityId) => `/api/forecast/${cityId}/`;
    // XWeather's WxBlox icon CDN path
    const ICON_BASE_URL = 'https://cdn.aerisapi.com/wxblox/icons/';

    // Initialize the map showing the whole world
    const map = L.map('map').setView([30, 10], 2);

    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19,
    }).addTo(map);

    // Store markers and the loaded cities for reference
    const markers = {};
    let allCities = [];

    // What each city's popup is showing: { weather, forecast, forecastError, tab }
    const popupState = {};

    // Enhancement 4: temperature unit preference. The server always returns
    // Celsius; the conversion happens only in the browser.
    let useFahrenheit = false;

    // Custom icon for city markers
    const cityIcon = L.divIcon({
        className: 'custom-div-icon',
        html: `<div style="
            background-color: #667eea;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            border: 3px solid white;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            cursor: pointer;
        "></div>`,
        iconSize: [30, 30],
        iconAnchor: [15, 15]
    });

    // Text from external APIs is escaped before it is placed in popup HTML
    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, (character) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[character]));
    }

    function isMissing(value) {
        return value === null || value === undefined || Number.isNaN(Number(value));
    }

    // Format a Celsius value in the selected unit: F = (C × 9/5) + 32
    function formatTemp(celsius) {
        if (isMissing(celsius)) return '–';
        const value = useFahrenheit ? (Number(celsius) * 9 / 5) + 32 : Number(celsius);
        return `${value.toFixed(1)}°${useFahrenheit ? 'F' : 'C'}`;
    }

    // Format any other number, showing a dash when the API sent no value
    function formatNumber(value, unit) {
        return isMissing(value) ? '–' : `${Number(value)}${unit}`;
    }

    function iconUrl(icon) {
        return icon ? ICON_BASE_URL + encodeURIComponent(icon) : '';
    }

    // Fetch JSON from our Django API; on failure, throw the server's safe error message
    async function fetchJson(url) {
        const response = await fetch(url);
        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(data.error || `Request failed (HTTP ${response.status})`);
        }
        return data;
    }

    // Fetch and display cities
    async function loadCities() {
        try {
            const response = await fetch(CITIES_URL);
            if (!response.ok) {
                throw new Error(`Failed to fetch cities (HTTP ${response.status})`);
            }

            const cities = await response.json();
            console.log(`Loaded ${cities.length} cities`);

            if (cities.length === 0) {
                showMapMessage('No cities found. Run: docker compose run --rm web python manage.py populate_cities');
                return;
            }

            allCities = cities;
            cities.forEach(addCityMarker);
            fillSearchOptions(cities);
        } catch (error) {
            console.error('Error loading cities:', error);
            showMapMessage(`Failed to load cities: ${error.message}`);
        }
    }

    // Show a message in a popup in the middle of the map
    function showMapMessage(message) {
        L.popup()
            .setLatLng(map.getCenter())
            .setContent(`<div class="error-message">${escapeHtml(message)}</div>`)
            .openOn(map);
    }

    // Add a marker for a city
    function addCityMarker(city) {
        const marker = L.marker([city.latitude, city.longitude], {
            icon: cityIcon,
            title: `${city.name}, ${city.country}`
        }).addTo(map);

        marker.on('click', () => fetchWeatherData(city.id, marker));
        markers[city.id] = marker;
    }

    // Fetch weather data for a city from OUR Django API (server-side proxy to XWeather)
    async function fetchWeatherData(cityId, marker) {
        showLoading();

        try {
            const data = await fetchJson(weatherUrl(cityId));
            popupState[cityId] = { weather: data, forecast: null, forecastError: null, tab: 'current' };
            displayWeatherPopup(cityId, marker);
        } catch (error) {
            console.error('Error fetching weather:', error);
            delete popupState[cityId];
            displayErrorPopup(marker, error.message);
        } finally {
            hideLoading();
        }
    }

    // Enhancement 1: fetch the 3-day forecast the first time the Forecast tab is opened
    async function fetchForecastData(cityId, marker) {
        const state = popupState[cityId];

        try {
            const data = await fetchJson(forecastUrl(cityId));
            state.forecast = data.days || [];
        } catch (error) {
            console.error('Error fetching forecast:', error);
            state.forecastError = error.message;
        }

        // Redraw only if this popup is still the one on screen
        if (popupState[cityId] === state && marker.isPopupOpen()) {
            displayWeatherPopup(cityId, marker);
        }
    }

    // HTML for the "Current" tab
    function currentTabHtml(data) {
        const description = escapeHtml(data.description);
        const icon = iconUrl(data.icon);

        return `
            <div class="weather-icon-container">
                ${icon ? `<img src="${icon}" alt="${description}">` : ''}
                <div class="weather-description">${description}</div>
            </div>

            <div class="weather-info">
                <div class="weather-item">
                    <div>
                        <strong>Temperature</strong>
                        <span>${formatTemp(data.temperature)}</span>
                    </div>
                </div>

                <div class="weather-item">
                    <div>
                        <strong>Feels Like</strong>
                        <span>${formatTemp(data.feels_like)}</span>
                    </div>
                </div>

                <div class="weather-item">
                    <div>
                        <strong>Humidity</strong>
                        <span>${formatNumber(data.humidity, '%')}</span>
                    </div>
                </div>

                <div class="weather-item">
                    <div>
                        <strong>Wind Speed</strong>
                        <span>${formatNumber(data.wind_speed, ' m/s')}</span>
                    </div>
                </div>

                <div class="weather-item">
                    <div>
                        <strong>Pressure</strong>
                        <span>${formatNumber(data.pressure, ' hPa')}</span>
                    </div>
                </div>
            </div>
        `;
    }

    // HTML for the "Forecast" tab
    function forecastTabHtml(state) {
        if (state.forecastError) {
            return `<div class="error-message">Unable to fetch forecast: ${escapeHtml(state.forecastError)}</div>`;
        }
        if (!state.forecast) {
            return '<div class="popup-note">Loading forecast...</div>';
        }
        if (state.forecast.length === 0) {
            return '<div class="popup-note">No forecast available.</div>';
        }

        const days = state.forecast.map((day) => {
            const description = escapeHtml(day.description);
            const icon = iconUrl(day.icon);

            // Build the date from its parts so the browser's time zone cannot shift the day
            const [year, month, dayOfMonth] = String(day.date).split('-').map(Number);
            const date = new Date(year, month - 1, dayOfMonth);
            const label = Number.isNaN(date.getTime())
                ? escapeHtml(day.date)
                : date.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' });

            return `
                <div class="forecast-day">
                    ${icon ? `<img src="${icon}" alt="${description}">` : '<span></span>'}
                    <div>
                        <strong>${label}</strong>
                        <span class="weather-description">${description}</span>
                    </div>
                    <div class="forecast-temps">
                        ${formatTemp(day.max_temp)}<br>
                        <span class="min">${formatTemp(day.min_temp)}</span>
                    </div>
                </div>
            `;
        }).join('');

        return `<div class="forecast-list">${days}</div>`;
    }

    // Display weather information in a popup with "Current" and "Forecast" tabs
    function displayWeatherPopup(cityId, marker) {
        const state = popupState[cityId];
        const data = state.weather;

        // The popup is built as a DOM element (not a string) so the tab
        // buttons can be given click handlers
        const container = document.createElement('div');
        container.className = 'weather-popup';
        container.innerHTML = `
            <h3>${escapeHtml(data.city)}, ${escapeHtml(data.country)}</h3>

            <div class="popup-tabs">
                <button type="button" class="popup-tab ${state.tab === 'current' ? 'active' : ''}" data-tab="current">Current</button>
                <button type="button" class="popup-tab ${state.tab === 'forecast' ? 'active' : ''}" data-tab="forecast">Forecast</button>
            </div>

            ${state.tab === 'current' ? currentTabHtml(data) : forecastTabHtml(state)}
        `;

        container.querySelectorAll('.popup-tab').forEach((button) => {
            button.addEventListener('click', () => {
                state.tab = button.dataset.tab;
                displayWeatherPopup(cityId, marker);

                if (state.tab === 'forecast' && !state.forecast && !state.forecastError) {
                    fetchForecastData(cityId, marker);
                }
            });
        });

        marker.unbindPopup();
        marker.bindPopup(container, {
            maxWidth: 320,
            className: 'weather-popup-container'
        }).openPopup();
    }

    // Display an error message in a popup
    function displayErrorPopup(marker, errorMessage = 'Unknown error') {
        const errorContent = `
            <div class="weather-popup">
                <h3>Error</h3>
                <div class="error-message">
                    Unable to fetch weather data: ${escapeHtml(errorMessage)}
                    <br><br>
                    Please try again later.
                </div>
            </div>
        `;

        marker.unbindPopup();
        marker.bindPopup(errorContent).openPopup();
    }

    // Show / hide the loading overlay
    function showLoading() {
        const loadingEl = document.getElementById('loading');
        if (loadingEl) loadingEl.classList.add('active');
    }

    function hideLoading() {
        const loadingEl = document.getElementById('loading');
        if (loadingEl) loadingEl.classList.remove('active');
    }

    // ----- Enhancement 3: search for a city and zoom to it -----

    const cityLabel = (city) => `${city.name}, ${city.country}`;

    // Lower-case and remove accents, so "sao paulo" finds "São Paulo"
    function normalise(text) {
        return String(text).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
    }

    // Offer the city names as suggestions while typing
    function fillSearchOptions(cities) {
        const options = document.getElementById('city-options');
        if (!options) return;

        options.replaceChildren(...cities.map((city) => {
            const option = document.createElement('option');
            option.value = cityLabel(city);
            return option;
        }));
    }

    // Best match: an exact name first, then names starting with the text, then any match
    function findCity(text) {
        const query = normalise(text);
        if (!query) return null;

        return allCities.find((city) => normalise(cityLabel(city)) === query || normalise(city.name) === query)
            || allCities.find((city) => normalise(city.name).startsWith(query))
            || allCities.find((city) => normalise(cityLabel(city)).includes(query))
            || null;
    }

    const searchForm = document.getElementById('search-form');
    const searchInput = document.getElementById('city-search');
    const searchMessage = document.getElementById('search-message');

    if (searchForm && searchInput) {
        searchForm.addEventListener('submit', (event) => {
            event.preventDefault();  // Do not reload the page
            const text = searchInput.value.trim();
            const city = findCity(text);

            if (!city) {
                if (searchMessage) {
                    searchMessage.textContent = text
                        ? `No city matches "${text}"`
                        : 'Type a city name to search';
                }
                return;
            }

            if (searchMessage) searchMessage.textContent = '';
            searchInput.value = cityLabel(city);

            // Zoom to the city and open its marker
            map.setView([city.latitude, city.longitude], 8);
            fetchWeatherData(city.id, markers[city.id]);
        });

        searchInput.addEventListener('input', () => {
            if (searchMessage) searchMessage.textContent = '';
        });
    }

    // ----- Enhancement 4: Celsius / Fahrenheit toggle -----

    const unitToggle = document.getElementById('unit-toggle');

    if (unitToggle) {
        unitToggle.addEventListener('click', () => {
            useFahrenheit = !useFahrenheit;
            unitToggle.textContent = useFahrenheit ? 'Show °C' : 'Show °F';

            // Redraw the popup that is open, if any, in the new unit
            Object.keys(popupState).forEach((cityId) => {
                const marker = markers[cityId];
                if (marker && marker.isPopupOpen()) {
                    displayWeatherPopup(cityId, marker);
                }
            });
        });
    }

    // Initialize the application
    loadCities();

    // Helper for debugging in the browser console
    window.debugMap = { map, markers, loadCities };
});
