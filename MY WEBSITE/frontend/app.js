const root = document.getElementById("root");

/* -----------------------
   ROUTER
------------------------ */
function router() {
  const route = window.location.hash.replace("#", "");

  if (route === "" || route === "home") return Home();
  if (route === "contact") return Contact();
  if (route === "login") return Login();

  return NotFound();
}

/* -----------------------
   RENDER
------------------------ */
function render() {
  root.innerHTML = `
    ${Navbar()}
    ${router()}
  `;
}

/* -----------------------
   COMPONENTS
------------------------ */
function Navbar() {
  return `
    <div class="nav">
      <div><strong>Astra Tech</strong></div>
      <div>
        <a href="#home">Home</a>
        <a href="#contact">Contact</a>
        <a href="#login">Login</a>
      </div>
    </div>
  `;
}

function Home() {
  return `
    <div class="section">
      <h1>Astra Tech</h1>
      <p>Full-stack digital systems built from scratch</p>
    </div>
  `;
}

/* -----------------------
   CONTACT → SENDS TO BACKEND
------------------------ */
function Contact() {
  return `
    <div class="section">
      <h2>Contact Us</h2>

      <input id="name" placeholder="Name">
      <input id="email" placeholder="Email">
      <textarea id="message" placeholder="Message"></textarea>

      <button onclick="sendMessage()">Send</button>
    </div>
  `;
}

/* -----------------------
   LOGIN
------------------------ */
async function login() {
  const data = {
    email: document.getElementById("loginEmail").value,
    password: document.getElementById("loginPassword").value
  };

  const res = await fetch("http://localhost:8000/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });

  const result = await res.json();

  if (result.token) {
    localStorage.setItem("token", result.token);
    alert("Logged in");
  } else {
    alert(result.message);
  }
}

function NotFound() {
  return `<div class="section"><h1>404</h1></div>`;
}

/* -----------------------
   BACKEND CONNECTION
------------------------ */
async function sendMessage() {
  const data = {
    name: document.getElementById("name").value,
    email: document.getElementById("email").value,
    message: document.getElementById("message").value
  };

  await fetch("http://localhost:8000/contact", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });

  alert("Message sent");
}

async function login() {
  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;

  const res = await fetch("https://chaotech-engineer.onrender.com", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  });

  const data = await res.json();

  alert(JSON.stringify(data));
}

/* -----------------------
   EVENTS
------------------------ */
window.addEventListener("hashchange", render);
window.addEventListener("load", render);