const API_BASE = 'http://localhost:7860/api/v1';

// ----------------------------------------------------
// 1. LEAFLET MAP INITIALIZATION & CONFIG (KARNATAKA, INDIA)
// ----------------------------------------------------
const map = L.map('vis-container', {
    center: [12.8, 77.2],
    zoom: 9,
    zoomControl: false,
    attributionControl: false
});
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { subdomains: 'abcd', maxZoom: 18 }).addTo(map);

// ----------------------------------------------------
// STATE & CACHING LOGIC
// ----------------------------------------------------
let lastState = null;
let lastGrade = null;
let simulationPaused = false; 
let demoActive = true; 

const loggedEvents = new Set();
const renderedTrucks = new Map(); 
const renderedHubs = new Map();   
const activeRoutes = new Map();   
const lastCargoCache = new Map(); 
const truckOrigins = new Map(); 
const osrmRoutesCache = new Map();

// ----------------------------------------------------
// DYNAMIC SVG LAYER SCALING MECHANICS (Leaflet Zoom Hack)
// ----------------------------------------------------
map.on('zoomend', () => {
    const zoom = map.getZoom();
    const dynamicWeight = zoom < 7 ? 2 : 5; // Scales massive paths down to 2px over India orbit!

    activeRoutes.forEach((line) => {
        if (line.options) line.setStyle({ weight: dynamicWeight });
    });
    truckTrails.forEach((t) => {
        if (t.polyline) t.polyline.setStyle({ weight: Math.max(2, dynamicWeight - 2) });
    });
});

// ----------------------------------------------------
// CORE PHYSICS VARIABLES
// ----------------------------------------------------
const visualTruckProgress = new Map(); 
const truckTrails = new Map(); 
let lastFrameTime = performance.now();

const KARNATAKA_NODES = {
    "W1": [13.0031, 77.5643], // Malleswaram
    "W2": [12.2958, 76.6394], // Mysore
    "W3": [12.9189, 77.2938], // Savandurga Hills
    "W4": [13.1989, 77.7068]  // Kempegowda Intl
};
function getHubLatLng(nodeId) { return KARNATAKA_NODES[nodeId] || [13.0, 77.5]; }

// ----------------------------------------------------
// OSRM ROUTING 
// ----------------------------------------------------
async function getOSRMRoute(fromId, toId) {
    const routeKey = [fromId, toId].sort().join("-");
    if (osrmRoutesCache.has(routeKey)) return osrmRoutesCache.get(routeKey);

    const fromCoord = getHubLatLng(fromId);
    const toCoord = getHubLatLng(toId);
    try {
        const url = `https://router.project-osrm.org/route/v1/driving/${fromCoord[1]},${fromCoord[0]};${toCoord[1]},${toCoord[0]}?overview=full&geometries=geojson`;
        const res = await fetch(url);
        const data = await res.json();
        if (data.routes && data.routes.length > 0) {
            let coords = data.routes[0].geometry.coordinates.map(c => [c[1], c[0]]);
            osrmRoutesCache.set(routeKey, coords);
            return coords;
        }
    } catch(e) { console.error("OSRM Failed", e); }
    const fallback = [fromCoord, toCoord];
    osrmRoutesCache.set(routeKey, fallback);
    return fallback;
}

// ----------------------------------------------------
// API & NETWORK LOOP
// ----------------------------------------------------
async function fetchAPI() {
    if (simulationPaused || demoActive) return; 
    try {
        const stateRes = await fetch(`${API_BASE}/state`);
        if (stateRes.ok) lastState = await stateRes.json();
        const gradeRes = await fetch(`${API_BASE}/grade`);
        if (gradeRes.ok) lastGrade = await gradeRes.json();
        
        if (lastState && lastState.routes) {
            for (const route of lastState.routes) await getOSRMRoute(route.from_warehouse, route.to_warehouse);
        }
        renderHUD(); renderStaticMapElements();
    } catch (e) { }
}

// ----------------------------------------------------
// RENDERERS
// ----------------------------------------------------
function triggerGlitchShake() {
    document.body.classList.add('system-glitch');
    setTimeout(() => { document.body.classList.remove('system-glitch'); }, 500);
}

function addToTerminal(msg, cssClass="muted") {
    const logList = document.getElementById('log-list');
    const li = document.createElement('li');
    li.className = cssClass;
    li.innerHTML = msg;
    logList.appendChild(li);
    logList.scrollTop = logList.scrollHeight;
}

function renderHUD() {
    if (!lastState) return;
    document.getElementById('stat-time').innerText = lastState.time_step || 0;
    document.getElementById('stat-completed').innerText = lastState.metrics?.completed_deliveries?.length || 0;
    if (lastGrade) {
        document.getElementById('stat-delivery').innerText = `${((lastGrade.delivery_rate || 0) * 100).toFixed(1)}%`;
        document.getElementById('stat-score').innerText = (lastGrade.score || 0).toFixed(4);
    }
    updateTruckSelector();
    renderOrdersPanel();
    renderWarehousePanel();
}

function renderOrdersPanel() {
    if (!lastState || !lastState.orders) return;
    const container = document.getElementById('order-list');
    const pending = lastState.orders.filter(o => o.status === 'pending');
    document.getElementById('order-count').innerText = pending.length;
    
    container.innerHTML = lastState.orders.map(order => {
        const isCompleted = order.status === 'delivered';
        const itemsStr = Object.entries(order.items).map(([k,v]) => `${k}:${v}`).join(', ');
        return `
            <div class="order-item ${isCompleted ? 'completed' : ''}">
                <span class="order-id">${order.id}</span>
                <span class="order-status ${order.status}">${order.status}</span>
                <div class="order-route">${order.source} → ${order.destination}</div>
                <div class="order-items">${itemsStr}</div>
                <div class="order-deadline">Deadline: T=${order.deadline}</div>
            </div>
        `;
    }).join('');
}

function renderWarehousePanel() {
    if (!lastState || !lastState.warehouses) return;
    const container = document.getElementById('warehouse-list');
    container.innerHTML = lastState.warehouses.map(w => {
        const invStr = Object.entries(w.inventory).filter(([_,q]) => q > 0).map(([k,v]) => `${k}:${v}`).join(', ');
        return `
            <div class="warehouse-item">
                <span class="warehouse-id">${w.id}</span>
                <div class="warehouse-inv">${invStr || 'EMPTY'}</div>
            </div>
        `;
    }).join('');
}

function addToActionHistory(action, result, reward) {
    const container = document.getElementById('action-log');
    const item = document.createElement('div');
    item.className = 'history-item';
    item.innerHTML = `
        <span class="time">T=${lastState?.time_step || 0}</span>
        <span class="action">${action}</span>
        <span class="result">${result} (${reward > 0 ? '+' : ''}${reward.toFixed(2)})</span>
    `;
    container.insertBefore(item, container.firstChild);
    if (container.children.length > 20) container.removeChild(container.lastChild);
}

function renderStaticMapElements() {
    if (!lastState || !lastState.warehouses) return;
    
    lastState.warehouses.forEach(w => {
        const currentLatLng = getHubLatLng(w.id);
        let marker = renderedHubs.get(w.id);
        const invStr = Object.entries(w.inventory || {}).filter(([_, q]) => q > 0).map(([item, qty]) => `${item}:${qty}`).join(' | ');

        if (!marker) {
            const icon = L.divIcon({
                className: 'hub-wrapper',
                html: `<div class="hub"><div class="hub-label">${w.id}</div><div class="hub-icon"><i class="fa-solid fa-building-circle-check"></i></div><div class="hub-inventory" id="inv-${w.id}">${invStr || 'EMPTY'}</div></div>`,
                iconSize: [80, 80], iconAnchor: [40, 40]
            });
            marker = L.marker(currentLatLng, {icon, zIndexOffset: 500}).addTo(map);
            renderedHubs.set(w.id, marker);
        } else {
            const el = marker.getElement();
            if(el) { const div = el.querySelector(`#inv-${w.id}`); if(div) div.innerHTML = invStr || 'EMPTY'; }
        }
    });
    
    // Grab explicit zoom target array
    const zoomWt = map.getZoom() < 7 ? 2 : 5;
    
    (lastState.routes || []).forEach(route => {
        const routeKey = [route.from_warehouse, route.to_warehouse].sort().join("-");
        const coords = osrmRoutesCache.get(routeKey);
        if(!coords) return; 
        
        const cssClass = route.status === 'blocked' ? 'route-hazard' : 'route-line';
        let line = activeRoutes.get(routeKey);
        if(!line) {
            line = L.polyline(coords, {className: cssClass, weight: zoomWt}).addTo(map);
            activeRoutes.set(routeKey, line);
        } else {
            if(line.options.className !== cssClass) line.setStyle({className: cssClass, weight: zoomWt});
            else line.setStyle({weight: zoomWt});
        }
    });
}

// ----------------------------------------------------
// NATIVE REQUEST-ANIMATION-FRAME PHYSICS (BEARING & TRANSLATION)
// ----------------------------------------------------
// Haversine Sphere logic for absolute true geographic orientation (ignores screen pixel warping!)
function calculateTrueBearing(lat1, lng1, lat2, lng2) {
    const toRad = p => p * Math.PI / 180;
    const toDeg = p => p * 180 / Math.PI;
    const dLng = toRad(lng2 - lng1);
    lat1 = toRad(lat1); lat2 = toRad(lat2);
    const y = Math.sin(dLng) * Math.cos(lat2);
    const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng);
    return (toDeg(Math.atan2(y, x)) + 360) % 360;
}

function getPathPointWithBearing(coords, progress, reversing) {
    if(!coords || coords.length === 0) return {latlng: [0,0], angle: null};
    if(progress <= 0 || progress >= 1) return {latlng: coords[progress<=0?0:coords.length-1], angle: null};
    
    let totalDist = 0; const segmentDists = [];
    for(let i=0; i < coords.length-1; i++) {
        const dx = coords[i+1][0] - coords[i][0]; const dy = coords[i+1][1] - coords[i][1];
        const d = Math.sqrt(dx*dx + dy*dy); segmentDists.push(d); totalDist += d;
    }
    const targetDist = totalDist * progress; let distSoFar = 0;
    
    for(let i=0; i < segmentDists.length; i++) {
        if(distSoFar + segmentDists[i] >= targetDist) {
            const lp = (targetDist - distSoFar) / (segmentDists[i] || 1);
            const lat = coords[i][0] + (coords[i+1][0] - coords[i][0]) * lp;
            const lng = coords[i][1] + (coords[i+1][1] - coords[i][1]) * lp;
            
            // Calculate absolute geographic spherical bearing regardless of viewport/pixel distortion
            let bearing = calculateTrueBearing(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1]);
            if (reversing) bearing = (bearing + 180) % 360; // 180 Array Inversion Flip

            // CSS Bearing mapping (0deg CSS points East, 0deg Bearing points North) => CSS = Bearing - 90
            return {latlng: [lat, lng], angle: bearing - 90};
        }
        distSoFar += segmentDists[i];
    }
    return {latlng: coords[coords.length-1], angle: null};
}

function physicsLoop() {
    const now = performance.now();
    const dt = (now - lastFrameTime) / 1000.0; 
    lastFrameTime = now;
    
    if (lastState && lastState.trucks && !simulationPaused) {
        lastState.trucks.forEach(t => {
            if (t.location !== 'transit') truckOrigins.set(t.id, t.location);
            
            let targetProgress = 0.0; let currentPath = null; let reversing = false;
            if (t.target_location && t.steps_to_destination > 0) {
                const safeOrig = t.location === 'transit' ? truckOrigins.get(t.id) : t.location;
                const route = lastState.routes.find(r => (r.from_warehouse === safeOrig && r.to_warehouse === t.target_location) || (r.from_warehouse === t.target_location && r.to_warehouse === safeOrig));
                const routeKey = [safeOrig, t.target_location].sort().join("-");
                currentPath = osrmRoutesCache.get(routeKey);
                if (currentPath && getHubLatLng(t.target_location)[0] === currentPath[0][0]) reversing = true;
                const dist = route ? route.distance : t.steps_to_destination;
                targetProgress = Math.max(0, Math.min(1, 1 - (t.steps_to_destination / (dist || 1))));
            }

            let visualProg = visualTruckProgress.get(t.id) || 0;
            if (t.steps_to_destination === 0 && !t.target_location) visualProg = 0; 
            else {
                const diff = targetProgress - visualProg;
                visualProg = Math.abs(diff) > 0.001 ? visualProg + diff * Math.min(1.0, dt * 1.5) : targetProgress;
            }
            visualTruckProgress.set(t.id, visualProg);

            let currentLatLng = getHubLatLng(truckOrigins.get(t.id) || t.location); 
            let angle = renderedTrucks.has(t.id) ? renderedTrucks.get(t.id)._lastAngle || 0 : 0;
            
            if (currentPath) {
                const samplingProg = reversing ? (1.0 - visualProg) : visualProg;
                const pathRes = getPathPointWithBearing(currentPath, samplingProg, reversing);
                currentLatLng = pathRes.latlng;
                
                // Without CSS interpolation jittering, `angle` locks seamlessly skipping -180/180 glitch thresholds natively!
                if (pathRes.angle !== null && t.target_location && visualProg > 0 && visualProg < 1) angle = pathRes.angle;
            }

            let trailMeta = truckTrails.get(t.id);
            if (!trailMeta) {
                trailMeta = { polyline: L.polyline([], { className: 'truck-neon-trail', weight: map.getZoom() < 7 ? 1: 3, zIndexOffset: 200 }).addTo(map), coords: [] };
                truckTrails.set(t.id, trailMeta);
            }
            if (t.target_location && visualProg > 0 && visualProg < 1) {
                trailMeta.coords.push(currentLatLng);
                if (trailMeta.coords.length > 40) trailMeta.coords.shift();
                trailMeta.polyline.setLatLngs(trailMeta.coords);
            } else { trailMeta.coords = []; trailMeta.polyline.setLatLngs([]); }

            const cap = t.capacity || 50;
            const loadPct = Math.min(1.0, (t.current_load||0) / cap);
            const dashOffset = 163 - (163 * loadPct);

            let marker = renderedTrucks.get(t.id);
            if (!marker) {
                const icon = L.divIcon({
                    className: 'truck-glider',
                    html: `<div class="truck"><svg class="cargo-meter"><circle cx="31" cy="31" r="26"></circle><circle class="cargo-fill" id="crcl-${t.id}" stroke-dashoffset="${dashOffset}"></circle></svg><div class="truck-icon-wrapper" id="iconWrap-${t.id}"><i class="fa-solid fa-truck"></i></div><div class="truck-id">${t.id}</div></div>`,
                    iconSize: [62, 62], iconAnchor: [31, 31]
                });
                marker = L.marker(currentLatLng, {icon, zIndexOffset: 1000}).addTo(map);
                marker._lastAngle = angle; renderedTrucks.set(t.id, marker);
            } else {
                marker.setLatLng(currentLatLng); marker._lastAngle = angle;
                const htmlEl = marker.getElement();
                if(htmlEl) {
                    const crcl = htmlEl.querySelector(`#crcl-${t.id}`);
                    if(crcl) crcl.style.strokeDashoffset = dashOffset;
                    const iconWrapper = htmlEl.querySelector(`#iconWrap-${t.id}`);
                    if(iconWrapper) iconWrapper.style.transform = `rotate(${angle}deg)`;
                }
            }
        });
    }
    requestAnimationFrame(physicsLoop);
}

// ----------------------------------------------------
// DEMO NARRATIVE STORY ENGINE (PRD ALIGNMENT)
// ----------------------------------------------------
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function typeWriter(text, isError=false) {
    const el = document.getElementById('narrative-text');
    el.innerHTML = '';
    el.style.color = isError ? "var(--neon-red)" : "var(--neon-blue)";
    for(let i=0; i<text.length; i++) {
        if(!demoActive) return; 
        el.innerHTML += text.charAt(i);
        await sleep(40);
    }
    await sleep(2000);
}

document.getElementById('btn-skip-demo').addEventListener('click', () => {
    demoActive = false;
    document.getElementById('narrative-box').style.display = 'none';
    
    // Show all panels
    const actionPanel = document.getElementById('action-panel');
    const orderPanel = document.getElementById('order-panel');
    const warehousePanel = document.getElementById('warehouse-panel');
    const taskPanel = document.getElementById('task-info');
    
    if (actionPanel) actionPanel.style.display = 'block';
    if (orderPanel) orderPanel.style.display = 'block';
    if (warehousePanel) warehousePanel.style.display = 'block';
    if (taskPanel) taskPanel.style.display = 'block';
    
    lastState = null;
    simulationPaused = false;
    initEnvironment();
});

document.getElementById('btn-execute').addEventListener('click', async () => {
    const truckId = document.getElementById('action-truck').value;
    const actionType = document.getElementById('action-type').value;
    const target = document.getElementById('action-target').value || null;
    const itemsStr = document.getElementById('action-items').value;
    const orderId = document.getElementById('action-order').value || null;
    
    if (!truckId) {
        addToTerminal('ERROR: Select a truck first', 'alert');
        return;
    }
    
    let items = null;
    if (itemsStr) {
        const itemParts = itemsStr.split(',');
        items = {};
        itemParts.forEach(part => {
            const [key, val] = part.trim().split(':');
            if (key && val) items[key] = parseInt(val);
        });
    }
    
    const action = {
        type: actionType,
        truck_id: truckId,
        target: target,
        items: items,
        order_id: orderId
    };
    
    addToTerminal(`EXECUTING: ${actionType} ${target || ''} ${items ? JSON.stringify(items) : ''}`, 'dispatch');
    
    try {
        const res = await fetch(`${API_BASE}/step`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({actions: [action]})
        });
        const result = await res.json();
        if (result.state) {
            lastState = result.state;
            addToActionHistory(actionType, target || orderId || 'wait', result.reward);
            if (result.info && result.info.message) {
                addToTerminal(result.info.message, result.reward > 0 ? 'success' : 'alert');
            }
            renderHUD();
            renderStaticMapElements();
            
            // Check for auto-move
            if (autoMoveEnabled && actionType === 'move' && target) {
                startAutoMove(truckId, target);
            }
        }
    } catch (e) {
        addToTerminal('ERROR: ' + e.message, 'alert');
    }
});

// Quick Actions
async function quickLoadMove() {
    const truck = lastState?.trucks?.[0];
    if (!truck) return;
    
    const order = lastState?.orders?.find(o => o.status === 'pending');
    if (!order) {
        addToTerminal('No pending orders!', 'alert');
        return;
    }
    
    // Load items from source
    const loadAction = {
        type: 'load',
        truck_id: truck.id,
        target: order.source,
        items: order.items
    };
    
    try {
        let res = await fetch(`${API_BASE}/step`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({actions: [loadAction]})
        });
        let result = await res.json();
        if (result.state) {
            lastState = result.state;
            addToActionHistory('LOAD', order.source, result.reward);
            renderHUD();
            renderStaticMapElements();
            
            // Now move to destination
            if (lastState) {
                const moveAction = {
                    type: 'move',
                    truck_id: truck.id,
                    target: order.destination
                };
                res = await fetch(`${API_BASE}/step`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({actions: [moveAction]})
                });
                result = await res.json();
                if (result.state) {
                    lastState = result.state;
                    addToActionHistory('MOVE', order.destination, result.reward);
                    renderHUD();
                    renderStaticMapElements();
                    addToTerminal(`Loaded & moving to ${order.destination}`, 'success');
                }
            }
        }
    } catch (e) {
        addToTerminal('Quick action failed: ' + e.message, 'alert');
    }
}

async function quickDeliver() {
    const truck = lastState?.trucks?.[0];
    if (!truck) return;
    
    const order = lastState?.orders?.find(o => o.status === 'pending');
    if (!order) {
        addToTerminal('No pending orders!', 'alert');
        return;
    }
    
    const deliverAction = {
        type: 'deliver',
        truck_id: truck.id,
        order_id: order.id
    };
    
    try {
        const res = await fetch(`${API_BASE}/step`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({actions: [deliverAction]})
        });
        const result = await res.json();
        if (result.state) {
            lastState = result.state;
            addToActionHistory('DELIVER', order.id, result.reward);
            renderHUD();
            renderStaticMapElements();
            addToTerminal(`Order ${order.id} delivered!`, result.reward > 0 ? 'success' : 'alert');
        }
    } catch (e) {
        addToTerminal('Quick deliver failed: ' + e.message, 'alert');
    }
}

// Auto-Move
let autoMoveEnabled = false;
let autoMoveInterval = null;

function toggleAutoMove() {
    autoMoveEnabled = !autoMoveEnabled;
    const btn = document.getElementById('btn-auto-move');
    btn.innerText = `Auto-Move: ${autoMoveEnabled ? 'ON' : 'OFF'}`;
    btn.classList.toggle('active', autoMoveEnabled);
    addToTerminal(`Auto-Move ${autoMoveEnabled ? 'enabled' : 'disabled'}`, 'dispatch');
}

async function startAutoMove(truckId, target) {
    if (autoMoveInterval) clearInterval(autoMoveInterval);
    
    autoMoveInterval = setInterval(async () => {
        if (!lastState) {
            clearInterval(autoMoveInterval);
            return;
        }
        
        const truck = lastState.trucks.find(t => t.id === truckId);
        if (!truck || truck.location === target || truck.steps_to_destination === 0) {
            clearInterval(autoMoveInterval);
            addToTerminal(`Arrived at ${target}`, 'success');
            return;
        }
        
        try {
            const res = await fetch(`${API_BASE}/step`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({actions: [{type: 'move', truck_id: truckId, target: target}]})
            });
            const result = await res.json();
            if (result.state) {
                lastState = result.state;
                renderHUD();
                renderStaticMapElements();
            }
        } catch (e) {
            clearInterval(autoMoveInterval);
        }
    }, 500);
}

// Task selector
document.getElementById('task-selector').addEventListener('change', (e) => {
    selectedTask = e.target.value;
    showTaskInfo(selectedTask);
});

document.getElementById('btn-reset').addEventListener('click', async () => {
    if (simulationPaused || demoActive) return;
    const taskId = document.getElementById('task-selector').value || 'easy_delivery';
    await fetch(`${API_BASE}/reset`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({task_id: taskId, seed: 42})
    });
    const stateRes = await fetch(`${API_BASE}/state`);
    if (stateRes.ok) lastState = await stateRes.json();
    
    // Clear history
    document.getElementById('action-log').innerHTML = '';
    visualTruckProgress.clear();
    truckTrails.forEach(t => map.removeLayer(t.polyline)); truckTrails.clear();
    renderedTrucks.forEach(m => map.removeLayer(m)); renderedTrucks.clear();
    
    renderHUD();
    renderStaticMapElements();
    showTaskInfo(taskId);
    addToTerminal(`ENVIRONMENT RESET: ${taskId}`, 'alert');
});

let selectedTask = 'easy_delivery';

function updateTruckSelector() {
    const select = document.getElementById('action-truck');
    const currentVal = select.value;
    select.innerHTML = '<option value="">Select Truck</option>';
    if (lastState && lastState.trucks) {
        lastState.trucks.forEach(t => {
            const loadInfo = t.current_load > 0 ? ` (Load: ${t.current_load})` : '';
            select.innerHTML += `<option value="${t.id}">${t.id} @ ${t.location}${loadInfo}</option>`;
        });
        // Auto-select first truck if nothing selected
        if (!currentVal && select.options.length > 1) {
            select.selectedIndex = 1;
        } else if (currentVal) {
            select.value = currentVal;
        }
    }
}

async function initEnvironment() {
    try {
        const taskId = document.getElementById('task-selector').value || 'easy_delivery';
        const res = await fetch(`${API_BASE}/reset`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({task_id: taskId, seed: 42})
        });
        if (res.ok) lastState = await res.json();
        renderHUD();
        renderStaticMapElements();
        updateTruckSelector();
        showTaskInfo(taskId);
        addToTerminal(`ENVIRONMENT READY: ${taskId}`, 'success');
    } catch(e) {
        addToTerminal('INIT ERROR: ' + e.message, 'alert');
    }
}

function showTaskInfo(taskId) {
    const taskNames = {
        'easy_delivery': 'Basic Delivery',
        'medium_optimization': 'Multi-Order Optimization',
        'hard_crisis': 'Crisis Management'
    };
    const taskDescs = {
        'easy_delivery': 'Deliver 30 items from W1 to W2 within 15 steps',
        'medium_optimization': 'Complete 5 orders across 3 warehouses',
        'hard_crisis': 'Handle 10 orders with route disruptions'
    };
    const taskOrders = {
        'easy_delivery': 1,
        'medium_optimization': 5,
        'hard_crisis': 10
    };
    const taskMaxSteps = {
        'easy_delivery': 15,
        'medium_optimization': 50,
        'hard_crisis': 100
    };
    
    document.getElementById('task-details').innerHTML = `
        <div class="task-name">${taskNames[taskId] || taskId}</div>
        <div class="task-desc">${taskDescs[taskId] || ''}</div>
        <div class="task-orders">Orders: <span>${taskOrders[taskId] || 0}</span></div>
        <div class="task-time">Time Limit: <span>${taskMaxSteps[taskId] || 0}</span></div>
    `;
    document.getElementById('task-info').style.display = 'block';
}

async function runCinematicReboot(stateSetupCb) {
    simulationPaused = true; 
    addToTerminal('SYS:// INITIATING CINEMATIC DRONE', 'alert');
    renderedTrucks.forEach(m => map.removeLayer(m)); renderedTrucks.clear();
    truckTrails.forEach(t => map.removeLayer(t.polyline)); truckTrails.clear();
    visualTruckProgress.clear(); lastCargoCache.clear();
    
    map.flyTo([22.0, 78.0], 5, {animate: false}); 
    await sleep(1500);
    
    stateSetupCb(); // Inject mock state!
    if (lastState && lastState.routes) {
        for (const route of lastState.routes) await getOSRMRoute(route.from_warehouse, route.to_warehouse);
    }
    renderHUD(); renderStaticMapElements();
    
    const bounds = L.latLngBounds(lastState.warehouses.map(w => getHubLatLng(w.id))).pad(0.3); 
    map.flyToBounds(bounds, {duration: 3.5, easeLinearity: 0.1});
    
    return new Promise(resolve => {
        map.once("zoomend", () => {
            addToTerminal('SYS:// FULL SECURE CONNECTED: HARD_CRISIS_NODE', 'success');
            simulationPaused = false; 
            resolve();
        });
    });
}

function spawnFloatingText(msg, latlng, isRed=false) {
    const pnt = map.latLngToContainerPoint(latlng);
    const div = document.createElement('div');
    div.className = isRed ? 'float-fail' : 'float-up';
    div.innerText = msg;
    div.style.left = `${pnt.x}px`;
    div.style.top = `${pnt.y - 40}px`;
    document.getElementById('vis-container').appendChild(div);
    setTimeout(() => div.remove(), 4500);
}

// Custom Absolute DOM Math overlay formula for PRD Scoring Visualization
function spawnScoreEquation(scoreStr, result) {
    const div = document.createElement('div');
    div.className = 'narrative-box crt-flicker';
    div.style.bottom = '150px'; div.style.width = '40%';
    div.innerHTML = `<span style="color:var(--text-muted)">Executing Grading Weights:</span><br/><br/><span style="color:var(--neon-green);font-size:1.6rem">${scoreStr} = <b>${result}</b></span>`;
    document.getElementById('vis-container').appendChild(div);
    setTimeout(() => div.remove(), 7000);
}

// PRD Story Sequence:
async function runDemoSequence() {
    simulationPaused = true;
    document.getElementById('narrative-box').style.display = 'block';
    
    // --- SCENE I: THE PROBLEM (Crisis Management Failure) ---
    addToTerminal('SYS:// INITIATING AGENT EVALUATION PROTOCOL [DEMO]', 'dispatch');
    let msg1 = typeWriter("SCENARIO: Task 3 (Crisis Management) [cite: 94]. Standard AI Agent.");
    
    lastGrade = { score: 1.0, delivery_rate: 1.0 };
    lastState = { 
        time_step: 50, task_id: "demo",
        warehouses: [ {id:"W1"}, {id:"W2"}, {id:"W3"} ],
        routes: [ 
            {from_warehouse: "W1", to_warehouse: "W2", status: "active", distance: 10},
            {from_warehouse: "W1", to_warehouse: "W3", status: "active", distance: 12},
            {from_warehouse: "W3", to_warehouse: "W2", status: "active", distance: 10}
        ],
        trucks: [ {id: "T1", location: "W1", target_location: "W2", steps_to_destination: 10, current_load: 50, capacity: 50} ],
        metrics: {}
    };
    
    if(!demoActive) return;
    for (const route of lastState.routes) await getOSRMRoute(route.from_warehouse, route.to_warehouse);
    
    map.fitBounds(L.latLngBounds(lastState.warehouses.map(w => getHubLatLng(w.id))).pad(0.2), {animate: false});
    renderStaticMapElements(); renderHUD();
    simulationPaused = false; 
    
    // Simulate T1 Movement to T=59
    for (let i = 10; i >= 6; i--) {
        if(!demoActive) return;
        lastState.time_step++;
        lastState.trucks[0].steps_to_destination = i;
        renderHUD(); await sleep(800); 
    }
    await msg1; 
    
    // DISRUPTION SHOT at T=60 [cite: 97]
    if(!demoActive) return;
    lastState.time_step = 60; // Hard PRD Match
    lastState.routes[0].status = "blocked";
    renderStaticMapElements(); 
    triggerGlitchShake();
    addToTerminal('SYS:// T=60 EVALUATION: ROUTE W1 <-> W2 BLOCKED [cite: 97]', 'alert');
    
    // Truck is stuck without resolving constraints!
    lastState.trucks[0].steps_to_destination = 0;
    lastState.trucks[0].target_location = null;
    await sleep(500); // 
    
    // SLA DROPS TO ZERO [cite: 100]
    spawnFloatingText("SLA FAILED: 0.0 [cite: 100]\nREROUTE FAILED", getPathPointWithBearing(osrmRoutesCache.get("W1-W2"), 0.5, false).latlng, true);
    lastGrade.score = 0.0;
    renderHUD();
    
    await sleep(4000);
    
    // --- SCENE II: THE SOLUTION (OpenLogistics Array Tuning) ---
    if(!demoActive) return;
    let msg2 = typeWriter("SOLUTION: OpenLogistics AI Evaluation Environment [cite: 107].");
    
    await sleep(2500);
    await msg2;
    
    if(!demoActive) return;
    await runCinematicReboot(() => {
        lastState.time_step = 60;
        lastState.routes[0].status = "blocked";
        lastState.trucks[0].location = "W1";
        lastState.trucks[0].target_location = "W3";
        lastState.trucks[0].steps_to_destination = 12;
    });
    
    // Successful T1 Movement Loop bypassing via Savandurga W1 -> W3 -> W2
    addToTerminal('REROUTE CALCULATED: W1 -> W3 -> W2', 'success');
    let msg3 = typeWriter("Benchmarking Adaptability, Optimization, and Execution.");
    
    for (let i = 12; i >= 0; i--) {
        if(!demoActive) return;
        lastState.trucks[0].steps_to_destination = i;
        await sleep(500);
    }
    
    if(!demoActive) return;
    lastState.trucks[0].location = "W3";
    lastState.trucks[0].target_location = "W2";
    lastState.trucks[0].steps_to_destination = 10;
    
    for (let i = 10; i >= 0; i--) {
        if(!demoActive) return;
        lastState.trucks[0].steps_to_destination = i;
        await sleep(500);
    }
    
    // Inject Dynamic Task 3 PRD Grading Math [cite: 99]
    spawnScoreEquation("Score = (0.4 * 1.0) + (0.3 * 1.0) + (0.3 * 0.8)", "0.94");
    lastGrade.score = 0.94;
    renderHUD();
    
    await msg3;
    await sleep(7000);
    
    // END OF SEQUENCES
    if(!demoActive) return;
    document.getElementById('btn-skip-demo').click();
}

// ----------------------------------------------------
// UI CONTROLS & EVENT LOOP KEEPALIVE
// ----------------------------------------------------

// Boot Main Sequence
setInterval(fetchAPI, 1000);
requestAnimationFrame(physicsLoop);

// Trigger Scripted Story Overlap Sandbox
runDemoSequence();
