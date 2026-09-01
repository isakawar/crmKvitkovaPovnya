/* Google Places (New) address autocomplete for delivery-address fields.
 *
 * Usage:
 *   initAddressAutocomplete(streetInput, dropdownEl, formEl, {
 *     cityInput,           // <input name="city"> — filled only if empty
 *     buildingInput,       // optional <input name="building_number">
 *     prefix = '',         // id prefix for the 4 hidden fields (multi-form pages)
 *   })
 *
 * Writes hidden inputs into formEl: latitude, longitude, google_place_id,
 * formatted_address. Names are fixed; ids are `${prefix}latitude` etc.
 *
 * Degrades silently to a plain text input when the Google JS SDK cannot load
 * or no API key is configured (window.GOOGLE_MAPS_API_KEY).
 */

(function () {
  'use strict';

  var _sdkPromise = null;

  function loadGoogleMaps() {
    if (_sdkPromise) return _sdkPromise;
    var key = window.GOOGLE_MAPS_API_KEY || '';
    if (!key) {
      _sdkPromise = Promise.reject(new Error('GOOGLE_MAPS_API_KEY not set'));
      return _sdkPromise;
    }
    _sdkPromise = new Promise(function (resolve, reject) {
      if (window.google && window.google.maps && window.google.maps.importLibrary) {
        resolve(window.google);
        return;
      }
      var s = document.createElement('script');
      s.src = 'https://maps.googleapis.com/maps/api/js?key=' + encodeURIComponent(key) +
              '&libraries=places&language=uk&region=UA&loading=async';
      s.async = true;
      s.onerror = function () { reject(new Error('Google Maps SDK failed to load')); };
      s.onload = function () { resolve(window.google); };
      document.head.appendChild(s);
    });
    return _sdkPromise;
  }

  function _debounce(fn, delay) {
    var t;
    return function () {
      var ctx = this, args = arguments;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, delay);
    };
  }

  function _ensureHidden(form, prefix, name) {
    var id = prefix + name;
    var el = form.querySelector('#' + CSS.escape(id));
    if (!el) {
      el = document.createElement('input');
      el.type = 'hidden';
      el.name = name;
      el.id = id;
      form.appendChild(el);
    }
    return el;
  }

  function _component(components, type) {
    if (!components) return '';
    for (var i = 0; i < components.length; i++) {
      var c = components[i];
      if (c.types && c.types.indexOf(type) !== -1) {
        return c.longText || c.long_name || c.shortText || '';
      }
    }
    return '';
  }

  function initAddressAutocomplete(streetInput, dropdownEl, formEl, opts) {
    if (!streetInput || !dropdownEl || !formEl) return;
    opts = opts || {};
    var prefix = opts.prefix || '';
    var cityInput = opts.cityInput || null;
    var buildingInput = opts.buildingInput || null;

    var hLat = _ensureHidden(formEl, prefix, 'latitude');
    var hLng = _ensureHidden(formEl, prefix, 'longitude');
    var hPlaceId = _ensureHidden(formEl, prefix, 'google_place_id');
    var hFormatted = _ensureHidden(formEl, prefix, 'formatted_address');

    var activeIdx = -1;
    var suggestions = [];
    var sessionToken = null;
    var placesLib = null;
    var lastPicked = '';   // street value we last wrote from a picked suggestion
    var sdkFailed = false;

    function clearCoords() {
      hLat.value = ''; hLng.value = ''; hPlaceId.value = ''; hFormatted.value = '';
    }

    function closeDropdown() {
      dropdownEl.style.display = 'none';
      dropdownEl.innerHTML = '';
      activeIdx = -1;
      suggestions = [];
    }

    function renderList(items) {
      if (!items.length) {
        dropdownEl.innerHTML = '<div class="city-autocomplete-empty">Адресу не знайдено</div>';
        dropdownEl.style.display = 'block';
        return;
      }
      dropdownEl.innerHTML = items.map(function (s, i) {
        var p = s.placePrediction;
        var main = (p.mainText && p.mainText.text) || (p.text && p.text.text) || '';
        var secondary = (p.secondaryText && p.secondaryText.text) || '';
        return '<div class="city-autocomplete-item address-autocomplete-item" data-idx="' + i + '">' +
                 '<span class="city-item-name"><i class="bi bi-geo-alt"></i> ' + _esc(main) + '</span>' +
                 (secondary ? '<span class="city-item-meta"><span class="city-item-region">' + _esc(secondary) + '</span></span>' : '') +
               '</div>';
      }).join('');
      dropdownEl.style.display = 'block';
    }

    function _esc(s) {
      return String(s).replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
      });
    }

    var fetchSuggestions = _debounce(function () {
      var val = streetInput.value.trim();
      activeIdx = -1;
      if (val.length < 3 || sdkFailed) { closeDropdown(); return; }

      loadGoogleMaps().then(function (google) {
        return google.maps.importLibrary('places');
      }).then(function (lib) {
        placesLib = lib;
        if (!sessionToken) sessionToken = new lib.AutocompleteSessionToken();
        var request = {
          input: val,
          includedRegionCodes: ['ua'],
          language: 'uk',
          sessionToken: sessionToken,
          locationBias: { center: { lat: 50.4501, lng: 30.5234 }, radius: 50000 },
        };
        return lib.AutocompleteSuggestion.fetchAutocompleteSuggestions(request);
      }).then(function (res) {
        // ignore stale responses
        if (streetInput.value.trim() !== val) return;
        suggestions = (res.suggestions || []).filter(function (s) { return s.placePrediction; });
        renderList(suggestions);
      }).catch(function (err) {
        sdkFailed = true;
        closeDropdown();
        if (window.console) console.warn('[address-autocomplete] disabled:', err.message);
      });
    }, 250);

    function pick(idx) {
      var s = suggestions[idx];
      if (!s) return;
      var place = s.placePrediction.toPlace();
      place.fetchFields({ fields: ['location', 'formattedAddress', 'addressComponents'] })
        .then(function () {
          var comps = place.addressComponents;
          var route = _component(comps, 'route');
          var streetNumber = _component(comps, 'street_number');
          var locality = _component(comps, 'locality') ||
                         _component(comps, 'administrative_area_level_2') ||
                         _component(comps, 'administrative_area_level_1');

          if (buildingInput) {
            streetInput.value = route || (s.placePrediction.mainText && s.placePrediction.mainText.text) || streetInput.value;
            if (streetNumber) buildingInput.value = streetNumber;
          } else {
            streetInput.value = [route, streetNumber].filter(Boolean).join(', ') ||
                                place.formattedAddress || streetInput.value;
          }
          lastPicked = streetInput.value;

          if (cityInput && !cityInput.value.trim() && locality) {
            var isSelect = cityInput.tagName === 'SELECT';
            var hasOption = !isSelect || Array.prototype.some.call(
              cityInput.options, function (o) { return o.value === locality; });
            if (hasOption) {
              cityInput.value = locality;
              cityInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
          }

          var loc = place.location;
          hLat.value = loc ? loc.lat() : '';
          hLng.value = loc ? loc.lng() : '';
          hPlaceId.value = place.id || (s.placePrediction.placeId || '');
          hFormatted.value = place.formattedAddress || '';

          sessionToken = null;  // one billing session per pick
          closeDropdown();
          streetInput.dispatchEvent(new Event('change', { bubbles: true }));
        })
        .catch(function (err) {
          if (window.console) console.warn('[address-autocomplete] fetchFields failed:', err);
          closeDropdown();
        });
    }

    streetInput.addEventListener('input', function () {
      // manual edit after a pick → the stored coords no longer match the text
      if (lastPicked && streetInput.value !== lastPicked) {
        clearCoords();
        lastPicked = '';
      }
      fetchSuggestions();
    });

    dropdownEl.addEventListener('mousedown', function (e) {
      var item = e.target.closest('[data-idx]');
      if (item) {
        e.preventDefault();
        pick(parseInt(item.dataset.idx, 10));
      }
    });

    streetInput.addEventListener('keydown', function (e) {
      if (dropdownEl.style.display === 'none') return;
      var items = dropdownEl.querySelectorAll('[data-idx]');
      if (!items.length) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        activeIdx = Math.min(activeIdx + 1, items.length - 1);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        activeIdx = Math.max(activeIdx - 1, 0);
      } else if (e.key === 'Enter' && activeIdx >= 0) {
        e.preventDefault();
        pick(activeIdx);
        return;
      } else if (e.key === 'Escape') {
        closeDropdown();
        return;
      } else {
        return;
      }
      items.forEach(function (el, i) {
        el.classList.toggle('city-autocomplete-item--active', i === activeIdx);
      });
      if (activeIdx >= 0) items[activeIdx].scrollIntoView({ block: 'nearest' });
    });

    streetInput.addEventListener('blur', function () {
      setTimeout(closeDropdown, 150);
    });

    document.addEventListener('click', function (e) {
      if (!streetInput.contains(e.target) && !dropdownEl.contains(e.target)) closeDropdown();
    });

    // Soft warning on submit when a courier address was typed but never confirmed.
    formEl.addEventListener('submit', function (e) {
      var isPickup = false;
      var pickupEl = formEl.querySelector('[name="is_pickup"]');
      if (pickupEl) isPickup = (pickupEl.value === 'on' || pickupEl.checked === true);
      var method = (formEl.querySelector('[name="delivery_method"]') || {}).value || 'courier';
      if (isPickup || method === 'nova_poshta') return;
      if (!streetInput.value.trim()) return;
      if (hLat.value && hLng.value) return;
      if (formEl.dataset.addrConfirmed === '1') return;
      if (!window.confirm('Адресу не підтверджено через Google Maps — координати не збережуться, і маршрут може порахуватись невірно.\n\nЗберегти як є?')) {
        e.preventDefault();
        e.stopPropagation();
      } else {
        formEl.dataset.addrConfirmed = '1';
      }
    }, true);

    // Warm up the SDK so the first keystroke is snappy.
    loadGoogleMaps().catch(function () { sdkFailed = true; });
  }

  window.initAddressAutocomplete = initAddressAutocomplete;
})();
