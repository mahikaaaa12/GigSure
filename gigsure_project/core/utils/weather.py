import requests

API_KEY = "3ed7b1e3120759cf991337fb2f2ee2f0"

def get_weather(city):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={API_KEY}&units=metric"

    response = requests.get(url)
    data = response.json()

    forecasts = []

    for item in data["list"][:5]:  # next few time slots
        forecasts.append({
            "time": item["dt_txt"],
            "temp": item["main"]["temp"],
            "weather": item["weather"][0]["main"],
            "rain": item.get("rain", {}).get("3h", 0)
        })

    return forecasts