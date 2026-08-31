// ============================================================
// Farm2Market API Configuration
// ============================================================

// Local development:
//   http://localhost:8000
//
// Deployed production backend:
//   https://farm2market-jxzz.onrender.com

const API_BASE =
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1"
    ? "http://localhost:8000"
    : "https://farm2market-jxzz.onrender.com";


// ============================================================
// Authentication / Session Management
// ============================================================

const Auth = {

  // Get the currently stored JWT token
  getToken() {
    return localStorage.getItem("f2m_token");
  },


  // Save login session
  setSession(token, user) {
    localStorage.setItem("f2m_token", token);
    localStorage.setItem("f2m_user", JSON.stringify(user));
  },


  // Get currently logged-in user
  getUser() {
    const raw = localStorage.getItem("f2m_user");

    if (!raw) {
      return null;
    }

    try {
      return JSON.parse(raw);
    } catch (error) {
      console.error("Could not read stored user:", error);
      return null;
    }
  },


  // Log out the current user
  logout() {
    localStorage.removeItem("f2m_token");
    localStorage.removeItem("f2m_user");

    window.location.href = "index.html";
  },


  // Require login before accessing a protected page
  requireLogin() {
    if (!this.getToken()) {
      window.location.href = "index.html";
    }
  }
};


// ============================================================
// API Request Helper
// ============================================================

async function apiRequest(
  path,
  {
    method = "GET",
    body = null,
    form = false,
    auth = true
  } = {}
) {

  const headers = {};


  // ----------------------------------------------------------
  // Add authentication token when required
  // ----------------------------------------------------------

  if (auth) {
    const token = Auth.getToken();

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }


  // ----------------------------------------------------------
  // Prepare request body
  // ----------------------------------------------------------

  let payload = undefined;

  if (body !== null) {

    if (form) {

      // Used by /auth/login
      payload = new URLSearchParams(body);

      headers["Content-Type"] =
        "application/x-www-form-urlencoded";

    } else {

      // Used by JSON API endpoints
      payload = JSON.stringify(body);

      headers["Content-Type"] =
        "application/json";
    }
  }


  // ----------------------------------------------------------
  // Send request
  // ----------------------------------------------------------

  let res;

  try {

    res = await fetch(
      `${API_BASE}${path}`,
      {
        method,
        headers,
        body: payload
      }
    );

  } catch (error) {

    console.error("API connection error:", error);

    throw new Error(
      "Could not connect to the Farm2Market backend."
    );
  }


  // ----------------------------------------------------------
  // Read response
  // ----------------------------------------------------------

  const contentType =
    res.headers.get("content-type") || "";

  const isJson =
    contentType.includes("application/json");

  const data =
    isJson
      ? await res.json()
      : null;


  // ----------------------------------------------------------
  // Handle HTTP errors
  // ----------------------------------------------------------

  if (!res.ok) {

    const message =
      data?.detail ||
      data?.message ||
      `Request failed (${res.status})`;

    throw new Error(
      typeof message === "string"
        ? message
        : JSON.stringify(message)
    );
  }


  // ----------------------------------------------------------
  // Return successful response
  // ----------------------------------------------------------

  return data;
}