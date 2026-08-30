Auth.requireLogin();
const user = Auth.getUser();

document.getElementById("role-badge").textContent = user.role;
document.getElementById("user-name").textContent = user.name;

const STATIONS = ["Placed", "Matched", "Batched / Direct", "Out for delivery", "Delivered", "Paid"];
const STATUS_INDEX = { placed: 0, matched: 1, batched: 2, out_for_delivery: 3, delivered: 4, paid: 5, cancelled: -1 };

function renderRail(status){
  const idx = STATUS_INDEX[status] ?? 0;
  const pct = idx <= 0 ? 0 : (idx / (STATIONS.length - 1)) * 100;
  let stations = STATIONS.map((label, i) => {
    const cls = i < idx ? "done" : (i === idx ? "current" : "");
    return `<div class="station ${cls}"><div class="dot">${i < idx ? "✓" : i + 1}</div><div class="label">${label}</div></div>`;
  }).join("");
  return `<div class="rail" style="--stations:${STATIONS.length}">
      <div class="rail-fill" style="width:${pct}%"></div>
      ${stations}
    </div>`;
}

// ---------------- FARMER ----------------
async function initFarmer(){
  document.getElementById("farmer-view").style.display = "block";

  document.getElementById("produce-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = document.getElementById("produce-msg");
    msg.innerHTML = "";
    try{
      await apiRequest("/produce", {
        method: "POST",
        body: {
          product_name: document.getElementById("p-name").value,
          quantity_available: parseFloat(document.getElementById("p-qty").value),
          unit: document.getElementById("p-unit").value,
          quality_grade: document.getElementById("p-grade").value,
          price_per_unit: parseFloat(document.getElementById("p-price").value),
          available_date: document.getElementById("p-date").value ? new Date(document.getElementById("p-date").value).toISOString() : null,
          pickup_location: document.getElementById("p-location").value,
        },
      });
      msg.innerHTML = `<div class="success-box">Listed on the platform.</div>`;
      document.getElementById("produce-form").reset();
      loadMyProduce();
    } catch(err){
      msg.innerHTML = `<div class="error-box">${err.message}</div>`;
    }
  });

  loadMyProduce();
}

async function loadMyProduce(){
  const list = document.getElementById("my-produce-list");
  list.innerHTML = `<p class="small-note">Loading...</p>`;
  try{
    const items = await apiRequest("/produce/mine");
    if(!items.length){ list.innerHTML = `<p class="small-note">You haven't listed any produce yet.</p>`; return; }
    list.innerHTML = items.map(p => `
      <div class="produce-card">
        <div class="name">${p.product_name}</div>
        <div class="meta">${p.quantity_available} ${p.unit} available · Grade ${p.quality_grade}</div>
        <div class="meta">Pickup: ${p.pickup_location}</div>
        <div class="price-tag">₹${p.price_per_unit} / ${p.unit}</div>
        <span class="badge">${p.status}</span>
      </div>
    `).join("");
  } catch(err){
    list.innerHTML = `<div class="error-box">${err.message}</div>`;
  }
}

// ---------------- BUYER ----------------
const CART_KEY = `f2m_cart_${user.id}`;
function getCart(){ return JSON.parse(localStorage.getItem(CART_KEY) || "[]"); }
function setCart(cart){ localStorage.setItem(CART_KEY, JSON.stringify(cart)); updateCartCount(); }
function updateCartCount(){
  const count = getCart().reduce((n, i) => n + 1, 0);
  const el = document.getElementById("cart-count");
  if(el) el.textContent = count ? `(${count})` : "";
}

async function initBuyer(){
  document.getElementById("buyer-view").style.display = "block";
  document.getElementById("buyer-type-label").textContent =
    user.buyer_type === "bulk" ? "Bulk buyer" : "Individual buyer";

  document.querySelectorAll("[data-btab]").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("[data-btab]").forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      ["market", "cart", "orders"].forEach(name => {
        document.getElementById(`btab-${name}`).style.display = (name === tab.dataset.btab) ? "block" : "none";
      });
      if(tab.dataset.btab === "cart") renderCart();
      if(tab.dataset.btab === "orders") loadOrders();
    });
  });

  document.getElementById("search-box").addEventListener("input", (e) => loadMarketplace(e.target.value));
  document.getElementById("place-order-btn").addEventListener("click", placeOrder);

  updateCartCount();
  loadMarketplace();
}

async function loadMarketplace(search = ""){
  const list = document.getElementById("marketplace-list");
  list.innerHTML = `<p class="small-note">Loading marketplace...</p>`;
  try{
    const qs = search ? `?product_name=${encodeURIComponent(search)}` : "";
    const items = await apiRequest(`/produce${qs}`);
    if(!items.length){ list.innerHTML = `<p class="small-note">No produce currently available.</p>`; return; }
    list.innerHTML = items.map(p => `
      <div class="produce-card">
        <div class="name">${p.product_name}</div>
        <div class="meta">${p.quantity_available} ${p.unit} available · Grade ${p.quality_grade}</div>
        <div class="meta">Pickup: ${p.pickup_location}</div>
        <div class="price-tag">₹${p.price_per_unit} / ${p.unit}</div>
        <div class="qty-control">
          <input type="number" min="0.5" step="0.5" value="1" id="qty-${p.id}">
          <button class="btn small" onclick="addToCart('${p.id}', '${p.product_name.replace(/'/g, "\\'")}', ${p.price_per_unit}, '${p.unit}')">Add to cart</button>
        </div>
      </div>
    `).join("");
  } catch(err){
    list.innerHTML = `<div class="error-box">${err.message}</div>`;
  }
}

function addToCart(produce_id, name, unit_price, unit){
  const qtyInput = document.getElementById(`qty-${produce_id}`);
  const quantity = parseFloat(qtyInput.value) || 1;
  const cart = getCart();
  const existing = cart.find(i => i.produce_id === produce_id);
  if(existing){ existing.quantity += quantity; }
  else{ cart.push({ produce_id, name, unit_price, unit, quantity }); }
  setCart(cart);
}

function renderCart(){
  const cart = getCart();
  const body = document.getElementById("cart-body");
  if(!cart.length){
    body.innerHTML = `<tr><td colspan="5" class="small-note">Your cart is empty.</td></tr>`;
  } else {
    body.innerHTML = cart.map((i, idx) => `
      <tr>
        <td>${i.name}</td>
        <td>${i.quantity} ${i.unit}</td>
        <td>₹${i.unit_price}</td>
        <td>₹${(i.quantity * i.unit_price).toFixed(2)}</td>
        <td><button class="btn-link" onclick="removeFromCart(${idx})">Remove</button></td>
      </tr>
    `).join("");
  }
  const total = cart.reduce((sum, i) => sum + i.quantity * i.unit_price, 0);
  document.getElementById("cart-total").textContent = `Total: ₹${total.toFixed(2)}`;
}

function removeFromCart(idx){
  const cart = getCart();
  cart.splice(idx, 1);
  setCart(cart);
  renderCart();
}

async function placeOrder(){
  const msg = document.getElementById("order-msg");
  msg.innerHTML = "";
  const cart = getCart();
  const location = document.getElementById("delivery-location").value;
  const date = document.getElementById("delivery-date").value;
  const slot = document.getElementById("delivery-slot-time").value;

  if(!cart.length){ msg.innerHTML = `<div class="error-box">Your cart is empty.</div>`; return; }
  if(!location || !date){ msg.innerHTML = `<div class="error-box">Enter a delivery location and date.</div>`; return; }

  try{
    await apiRequest("/orders", {
      method: "POST",
      body: {
        order_type: user.buyer_type === "bulk" ? "bulk" : "individual",
        delivery_location: location,
        delivery_slot: `${date}|${slot}`,
        items: cart.map(i => ({ produce_id: i.produce_id, quantity: i.quantity })),
      },
    });
    setCart([]);
    renderCart();
    msg.innerHTML = `<div class="success-box">Order placed! Check "My orders" for live status.</div>`;
  } catch(err){
    msg.innerHTML = `<div class="error-box">${err.message}</div>`;
  }
}

async function loadOrders(){
  const list = document.getElementById("orders-list");
  list.innerHTML = `<p class="small-note">Loading orders...</p>`;
  try{
    const orders = await apiRequest("/orders/mine");
    if(!orders.length){ list.innerHTML = `<p class="small-note">No orders yet.</p>`; return; }

    list.innerHTML = "";
    for(const o of orders){
      const row = document.createElement("div");
      row.className = "order-row";
      row.innerHTML = `
        <div class="order-row-head">
          <div><strong>Order #${o.id.slice(0,8)}</strong> · ${o.order_type}</div>
          <span class="badge">${o.status}</span>
        </div>
        <div class="small-note">Deliver to ${o.delivery_location} · Slot: ${o.delivery_slot}</div>
        ${renderRail(o.status)}
        <table>
          <thead><tr><th>Item</th><th>Qty</th><th>Unit price</th><th>Subtotal</th></tr></thead>
          <tbody>
            ${o.items.map(i => `<tr><td>${i.produce_id.slice(0,8)}</td><td>${i.quantity}</td><td>₹${i.unit_price}</td><td>₹${i.subtotal.toFixed(2)}</td></tr>`).join("")}
          </tbody>
        </table>
        <div class="mono" style="margin-top:8px;">Total: ₹${o.total_amount.toFixed(2)}</div>
        <div id="extra-${o.id}" style="margin-top:14px;"></div>
      `;
      list.appendChild(row);
      loadOrderExtras(o);
    }
  } catch(err){
    list.innerHTML = `<div class="error-box">${err.message}</div>`;
  }
}

async function loadOrderExtras(order){
  const box = document.getElementById(`extra-${order.id}`);
  let html = "";

  if(order.status === "batched"){
    html += `<button class="btn secondary small" onclick="requestDirect('${order.id}')">Don't want to wait? Get direct delivery (extra cost)</button>`;
  }

  try{
    const delivery = await apiRequest(`/orders/${order.id}/delivery`);
    html += `<div class="small-note" style="margin-top:10px;">Route: ${delivery.route_sequence || "—"}</div>`;
    if(delivery.distance_km) html += `<div class="small-note">Distance: ${delivery.distance_km} km · Delivery cost: ₹${delivery.delivery_cost ?? "—"}</div>`;

    if(delivery.status !== "delivered" && (order.status === "out_for_delivery")){
      html += `
        <div class="split-view" style="margin-top:10px;">
          <input type="text" id="otp-${order.id}" placeholder="Enter delivery OTP" style="max-width:180px;">
          <button class="btn small" onclick="confirmDelivery('${order.id}')">Confirm delivery</button>
        </div>
        <div class="small-note">Your delivery OTP (shown here for this demo, normally sent via SMS): <span class="mono">${delivery.otp || "—"}</span></div>
      `;
    }
  } catch(err){
    // no delivery record yet - fine, still waiting on batching/matching
  }

  if(order.status === "paid"){
    try{
      const payment = await apiRequest(`/orders/${order.id}/payment`);
      html += `
        <div class="small-note" style="margin-top:10px;">
          Payment settled — Farmer receives ₹${payment.farmer_share.toFixed(2)},
          logistics partner receives ₹${payment.logistics_share.toFixed(2)},
          platform fee ₹${payment.platform_fee.toFixed(2)}.
        </div>`;
    } catch(err){ /* ignore */ }
  }

  box.innerHTML = html;
}

async function requestDirect(orderId){
  try{
    await apiRequest(`/orders/${orderId}/request-direct-delivery`, { method: "POST" });
    loadOrders();
  } catch(err){
    alert(err.message);
  }
}

async function confirmDelivery(orderId){
  const otp = document.getElementById(`otp-${orderId}`).value;
  try{
    await apiRequest(`/orders/${orderId}/confirm-delivery`, { method: "POST", body: { otp } });
    loadOrders();
  } catch(err){
    alert(err.message);
  }
}

// ---------------- LOGISTICS ----------------
async function initLogistics(){
  document.getElementById("logistics-view").style.display = "block";

  document.getElementById("partner-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = document.getElementById("partner-msg");
    msg.innerHTML = "";
    try{
      await apiRequest("/logistics-partners", {
        method: "POST",
        body: {
          name: document.getElementById("lp-name").value,
          vehicle_type: document.getElementById("lp-vehicle").value,
          capacity_kg: parseFloat(document.getElementById("lp-capacity").value),
          cost_per_km: parseFloat(document.getElementById("lp-cost-km").value),
          base_cost: parseFloat(document.getElementById("lp-base-cost").value || 0),
          supports_cold_chain: document.getElementById("lp-cold-chain").checked,
          current_location: document.getElementById("lp-location").value || null,
        },
      });
      msg.innerHTML = `<div class="success-box">Partner added.</div>`;
      document.getElementById("partner-form").reset();
      loadPartners();
    } catch(err){
      msg.innerHTML = `<div class="error-box">${err.message}</div>`;
    }
  });

  loadPartners();
  loadLogisticsOrders();
}

async function loadPartners(){
  const body = document.getElementById("partners-body");
  try{
    const partners = await apiRequest("/logistics-partners");
    body.innerHTML = partners.map(p => `
      <tr><td>${p.name}</td><td>${p.vehicle_type}</td><td>${p.capacity_kg} kg</td><td>₹${p.cost_per_km}</td></tr>
    `).join("") || `<tr><td colspan="4" class="small-note">No partners yet.</td></tr>`;
  } catch(err){
    body.innerHTML = `<tr><td colspan="4" class="error-box">${err.message}</td></tr>`;
  }
}
// ---------------- LOGISTICS ORDERS ----------------
async function loadLogisticsOrders(){
  const list = document.getElementById("logistics-orders");

  list.innerHTML = `<p class="small-note">Loading deliveries...</p>`;

  try{
    const orders = await apiRequest("/orders/logistics");

    if(!orders.length){
      list.innerHTML = `
        <p class="small-note">
          No deliveries assigned yet.
        </p>
      `;
      return;
    }

    list.innerHTML = orders.map(o => `
      <div class="order-row" style="margin-bottom:16px;">

        <div class="order-row-head">
          <div>
            <strong>Order #${o.id.slice(0,8)}</strong>
            · ${o.order_type}
          </div>

          <span class="badge">
            ${o.status}
          </span>
        </div>

        <div class="small-note">
          Deliver to ${o.delivery_location}
          · Slot: ${o.delivery_slot}
        </div>

        <div style="margin-top:10px;">
  <strong>
    Total: ₹${Number(o.total_amount).toFixed(2)}
  </strong>
</div>

<div class="small-note" style="margin-top:10px;">
  Delivery status: ${o.status}
</div>
<div id="logistics-extra-${o.id}" style="margin-top:10px;">
${o.status === "out_for_delivery" ? `
  <button class="btn small" style="margin-top:12px;"
    onclick="confirmLogisticsDelivery('${o.id}')">
    Confirm Delivery
  </button>
` : ""}

      </div>
    `).join("");
    for (const o of orders) {
  if (o.status === "out_for_delivery") {
    try {
      const delivery = await apiRequest(`/orders/${o.id}/delivery`);

      const extra = document.getElementById(`logistics-extra-${o.id}`);
if (extra) {
  extra.innerHTML = `
    <div class="small-note">
      Enter the OTP provided by the customer:
    </div>

    <div class="split-view" style="margin-top:10px;">
      <input
        type="text"
        id="logistics-otp-${o.id}"
        placeholder="Enter OTP"
        style="max-width:180px;"
      >

      <button
        class="btn small"
        onclick="confirmLogisticsDelivery('${o.id}')"
      >
        Confirm Delivery
      </button>
    </div>
  `;
}
    } catch (err) {
      console.error("Could not load delivery OTP:", err);
    }
  }
}

  } catch(err){

    list.innerHTML = `
      <div class="error-box">
        ${err.message}
      </div>
    `;

  }
}
// ---------------- ROUTER ----------------
if(user.role === "farmer") initFarmer();
else if(user.role === "buyer") initBuyer();
else if(user.role === "logistics" || user.role === "admin") initLogistics();
async function confirmLogisticsDelivery(orderId){
  const otp = prompt("Enter delivery OTP:");

  if(!otp){
    return;
  }

  try{
    await apiRequest(`/orders/${orderId}/confirm-delivery`, {
      method: "POST",
      body: {
        otp: otp
      }
    });

    alert("Delivery confirmed successfully!");
    loadLogisticsOrders();

  } catch(err){
    alert(err.message);
  }
}
