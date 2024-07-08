from fastapi import FastAPI, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import websockets
import json
import httpx
from typing import List
from pydantic import BaseModel
from sortedcontainers import SortedDict

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Asset(BaseModel):
    symbol: str
    mcap: float

class RebalanceRequest(BaseModel):
    asset_cap: float
    total_capital: float
    assets: List[Asset]

class RebalanceResponse(BaseModel):
    symbol: str
    amount: float
    usd_value: float
    final_percentage: float

order_book = {
    "bids": SortedDict(),  
    "asks": SortedDict()
}
usdt_zar_price = None

async def fetch_orderbook():
    uri = "wss://api.valr.com/ws/trade"
    try:
        async with websockets.connect(uri) as websocket:
            subscribe_message = json.dumps({
                "type": "SUBSCRIBE",
                "subscriptions": [
                    {
                        "event": "FULL_ORDERBOOK_UPDATE",
                        "pairs": ["USDTZAR"]
                    }
                ]
            })
            await websocket.send(subscribe_message)
            async for message in websocket:
                data = json.loads(message)
                if data['type'] == "FULL_ORDERBOOK_UPDATE":
                    update_order_book(data['data'])
                    await asyncio.sleep(0.1)  
    except Exception as e:
        print(f"Error connecting to WebSocket: {e}")


def update_order_book(data):
    global order_book, usdt_zar_price

    if 'Bids' in data and data['Bids']:
        order_book['bids'].clear()
        for bid in data['Bids']:
            price = float(bid['Price'])
            quantity = float(bid['Orders'][0]['quantity'].replace(",", ""))
            if quantity > 0:
                order_book['bids'][price] = quantity

    if 'Asks' in data and data['Asks']:
        order_book['asks'].clear()
        for ask in data['Asks']:
            price = float(ask['Price'])
            quantity = float(ask['Orders'][0]['quantity'].replace(",", ""))
            if quantity > 0:
                order_book['asks'][price] = quantity


    usdt_zar_price = get_price_from_orderbook(1)


def get_price_from_orderbook(usdt: float):
    if not order_book['asks']:
        return None
    
    remaining_usdt = usdt
    total_cost = 0.0

    for price, volume in order_book['asks'].items():
        if remaining_usdt <= volume:
            total_cost += remaining_usdt * price
            remaining_usdt = 0
            break
        else:
            total_cost += volume * price
            remaining_usdt -= volume

    if remaining_usdt > 0:
        return None

    return total_cost

# connection  o valr on startup
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(fetch_orderbook())

@app.get("/")
async def read_root():
    return {"message": "FastAPI server is running"}


@app.get("/price")
async def get_price(usdt: float = 1):
    global usdt_zar_price
    if usdt_zar_price is None:
        return {"price": None, "message": "Order book is empty"}
    return {"price": usdt_zar_price}

async def fetch_binance_price(symbol: str, timeout=5):
    url = f"https://api.binance.com/api/v3/depth?symbol={symbol}USDT&limit=1"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                if 'asks' in data and data['asks']:
                    ask_price = float(data['asks'][0][0])
                    return ask_price
                else:
                    raise HTTPException(status_code=404, detail=f"No asks found for {symbol}USDT on Binance")
            else:
                raise HTTPException(status_code=response.status_code, detail=f"Error fetching Binance price for {symbol}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
@app.post("/rebalance")
async def rebalance_fund(request: RebalanceRequest = Body(...)):
    global usdt_zar_price
    if usdt_zar_price is None:
        raise HTTPException(status_code=500, detail="Order book is empty")

    # fetch calculate asset prices 
    assets = []
    for asset in request.assets:
        asset_usdt_price = await fetch_binance_price(asset.symbol)
        asset_price_zar = asset_usdt_price * usdt_zar_price
        assets.append({
            "symbol": asset.symbol,
            "mcap": asset.mcap,
            "price": asset_price_zar,
            "usd_price":asset_usdt_price
        })

    total_mcap = sum(asset['mcap'] for asset in assets)

    # target percentages without cap
    for asset in assets:
        asset['target_percentage'] = asset['mcap'] / total_mcap

    # applied asset cap
    capped_percentages = []
    remaining_capital = request.total_capital
    for asset in sorted(assets, key=lambda x: x['mcap'], reverse=True):
        if asset['target_percentage'] <= request.asset_cap:
            asset['final_percentage'] = asset['target_percentage']
            capped_percentages.append(asset)
        else:
            asset['final_percentage'] = request.asset_cap
            capped_percentages.append(asset)

    # redistribute remaining of total capital
    total_capped_allocation = sum(asset['final_percentage'] for asset in capped_percentages)
    if total_capped_allocation < 1.0:
        redistribution_capital = 1.0 - total_capped_allocation
        uncapped_assets = [asset for asset in capped_percentages if asset['final_percentage'] < request.asset_cap]
        if uncapped_assets:
            equal_share = redistribution_capital / len(uncapped_assets)
            for asset in uncapped_assets:
                asset['final_percentage'] += equal_share
                if asset['final_percentage'] > request.asset_cap:
                    asset['final_percentage'] = request.asset_cap

    # get my percentage right
    total_final_percentage = sum(asset['final_percentage'] for asset in capped_percentages)
    for asset in capped_percentages:
        asset['final_percentage'] = (asset['final_percentage'] / total_final_percentage)

    results = []
    for asset in capped_percentages:
        asset_amount = (asset['final_percentage'] * request.total_capital) / asset['price']
        asset_usd_value =   asset_amount * asset["usd_price"]
        results.append({
            "symbol": asset['symbol'],
            "price": asset['usd_price'],
            "amount": asset_amount,
            "usd_value": asset_usd_value,
            "final_percentage": asset['final_percentage'] * 100,
        })

    return results



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
