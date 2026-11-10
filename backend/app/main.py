from fastapi import FastAPI

# creation de l'application FormIA
app = FastAPI(
    title="FoamIA",
    description="il sagit la d'un teste du backend",
    version="0.1.0"
)

@app.get("/")
def accueil():
    return{
        "Message": "Bienvenue sur FormIA",
        "status": "online"
    }

@app.get("/health")
def health_check():
    return{
        "status": "healthy"
    }
    