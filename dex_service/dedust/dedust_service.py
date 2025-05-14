from fastapi import FastAPI
from dedust_client import DedustClient, ADDR_STR, TOKEN_PRICE, GOTTEN, FEE, DECIMALS
import redis
import consul
import socket
import os
import uuid
import time

app = FastAPI()
dedust = DedustClient()
SERVICE_NAME = "dex-dedust"
SERVICE_ID = f"{SERVICE_NAME}-{uuid.uuid1()}"
SERVICE_PORT = int(os.environ.get("SERVICE_PORT", default=8000))
CONSUL_HOST = os.environ.get("CONSUL_HOST", default="localhost")
CONSUL_PORT = int(os.environ.get("CONSUL_PORT", default=8500))
REDIS_HOST = os.environ.get("REDIS_HOST", default="localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", default=6379))
CACHE_SEC = float(os.environ.get("CACHE_SEC", default=0.1))

CONSUL_CLIENT = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)

REDIS_CLIENT = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

PAIRS = ["ton-usdt"]

dex_url = "https://dedust.io/swap"


class FastDict:
    def __init__(self, max_time_to_hold=0.1):
        self.data = {}
        self.max_time_to_hold = max_time_to_hold

    def put_data(self, key, value):
        self.data[key] = (time.time(), value)

    def get_data(self, key, max_time=None):
        max_time = self.max_time_to_hold if max_time is None else max_time
        if key not in self.data:
            return None
        stamp, value = self.data[key]
        if time.time() <= max_time + stamp:
            return value
        else:
            self.data.pop(key, 1)
            return None


fast_price = FastDict(CACHE_SEC)


def get_ready_token_name(token: str) -> str | None:
    if token in dedust.token_pretty_name:
        return token
    if token.upper() in dedust.token_dict:
        return dedust.token_dict[token.upper()][ADDR_STR]
    print(f"BAD token: {token}")
    return None


def get_token_addr_short_name(token: str):
    return dedust.token_pretty_name[token]


@app.on_event("startup")
async def startup_event():
    await dedust.start_client()

    service_host = socket.gethostbyname(socket.gethostname())
    print(f"service_host: {service_host}; for health check: http://{service_host}:{SERVICE_PORT}/health")
    check = consul.Check.http(url=f"http://{service_host}:{SERVICE_PORT}/health", interval="20s", deregister="45s")

    try:
        CONSUL_CLIENT.agent.service.register(
            name=SERVICE_NAME,
            service_id=SERVICE_ID,
            address=service_host,
            port=SERVICE_PORT,
            check=check
        )
        print(f"Registered '{SERVICE_NAME}' in Consul at {CONSUL_HOST}:{CONSUL_PORT}")
        print(f"SERVICE_ID: {SERVICE_ID}")
    except Exception as e:
        print(f"Failed to register service in Consul: {e}")

    for pair in PAIRS:
        REDIS_CLIENT.sadd(pair, SERVICE_NAME)
        print(f"redis pair created: {pair}, value: {SERVICE_NAME}")


@app.on_event("shutdown")
def deregister_service():
    try:
        CONSUL_CLIENT.agent.service.deregister(SERVICE_ID)
        print(f"Deregistered '{SERVICE_NAME}' from Consul")
    except Exception as e:
        print(f"Failed to deregister service from Consul: {e}")
    REDIS_CLIENT.close()


@app.get("/test")
async def get_test_method():
    return "test string"


@app.get("/test-pojo")
async def get_test_pojo_method():
    return {"result": f"test from {SERVICE_ID} ", "id": 1}


@app.get("/health")
async def health_check():
    return {"status": f"ok {SERVICE_ID}"}


@app.get("/redis/{key_r}/{val_r}")
async def get_to_redis(key_r: str, val_r: str):
    print(f"set key = {key_r}, val = {val_r}")
    REDIS_CLIENT.sadd(key_r, val_r)
    return "ok"


@app.get("/redis/{key_r}")
async def get_from_redis(key_r: str):
    print("get by key")
    r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    v = r.smembers(key_r)
    print(f"value: {v}")
    r.close()
    return f"value: {v}"


@app.get("/cached_swap/{source_token}/{destination_token}/{amount}/{max_time_sec}")
async def get_swap_cached_data(source_token: str, destination_token: str, amount: int, max_time_sec: float):
    start = time.time()
    src_ready = get_ready_token_name(source_token)
    dest_ready = get_ready_token_name(destination_token)
    if src_ready is None or dest_ready is None or amount <= 0:
        return {"result": {}, "status": "bad input"}

    key = src_ready + '-=-' + dest_ready
    curr_price = fast_price.get_data(key, max_time_sec)
    print(f"curr_price: {curr_price} max_time={max_time_sec}")
    result = None
    if curr_price is not None:
        result = {TOKEN_PRICE: curr_price[0],
                  GOTTEN: curr_price[0] * amount / dedust.token_dict[get_token_addr_short_name(src_ready)][DECIMALS],
                  FEE: curr_price[1]
                  }
    else:
        result = await dedust.get_usdt_ton_price(src_ready, amount)
        fast_price.put_data(key, (result[TOKEN_PRICE], result[FEE]))

    result["exchangeURL"] = dex_url
    result["currentURL"] = f"{dex_url}/{source_token}/{destination_token}?amount={amount}"
    print(f"response: tokenPriceWithFee= {result[TOKEN_PRICE]}; gottenAmount={result[GOTTEN]}")
    time_res = f"time to answer: {time.time() - start} sec"
    result["time"] = time_res
    print(time_res)
    return result


@app.get("/swap/{source_token}/{destination_token}/{amount}")
async def get_swap_data(source_token: str, destination_token: str, amount: int):
    src_ready = get_ready_token_name(source_token)
    dest_ready = get_ready_token_name(destination_token)
    if src_ready is None or dest_ready is None or amount <= 0:
        return {"result": {}, "status": "bad input"}

    key = src_ready + '-=-' + dest_ready
    curr_price = fast_price.get_data(key)
    result = None
    if curr_price is not None:
        result = {TOKEN_PRICE: curr_price[0],
                  GOTTEN: curr_price[0] * amount / dedust.token_dict[get_token_addr_short_name(src_ready)][DECIMALS],
                  FEE: curr_price[1]
                  }
    else:
        result = await dedust.get_usdt_ton_price(src_ready, amount)
        fast_price.put_data(key, (result[TOKEN_PRICE], result[FEE]))

    result["exchangeURL"] = dex_url
    result["currentURL"] = f"{dex_url}/{source_token}/{destination_token}?amount={amount}"
    # print(f"response: tokenPriceWithFee= {result[TOKEN_PRICE]}; gottenAmount={result[GOTTEN]}")
    return result
