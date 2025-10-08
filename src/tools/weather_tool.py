from typing import Optional, Type, ClassVar, Dict
import aiohttp
import json

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain.tools import BaseTool
from pydantic.v1 import BaseModel

from src.api.websocket_manager import WebSocketManager
from src.agent.session_manager import ChatSessionManager
from src.helpers.enums import ActionType
from src.message_templates.websocket_message_template import WebsocketMessageTemplate


class ShowWeatherToolInput(BaseModel):
    pass


class ShowWeatherTool(BaseTool):
    name: str = "weather_info"
    description: str = "天気についての話しの時に役に立つツール。現在地を取得して天気予報を表示します。"
    args_schema: Type[BaseModel] = ShowWeatherToolInput
    ws_manager: Optional[WebSocketManager] = None
    message_manager: Optional[WebsocketMessageTemplate] = None
    session_manager: Optional[ChatSessionManager] = None
    return_direct: bool = False
    
    # Major Japanese cities with tenki.jp codes
    JAPAN_CITIES: ClassVar[Dict[str, Dict[str, str]]] = {
        # Hokkaido
        'Sapporo': {'code': '1/1/1400', 'prefecture': '北海道'},
        '札幌市': {'code': '1/1/1400', 'prefecture': '北海道'},
        'Hakodate': {'code': '1/2/1300', 'prefecture': '北海道'},
        '函館市': {'code': '1/2/1300', 'prefecture': '北海道'},
        'Asahikawa': {'code': '1/3/1200', 'prefecture': '北海道'},
        '旭川市': {'code': '1/3/1200', 'prefecture': '北海道'},
        # Tohoku
        'Sendai': {'code': '2/4/3410', 'prefecture': '宮城県'},
        '仙台市': {'code': '2/4/3410', 'prefecture': '宮城県'},
        'Aomori': {'code': '2/5/3110', 'prefecture': '青森県'},
        '青森市': {'code': '2/5/3110', 'prefecture': '青森県'},
        # Kanto
        'Yokohama': {'code': '3/16/4610', 'prefecture': '神奈川県'},
        '横浜市': {'code': '3/16/4610', 'prefecture': '神奈川県'},
        'Chiba': {'code': '3/17/4510', 'prefecture': '千葉県'},
        '千葉市': {'code': '3/17/4510', 'prefecture': '千葉県'},
        'Saitama': {'code': '3/19/4310', 'prefecture': '埼玉県'},
        'さいたま市': {'code': '3/19/4310', 'prefecture': '埼玉県'},
        'Tokyo': {'code': '3/16', 'prefecture': '東京都'},
        '東京都': {'code': '3/16', 'prefecture': '東京都'},
        # Chubu
        'Nagoya': {'code': '5/23/5110', 'prefecture': '愛知県'},
        '名古屋市': {'code': '5/23/5110', 'prefecture': '愛知県'},
        'Niigata': {'code': '5/27/5410', 'prefecture': '新潟県'},
        '新潟市': {'code': '5/27/5410', 'prefecture': '新潟県'},
        # Kansai
        'Osaka': {'code': '6/30/6200', 'prefecture': '大阪府'},
        '大阪市': {'code': '6/30/6200', 'prefecture': '大阪府'},
        'Kyoto': {'code': '6/29/6110', 'prefecture': '京都府'},
        '京都市': {'code': '6/29/6110', 'prefecture': '京都府'},
        'Kobe': {'code': '6/31/6310', 'prefecture': '兵庫県'},
        '神戸市': {'code': '6/31/6310', 'prefecture': '兵庫県'},
        # Chugoku
        'Hiroshima': {'code': '7/35/6710', 'prefecture': '広島県'},
        '広島市': {'code': '7/35/6710', 'prefecture': '広島県'},
        # Kyushu
        'Fukuoka': {'code': '9/43/8310', 'prefecture': '福岡県'},
        '福岡市': {'code': '9/43/8310', 'prefecture': '福岡県'},
        # Okinawa
        'Naha': {'code': '10/47/9110', 'prefecture': '沖縄県'},
        '那覇市': {'code': '10/47/9110', 'prefecture': '沖縄県'},
    }

    async def get_location(self) -> dict:
        """Get current location using IP geolocation"""
        try:
            async with aiohttp.ClientSession() as session:
                # First, try to get location from ip-api.com
                async with session.get('http://ip-api.com/json/') as response:
                    if response.status == 200:
                        data = await response.json()
                        city = data.get('city', 'Unknown')
                        region = data.get('regionName', '')
                        lat = data.get('lat')
                        lon = data.get('lon')
                        
                        # Check if it's a major Japanese city
                        city_info = self.JAPAN_CITIES.get(city)
                        
                        return {
                            'city': city,
                            'region': region,
                            'country': data.get('country', ''),
                            'lat': lat,
                            'lon': lon,
                            'tenki_code': city_info['code'] if city_info else None,
                            'prefecture': city_info['prefecture'] if city_info else region
                        }
        except Exception as e:
            print(f"Location detection error: {e}")
        
        # Fallback location (Tokyo)
        return {
            'city': 'Tokyo',
            'region': 'Tokyo',
            'country': 'Japan',
            'lat': 35.6762,
            'lon': 139.6503,
            'tenki_code': 3/16,
            'prefecture': 'Tokyo'
        }

    async def get_weather_forecast(self, lat: float, lon: float) -> dict:
        """Get weather forecast using Open-Meteo API (free, no API key needed)"""
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=auto"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
        except Exception as e:
            print(f"Weather fetch error: {e}")
        
        return None

    def get_weather_website_url(self, location: dict) -> str:
        """Generate weather website URL based on location"""
        city = location['city']
        country = location['country']
        tenki_code = location.get('tenki_code')
        
        if country == 'Japan':
            if tenki_code:
                return f"https://tenki.jp/forecast/{tenki_code}/"
            
            # Return general Japanese weather service URL
            return "https://tenki.jp/"
        else:
            # Return international weather service
            city_encoded = city.replace(' ', '+')
            return f"https://weather.com/weather/today/l/{city_encoded}"

    def format_weather_message(self, location: dict, weather: dict, website_url: str) -> str:
        """Format the weather information message"""
        city = location['city']
        prefecture = location.get('prefecture', location.get('region', ''))
        
        if not weather or 'current' not in weather:
            location_str = f"{prefecture} {city}" if prefecture and prefecture != city else city
            return f"{location_str}の天気情報を取得できませんでした。\n詳細はこちらをご覧ください: {website_url}"
        
        current = weather['current']
        temp = current.get('temperature_2m', 'N/A')
        wind = current.get('wind_speed_10m', 'N/A')
        
        daily = weather.get('daily', {})
        temp_max = daily.get('temperature_2m_max', [None])[0]
        temp_min = daily.get('temperature_2m_min', [None])[0]
        
        # Format location string
        location_str = f"{prefecture} {city}" if prefecture and prefecture != city else city
        
        message = f"{location_str}の天気予報\n\n"
        message += f"現在の気温: {temp}°C\n"
        
        if temp_max and temp_min:
            message += f"今日の予想: 最高 {temp_max}°C / 最低 {temp_min}°C\n"
        
        message += f"風速: {wind} km/h\n\n"
        
        return message

    async def show_weather_info(self):
        # Get current location
        location = await self.get_location()
        
        # Get weather forecast
        weather = await self.get_weather_forecast(location['lat'], location['lon'])
        
        # Get weather website URL
        website_url = self.get_weather_website_url(location)
        
        # Format response message
        response_message = self.format_weather_message(location, weather, website_url)
        
        # Send action to client (show weather widget)
        action_message = self.message_manager.url_action_message(website_url,
            ActionType.SHOW_WEATHER.value
        )
        
        await self.ws_manager.send_to_client(action_message)
        
        return response_message

    def _run(
        self,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        import asyncio
        return asyncio.run(self.show_weather_info())

    async def _arun(
        self,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        self.session_manager.context.last_tool_name = self.name
        return await self.show_weather_info()