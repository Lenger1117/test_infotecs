import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import asyncio
from typing import List, Dict
import uuid
from typing import Optional

app = FastAPI()

users = {}
user_weather_data = {}

class City(BaseModel):
    name: str
    latitude: float
    longitude: float

class WeatherResponse(BaseModel):
    temperature: float
    windspeed: float
    pressure: Optional[float]

class WeatherRequest(BaseModel):
    city: str
    time: str
    parameters: List[str]

class UserRegistration(BaseModel):
    username: str

async def fetch_weather(latitude: float, longitude: float):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current_weather=true"
        )
        response.raise_for_status()
        return response.json()

async def update_weather(user_id: str, city_name: str, latitude: float, longitude: float):
    while True:
        weather = await fetch_weather(latitude, longitude)
        current_weather = weather['current_weather']
        
        user_weather_data[user_id][city_name] = WeatherResponse(
            temperature=current_weather.get('temperature'),
            windspeed=current_weather.get('windspeed'),
            pressure=current_weather.get('pressure')
        )
        
        await asyncio.sleep(900)

@app.post("/register/", response_model=str, summary='Регистрация пользователя')
async def register_user(user: UserRegistration):
    user_id = str(uuid.uuid4())
    users[user_id] = user.username
    user_weather_data[user_id] = {}
    return user_id

@app.post("/add_city/{user_id}/", response_model=str, summary='Добавить город в список')
async def add_city(user_id: str, city: City):
    if user_id not in user_weather_data:
        raise HTTPException(status_code=404, detail="Пользователь не найден.")
    
    if city.name in user_weather_data[user_id]:
        raise HTTPException(status_code=400, detail="Город уже добавлен.")
    
    user_weather_data[user_id][city.name] = {}
    asyncio.create_task(update_weather(user_id, city.name, city.latitude, city.longitude))
    return f"Город {city.name} добавлен в список."

@app.get("/current_weather/{user_id}/{city_name}", response_model=WeatherResponse, summary='Получить прогноз погоды')
async def get_current_weather(user_id: str, city_name: str):
    if user_id not in user_weather_data:
        raise HTTPException(status_code=404, detail="Пользователь не найден.")
    if city_name not in user_weather_data[user_id]:
        raise HTTPException(status_code=404, detail="Город не найден.")
    return user_weather_data[user_id][city_name]

@app.get("/cities/{user_id}/", response_model=List[str], summary='Вывести список городов')
async def list_cities(user_id: str):
    if user_id not in user_weather_data:
        raise HTTPException(status_code=404, detail="Пользователь не найден.")
    
    return list(user_weather_data[user_id].keys())

@app.post("/weather_at_time/{user_id}/", response_model=Dict[str, float], summary='Получить прогноз погоды на текущую дату с выбранными параметрами, но на другое время')
async def get_weather_at_time(user_id: str, request: WeatherRequest):
    if user_id not in user_weather_data:
        raise HTTPException(status_code=404, detail="Пользователь не найден.")
    
    if request.city not in user_weather_data[user_id]:
        raise HTTPException(status_code=404, detail="Город не найден.")
    
    city_weather = user_weather_data[user_id][request.city]
    
    response = {}
    for param in request.parameters:
        if hasattr(city_weather, param):
            response[param] = getattr(city_weather, param)
        else:
            raise HTTPException(status_code=400, detail=f"Параметр {param} не доступен.")
    
    return response

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)