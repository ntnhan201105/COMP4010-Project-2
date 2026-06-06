/**
 * Demographic Globe — adapted from globevis/deck_map.js
 *
 * Key additions on top of globevis:
 *  - Container: #globe-container (sidebar-ready)
 *  - Shiny bridge: split_update_globe_data / split_select_country / split_country_iso
 *  - War-torn country red-outline overlay
 *  - Dark / light ocean via data-theme
 *  - ResizeObserver so the canvas tracks sidebar drag
 *  - Handles both "pop" (globevis) and "population" (legacy) in payload rows
 */
document.addEventListener("DOMContentLoaded", () => {
  let deckWaitAttempts = 0;

  function getDeckLib() {
    try {
      if (typeof deck !== "undefined") return deck;
    } catch (_err) {
      // Ignore cross-script/global lookup failures.
    }
    return window.deck || null;
  }

  function waitForDeck() {
    const deckLib = getDeckLib();
    if (deckLib) {
      initializeSplitGlobe(deckLib);
      return;
    }

    deckWaitAttempts += 1;
    if (deckWaitAttempts <= 80) {
      setTimeout(waitForDeck, 250);
      return;
    }

    console.error("Split globe could not start because deck.gl did not load.");
  }

  waitForDeck();
});

function initializeSplitGlobe(deck) {
  let deckgl = null;
  let geojsonObject = null;
  let currentYearData = [];
  let dataMap = new Map();               // O(1) iso_alpha → row
  let currentIndicator = "Demographic Cluster";
  let selectedIso = null;
  let isInteracting = false;
  let rotateTimer = null;
  let isPanelOpen = false;
  let is3D = true;
  let focusGroupData = null;  // { origins, hosts, isos, dim, open }

  const globeView = new deck._GlobeView({ id: "globe" });
  const mapView = new deck.MapView({ id: "map", repeat: true });

  const containerId = "globe-container";
  const GEOJSON_URL =
    "https://d2ad6b4ur7yvpq.cloudfront.net/naturalearth-3.3.0/ne_50m_admin_0_countries.geojson";

  let currentViewState = {
    longitude: 12,
    latitude: 18,
    zoom: 1.05,
    pitch: 0,
    bearing: 0,
  };

  /* ────────── Custom DOM Tooltip (no flicker during rotation) ────────── */
  const tooltip = document.createElement("div");
  tooltip.id = "globe-custom-tooltip";
  tooltip.style.cssText = `
    position: fixed;
    pointer-events: none;
    z-index: 9999;
    background: #101828;
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 8px;
    color: #ffffff;
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 0.88rem;
    line-height: 1.45;
    padding: 10px 14px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.55);
    max-width: 240px;
    display: none;
    transition: opacity 0.15s ease;
    opacity: 0;
  `;
  document.body.appendChild(tooltip);

  let tooltipVisible = false;
  let tooltipHideTimer = null;
  let lastTooltipHtml = "";
  let hoveredIso = null;
  let mouseX = 0, mouseY = 0;

  document.addEventListener("mousemove", (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
    if (tooltipVisible) positionTooltip();
  });

  function positionTooltip() {
    const pad = 14;
    const tw = tooltip.offsetWidth;
    const th = tooltip.offsetHeight;
    let x = mouseX + pad;
    let y = mouseY + pad;
    if (x + tw > window.innerWidth) x = mouseX - tw - pad;
    if (y + th > window.innerHeight) y = mouseY - th - pad;
    tooltip.style.left = x + "px";
    tooltip.style.top = y + "px";
  }

  function showTooltip(html) {
    if (tooltipHideTimer) {
      clearTimeout(tooltipHideTimer);
      tooltipHideTimer = null;
    }

    if (html !== lastTooltipHtml) {
      tooltip.innerHTML = html;
      lastTooltipHtml = html;
    }

    if (!tooltipVisible) {
      tooltip.style.display = "block";
      requestAnimationFrame(() => {
        tooltip.style.opacity = "1";
        positionTooltip();
      });
    } else {
      positionTooltip();
    }
    tooltipVisible = true;
  }

  function hideTooltip() {
    tooltip.style.opacity = "0";
    tooltipVisible = false;
    hoveredIso = null;
    tooltipHideTimer = setTimeout(() => {
      if (!tooltipVisible) tooltip.style.display = "none";
      tooltipHideTimer = null;
    }, 150);
  }

  /* ────────── Helpers ────────── */
  const isDark = () =>
    document.documentElement.getAttribute("data-theme") === "dark";

  const generateGlobePolygon = () => {
    const coords = [];
    for (let lng = -180; lng <= 180; lng += 2) coords.push([lng, 89.9]);
    coords.push([180, 89.9]);
    for (let lng = 180; lng >= -180; lng -= 2) coords.push([lng, -89.9]);
    coords.push([-180, -89.9]);
    coords.push([-180, 89.9]);
    return [coords];
  };

  const flattenCoords = (coords, out = []) => {
    if (!Array.isArray(coords)) return out;
    if (typeof coords[0] === "number" && typeof coords[1] === "number") {
      out.push(coords);
      return out;
    }
    coords.forEach((c) => flattenCoords(c, out));
    return out;
  };

  const centroidForIso = (iso) => {
    if (!geojsonObject || !iso) return null;
    const f = geojsonObject.features.find(
      (f) => (f.properties.iso_a3 || "").toUpperCase() === iso.toUpperCase()
    );
    if (!f) return null;
    const pts = flattenCoords(f.geometry.coordinates).filter(
      ([lng, lat]) => Number.isFinite(lng) && Number.isFinite(lat)
    );
    if (!pts.length) return null;
    return [
      pts.reduce((s, p) => s + p[0], 0) / pts.length,
      pts.reduce((s, p) => s + p[1], 0) / pts.length,
    ];
  };

  /* ────────── Tooltip HTML ────────── */
  function tooltipHtml(d) {
    if (!d) return "<div>No demographic data</div>";
    let value = d.raw_value;
    if (typeof value === "number") {
      value =
        currentIndicator === "Population"
          ? Math.round(value).toLocaleString()
          : value.toFixed(2);
    }
    const popVal = d.population || d.pop || 0;
    const pop = Math.round(popVal).toLocaleString();
    return `
      <div style="margin-bottom:4px;">
        <strong style="color:#93c5fd;font-size:1.05em;">${d.country}</strong>
      </div>
      <div style="color:#94a3b8;font-size:0.78em;margin-bottom:2px;">
        Population: <span style="color:#e2e8f0;">${pop}</span>
      </div>
      <div style="color:#94a3b8;font-size:0.78em;">
        ${currentIndicator}: <strong style="color:#ffffff;">${value ?? "-"}</strong>
      </div>
    `;
  }

  /* ────────── Layers ────────── */
  // Singleton ocean — created once, never recreated (matching ThaiAn approach)
  const _oceanLayer = new deck.SolidPolygonLayer({
    id: "split-ocean",
    data: [generateGlobePolygon()],
    getPolygon: (d) => d,
    stroked: false,
    filled: true,
    pickable: true,
    getFillColor: isDark() ? [8, 18, 54, 255] : [210, 225, 240, 255],
  });
  // Update ocean color on theme change
  function updateOceanColor() {
    _oceanLayer.setProps({
      getFillColor: isDark() ? [8, 18, 54, 255] : [210, 225, 240, 255],
    });
  }

  function renderLayers(data) {
    if (!deckgl || !geojsonObject) return;

    // O(1) lookup map
    dataMap.clear();
    if (data) {
      data.forEach((d) => {
        if (d.iso_alpha) dataMap.set(d.iso_alpha.toLowerCase(), d);
      });
      currentYearData = data;
    }

    // Map Python colours onto GeoJSON features
    geojsonObject.features.forEach((f) => {
      const iso = (f.properties.iso_a3 || "").toLowerCase();
      const d = dataMap.get(iso);
      if (d) {
        f.properties._fillColor = [d.color_r, d.color_g, d.color_b, 240];
        f.properties._isWar = d.is_war_torn === true;
      } else {
        f.properties._fillColor = isDark()
          ? [54, 61, 74, 225]
          : [214, 224, 233, 225];
        f.properties._isWar = false;
      }
    });

    const landLayer = new deck.GeoJsonLayer({
      id: "split-earth-land",
      data: geojsonObject,
      stroked: true,
      filled: true,
      lineWidthMinPixels: 0.8,
      getLineColor: (f) => {
        if (f.properties._isWar) return [255, 49, 49, 245];
        if (
          selectedIso &&
          (f.properties.iso_a3 || "").toUpperCase() === selectedIso
        )
          return [255, 49, 49, 255];
        return isDark() ? [80, 90, 110, 70] : [95, 108, 130, 95];
      },
      getLineWidth: (f) => {
        if (f.properties._isWar) return 2.2;
        if (
          selectedIso &&
          (f.properties.iso_a3 || "").toUpperCase() === selectedIso
        )
          return 3;
        return 0.8;
      },
      getFillColor: (f) => f.properties._fillColor,
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 38],
      updateTriggers: {
        getFillColor: [data, selectedIso],
        getLineColor: [data, selectedIso],
        getLineWidth: [data, selectedIso],
      },
      transitions: {
        getFillColor: { duration: 500, type: "interpolation" },
      },
    });

    // ── Floating labels (TextLayer) — country name + indicator value ──
    var labelData = [];
    if (currentYearData && currentYearData.length > 0 && geojsonObject) {
      var focusIsos = (focusGroupData && focusGroupData.open && focusGroupData.isos)
        ? new Set(focusGroupData.isos.map(function (i) { return i.toUpperCase(); }))
        : null;

      var candidates = currentYearData.filter(function (d) {
        if (!d.iso_alpha) return false;
        if (focusIsos) return focusIsos.has(d.iso_alpha.toUpperCase());
        // In global mode, show top 8 most populous
        return d.population > 50000000;
      }).slice(0, focusIsos ? 12 : 8);

      candidates.forEach(function (d) {
        var c = centroidForIso(d.iso_alpha);
        if (!c || !isFinite(c[0]) || !isFinite(c[1])) return;
        var val = d.raw_value;
        var valStr = "";
        if (typeof val === "number") {
          if (currentIndicator === "Population") valStr = (Math.round(val) / 1e6).toFixed(1) + "M";
          else if (currentIndicator === "net_migration_rate") valStr = val.toFixed(2);
          else if (currentIndicator === "fertility_rate") valStr = val.toFixed(2);
          else valStr = val.toFixed(1);
        }
        labelData.push({
          position: [c[0], c[1], 0],
          text: d.country + (valStr ? " " + valStr : ""),
        });
      });
    }

    var textLayer = null;
    if (labelData.length > 0 && deck.TextLayer) {
      textLayer = new deck.TextLayer({
        id: "globe-labels",
        data: labelData,
        getPosition: function (d) { return d.position; },
        getText: function (d) { return d.text; },
        getSize: 12,
        getAngle: 0,
        getTextAnchor: "middle",
        getAlignmentBaseline: "center",
        fontFamily: "Inter, sans-serif",
        getFontWeight: 600,
        getColor: [255, 255, 255, 230],
        background: true,
        getBackgroundColor: [8, 16, 36, 200],
        backgroundPadding: [6, 4],
        billboard: true,
        sizeScale: 1,
        sizeUnits: "pixels",
        pickable: false,
      });
    }

    // ── Migration arcs (ArcLayer or LineLayer) — flow lines ──
    var arcData = [];
    if (focusGroupData && focusGroupData.open && focusGroupData.origins && focusGroupData.hosts) {
      focusGroupData.origins.forEach(function (originIso) {
        var from = centroidForIso(originIso);
        if (!from || !isFinite(from[0])) return;
        focusGroupData.hosts.forEach(function (hostIso) {
          var to = centroidForIso(hostIso);
          if (!to || !isFinite(to[0])) return;
          arcData.push({ from: [from[0], from[1], 0], to: [to[0], to[1], 0] });
        });
      });
    }

    var arcLayer = null;
    if (arcData.length > 0 && deck.ArcLayer) {
      arcLayer = new deck.ArcLayer({
        id: "globe-arcs",
        data: arcData,
        getSourcePosition: function (d) { return d.from; },
        getTargetPosition: function (d) { return d.to; },
        getSourceColor: [239, 68, 68, 200],
        getTargetColor: [34, 211, 238, 200],
        getWidth: 2,
        greatCircle: true,
        pickable: false,
      });
    }

    deckgl.setProps({ layers: [_oceanLayer, landLayer, textLayer, arcLayer].filter(Boolean) });
  }

  /* ────────── Deck.gl initialisation ────────── */
  function initDeck() {
    const container = document.getElementById(containerId);
    if (!container || !window.deck) return;

    deckgl = new deck.DeckGL({
      container,
      views: is3D ? globeView : mapView,
      viewState: currentViewState,
      controller: true,
      // Disable built-in tooltip — custom DOM tooltip used instead
      getTooltip: () => null,

      onHover: (info) => {
        if (isInteracting) {
          hideTooltip();
          return;
        }
        const { object, layer, coordinate } = info;

        if (object && layer && layer.id === "split-earth-land") {
          /* ── Back-face culling ── */
          if (coordinate) {
            const [lng, lat] = coordinate;
            const camLng = (currentViewState.longitude * Math.PI) / 180;
            const camLat = ((currentViewState.latitude || 0) * Math.PI) / 180;
            const ptLng = (lng * Math.PI) / 180;
            const ptLat = (lat * Math.PI) / 180;
            const dot =
              Math.sin(camLat) * Math.sin(ptLat) +
              Math.cos(camLat) * Math.cos(ptLat) * Math.cos(ptLng - camLng);
            if (dot < 0.05) {
              container.style.cursor = "grab";
              hideTooltip();
              return;
            }
          }

          container.style.cursor = "pointer";
          const iso = (object.properties.iso_a3 || "").toLowerCase();
          hoveredIso = iso;
          showTooltip(tooltipHtml(dataMap.get(iso) || null));
        } else {
          container.style.cursor = "grab";
          hideTooltip();
        }
      },

      onClick: (info) => {
        const { object, layer, coordinate } = info;
        if (object && layer && layer.id === "split-earth-land") {
          /* ── Back-face culling ── */
          if (coordinate) {
            const [lng, lat] = coordinate;
            const camLng = (currentViewState.longitude * Math.PI) / 180;
            const camLat = ((currentViewState.latitude || 0) * Math.PI) / 180;
            const ptLng = (lng * Math.PI) / 180;
            const ptLat = (lat * Math.PI) / 180;
            const dot =
              Math.sin(camLat) * Math.sin(ptLat) +
              Math.cos(camLat) * Math.cos(ptLat) * Math.cos(ptLng - camLng);
            if (dot < 0.05) return;
          }

          const iso = (object.properties.iso_a3 || "").toUpperCase();
          if (!iso || iso === "-99") return;

          selectedIso = iso;
          isPanelOpen = true;
          isInteracting = true;
          clearTimeout(rotateTimer);

          const centroid = centroidForIso(iso);
          const newState = Object.assign({}, currentViewState);
          if (centroid) {
            newState.longitude = centroid[0];
            newState.latitude = Math.max(Math.min(centroid[1], 70), -65);
          }
          newState.zoom = Math.max(currentViewState.zoom, 2.2);
          newState.transitionDuration = 1500;
          newState.transitionInterpolator = new deck.FlyToInterpolator();
          currentViewState = newState;
          deckgl.setProps({ viewState: currentViewState });

          renderLayers(currentYearData);

          rotateTimer = setTimeout(() => {
            isInteracting = false;
          }, 2500);

          // Send to Shiny after animation settles
          if (window.Shiny) {
            setTimeout(() => {
              Shiny.setInputValue("split_country_iso", iso, {
                priority: "event",
              });
            }, 1200);
          }
        }
      },

      onViewStateChange: ({ viewState, interactionState }) => {
        currentViewState = viewState;
        deckgl.setProps({ viewState: currentViewState });

        if (
          interactionState &&
          (interactionState.isDragging ||
            interactionState.isPanning ||
            interactionState.isZooming)
        ) {
          isInteracting = true;
          clearTimeout(rotateTimer);
          rotateTimer = setTimeout(() => {
            isInteracting = false;
          }, 3000);
        }
      },
      layers: [],
    });

    // Fetch GeoJSON
    fetch(GEOJSON_URL)
      .then((res) => res.json())
      .then((geojson) => {
        geojsonObject = geojson;
        if (currentYearData.length) {
          renderLayers(currentYearData);
        } else {
          // Fallback grey landmass while waiting for Python data
          geojsonObject.features.forEach(
            (f) => (f.properties._fillColor = [58, 65, 78, 255])
          );
          const defaultLand = new deck.GeoJsonLayer({
            id: "split-earth-land",
            data: geojsonObject,
            stroked: true,
            filled: true,
            lineWidthMinPixels: 0.8,
            getLineColor: [80, 90, 110, 70],
            getFillColor: (f) => f.properties._fillColor,
            pickable: true,
            autoHighlight: true,
            highlightColor: [255, 255, 255, 38],
          });
          deckgl.setProps({ layers: [_oceanLayer, defaultLand] });
        }
      })
      .catch((err) =>
        console.error("Split globe GeoJSON failed to load:", err)
      );

    /* ── Auto-rotation (30 FPS) ── */
    let lastRot = 0;
    const TARGET_FPS = 30;
    const FRAME_MS = 1000 / TARGET_FPS;

    function rotateGlobe(ts) {
      if (ts - lastRot >= FRAME_MS) {
        lastRot = ts;
        if (deckgl && !isInteracting && !isPanelOpen && is3D) {
          currentViewState = Object.assign({}, currentViewState, {
            longitude: (currentViewState.longitude + 0.06) % 360,
          });
          deckgl.setProps({ viewState: currentViewState });
        }
      }
      requestAnimationFrame(rotateGlobe);
    }
    setTimeout(() => requestAnimationFrame(rotateGlobe), 2500);

    /* ── ResizeObserver for sidebar drag ── */
    if (window.ResizeObserver) {
      new ResizeObserver(() => {
        if (deckgl) {
          deckgl.setProps({ viewState: currentViewState });
          if (deckgl.deck && typeof deckgl.deck.redraw === "function") {
            deckgl.deck.redraw(true);
          }
          renderLayers(currentYearData);
        }
      }).observe(container);
    }
  }

  /* ────────── Shiny bridge ────────── */
  if (window.Shiny) {
    Shiny.addCustomMessageHandler("split_update_globe_data", (msg) => {
      const data = msg.data || [];
      currentYearData = data;
      currentIndicator = msg.indicator || "Demographic Cluster";
      currentYearData.forEach((d) => {
        if (d.iso_alpha) dataMap.set(d.iso_alpha.toLowerCase(), d);
      });

      if (!deckgl) {
        initDeck();
      } else {
        renderLayers(data);
        if (tooltipVisible && hoveredIso) {
          showTooltip(tooltipHtml(dataMap.get(hoveredIso) || null));
        }
      }
    });

    Shiny.addCustomMessageHandler("split_select_country", (msg) => {
      const iso = (msg.iso || "").toUpperCase();
      selectedIso = iso;
      isPanelOpen = true;
      isInteracting = true;
      clearTimeout(rotateTimer);

      const centroid = centroidForIso(iso);
      if (centroid && deckgl) {
        const newState = Object.assign({}, currentViewState);
        newState.longitude = centroid[0];
        newState.latitude = Math.max(Math.min(centroid[1], 70), -65);
        newState.zoom = Math.max(currentViewState.zoom, 2.2);
        newState.transitionDuration = 1500;
        newState.transitionInterpolator = new deck.FlyToInterpolator();
        currentViewState = newState;
        deckgl.setProps({ viewState: currentViewState });
      }

      renderLayers(currentYearData);

      rotateTimer = setTimeout(() => {
        isInteracting = false;
        isPanelOpen = false;
      }, 3000);
    });

    // Deep Dive panel closed — zoom back out, resume rotation
    Shiny.addCustomMessageHandler("panel_closed", (_msg) => {
      isPanelOpen = false;
      if (deckgl) {
        isInteracting = true;
        clearTimeout(rotateTimer);

        const newState = Object.assign({}, currentViewState);
        newState.zoom = 1.05;
        newState.latitude = 18;
        newState.transitionDuration = 1500;
        newState.transitionInterpolator = new deck.FlyToInterpolator();
        currentViewState = newState;
        deckgl.setProps({ viewState: currentViewState });

        rotateTimer = setTimeout(() => {
          isInteracting = false;
        }, 2000);
      }
    });

    // Story focus group — dim non-focused countries, highlight story isos
    Shiny.addCustomMessageHandler("focus_group", (msg) => {
      focusGroupData = msg;  // store for renderLayers (labels + arcs)
      if (!geojsonObject) return;
      const focusSet = new Set((msg.isos || []).map((i) => i.toUpperCase()));
      const originsSet = new Set((msg.origins || []).map((i) => i.toUpperCase()));
      const hostsSet = new Set((msg.hosts || []).map((i) => i.toUpperCase()));
      const shouldDim = msg.dim && focusSet.size > 0;

      geojsonObject.features.forEach((f) => {
        const iso = (f.properties.iso_a3 || "").toUpperCase();
        const d = dataMap.get(iso.toLowerCase());
        if (!d) return;
        if (!shouldDim) {
          f.properties.fillColor = [d.color_r, d.color_g, d.color_b, 240];
        } else if (originsSet.has(iso)) {
          f.properties.fillColor = [240, 40, 40, 240];       // red = outflow
        } else if (hostsSet.has(iso)) {
          f.properties.fillColor = [0, 200, 230, 240];        // cyan = inflow
        } else if (focusSet.has(iso)) {
          f.properties.fillColor = [d.color_r, d.color_g, d.color_b, 240];
        } else {
          f.properties.fillColor = [38, 42, 55, 180];         // dimmed
        }
      });

      if (deckgl) renderLayers(currentYearData);

      // Fly to target region
      if (msg.targetState && deckgl) {
        isInteracting = true;
        clearTimeout(rotateTimer);
        const ns = Object.assign({}, currentViewState, msg.targetState, {
          transitionDuration: 1800,
          transitionInterpolator: new deck.FlyToInterpolator(),
        });
        currentViewState = ns;
        deckgl.setProps({ viewState: currentViewState });
        rotateTimer = setTimeout(() => { isInteracting = false; }, 3000);
      }
    });
  }

  /* ── 2D / 3D toggle — attaches to Python-rendered button ── */
  let _viewToggleReady = false;
  function setupViewToggle() {
    const btn = document.getElementById("globe-view-toggle");
    if (!btn) { setTimeout(setupViewToggle, 300); return; }
    if (_viewToggleReady) return;
    _viewToggleReady = true;

    function updateLabel() {
      if (is3D) {
        btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:5px;"><polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21"></polygon><line x1="9" y1="3" x2="9" y2="18"></line><line x1="15" y1="6" x2="15" y2="21"></line></svg>2D Map';
      } else {
        btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:5px;"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>3D Globe';
      }
    }

    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (!deckgl) return;
      is3D = !is3D;
      updateLabel();
      if (!is3D) {
        currentViewState.pitch = 0;
        currentViewState.bearing = 0;
      }
      hideTooltip();
      deckgl.setProps({ views: is3D ? globeView : mapView });
    });
  }
  setTimeout(setupViewToggle, 600);

  function splitGlobeDebug() {
    return {
      hasDeck: Boolean(window.deck),
      hasDeckgl: Boolean(deckgl),
      hasGeojson: Boolean(geojsonObject),
      is3D,
      currentRows: currentYearData.length,
      layers: deckgl && deckgl.props && deckgl.props.layers
        ? deckgl.props.layers.length
        : 0,
    };
  }

  try {
    window._toggleGlobeView = toggleGlobeView;
    window._splitGlobeDebug = splitGlobeDebug;
  } catch (_err) {
    // Some embedded browser contexts prevent adding globals; the direct listener above still works.
  }

  // Fallback
  document.addEventListener("shiny:connected", initDeck);
  setTimeout(initDeck, 500);
}
