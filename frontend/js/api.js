// Point this at wherever uvicorn is running.
cconst API_BASE = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? "http://localhost:8000"
  : "https://farm2market-jxzz.onrender.com";

const Auth = {
  getToken(){ return localStorage.getItem("f2m_token"); },
  setSession(token, user){
    localStorage.setItem("f2m_token", token);
    localStorage.setItem("f2m_user", JSON.stringify(user));
  },
  getUser(){
    const raw = localStorage.getItem("f2m_user");
    return raw ? JSON.parse(raw) : null;
  },
  logout(){
    localStorage.removeItem("f2m_token");
    localStorage.removeItem("f2m_user");
    window.location.href = "index.html";
  },
  requireLogin(){
    if(!this.getToken()){ window.location.href = "index.html"; }
  }
};

async function apiRequest(path, { method = "GET", body = null, form = false, auth = true } = {}){
  const headers = {};
  if(auth && Auth.getToken()){
    headers["Authorization"] = `Bearer ${Auth.getToken()}`;
  }

  let payload = undefined;
  if(body !== null){
    if(form){
      payload = new URLSearchParams(body);
      headers["Content-Type"] = "application/x-www-form-urlencoded";
    } else {
      payload = JSON.stringify(body);
      headers["Content-Type"] = "application/json";
    }
  }

  const res = await fetch(`${API_BASE}${path}`, { method, headers, body: payload });
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json() : null;

  if(!res.ok){
    const message = (data && (data.detail || JSON.stringify(data))) || `Request failed (${res.status})`;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return data;
}
