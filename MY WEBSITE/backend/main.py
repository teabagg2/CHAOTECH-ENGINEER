from fastapi import FastAPI
from pydantic import BaseModel
from database import get_contacts, save_contact, get_user
from auth import create_token
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

class Contact(BaseModel):
    name: str
    email: str
    message: str

class Login(BaseModel):
    email: str
    password: str

@app.post("/contact")
def contact(data: Contact):
    save_contact(data.name, data.email, data.message)
    return {"message": "Saved"}

@app.post("/login")
def login(data: Login):
    user = get_user(data.email, data.password)

    if user:
        token = create_token(data.email)
        return {"token": token}

    return {"message": "Invalid credentials"}

@app.get("/admin/contacts")
def admin_contacts():
    return get_contacts()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

