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

let aadhaarDemoVerified = false;


function toggleRoleFields(){

  const isFarmer = roleSelect.value === "farmer";
  const isBuyer = roleSelect.value === "buyer";

  document.getElementById("farmer-fields").style.display =
    isFarmer ? "block" : "none";

  document.getElementById("buyer-fields").style.display =
    isBuyer ? "block" : "none";

  const registerButton = document.querySelector(
    '#register-form button[type="submit"]'
  );

  if(isFarmer){
    registerButton.disabled = !aadhaarDemoVerified;
  }else{
    registerButton.disabled = false;
  }
}


roleSelect.addEventListener("change", () => {

  aadhaarDemoVerified = false;

  const otpSection = document.getElementById("otp-section");
  const otpMessage = document.getElementById("otp-message");

  if(otpSection){
    otpSection.style.display = "none";
  }

  if(otpMessage){
    otpMessage.innerHTML = "";
  }

  const aadhaarInput = document.getElementById("reg-aadhaar");
  const otpInput = document.getElementById("reg-otp");

  if(aadhaarInput){
    aadhaarInput.value = "";
  }

  if(otpInput){
    otpInput.value = "";
  }

  toggleRoleFields();
});


toggleRoleFields();


/* ---------------- LOGIN ---------------- */

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


/* ---------------- DEMO AADHAAR OTP ---------------- */

document.getElementById("send-otp-btn").addEventListener("click", () => {

  const aadhaar = document.getElementById("reg-aadhaar").value.trim();
  const otpSection = document.getElementById("otp-section");
  const otpMessage = document.getElementById("otp-message");

  aadhaarDemoVerified = false;

  if(!/^\d{12}$/.test(aadhaar)){

    otpSection.style.display = "none";

    otpMessage.innerHTML =
      `<div class="error-box">Enter a 12-digit demo Aadhaar number.</div>`;

    return;
  }

  otpSection.style.display = "block";

  otpMessage.innerHTML =
    `<div class="small-note">Demo OTP is ready. Enter 123456 to verify.</div>`;

});


/* ---------------- VERIFY DEMO OTP ---------------- */

document.getElementById("verify-otp-btn").addEventListener("click", () => {

  const otp = document.getElementById("reg-otp").value.trim();
  const otpMessage = document.getElementById("otp-message");

  if(otp !== "123456"){

    aadhaarDemoVerified = false;

    otpMessage.innerHTML =
      `<div class="error-box">Incorrect OTP. Use the Demo OTP: 123456</div>`;

    toggleRoleFields();

    return;
  }

  aadhaarDemoVerified = true;

  otpMessage.innerHTML =
    `<div class="success-box">✓ Aadhaar verified successfully (Demo).</div>`;

  toggleRoleFields();

});


/* ---------------- REGISTER ---------------- */

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

    if(!aadhaarDemoVerified){

      errBox.innerHTML =
        `<div class="error-box">Please complete Demo Aadhaar verification first.</div>`;

      return;
    }

    payload.aadhaar_demo_verified = true;

    payload.farm_or_fpo_name =
      document.getElementById("reg-farm-name").value;

    payload.pickup_location =
      document.getElementById("reg-pickup-location").value;

  }


  else if(role === "buyer"){

    payload.buyer_type =
      document.getElementById("reg-buyer-type").value;

    payload.business_name =
      document.getElementById("reg-business-name").value || null;

    payload.default_location =
      document.getElementById("reg-default-location").value || null;

  }


  try{

    const data = await apiRequest("/auth/register", {
      method: "POST",
      auth: false,
      body: payload
    });

    Auth.setSession(data.access_token, data.user);

    window.location.href = "dashboard.html";

  } catch(err){

    errBox.innerHTML =
      `<div class="error-box">${err.message}</div>`;

  }

});