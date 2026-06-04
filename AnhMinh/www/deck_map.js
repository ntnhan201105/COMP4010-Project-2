document.addEventListener('DOMContentLoaded', () => {
    let deckgl = null;
    let choroplethLayer = null;
    let oceanLayer = null;
    let lastReceivedData = null;
    let geojsonObject = null;
    let currentYearData = [];
    let currentIndicator = 'life_expectancy';
    let isInteracting = false;
    let rotateTimer = null;
    let isPanelOpen = false; // Tracks if Deep Dive panel is open

    // Reactively managed viewState unified for both interaction and animation
    let currentViewState = {
        longitude: 0,
        latitude: 20,
        zoom: 1.0,
        pitch: 0,
        bearing: 0
    };

    // ---------- Custom DOM Tooltip (no flicker during globe spin) ----------
    const tooltip = document.createElement('div');
    tooltip.id = 'globe-custom-tooltip';
    tooltip.style.cssText = `
        position: fixed;
        pointer-events: none;
        z-index: 9999;
        background: #161c26;
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 8px;
        color: #ffffff;
        font-family: 'Inter', system-ui, sans-serif;
        font-size: 0.9rem;
        line-height: 1.5;
        padding: 10px 14px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.55);
        max-width: 240px;
        display: none;
        transition: opacity 0.15s ease;
        opacity: 0;
    `;
    document.body.appendChild(tooltip);

    let tooltipVisible = false;
    let mouseX = 0, mouseY = 0;

    document.addEventListener('mousemove', (e) => {
        mouseX = e.clientX;
        mouseY = e.clientY;
        if (tooltipVisible) {
            positionTooltip();
        }
    });

    const positionTooltip = () => {
        const pad = 16;
        const tw = tooltip.offsetWidth;
        const th = tooltip.offsetHeight;
        let x = mouseX + pad;
        let y = mouseY + pad;
        if (x + tw > window.innerWidth)  x = mouseX - tw - pad;
        if (y + th > window.innerHeight) y = mouseY - th - pad;
        tooltip.style.left = x + 'px';
        tooltip.style.top  = y + 'px';
    };

    const showTooltip = (html) => {
        tooltip.innerHTML = html;
        tooltip.style.display = 'block';
        requestAnimationFrame(() => {
            tooltip.style.opacity = '1';
            positionTooltip();
        });
        tooltipVisible = true;
    };

    const hideTooltip = () => {
        tooltip.style.opacity = '0';
        tooltipVisible = false;
        setTimeout(() => {
            if (!tooltipVisible) tooltip.style.display = 'none';
        }, 150);
    };
    // -----------------------------------------------------------------------

    // Helper to generate a high-resolution subdivided polygon covering the entire Earth.
    const generateGlobePolygon = () => {
        const coords = [];
        for (let lng = -180; lng <= 180; lng += 2) {
            coords.push([lng, 89.9]);
        }
        coords.push([180, 89.9]);
        for (let lng = 180; lng >= -180; lng -= 2) {
            coords.push([lng, -89.9]);
        }
        coords.push([-180, -89.9]);
        coords.push([-180, 89.9]);
        return [coords];
    };

    const initMap = () => {
        const globeView = new deck._GlobeView();
        
        // Solid ocean background layer to block seeing backside countries through transparency.
        oceanLayer = new deck.SolidPolygonLayer({
            id: 'ocean',
            data: [generateGlobePolygon()],
            getPolygon: d => d,
            stroked: false,
            filled: true,
            getFillColor: [8, 20, 58, 255] // Deep midnight blue — clearly distinct from dark land
        });

        deckgl = new deck.DeckGL({
            container: 'deck-map-container',
            views: globeView,
            viewState: currentViewState,
            controller: true,
            // Disable built-in tooltip — we use our custom DOM tooltip
            getTooltip: () => null,
            // Handle hover events for custom tooltip
            onHover: (info) => {
                const container = document.getElementById('deck-map-container');
                const {object, layer, coordinate} = info;

                if (object && layer && layer.id === 'earth-land') {

                    // --- Back-face culling ---
                    // A country on the back hemisphere should NOT be hoverable.
                    // Compute the spherical dot product between the hovered point
                    // and the current camera center. If < 0, it's >90° away = hidden side.
                    if (coordinate) {
                        const [lng, lat] = coordinate;
                        const camLng = currentViewState.longitude * Math.PI / 180;
                        const camLat = (currentViewState.latitude || 0) * Math.PI / 180;
                        const ptLng  = lng * Math.PI / 180;
                        const ptLat  = lat * Math.PI / 180;
                        const dot = Math.sin(camLat) * Math.sin(ptLat)
                                  + Math.cos(camLat) * Math.cos(ptLat) * Math.cos(ptLng - camLng);
                        if (dot < 0.05) { // slight buffer so edge countries don't flicker
                            if (container) container.style.cursor = 'grab';
                            hideTooltip();
                            return;
                        }
                    }

                    if (container) container.style.cursor = 'pointer';

                    const iso = object.properties.iso_a3 ? object.properties.iso_a3.toLowerCase() : '';
                    const name = object.properties.name ? object.properties.name.toLowerCase() : '';
                    const formalName = object.properties.formal_en ? object.properties.formal_en.toLowerCase() : '';

                    const countryData = currentYearData.find(d => {
                        const dIso = d.iso_alpha ? d.iso_alpha.toLowerCase() : '';
                        const dName = d.country ? d.country.toLowerCase() : '';
                        return (iso && dIso === iso) || (name && dName === name) || (formalName && dName === formalName);
                    });

                    if (countryData) {
                        const indicatorName = currentIndicator === 'life_expectancy' ? 'Life Expectancy' :
                                              currentIndicator === 'fertility_rate' ? 'Fertility Rate' : 'Net Migration';
                        let valueStr = '';
                        if (currentIndicator === 'life_expectancy') {
                            valueStr = `${countryData.raw_value.toFixed(1)} years`;
                        } else if (currentIndicator === 'fertility_rate') {
                            valueStr = `${countryData.raw_value.toFixed(2)} births/woman`;
                        } else {
                            valueStr = countryData.raw_value.toLocaleString(undefined, {signDisplay: 'always'});
                        }
                        showTooltip(`
                            <div style="margin-bottom:4px;">
                                <strong style="color:#818cf8;font-size:1.05em;">${countryData.country}</strong>
                            </div>
                            <div style="color:#94a3b8;font-size:0.82em;margin-bottom:2px;">
                                Population: <span style="color:#e2e8f0;">${Math.round(countryData.pop).toLocaleString()}</span>
                            </div>
                            <div style="color:#94a3b8;font-size:0.82em;">
                                ${indicatorName}: <strong style="color:#ffffff;">${valueStr}</strong>
                            </div>
                        `);
                    } else {
                        showTooltip(`
                            <strong style="color:#818cf8;">${object.properties.name}</strong>
                            <div style="color:#64748b;font-size:0.82em;margin-top:3px;">No demographic data</div>
                        `);
                    }
                } else {
                    if (container) container.style.cursor = 'grab';
                    hideTooltip();
                }
            },
            onClick: (info) => {
                const {object, layer, coordinate} = info;
                if (object && layer && layer.id === 'earth-land') {
                    // Similar back-face culling check as hover
                    if (coordinate) {
                        const [lng, lat] = coordinate;
                        const camLng = currentViewState.longitude * Math.PI / 180;
                        const camLat = (currentViewState.latitude || 0) * Math.PI / 180;
                        const ptLng  = lng * Math.PI / 180;
                        const ptLat  = lat * Math.PI / 180;
                        const dot = Math.sin(camLat) * Math.sin(ptLat)
                                  + Math.cos(camLat) * Math.cos(ptLat) * Math.cos(ptLng - camLng);
                        if (dot < 0.05) return; // Ignore clicks on the back side
                    }

                    const iso = object.properties.iso_a3 ? object.properties.iso_a3.toLowerCase() : '';
                    if (iso) {
                        isPanelOpen = true; // Stop rotation
                        Shiny.setInputValue("selected_country_iso", iso, {priority: "event"});
                    }
                }
            },
            // Controlled state updates sync with canvas dynamically
            onViewStateChange: ({viewState, interactionState}) => {
                currentViewState = viewState;
                deckgl.setProps({viewState: currentViewState});

                // Detect dragging/zooming to pause auto-rotate
                if (interactionState && (interactionState.isDragging || interactionState.isPanning || interactionState.isZooming)) {
                    isInteracting = true;
                    clearTimeout(rotateTimer);
                    rotateTimer = setTimeout(() => {
                        isInteracting = false;
                    }, 3000); // Resume auto-rotate after 3s of complete idle
                }
            },
            layers: []
        });

        // Pre-fetch GeoJSON to load background Layer
        fetch('https://d2ad6b4ur7yvpq.cloudfront.net/naturalearth-3.3.0/ne_50m_admin_0_countries.geojson')
            .then(res => res.json())
            .then(geojson => {
                geojsonObject = geojson;
                
                // If we already received data from server, render it now
                if (lastReceivedData) {
                    renderLayers(lastReceivedData);
                } else {
                    // Render default loading landmass colors — medium gray, distinct from ocean
                    geojsonObject.features.forEach(f => {
                        f.properties.fillColor = [58, 65, 78, 255];
                    });
                    
                    choroplethLayer = new deck.GeoJsonLayer({
                        id: 'earth-land',
                        data: geojsonObject,
                        stroked: true,
                        filled: true,
                        lineWidthMinPixels: 1.0,
                        getLineColor: [99, 102, 241, 55], // Soft indigo outlines
                        getFillColor: f => f.properties.fillColor,
                        pickable: true,
                        autoHighlight: true,
                        highlightColor: [99, 102, 241, 40]
                    });
                    
                    deckgl.setProps({layers: [oceanLayer, choroplethLayer]});
                }
            })
            .catch(err => {
                console.error("Failed to load world countries GeoJSON:", err);
            });

        // Majestic auto-rotation loop — continues even during hover, only pauses on active drag/zoom/scroll or when panel is open
        const rotateGlobe = () => {
            if (deckgl && !isInteracting && !isPanelOpen) {
                currentViewState = Object.assign({}, currentViewState, {
                    longitude: (currentViewState.longitude + 0.04) % 360
                });
                deckgl.setProps({viewState: currentViewState});
            }
            requestAnimationFrame(rotateGlobe);
        };
        setTimeout(rotateGlobe, 2500);

        // Only actual drag/zoom/scroll pauses the rotation
        const resetIdleTimer = () => {
            isInteracting = true;
            clearTimeout(rotateTimer);
            rotateTimer = setTimeout(() => {
                isInteracting = false;
            }, 3000);
        };

        const container = document.getElementById('deck-map-container');
        if (container) {
            container.addEventListener('pointerdown', resetIdleTimer);
            container.addEventListener('pointermove', (e) => {
                if (e.buttons > 0) resetIdleTimer();
            });
            container.addEventListener('wheel', resetIdleTimer);
        }
    };

    const renderLayers = (data) => {
        if (!deckgl || !geojsonObject) return;

        // Map colors from Python data onto the GeoJSON features dynamically
        geojsonObject.features.forEach(f => {
            const iso = f.properties.iso_a3 ? f.properties.iso_a3.toLowerCase() : '';
            const name = f.properties.name ? f.properties.name.toLowerCase() : '';
            const formalName = f.properties.formal_en ? f.properties.formal_en.toLowerCase() : '';
            
            const countryData = data.find(d => {
                const dIso = d.iso_alpha ? d.iso_alpha.toLowerCase() : '';
                const dName = d.country ? d.country.toLowerCase() : '';
                return (iso && dIso === iso) || (name && dName === name) || (formalName && dName === formalName);
            });

            if (countryData) {
                f.properties.fillColor = [countryData.color_r, countryData.color_g, countryData.color_b, 245];
            } else {
                // No data — medium gray, clearly distinct from midnight-blue ocean
                f.properties.fillColor = [58, 65, 78, 255];
            }
        });

        choroplethLayer = new deck.GeoJsonLayer({
            id: 'earth-land',
            data: geojsonObject,
            stroked: true,
            filled: true,
            lineWidthMinPixels: 1.0,
            getLineColor: [99, 102, 241, 55],
            getFillColor: f => f.properties.fillColor,
            pickable: true,
            autoHighlight: true,
            highlightColor: [99, 102, 241, 40],
            updateTriggers: {
                getFillColor: [data]
            },
            transitions: {
                getFillColor: {duration: 600, type: 'interpolation'}
            }
        });

        deckgl.setProps({layers: [oceanLayer, choroplethLayer]});
    };

    // Handlers will be defined inside if (window.Shiny)

    if (window.Shiny) {
        Shiny.addCustomMessageHandler('update_deck_data', function(message) {
            lastReceivedData = message.data;
            currentYearData = message.data;
            currentIndicator = message.indicator || 'life_expectancy';
            
            if (!deckgl) {
                initMap();
            } else {
                renderLayers(lastReceivedData);
            }
        });

        // Listen for Shiny panel close to resume globe spin
        Shiny.addCustomMessageHandler("panel_closed", function(msg) {
            isPanelOpen = false;
        });

        Shiny.addCustomMessageHandler('fly_to', function(targetState) {
            if (!deckgl) return;
            isInteracting = true;
            clearTimeout(rotateTimer);
            
            const newState = Object.assign({}, currentViewState);
            newState.longitude = targetState.longitude;
            newState.latitude = targetState.latitude;
            newState.zoom = targetState.zoom;
            newState.transitionDuration = 2000;
            newState.transitionInterpolator = new deck.FlyToInterpolator();
            
            currentViewState = newState;
            deckgl.setProps({viewState: currentViewState});
            
            rotateTimer = setTimeout(() => {
                isInteracting = false;
            }, 3500);
        });
    }
});