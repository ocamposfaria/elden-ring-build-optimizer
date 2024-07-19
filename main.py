from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import pandas as pd
from config import GetAllData

app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_main(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/submit", response_class=HTMLResponse)
async def submit(
    request: Request,
    forca: int = Form(...),
    destreza: int = Form(...),
    inteligencia: int = Form(...),
    fe: int = Form(...),
    arcano: int = Form(...),
    nivelarma: int = Form(...)
):
    
    stats = {'strength': forca, 
         'dexterity': destreza,
         'intelligence': inteligencia,
         'faith': fe,
         'arcane': arcano}

    weapon_upgrade = nivelarma

    
    df = pd.DataFrame(GetAllData(stats, weapon_upgrade).items(), columns=['Arma', 'Dano']).dropna()
    df['Dano'] = df['Dano'].astype(int)
    df = df.sort_values(by=['Dano'], ascending=False)
    table_html = df.to_html(index=False)
    table_html = table_html.replace('<table border="1" class="dataframe">', '<table class="ui selectable table">')

    return templates.TemplateResponse("index.html", {"request": request, "table": table_html})
