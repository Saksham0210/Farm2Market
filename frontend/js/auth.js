document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    const isLogin = tab.dataset.tab === "login";
    document.getElementById("login-form").style.display = isLogin ? "block" : "none";
    document.getElementById("register-form").style.display = isLogin ? "none" : "block";
  });
});

const roleSelect = document.getElementById("reg-role");
function toggleRoleFields(){
  document.getElementById("farmer-fields").style.display = roleSelect.value === "farmer" ? "block" : "none";
  document.getElementById("buyer-fields").style.display = roleSelect.value === "buyer" ? "block" : "none";
}
roleSelect.addEventListener("change", toggleRoleFields);
toggleRoleFields();

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errBox = document.getElementById("login-error");
  errBox.innerHTML = "";
  try{
    const data = await apiRequest("/auth/login", {
      method: "POST",
      auth: false,
      form: true,
      body: {
        username: document.getElementById("login-email").value,
        password: document.getElementById("login-password").value,
      },
    });
    Auth.setSession(data.access_token, data.user);
    window.location.href = "dashboard.html";
  } catch(err){
    errBox.innerHTML = `<div class="error-box">${err.message}</div>`;
  }
});

document.getElementById("register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errBox = document.getElementById("register-error");
  errBox.innerHTML = "";

  const role = roleSelect.value;
  const payload = {
    name: document.getElementById("reg-name").value,
    email: document.getElementById("reg-email").value,
    phone: document.getElementById("reg-phone").value || null,
    password: document.getElementById("reg-password").value,
    role,
  };

  if(role === "farmer"){
    payload.farm_or_fpo_name = document.getElementById("reg-farm-name").value;
    payload.pickup_location = document.getElementById("reg-pickup-location").value;
  } else if(role === "buyer"){
    payload.buyer_type = document.getElementById("reg-buyer-type").value;
    payload.business_name = document.getElementById("reg-business-name").value || null;
    payload.default_location = document.getElementById("reg-default-location").value || null;
  }

  try{
    const data = await apiRequest("/auth/register", { method: "POST", auth: false, body: payload });
    Auth.setSession(data.access_token, data.user);
    window.location.href = "dashboard.html";
  } catch(err){
    errBox.innerHTML = `<div class="error-box">${err.message}</div>`;
  }
});
