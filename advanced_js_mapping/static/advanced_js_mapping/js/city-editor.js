(() => {
    const form = document.getElementById('city-editor');
    if (!form) return;

    const choice = document.getElementById('city-choice');
    const name = document.getElementById('city-name');
    const country = document.getElementById('city-country');
    const population = document.getElementById('city-population');
    const latitude = document.getElementById('city-latitude');
    const longitude = document.getElementById('city-longitude');
    const location = document.getElementById('city-location');
    const message = document.getElementById('city-message');
    const save = document.getElementById('city-save');

    function selectCity() {
        const option = choice.selectedOptions[0];
        const editing = Boolean(option && option.value);
        name.value = editing ? option.dataset.name : '';
        country.value = editing ? option.dataset.country : '';
        population.value = editing ? option.dataset.population : '';
        location.hidden = editing;
        latitude.required = !editing;
        longitude.required = !editing;
        save.disabled = !option;
        message.textContent = option ? '' : 'No cities are available to edit.';
    }

    choice.addEventListener('change', selectCity);
    selectCity();
    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const option = choice.selectedOptions[0];
        if (!option) return;
        const editing = Boolean(option.value);
        const data = {
            name: name.value,
            country: country.value,
            population: population.value
        };
        if (!editing) {
            data.latitude = latitude.value;
            data.longitude = longitude.value;
        }
        save.disabled = true;
        message.textContent = 'Saving...';
        try {
            const response = await fetch(editing ? option.dataset.url : form.dataset.createUrl, {
                method: editing ? 'PUT' : 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify(data)
            });
            if (!response.ok) {
                const text = await response.text();
                let detail = `Request failed (HTTP ${response.status}).`;
                try {
                    const body = JSON.parse(text);
                    if (body.error) detail += ` ${body.error}`;
                    if (body.fields) detail += ` ${JSON.stringify(body.fields)}`;
                } catch (error) {
                    // CSRF middleware may return an HTML error page.
                }
                throw new Error(detail);
            }
            message.textContent = 'Saved. Reloading map...';
            window.location.reload();
        } catch (error) {
            message.textContent = error.message || 'Unable to save the city.';
            save.disabled = false;
        }
    });
})();
