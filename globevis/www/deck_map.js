document.addEventListener('DOMContentLoaded', () => {
    let deckgl = null;
    let choroplethLayer = null;
    let oceanLayer = null;
    let lastReceivedData = null;
    let geojsonObject = null;
    let currentYearData = [];
    let dataMap = new Map(); // O(1) lookup map
    let currentIndicator = 'life_expectancy';
    let activeGroupIsos = new Set();
    let activeOriginIsos = new Set();
    let activeHostIsos = new Set();
    let groupFocusOpen = false;
    let dimNonGroup = false;
    let isInteracting = false;
    let rotateTimer = null;
    let isPanelOpen = false; // Tracks if Deep Dive panel is open
    let is3D = true;
    const globeView = new deck._GlobeView({ id: 'globe' });
    const mapView = new deck.MapView({ id: 'map', repeat: true });

    // Reactively managed viewState unified for both interaction and animation
    let currentViewState = {
        longitude: 0,
        latitude: 10,
        zoom: 0.85,
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
        if (x + tw > window.innerWidth) x = mouseX - tw - pad;
        if (y + th > window.innerHeight) y = mouseY - th - pad;
        tooltip.style.left = x + 'px';
        tooltip.style.top = y + 'px';
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

    const syncStageLayout = () => {
        const stage = document.getElementById('story-stage');
        const panel = document.querySelector('.story-dashboard-panel');
        if (stage) stage.classList.toggle('is-focused', groupFocusOpen);
        if (panel) panel.classList.toggle('is-open', groupFocusOpen);
        setTimeout(() => {
            window.dispatchEvent(new Event('resize'));
            if (deckgl) deckgl.redraw(true);
        }, 420);
    };

    const activeGroupData = () => currentYearData.filter(d =>
        d.iso_alpha && activeGroupIsos.has(d.iso_alpha.toLowerCase())
    );

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
        // Solid ocean background layer to block seeing backside countries through transparency.
        oceanLayer = new deck.SolidPolygonLayer({
            id: 'ocean',
            data: [generateGlobePolygon()],
            getPolygon: d => d,
            stroked: false,
            filled: true,
            pickable: true,
            getFillColor: [8, 20, 58, 255] // Deep midnight blue — clearly distinct from dark land
        });

        deckgl = new deck.DeckGL({
            container: 'deck-map-container',
            views: is3D ? globeView : mapView,
            viewState: currentViewState,
            controller: true,
            // Disable built-in tooltip — we use our custom DOM tooltip
            getTooltip: () => null,
            // Handle hover events for custom tooltip
            onHover: (info) => {
                if (isInteracting) {
                    hideTooltip();
                    return;
                }
                const container = document.getElementById('deck-map-container');
                const { object, layer, coordinate } = info;

                if (object && layer && layer.id === 'earth-land') {

                    // --- Back-face culling ---
                    // A country on the back hemisphere should NOT be hoverable.
                    // Compute the spherical dot product between the hovered point
                    // and the current camera center. If < 0, it's >90° away = hidden side.
                    if (is3D && coordinate) {
                        const [lng, lat] = coordinate;
                        const camLng = currentViewState.longitude * Math.PI / 180;
                        const camLat = (currentViewState.latitude || 0) * Math.PI / 180;
                        const ptLng = lng * Math.PI / 180;
                        const ptLat = lat * Math.PI / 180;
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
                    let countryData = null;
                    if (iso && dataMap.has(iso)) {
                        countryData = dataMap.get(iso);
                    }

                    if (countryData) {
                        const indicatorName = {
                            net_migration_rate: 'Migration Rate',
                            fertility_rate: 'Fertility Rate',
                            life_expectancy: 'Life Expectancy',
                            child_mortality: 'Child Mortality',
                            death_rate: 'Death Rate'
                        }[currentIndicator] || 'Value';
                        let valueStr = '';
                        if (countryData.raw_value === null || countryData.raw_value === undefined || Number.isNaN(countryData.raw_value)) {
                            valueStr = 'No data';
                        } else if (currentIndicator === 'net_migration_rate') {
                            valueStr = `${countryData.raw_value.toLocaleString(undefined, { signDisplay: 'always', maximumFractionDigits: 1 })} per 1,000`;
                        } else if (currentIndicator === 'fertility_rate') {
                            valueStr = `${countryData.raw_value.toFixed(2)} children per woman`;
                        } else if (currentIndicator === 'life_expectancy') {
                            valueStr = `${countryData.raw_value.toFixed(1)} years`;
                        } else if (currentIndicator === 'child_mortality') {
                            valueStr = `${countryData.raw_value.toFixed(2)}% of children`;
                        } else {
                            valueStr = `${countryData.raw_value.toFixed(1)} deaths per 1,000`;
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
                const { object, layer, coordinate } = info;
                if (object && layer && layer.id === 'earth-land') {
                    // Similar back-face culling check as hover
                    if (is3D && coordinate) {
                        const [lng, lat] = coordinate;
                        const camLng = currentViewState.longitude * Math.PI / 180;
                        const camLat = (currentViewState.latitude || 0) * Math.PI / 180;
                        const ptLng = lng * Math.PI / 180;
                        const ptLat = lat * Math.PI / 180;
                        const dot = Math.sin(camLat) * Math.sin(ptLat)
                            + Math.cos(camLat) * Math.cos(ptLat) * Math.cos(ptLng - camLng);
                        if (dot < 0.05) return; // Ignore clicks on the back side
                    }

                    const iso = object.properties.iso_a3 ? object.properties.iso_a3.toLowerCase() : '';
                    if (iso) {
                        isPanelOpen = true; // Stop rotation

                        if (coordinate) {
                            const [lng, lat] = coordinate;
                            isInteracting = true;
                            clearTimeout(rotateTimer);

                            const newState = Object.assign({}, currentViewState);
                            newState.longitude = lng;
                            newState.latitude = lat;
                            const targetZoom = is3D ? 2.5 : 3.2;
                            newState.zoom = Math.max(currentViewState.zoom, targetZoom);
                            newState.transitionDuration = 1500;
                            newState.transitionInterpolator = new deck.FlyToInterpolator();

                            currentViewState = newState;
                            deckgl.setProps({ viewState: currentViewState });

                            // Immediately hide the panel and tooltip so Plotly/DOM doesn't steal frame budget
                            // from the WebGL animation.
                            const panel = document.querySelector('.deep-dive-panel');
                            if (panel) panel.classList.remove('is-visible');
                            hideTooltip();

                            rotateTimer = setTimeout(() => {
                                isInteracting = false;
                            }, 2000);

                            // Delay the Shiny UI event until the animation is mostly finished
                            // to avoid stutter caused by heavy DOM and Plotly updates.
                            setTimeout(() => {
                                Shiny.setInputValue("selected_country_iso", iso, { priority: "event" });
                            }, 2000);
                        } else {
                            Shiny.setInputValue("selected_country_iso", iso, { priority: "event" });
                        }
                    }
                }
            },
            // Controlled state updates sync with canvas dynamically
            onViewStateChange: ({ viewState, interactionState }) => {
                currentViewState = viewState;
                deckgl.setProps({ viewState: currentViewState });

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

                    deckgl.setProps({ layers: [oceanLayer, choroplethLayer] });
                }
            })
            .catch(err => {
                console.error("Failed to load world countries GeoJSON:", err);
            });

        // Majestic auto-rotation loop — throttled to 30 FPS for performance
        let lastRotationTime = 0;
        const targetFPS = 30;
        const frameInterval = 1000 / targetFPS;
        
        const rotateGlobe = (timestamp) => {
            if (timestamp - lastRotationTime >= frameInterval) {
                lastRotationTime = timestamp;
                if (deckgl && !isInteracting && !isPanelOpen && !groupFocusOpen && is3D) {
                    // Increased step size from 0.04 to 0.08 since we're running at half the framerate
                    currentViewState = Object.assign({}, currentViewState, {
                        longitude: (currentViewState.longitude + 0.08) % 360
                    });
                    deckgl.setProps({ viewState: currentViewState });
                }
            }
            requestAnimationFrame(rotateGlobe);
        };
        setTimeout(() => requestAnimationFrame(rotateGlobe), 2500);

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
            let countryData = null;
            if (iso && dataMap.has(iso)) {
                countryData = dataMap.get(iso);
            }

            if (countryData) {
                const isGroupMember = activeGroupIsos.has(iso);
                const isOrigin = activeOriginIsos.has(iso);
                const isHost = activeHostIsos.has(iso);
                const shouldDim = groupFocusOpen && dimNonGroup && !isGroupMember;
                f.properties.fillColor = shouldDim
                    ? [24, 30, 44, 82]
                    : groupFocusOpen && isOrigin
                        ? [239, 68, 68, 255]
                        : groupFocusOpen && isHost
                            ? [34, 211, 238, 255]
                            : [countryData.color_r, countryData.color_g, countryData.color_b, isGroupMember && groupFocusOpen ? 255 : 245];
                f.properties.isGroupMember = isGroupMember;
                f.properties.isOrigin = isOrigin;
                f.properties.isHost = isHost;
            } else {
                // No data — medium gray, clearly distinct from midnight-blue ocean
                f.properties.fillColor = groupFocusOpen && dimNonGroup ? [24, 30, 44, 70] : [58, 65, 78, 255];
                f.properties.isGroupMember = false;
                f.properties.isOrigin = false;
                f.properties.isHost = false;
            }
        });

        const pulseLayer = groupFocusOpen ? new deck.ScatterplotLayer({
            id: 'group-pulse',
            data: activeGroupData(),
            getPosition: d => [d.longitude, d.latitude],
            getRadius: 520000,
            radiusMinPixels: 8,
            radiusMaxPixels: 34,
            stroked: true,
            filled: true,
            getFillColor: [255, 255, 255, 32],
            getLineColor: [255, 255, 255, 220],
            lineWidthMinPixels: 2,
            pickable: false
        }) : null;

        choroplethLayer = new deck.GeoJsonLayer({
            id: 'earth-land',
            data: geojsonObject,
            stroked: true,
            filled: true,
            lineWidthUnits: 'pixels',
            lineWidthMinPixels: 1.0,
            getLineWidth: f => {
                if (groupFocusOpen && f.properties.isGroupMember) return 4;
                return 1;
            },
            getLineColor: f => {
                if (groupFocusOpen && f.properties.isOrigin) return [255, 180, 180, 255];
                if (groupFocusOpen && f.properties.isHost) return [180, 245, 255, 255];
                if (groupFocusOpen && f.properties.isGroupMember) return [255, 255, 255, 245];
                return [99, 102, 241, 55];
            },
            getFillColor: f => f.properties.fillColor,
            pickable: true,
            autoHighlight: true,
            highlightColor: [99, 102, 241, 40],
            updateTriggers: {
                getFillColor: [data, groupFocusOpen, dimNonGroup],
                getLineColor: [data, groupFocusOpen, dimNonGroup],
                getLineWidth: [data, groupFocusOpen]
            },
            transitions: {
                getFillColor: { duration: 600, type: 'interpolation' }
            }
        });

        const layers = [oceanLayer, choroplethLayer];
        if (pulseLayer) layers.push(pulseLayer);
        deckgl.setProps({ layers });
    };

    // Handlers will be defined inside if (window.Shiny)

    if (window.Shiny) {
        Shiny.addCustomMessageHandler('update_deck_data', function (message) {
            lastReceivedData = message.data;
            currentYearData = message.data;

            // Rebuild O(1) map for quick lookup
            dataMap.clear();
            currentYearData.forEach(d => {
                if (d.iso_alpha) {
                    dataMap.set(d.iso_alpha.toLowerCase(), d);
                }
            });

            currentIndicator = message.indicator || 'life_expectancy';

            if (!deckgl) {
                initMap();
            } else {
                renderLayers(lastReceivedData);
            }
        });

        Shiny.addCustomMessageHandler('focus_group', function (message) {
            groupFocusOpen = !!message.open;
            dimNonGroup = !!message.dim;
            activeGroupIsos = new Set((message.isos || []).map(iso => String(iso).toLowerCase()));
            activeOriginIsos = new Set((message.origins || []).map(iso => String(iso).toLowerCase()));
            activeHostIsos = new Set((message.hosts || []).map(iso => String(iso).toLowerCase()));
            isPanelOpen = groupFocusOpen;
            syncStageLayout();

            if (deckgl && lastReceivedData) {
                renderLayers(lastReceivedData);
            }

            if (!deckgl) return;

            isInteracting = true;
            clearTimeout(rotateTimer);

            const targetState = message.targetState || {};
            const newState = Object.assign({}, currentViewState);
            if (groupFocusOpen) {
                newState.longitude = targetState.longitude ?? 44;
                newState.latitude = targetState.latitude ?? 18;
                newState.zoom = targetState.zoom ?? 0.72;
            } else {
                newState.longitude = 0;
                newState.latitude = 10;
                newState.zoom = 0.85;
            }
            newState.pitch = 0;
            newState.bearing = 0;
            newState.transitionDuration = 1600;
            newState.transitionInterpolator = new deck.FlyToInterpolator();

            currentViewState = newState;
            deckgl.setProps({ viewState: currentViewState });

            rotateTimer = setTimeout(() => {
                isInteracting = false;
            }, 2200);
        });

        // Listen for Shiny panel close to resume globe spin and zoom back out
        Shiny.addCustomMessageHandler("panel_closed", function (msg) {
            const panel = document.querySelector('.deep-dive-panel');
            if (panel) panel.classList.remove('is-visible');
            isPanelOpen = groupFocusOpen;
            if (groupFocusOpen) {
                if (deckgl && lastReceivedData) renderLayers(lastReceivedData);
                return;
            }

            if (deckgl) {
                isInteracting = true;
                clearTimeout(rotateTimer);

                const newState = Object.assign({}, currentViewState);
                newState.zoom = 0.85;
                newState.latitude = 10;
                newState.transitionDuration = 1500;
                newState.transitionInterpolator = new deck.FlyToInterpolator();

                currentViewState = newState;
                deckgl.setProps({ viewState: currentViewState });

                rotateTimer = setTimeout(() => {
                    isInteracting = false;
                }, 2000);
            }
        });

        Shiny.addCustomMessageHandler("deep_dive_visibility", function (msg) {
            const panel = document.querySelector('.deep-dive-panel');
            if (!panel) return;
            panel.classList.toggle('is-visible', !!msg.open);
        });

        Shiny.addCustomMessageHandler('fly_to', function (targetState) {
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
            deckgl.setProps({ viewState: currentViewState });

            rotateTimer = setTimeout(() => {
                isInteracting = false;
            }, 3500);
        });
    }

    // Setup View Toggle Button
    const toggleBtn = document.getElementById('view-toggle-btn');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            if (!deckgl) return;
            is3D = !is3D;
            if (is3D) {
                toggleBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-map" style="margin-right: 6px;"><polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21"></polygon><line x1="9" y1="3" x2="9" y2="18"></line><line x1="15" y1="6" x2="15" y2="21"></line></svg> 2D Map`;
            } else {
                toggleBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-globe" style="margin-right: 6px;"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg> 3D Globe`;
                // Reset pitch and bearing for 2D View
                currentViewState.pitch = 0;
                currentViewState.bearing = 0;
                deckgl.setProps({ viewState: currentViewState });
            }
            deckgl.setProps({
                views: is3D ? globeView : mapView
            });
        });
    }
});
